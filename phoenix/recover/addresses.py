"""Prove Ghidra-to-ELF conversions through original source bytes."""

import json
from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from struct import Struct
from typing import NewType

from phoenix.lift.index import LiftIndex, Location
from phoenix.lift.mapping import (
    MAX_BYTES,
    FileOffset,
    GhidraVA,
    LiftMapping,
    LiftSpan,
    MappingError,
    uint,
)

ElfVA = NewType("ElfVA", int)
_HEADER = Struct("<16sHHIQQQIHHHHHH")
_PROGRAM = Struct("<IIQQQQQQ")
_DYNAMIC = Struct("<qQ")


def checked_end(start: int, size: int) -> int:
    uint(start)
    uint(size)
    end = start + size
    if end > 1 << 64:
        raise MappingError("The address range overflows unsigned 64-bit bounds.")
    return end


def signed_difference(left: int, right: int) -> int:
    uint(left)
    uint(right)
    difference = left - right
    if not -(1 << 63) <= difference < 1 << 63:
        raise MappingError("The address difference exceeds signed 64-bit bounds.")
    return difference


@dataclass(frozen=True, slots=True)
class LoadSegment:
    index: int
    va: ElfVA
    file_offset: FileOffset
    file_size: int
    memory_size: int
    flags: int
    alignment: int


@dataclass(frozen=True, slots=True)
class ElfImage:
    entry: ElfVA
    kind: int
    segments: tuple[LoadSegment, ...]
    dynamic: tuple[tuple[int, int], ...]

    def segment(
        self, address: ElfVA, size: int, *, executable: bool = False
    ) -> LoadSegment:
        end = checked_end(address, size)
        owners = [
            segment
            for segment in self.segments
            if size > 0
            and segment.va <= address
            and end <= segment.va + segment.file_size
            and (not executable or segment.flags & 1)
        ]
        if len(owners) != 1:
            raise MappingError("The full range needs one file-backed segment owner.")
        return owners[0]

    def offset(self, address: ElfVA, size: int) -> FileOffset:
        segment = self.segment(address, size)
        return FileOffset(segment.file_offset + address - segment.va)


def read_elf(binary: bytes) -> ElfImage:
    """Read only bounded ELF64 x86-64 program headers and dynamic records."""
    if not _HEADER.size <= len(binary) <= MAX_BYTES:
        raise MappingError("Invalid ELF file size.")
    header = _HEADER.unpack_from(binary)
    ident, kind, machine, version, entry, phoff = header[:6]
    if (
        ident[:7] != b"\x7fELF\x02\x01\x01"
        or kind not in (2, 3)
        or machine != 62
        or version != 1
        or header[8] != _HEADER.size
        or header[9] != _PROGRAM.size
        or not 1 <= header[10] <= 1024
        or phoff < _HEADER.size
        or checked_end(phoff, header[10] * _PROGRAM.size) > len(binary)
    ):
        raise MappingError("Unsupported or malformed ELF program headers.")
    segments = []
    dynamics = []
    for index in range(header[10]):
        record = _PROGRAM.unpack_from(binary, phoff + index * _PROGRAM.size)
        ptype, flags, offset, va, _, filesz, memsz, align = record
        if ptype not in (1, 2):
            continue
        if (
            checked_end(offset, filesz) > len(binary)
            or filesz > memsz
            or checked_end(va, memsz) > 1 << 64
            or align & (align - 1)
            or (align > 1 and (va - offset) % align)
        ):
            raise MappingError("Invalid ELF segment bounds or alignment.")
        segment = LoadSegment(
            index, ElfVA(va), FileOffset(offset), filesz, memsz, flags, align
        )
        if ptype == 1:
            segments.append(segment)
        else:
            dynamics.append(segment)
    segments.sort(key=lambda segment: segment.va)
    if (
        not segments
        or len(dynamics) != 1
        or any(
            left.va + left.memory_size > right.va
            for left, right in zip(segments, segments[1:])
        )
    ):
        raise MappingError("ELF load segments overlap or dynamic ownership is invalid.")
    file_order = sorted(
        (s.file_offset, s.file_offset + s.file_size) for s in segments if s.file_size
    )
    if any(left[1] > right[0] for left, right in zip(file_order, file_order[1:])):
        raise MappingError("ELF file-backed load segments overlap.")
    image = ElfImage(ElfVA(entry), kind, tuple(segments), ())
    image.segment(image.entry, 1, executable=True)
    dynamic = dynamics[0]
    if (
        not dynamic.file_size
        or dynamic.file_size % _DYNAMIC.size
        or dynamic.file_size // _DYNAMIC.size > 65536
        or image.offset(dynamic.va, dynamic.file_size) != dynamic.file_offset
    ):
        raise MappingError("Invalid dynamic segment.")
    records = []
    terminated = False
    for offset in range(
        dynamic.file_offset, dynamic.file_offset + dynamic.file_size, _DYNAMIC.size
    ):
        tag, value = _DYNAMIC.unpack_from(binary, offset)
        if terminated:
            if tag or value:
                raise MappingError("Nonzero dynamic data follows DT_NULL.")
        elif tag == 0:
            terminated = True
        else:
            records.append((tag, value))
    if not terminated:
        raise MappingError("The dynamic segment has no DT_NULL.")
    return ElfImage(image.entry, kind, image.segments, tuple(records))


@dataclass(frozen=True, slots=True)
class InstructionWitness:
    ghidra: GhidraVA
    elf: ElfVA
    file_offset: FileOffset
    owner: GhidraVA
    data: bytes


@dataclass(frozen=True, slots=True)
class AddressProof:
    binary_sha256: str
    lift_sha256: str
    image: ElfImage
    ghidra_delta: int
    spans: tuple[LiftSpan, ...]
    witnesses: tuple[InstructionWitness, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]
    sha256: str
    span_starts: tuple[GhidraVA, ...] = field(init=False, repr=False)
    witness_starts: tuple[GhidraVA, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "span_starts", tuple(span.ghidra_start for span in self.spans)
        )
        object.__setattr__(
            self, "witness_starts", tuple(w.ghidra for w in self.witnesses)
        )

    def to_elf(self, address: GhidraVA, size: int = 1) -> ElfVA:
        checked_end(address, size)
        result = address - self.ghidra_delta
        uint(result)
        self.image.segment(ElfVA(result), size)
        index = bisect_right(self.span_starts, address) - 1
        if (
            index < 0
            or address + size
            > self.spans[index].ghidra_start + self.spans[index].length
        ):
            raise MappingError("The address lacks one complete source span.")
        return ElfVA(result)

    def to_ghidra(self, address: ElfVA, size: int = 1) -> GhidraVA:
        result = address + self.ghidra_delta
        uint(result)
        converted = GhidraVA(result)
        if self.to_elf(converted, size) != address:
            raise MappingError("The address round trip failed.")
        return converted

    def witness(
        self, address: GhidraVA, *, owner: GhidraVA | None = None
    ) -> InstructionWitness:
        index = bisect_right(self.witness_starts, address) - 1
        if index < 0 or self.witnesses[index].ghidra != address:
            raise MappingError("The target has no exact admitted instruction witness.")
        witness = self.witnesses[index]
        if owner is not None and owner != witness.owner:
            raise MappingError("The instruction witness has a different owner.")
        return witness


def synthetic_external_target(
    lift: LiftIndex, proof: AddressProof, address: GhidraVA
) -> Location | None:
    function = lift.functions.get(address)
    if (
        function is None
        or function.instructions
        or function.ranges != ((address, address),)
        or lift.owners(address) != (address,)
        or function.thunk_target is None
        or function.thunk_target.space != "EXTERNAL"
    ):
        return None
    elf = address - proof.ghidra_delta
    if not 0 <= elf < 1 << 64 or any(
        segment.va <= elf < segment.va + segment.memory_size
        for segment in proof.image.segments
    ):
        return None
    return function.thunk_target


def prove_addresses(
    binary: bytes, lift: LiftIndex, mapping: LiftMapping
) -> AddressProof:
    if (
        sha256(binary).hexdigest() != lift.binary_sha256
        or mapping.binary_sha256 != lift.binary_sha256
        or mapping.lift_sha256 != lift.lift_sha256
        or mapping.image_base != lift.image_base
        or mapping.startup != lift.startup
    ):
        raise MappingError("The mapping, lift, and binary identities disagree.")
    image = read_elf(binary)
    if (
        tuple(sorted(mapping.spans, key=lambda span: span.ghidra_start))
        != mapping.spans
    ):
        raise MappingError("Source spans must have deterministic address order.")
    deltas = set()
    gaps = []
    previous_end = -1
    for span in sorted(mapping.spans, key=lambda span: span.ghidra_start):
        end = checked_end(span.ghidra_start, span.length)
        file_end = checked_end(span.file_offset, span.length)
        if (
            not span.length
            or file_end > len(binary)
            or span.ghidra_start < previous_end
        ):
            raise MappingError("Invalid or overlapping source span.")
        previous_end = end
        owners = [
            segment
            for segment in image.segments
            if segment.file_offset <= span.file_offset
            and file_end <= segment.file_offset + segment.file_size
        ]
        if len(owners) != 1:
            raise MappingError("The source span needs one file-backed load owner.")
        segment = owners[0]
        elf = segment.va + span.file_offset - segment.file_offset
        deltas.add(signed_difference(span.ghidra_start, elf))
        original = sha256(binary[span.file_offset : file_end]).hexdigest()
        if original != span.original_sha256:
            raise MappingError("The source span does not match original bytes.")
        if original != span.memory_sha256:
            gaps.append((span.ghidra_start, "changed_memory_bytes"))
    if len(deltas) != 1:
        raise MappingError("The source spans do not prove one uniform rebase.")
    delta = deltas.pop()
    if lift.startup - delta != image.entry:
        raise MappingError("The startup and ELF entry disagree.")
    # The supported profile anchors the Ghidra image base at the lowest PT_LOAD.
    if lift.image_base - delta != min(segment.va for segment in image.segments):
        raise MappingError("The image base disagrees with the proven load mapping.")
    provisional = AddressProof(
        lift.binary_sha256, lift.lift_sha256, image, delta, mapping.spans, (), (), ""
    )
    witnesses = []
    for instruction in sorted(lift.instructions.values(), key=lambda ins: ins.address):
        try:
            elf = provisional.to_elf(instruction.address, instruction.size)
            segment = image.segment(elf, instruction.size, executable=True)
            instruction_owners = lift.owners(instruction.address, instruction.size)
            if len(instruction_owners) != 1:
                raise MappingError("Ambiguous instruction ownership.")
            span = mapping.spans[
                bisect_right(provisional.span_starts, instruction.address) - 1
            ]
            if span.memory_sha256 != span.original_sha256:
                raise MappingError("Changed memory cannot witness an instruction.")
            offset = FileOffset(segment.file_offset + elf - segment.va)
            witnesses.append(
                InstructionWitness(
                    instruction.address,
                    elf,
                    offset,
                    instruction_owners[0],
                    binary[offset : offset + instruction.size],
                )
            )
        except MappingError as error:
            gaps.append((instruction.address, str(error)))
    admitted = {witness.ghidra for witness in witnesses}
    if lift.startup not in admitted or lift.main not in admitted:
        raise MappingError("The startup and main need admitted instruction witnesses.")
    certificate = {
        "rule": "phoenix-addresses-u1-v1",
        "binary": lift.binary_sha256,
        "lift": lift.lift_sha256,
        "mapping": asdict(mapping),
        "image": asdict(image),
        "delta": delta,
        "witnesses": [
            (w.ghidra, w.elf, w.file_offset, w.owner, w.data.hex()) for w in witnesses
        ],
        "gaps": gaps,
    }
    proof_hash = sha256(
        json.dumps(certificate, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return AddressProof(
        lift.binary_sha256,
        lift.lift_sha256,
        image,
        delta,
        mapping.spans,
        tuple(witnesses),
        tuple(gaps),
        proof_hash,
    )
