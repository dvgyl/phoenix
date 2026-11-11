"""Bind import sites only when Ghidra and ELF dynamic evidence agree."""

from collections import defaultdict
from dataclasses import dataclass, replace
from hashlib import sha256
from struct import Struct

from phoenix.lift.index import (
    ExternalImport,
    LiftIndex,
    Location,
    Operation,
    StaticEdge,
    call_transfer_kind,
)
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.recover.addresses import (
    AddressProof,
    ElfImage,
    ElfVA,
    checked_end,
    synthetic_external_target,
)

_U32 = Struct("<I")
_U16 = Struct("<H")
_SYMBOL = Struct("<IBBHQQ")
_RELA = Struct("<QQq")
_MAX_RECORDS = 65536
# x86-64 ELF relocation write widths. COPY uses the destination symbol size.
_WRITE_WIDTH = {0: 0, 1: 8, 2: 4, 6: 8, 7: 8, 8: 8, 10: 4, 11: 4, 37: 8}


@dataclass(frozen=True, slots=True)
class ImportId:
    symbol: str
    version: str | None
    version_hidden: bool
    needed_library: str | None = None


@dataclass(frozen=True, slots=True)
class Relocation:
    slot: ElfVA
    kind: int
    identity: ImportId | None
    gap: str | None
    file_offset: int
    symbol_index: int
    write_size: int | None


@dataclass(frozen=True, slots=True)
class ImportBinding:
    site: GhidraVA
    function: GhidraVA | None
    identity: ImportId | None
    relocation_slot: ElfVA | None
    relocation_kind: int | None
    thunk_path: tuple[GhidraVA, ...]
    gap: str | None
    binary_sha256: str = ""
    lift_sha256: str = ""
    address_proof_sha256: str = ""
    relocation_file_offset: int | None = None
    symbol_index: int | None = None


class _DynamicReader:
    def __init__(self, binary: bytes, image: ElfImage) -> None:
        self.binary = binary
        self.image = image
        self.tags: dict[int, list[int]] = defaultdict(list)
        for tag, value in image.dynamic:
            self.tags[tag].append(value)
        for tag, values in self.tags.items():
            if tag != 1 and len(values) != 1:
                raise MappingError("Duplicate dynamic tag.")
        if not 1 <= self.one(10) <= 1024 * 1024:
            raise MappingError("Dynamic strings exceed 1 MiB.")
        self.strings = self.read(self.one(5), self.one(10))
        if (
            not 1 <= len(self.strings) <= 1024 * 1024
            or self.strings[0]
            or self.strings[-1]
        ):
            raise MappingError("Invalid dynamic string table.")
        self.text_total = 0
        self.needed = tuple(self.string(index) for index in self.tags.get(1, []))
        if self.one(11) != _SYMBOL.size:
            raise MappingError("Unsupported dynamic symbol size.")
        self.count = self.symbol_count()
        self.symbols = self.read(self.one(6), self.count * _SYMBOL.size)
        if any(self.symbols[: _SYMBOL.size]):
            raise MappingError("The null dynamic symbol is not zero.")
        self.versions = self.version_requirements()
        self.versym = (
            self.read(self.one(0x6FFFFFF0), self.count * 2)
            if 0x6FFFFFF0 in self.tags
            else None
        )
        if self.versions and self.versym is None:
            raise MappingError("Version requirements have no symbol version table.")

    def one(self, tag: int) -> int:
        values = self.tags.get(tag)
        if values is None or len(values) != 1:
            raise MappingError("A required dynamic tag is missing.")
        return values[0]

    def read(self, address: int, size: int) -> bytes:
        if not 0 < size <= 4 * 1024 * 1024:
            raise MappingError("Dynamic data exceeds the supported byte bound.")
        offset = self.image.offset(ElfVA(address), size)
        return self.binary[offset : offset + size]

    def string(self, index: int) -> str:
        if not 0 <= index < len(self.strings):
            raise MappingError("A dynamic string offset is outside its table.")
        end = self.strings.find(b"\0", index)
        if end < 0 or end - index > 4096:
            raise MappingError("A dynamic string is unterminated or too long.")
        self.text_total += end - index
        if self.text_total > 1024 * 1024:
            raise MappingError("Import text exceeds 1 MiB.")
        try:
            return self.strings[index:end].decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise MappingError("Invalid dynamic symbol text.") from error

    def symbol_count(self) -> int:
        counts = []
        if 4 in self.tags:
            address = self.one(4)
            buckets, count = (
                int(value) for value in Struct("<II").unpack(self.read(address, 8))
            )
            if not 1 <= buckets <= _MAX_RECORDS or not 1 <= count <= _MAX_RECORDS:
                raise MappingError("Invalid ELF hash table bounds.")
            data = self.read(address + 8, (buckets + count) * 4)
            if any(value[0] >= count for value in Struct("<I").iter_unpack(data)):
                raise MappingError("Invalid ELF hash symbol reference.")
            counts.append(count)
        if 0x6FFFFEF5 in self.tags:
            address = self.one(0x6FFFFEF5)
            buckets, first, bloom, shift = Struct("<IIII").unpack(
                self.read(address, 16)
            )
            if (
                not 1 <= buckets <= _MAX_RECORDS
                or not 1 <= first <= _MAX_RECORDS
                or not 1 <= bloom <= _MAX_RECORDS
                or bloom & (bloom - 1)
                or shift >= 64
            ):
                raise MappingError("Invalid GNU hash table bounds.")
            self.read(address + 16, bloom * 8)
            bucket_start = address + 16 + bloom * 8
            bucket_data = self.read(bucket_start, buckets * 4)
            chain_start = bucket_start + buckets * 4
            count = first
            steps = 0
            visited: set[int] = set()
            for (index,) in _U32.iter_unpack(bucket_data):
                if index == 0:
                    continue
                if not first <= index < _MAX_RECORDS or index in visited:
                    raise MappingError("Invalid or overlapping GNU hash bucket.")
                while True:
                    steps += 1
                    if (
                        index >= _MAX_RECORDS
                        or steps > _MAX_RECORDS
                        or index in visited
                    ):
                        raise MappingError("GNU hash chain exceeds the bound.")
                    visited.add(index)
                    value = _U32.unpack(
                        self.read(chain_start + (index - first) * 4, 4)
                    )[0]
                    count = max(count, index + 1)
                    if value & 1:
                        break
                    index += 1
            if visited and visited != set(range(first, count)):
                raise MappingError("GNU hash chains have gaps.")
            counts.append(count)
        if not counts or len(set(counts)) != 1:
            raise MappingError("Dynamic symbol bounds are missing or conflicting.")
        return counts[0]

    def version_requirements(self) -> dict[int, str]:
        present = [tag in self.tags for tag in (0x6FFFFFFE, 0x6FFFFFFF)]
        if any(present) != all(present):
            raise MappingError("Incomplete version requirement tags.")
        if not any(present):
            return {}
        count = self.one(0x6FFFFFFF)
        if not 1 <= count <= _MAX_RECORDS:
            raise MappingError("Invalid version requirement count.")
        address = self.one(0x6FFFFFFE)
        versions: dict[int, str] = {}
        visited: set[int] = set()
        total = 0
        for index in range(count):
            if address in visited:
                raise MappingError("Cyclic version requirement.")
            visited.add(address)
            version, auxiliaries, library, aux, next_offset = Struct("<HHIII").unpack(
                self.read(address, 16)
            )
            if (
                version != 1
                or not auxiliaries
                or aux < 16
                or self.string(library) not in self.needed
            ):
                raise MappingError("Invalid version requirement header.")
            cursor = checked_end(address, aux)
            for aux_index in range(auxiliaries):
                total += 1
                if total > _MAX_RECORDS or cursor in visited:
                    raise MappingError("Version auxiliary bounds or cycle.")
                visited.add(cursor)
                version_hash, flags, other, name, following = Struct("<IHHII").unpack(
                    self.read(cursor, 16)
                )
                label = self.string(name)
                if (
                    not label
                    or flags & ~3
                    or not 2 <= other < 0x8000
                    or other in versions
                    or version_hash != _elf_hash(label.encode())
                ):
                    raise MappingError("Invalid version identity.")
                versions[other] = label
                if (aux_index == auxiliaries - 1) != (following == 0) or (
                    following and following < 16
                ):
                    raise MappingError("Invalid version auxiliary chain.")
                cursor = checked_end(cursor, following)
            if (index == count - 1) != (next_offset == 0) or (
                next_offset and next_offset < 16
            ):
                raise MappingError("Invalid version requirement chain.")
            address = checked_end(address, next_offset)
        return versions

    def symbol(self, index: int) -> ImportId | None:
        if not 0 < index < self.count:
            raise MappingError(
                "The relocation symbol is outside the dynamic symbol table."
            )
        name, info, visibility, section, value, size = _SYMBOL.unpack_from(
            self.symbols, index * _SYMBOL.size
        )
        symbol = self.string(name)
        version = None
        hidden = False
        if self.versym is not None:
            raw = _U16.unpack_from(self.versym, index * 2)[0]
            hidden, version_index = bool(raw & 0x8000), raw & 0x7FFF
            if version_index == 0:
                raise MappingError(
                    "An external relocation uses a local version identity."
                )
            if version_index > 1:
                if version_index not in self.versions:
                    raise MappingError(
                        "The imported symbol has an unknown version identity."
                    )
                version = self.versions[version_index]
            elif hidden:
                raise MappingError("Invalid hidden unversioned symbol.")
        if not symbol or visibility & ~3:
            raise MappingError("Invalid dynamic symbol name or visibility.")
        # Defined functions and IFUNC resolvers cannot identify an external import.
        if (
            section != 0
            or value != 0
            or info & 15 != 2
            or info >> 4 not in (1, 2)
            or visibility & 3 not in (0, 3)
        ):
            return None
        return ImportId(symbol, version, hidden)

    def relocations(self) -> tuple[Relocation, ...]:
        tables = []
        if any(tag in self.tags for tag in (7, 8, 9)):
            if self.one(9) != _RELA.size:
                raise MappingError("Unsupported RELA entry size.")
            tables.append((self.one(7), self.one(8), False))
        if any(tag in self.tags for tag in (23, 2, 20)):
            if self.one(20) != 7:
                raise MappingError("Only RELA PLT relocations are supported.")
            tables.append((self.one(23), self.one(2), True))
        if any(tag in self.tags for tag in (17, 18, 19, 35, 36, 37)):
            raise MappingError("REL and RELR relocations are unsupported.")
        records: list[Relocation] = []
        occupied: set[int] = set()
        ranges = []
        writes: list[tuple[int, int, int]] = []
        for address, size, plt in tables:
            if size % _RELA.size or size // _RELA.size > _MAX_RECORDS:
                raise MappingError("Invalid relocation table size.")
            if not size:
                continue
            ranges.append((address, address + size))
            data = self.read(address, size)
            file_offset = self.image.offset(ElfVA(address), size)
            for index, (slot, info, addend) in enumerate(_RELA.iter_unpack(data)):
                if len(records) >= _MAX_RECORDS or slot in occupied:
                    raise MappingError(
                        "Duplicate relocation slot or exceeded relocation bound."
                    )
                occupied.add(slot)
                kind, symbol_index = info & 0xFFFFFFFF, info >> 32
                if symbol_index >= self.count:
                    raise MappingError("A relocation has an invalid symbol index.")
                width = _WRITE_WIDTH.get(kind)
                if kind == 5 and symbol_index and not addend:
                    _, info, _, section, value, size_bytes = _SYMBOL.unpack_from(
                        self.symbols, symbol_index * _SYMBOL.size
                    )
                    if (
                        info & 15 == 1
                        and 0 < section < 0xFF00
                        and value == slot
                        and size_bytes
                    ):
                        width = size_bytes
                end = checked_end(slot, max(1, width or 0))
                if width != 0 and not any(
                    segment.va <= slot and end <= segment.va + segment.memory_size
                    for segment in self.image.segments
                ):
                    raise MappingError("A relocation has no unique memory owner.")
                if width != 0:
                    # Without a write width, a later slot cannot prove exclusion.
                    writes.append(
                        (slot, (1 << 64) if width is None else end, len(records))
                    )
                identity = None
                gap: str | None = "unsupported_relocation"
                if kind in (6, 7):
                    self.image.segment(ElfVA(slot), 8)
                    if addend or (plt and kind != 7):
                        raise MappingError("Invalid import relocation form.")
                    identity = self.symbol(symbol_index)
                    gap = (
                        None if identity is not None else "unsupported_symbol_or_ifunc"
                    )
                records.append(
                    Relocation(
                        ElfVA(slot),
                        kind,
                        identity,
                        gap,
                        file_offset + index * _RELA.size,
                        symbol_index,
                        width,
                    )
                )
        ranges.sort()
        if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
            raise MappingError("Relocation tables overlap.")
        writes.sort()
        previous_end = 0
        for index, (start, end, record_index) in enumerate(writes):
            record = records[record_index]
            if record.identity is not None and (
                previous_end > start
                or (index + 1 < len(writes) and writes[index + 1][0] < end)
            ):
                records[record_index] = replace(
                    record, identity=None, gap="overlapping_relocation"
                )
            previous_end = max(previous_end, end)
        return tuple(records)


def _elf_hash(value: bytes) -> int:
    result = 0
    for byte in value:
        result = (result << 4) + byte
        high = result & 0xF0000000
        if high:
            result ^= high >> 24
        result &= ~high
    return result


def read_dynamic_imports(binary: bytes, image: ElfImage) -> tuple[Relocation, ...]:
    return _DynamicReader(binary, image).relocations()


def _transfer_slot(lift: LiftIndex, site: GhidraVA) -> GhidraVA | None:
    """Accept only raw memory operands carried by width-preserving COPY operations."""
    instruction = lift.instructions.get(site)
    if instruction is None:
        return None
    values: dict[Location, GhidraVA] = {}
    memory_written = False
    found_transfer = False
    slot = None
    for operation in instruction.pcode:
        if operation.opcode in ("BRANCH", "CBRANCH", "CALL", "CALLOTHER", "RETURN"):
            return None
        operand = operation.inputs[0] if operation.inputs else None
        source = None
        if operand is not None and operand.size == 8 and operand.definition is None:
            source = values.get(operand.address)
            if source is None and not memory_written:
                source = operand.address.ram
        if operation.opcode in ("CALLIND", "BRANCHIND"):
            if found_transfer or len(operation.inputs) != 1:
                return None
            found_transfer = True
            slot = source
        if operation.opcode == "STORE":
            memory_written = True
        if operation.output is not None:
            output = operation.output
            address = output.address
            memory_written |= address.ram is not None
            values = {
                stored: slot
                for stored, slot in values.items()
                if stored.space != address.space
                or (
                    output.size > 0
                    and address.offset + output.size <= 1 << 64
                    and (
                        stored.offset + 8 <= address.offset
                        or address.offset + output.size <= stored.offset
                    )
                )
            }
            if (
                operation.opcode == "COPY"
                and len(operation.inputs) == 1
                and address.space in ("register", "unique")
                and output.size == 8
                and output.definition is None
                and address.offset + 8 <= 1 << 64
                and source is not None
            ):
                values[address] = source
    return slot


def _binding(
    edge: StaticEdge,
    lift: LiftIndex,
    proof: AddressProof,
    relocations: dict[ElfVA, Relocation],
    imports: dict[Location, ExternalImport],
) -> ImportBinding:
    instruction = lift.instructions.get(edge.site)
    if instruction is None:
        return ImportBinding(
            edge.site, edge.caller, None, None, None, (), "unavailable_instruction"
        )
    transfer = call_transfer_kind(instruction, edge.target)
    if transfer is None:
        return ImportBinding(
            edge.site, edge.caller, None, None, None, (), "conflicting_call_target"
        )
    path: list[GhidraVA] = []
    transfer_site = edge.site if transfer == "indirect" else None
    target = edge.target
    seen: set[Location] = set()
    gap = "unknown_import"
    while target is not None and target.space != "EXTERNAL":
        if target in seen or len(seen) >= 32:
            gap = "thunk_cycle_or_bound"
            break
        seen.add(target)
        address = target.ram
        if address is None or address not in lift.functions:
            break
        function = lift.functions[address]
        next_target = function.thunk_target
        if next_target is None:
            break
        synthetic = synthetic_external_target(lift, proof, address)
        if synthetic is not None:
            target = synthetic
            continue
        if transfer != "direct" and not path:
            gap = "unproven_indirect_thunk_target"
            break
        proof.witness(address, owner=address)
        transfers: list[tuple[GhidraVA, Operation]] = []
        next_instruction = address
        for ins in function.instructions:
            proof.witness(ins.address, owner=address)
            if not transfers and ins.address != next_instruction:
                break
            next_instruction = GhidraVA(ins.address + ins.size)
            transfers.extend(
                (ins.address, op)
                for op in ins.pcode
                if op.opcode
                in (
                    "BRANCH",
                    "BRANCHIND",
                    "CBRANCH",
                    "CALL",
                    "CALLIND",
                    "CALLOTHER",
                    "RETURN",
                )
            )
        if len(transfers) != 1:
            gap = "unsupported_thunk_transfer"
            break
        site, operation = transfers[0]
        if operation.opcode == "BRANCHIND":
            transfer_site = site
            if next_target.space != "EXTERNAL" and (
                next_target.ram is None
                or synthetic_external_target(lift, proof, next_target.ram) is None
            ):
                gap = "unsupported_thunk_transfer"
                break
        elif (
            operation.opcode != "BRANCH"
            or len(operation.inputs) != 1
            or operation.inputs[0].address != next_target
            or next_target.ram is None
        ):
            gap = "conflicting_thunk_target"
            break
        path.append(address)
        target = next_target
    else:
        if target is not None and target in imports and transfer_site is not None:
            gap = "missing_or_ambiguous_got_slot"
            operand_address = _transfer_slot(lift, transfer_site)
            relocation = None
            if operand_address is not None:
                try:
                    relocation = relocations.get(proof.to_elf(operand_address, 8))
                except MappingError:
                    pass
            if relocation is not None:
                identity = relocation.identity
                if identity is not None and imports[target].name == identity.symbol:
                    return ImportBinding(
                        edge.site,
                        edge.caller,
                        identity,
                        relocation.slot,
                        relocation.kind,
                        tuple(path),
                        None,
                    )
                gap = relocation.gap or "conflicting_import_identity"
    return ImportBinding(edge.site, edge.caller, None, None, None, tuple(path), gap)


def bind_imports(
    binary: bytes, lift: LiftIndex, proof: AddressProof
) -> tuple[ImportBinding, ...]:
    if (
        sha256(binary).hexdigest() != proof.binary_sha256
        or lift.binary_sha256 != proof.binary_sha256
        or lift.lift_sha256 != proof.lift_sha256
    ):
        raise MappingError("Import evidence identities disagree.")
    relocations = {
        record.slot: record for record in read_dynamic_imports(binary, proof.image)
    }
    external_imports = {imported.address: imported for imported in lift.imports}
    result = []
    for edge in lift.edges:
        if edge.kind != "call":
            continue
        try:
            witness = proof.witness(edge.site)
            if edge.caller != witness.owner:
                raise MappingError("Call ownership disagrees.")
            proof.witness(witness.owner, owner=witness.owner)
            result.append(_binding(edge, lift, proof, relocations, external_imports))
        except MappingError:
            result.append(
                ImportBinding(
                    edge.site,
                    edge.caller,
                    None,
                    None,
                    None,
                    (),
                    "unavailable_instruction",
                )
            )
    by_site: dict[GhidraVA, list[ImportBinding]] = defaultdict(list)
    for binding in result:
        by_site[binding.site].append(binding)
    identities = {
        site: {(binding.identity, binding.relocation_slot) for binding in alternatives}
        for site, alternatives in by_site.items()
    }
    checked = []
    for binding in result:
        if binding.identity is not None and len(identities[binding.site]) != 1:
            binding = replace(
                binding,
                identity=None,
                relocation_slot=None,
                relocation_kind=None,
                gap="conflicting_import_paths",
            )
        relocation = (
            relocations.get(binding.relocation_slot)
            if binding.relocation_slot is not None
            else None
        )
        checked.append(
            replace(
                binding,
                binary_sha256=proof.binary_sha256,
                lift_sha256=proof.lift_sha256,
                address_proof_sha256=proof.sha256,
                relocation_file_offset=None
                if relocation is None
                else relocation.file_offset,
                symbol_index=None if relocation is None else relocation.symbol_index,
            )
        )
    return tuple(checked)
