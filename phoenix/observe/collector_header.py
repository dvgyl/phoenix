"""Render complete typed constants. No constructor or digest issues authority."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field, fields, is_dataclass
from hashlib import sha256
from typing import cast

from phoenix.lift.mapping import MappingError
from phoenix.observe import collector_data as data_types
from phoenix.observe import plan as plan_types
from phoenix.observe import scope as scope_types
from phoenix.observe.collector_data import CollectorData, CollectorRejected
from phoenix.observe.collector_header_read import (
    DIRECTORY,
    DIRECTORY_BYTES,
    FIELDS,
    KINDS,
    MAX_SOURCE,
    MAX_STORAGE,
    PREFIX,
    SUFFIX,
    TABLES,
    U64,
    Cell,
    HeaderReadError,
    declaration,
    directory_entry,
    element_bytes,
    native_bytes,
    read_header,
    renderer_identity,
    require,
    uint,
    width,
)
from phoenix.recover import addresses as address_types
from phoenix.recover import imports as import_types


@dataclass(frozen=True, slots=True)
class HeaderLimits:
    source_bytes: int = MAX_SOURCE
    initializer_bytes: int = MAX_STORAGE


@dataclass(frozen=True, slots=True)
class GeneratedHeader:
    raw: bytes
    sha256: str
    logical_data_sha256: str
    renderer_sha256: str
    native_source_sha256: str
    counts: tuple[tuple[str, int], ...]
    initializer_bytes: int
    relative_name: str = field(init=False, default="generated/collector_data.h")


_CLASSES = (
    data_types.Original,
    data_types.Geometry,
    data_types.TransportLimits,
    data_types.CollectorData,
    plan_types.Call,
    plan_types.Jump,
    plan_types.Return,
    plan_types.TraceSite,
    plan_types.TraceLimits,
    plan_types.TracePlan,
    scope_types.LiftMain,
    scope_types.ExplicitEntry,
    scope_types.RequestedScope,
    scope_types.User,
    scope_types.Transit,
    scope_types.Omitted,
    scope_types.OmittedSite,
    scope_types.TransitRoute,
    scope_types.Ordinary,
    scope_types.LocalDirect,
    scope_types.LocalConditional,
    scope_types.PlannedRoles,
    scope_types.TransitInstruction,
    scope_types.Reject,
    scope_types.GuardInstruction,
    scope_types.DormantOutsideWindow,
    scope_types.GuardReject,
    scope_types.LocalBranchGuard,
    scope_types.MetadataOnly,
    scope_types.GapRecord,
    scope_types.CaptureLimits,
    scope_types.ExitFromSupportedBits,
    scope_types.ExactSignal,
    scope_types.TerminationContract,
    scope_types.ScopeSelection,
    address_types.LoadSegment,
    address_types.ElfImage,
    import_types.ImportId,
    import_types.ImportBinding,
)
CLASSES = {item.__name__: item for item in _CLASSES}


def _members(table: str, value: object) -> tuple[object, ...]:
    kind = KINDS[table]
    if kind == "$scalar":
        return (value,)
    if kind == "$pair":
        require(
            type(value) is tuple
            and len(cast(tuple[object, ...], value)) == len(FIELDS[table]),
            "Invalid typed pair.",
        )
        return cast(tuple[object, ...], value)
    require(type(value) is CLASSES[kind], f"Invalid record type for {table}.")
    require(
        sorted(item.name for item in fields(CLASSES[kind]))
        == sorted(name for name, _ in FIELDS[table]),
        "The record schema changed.",
    )
    return tuple(cast(object, getattr(value, name)) for name, _ in FIELDS[table])


def _variant(descriptor: str, value: object) -> tuple[int, str | None]:
    alternatives = descriptor.split(":", 1)[1].split(",")
    if value is None and descriptor.startswith("v0:"):
        return 0, None
    for tag, name in enumerate(alternatives, 1):
        if type(value) is CLASSES[KINDS[name]]:
            return tag, name
    raise HeaderReadError("Invalid typed variant.")


def _zero(descriptor: str) -> Cell:
    if descriptor.startswith("o:"):
        return 0, _zero(descriptor[2:])
    if descriptor.startswith(("v:", "v0:")):
        return (0, *((0, 0) for _ in descriptor.split(":", 1)[1].split(",")))
    return (0, 0) if width(descriptor) == 2 else 0


def _cell_text(cell: Cell) -> str:
    if type(cell) is int:
        return uint(cell)
    return (
        "{"
        + ", ".join(_cell_text(child) for child in cast(tuple[Cell, ...], cell))
        + "}"
    )


def _row_length(table: str) -> int:
    if table == "bytes":
        return len("    0x00,\n")
    return len("    " + _cell_text(tuple(_zero(d) for _, d in FIELDS[table])) + ",\n")


def _empty_row(table: str) -> str:
    return "    0x00,\n" if table == "bytes" else "    {0},\n"


def _source_length(counts: dict[str, int]) -> int:
    # Every unsigned token has the same width, including directory fields.
    identities_length = 3 * len("    {" + ", ".join(["0x00"] * 32) + "},\n")
    return (
        len(PREFIX)
        + len(DIRECTORY)
        + identities_length
        + len("    {\n    }\n")
        + len(SUFFIX)
        + sum(
            len(declaration(table, count))
            + len(SUFFIX)
            + (_row_length(table) * count if count else len(_empty_row(table)))
            + len(directory_entry(table, count))
            for table, count in counts.items()
        )
    )


class _Measure:
    def __init__(self, limits: HeaderLimits) -> None:
        self.limits = limits
        self.counts = dict.fromkeys(TABLES, 0)
        self.storage = DIRECTORY_BYTES
        require(
            self.storage <= limits.initializer_bytes,
            "The directory exceeds its byte limit.",
        )
        self.source = _source_length(self.counts)
        require(
            self.source <= limits.source_bytes,
            "The fixed source exceeds the header limit.",
        )

    def reserve(self, table: str, count: int) -> int:
        old = self.counts[table]
        new = old + count
        require(new < 1 << 32, "A table index exceeds unsigned 32-bit bounds.")
        total = self.storage + count * element_bytes(table)
        require(
            total <= self.limits.initializer_bytes,
            "Logical constants exceed their byte limit.",
        )
        previous_length = _row_length(table) * old if old else len(_empty_row(table))
        new_length = _row_length(table) * new if new else len(_empty_row(table))
        source = (
            self.source
            + new_length
            - previous_length
            + len(declaration(table, new))
            - len(declaration(table, old))
        )
        require(
            source <= self.limits.source_bytes,
            "The generated source exceeds its byte limit.",
        )
        self.counts[table] = new
        self.storage = total
        self.source = source
        return old

    def text(self, value: object, descriptor: str) -> None:
        require(type(value) is str, "Text must be an exact string.")
        text = cast(str, value)
        if descriptor == "w":
            require(
                re.fullmatch(r"(?:[0-9a-f]{2}){1,15}", text) is not None,
                "Invalid original instruction witness.",
            )
            self.reserve("bytes", len(text) // 2)
            return
        if descriptor == "h":
            require(re.fullmatch(r"[0-9a-f]{64}", text) is not None, "Invalid digest.")
        if descriptor.startswith("e:"):
            require(text in descriptor[2:].split("|"), "Invalid fixed literal.")
        require(
            len(text) <= self.limits.initializer_bytes - self.storage,
            "Text exceeds the remaining constant bound.",
        )
        size = 0
        for character in text:
            number = ord(character)
            require(not 0xD800 <= number <= 0xDFFF, "Text is not strict UTF-8.")
            size += (
                1
                if number < 0x80
                else 2
                if number < 0x800
                else 3
                if number < 0x10000
                else 4
            )
            require(
                size <= self.limits.initializer_bytes - self.storage,
                "UTF-8 text exceeds the remaining constant bound.",
            )
        self.reserve("bytes", size)

    def value(
        self, descriptor: str, value: object, previous: dict[str, object]
    ) -> None:
        if descriptor.startswith("o:"):
            if value is not None:
                self.value(descriptor[2:], value, previous)
        elif descriptor.startswith(("v:", "v0:")):
            _, table = _variant(descriptor, value)
            if table is not None:
                self.reserve(table, 1)
                self.record(table, value)
        elif descriptor.startswith("a:"):
            require(type(value) is tuple, "An array must be an exact tuple.")
            values = cast(tuple[object, ...], value)
            table = descriptor[2:]
            self.reserve(table, len(values))
            for child in values:
                self.record(table, child)
        elif descriptor.startswith("r:"):
            table = descriptor[2:]
            self.reserve(table, 1)
            self.record(table, value)
        elif descriptor in ("s", "h", "w") or descriptor.startswith("e:"):
            self.text(value, descriptor)
        elif descriptor == "b":
            require(type(value) is bool, "Invalid exact Boolean type.")
        else:
            require(type(value) is int, "An integer must have the exact integer type.")
            integer = cast(int, value)
            if descriptor == "i":
                require(
                    -(1 << 63) <= integer < 1 << 63, "A signed tag exceeds its bound."
                )
                return
            if descriptor.startswith("end:"):
                start = cast(int, previous[descriptor[4:]])
                require(start <= integer <= 1 << 64, "Invalid geometry endpoint.")
                integer -= start
            require(
                0 <= integer <= U64,
                "An unsigned value or span size is not representable.",
            )
            if descriptor.startswith("n:"):
                require(integer == int(descriptor[2:]), "Invalid schema number.")

    def record(self, table: str, value: object) -> None:
        previous: dict[str, object] = {}
        for (name, descriptor), child in zip(
            FIELDS[table], _members(table, value), strict=True
        ):
            self.value(descriptor, child, previous)
            previous[name] = child


class _Tables:
    def __init__(self) -> None:
        self.rows: dict[str, list[tuple[Cell, ...]]] = {
            name: [] for name in TABLES if name != "bytes"
        }
        self.octets = bytearray()

    def records(self, table: str, values: tuple[object, ...]) -> tuple[int, int]:
        offset = len(self.rows[table])
        self.rows[table].extend([()] * len(values))
        for index, value in enumerate(values, offset):
            previous: dict[str, object] = {}
            row = []
            for (name, descriptor), child in zip(
                FIELDS[table], _members(table, value), strict=True
            ):
                row.append(self.value(descriptor, child, previous))
                previous[name] = child
            self.rows[table][index] = tuple(row)
        return offset, len(values)

    def value(
        self, descriptor: str, value: object, previous: dict[str, object]
    ) -> Cell:
        if descriptor.startswith("o:"):
            return (
                (0, _zero(descriptor[2:]))
                if value is None
                else (1, self.value(descriptor[2:], value, previous))
            )
        if descriptor.startswith(("v:", "v0:")):
            tag, table = _variant(descriptor, value)
            alternatives = descriptor.split(":", 1)[1].split(",")
            return (
                tag,
                *(
                    self.records(name, (value,)) if name == table else (0, 0)
                    for name in alternatives
                ),
            )
        if descriptor.startswith("a:"):
            return self.records(descriptor[2:], cast(tuple[object, ...], value))
        if descriptor.startswith("r:"):
            return self.records(descriptor[2:], (value,))
        if descriptor in ("s", "h", "w") or descriptor.startswith("e:"):
            text = cast(str, value)
            raw = (
                bytes.fromhex(text)
                if descriptor == "w"
                else text.encode("utf-8", errors="strict")
            )
            offset = len(self.octets)
            self.octets.extend(raw)
            return offset, len(raw)
        if descriptor == "i":
            number = cast(int, value)
            return int(number < 0), abs(number)
        if descriptor.startswith("end:"):
            return cast(int, value) - cast(int, previous[descriptor[4:]])
        return int(cast(int, value))


def _limits(supplied: object, maximum: object) -> None:
    require(type(supplied) is type(maximum), "Invalid exact limit record type.")
    for item in fields(cast(type[HeaderLimits], type(maximum))):
        value: object = getattr(supplied, item.name)
        require(
            type(value) is int and 0 < value <= getattr(maximum, item.name),
            f"Invalid lower limit for {item.name}.",
        )
    if isinstance(supplied, (scope_types.CaptureLimits, plan_types.TraceLimits)):
        require(supplied.snapshot_bytes == 8, "The snapshot width must be eight.")


def _json_tokens(value: object) -> Iterator[str]:
    if is_dataclass(value) and not isinstance(value, type):
        yield "{"
        for index, item in enumerate(sorted(fields(value), key=lambda item: item.name)):
            if index:
                yield ","
            yield json.dumps(item.name) + ":"
            yield from _json_tokens(getattr(value, item.name))
        yield "}"
    elif type(value) is tuple:
        yield "["
        for index, child in enumerate(cast(tuple[object, ...], value)):
            if index:
                yield ","
            yield from _json_tokens(child)
        yield "]"
    elif type(value) is str:
        yield '"'
        for character in value:
            yield json.dumps(character, ensure_ascii=True)[1:-1]
        yield '"'
    else:
        yield json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _canonical_identity(value: object, limit: int) -> str:
    digest = sha256()
    length = 1
    for token in _json_tokens(value):
        length += len(token)
        require(length <= limit, "The canonical record exceeds its lower byte limit.")
        digest.update(token.encode("ascii"))
    digest.update(b"\n")
    return digest.hexdigest()


def _identities(data: CollectorData) -> None:
    """Check internal consistency. Raw reconstruction remains a separate boundary."""
    plan, scope, image = data.full_plan, data.scope, data.image
    _limits(data.transport_limits, data_types.TransportLimits())
    _limits(plan.limits, plan_types.TraceLimits())
    _limits(scope.limits, scope_types.CaptureLimits())
    require(
        _canonical_identity(plan, scope.limits.full_plan_bytes) == data.full_plan_sha256
        and _canonical_identity(scope, scope.limits.scope_bytes) == data.scope_sha256,
        "The complete canonical record identity differs.",
    )
    for record in (plan, scope):
        require(
            record.binary_sha256 == data.original.sha256
            and record.lift_sha256 == data.lift_sha256
            and record.address_proof_sha256 == data.address_proof_sha256,
            "The complete record evidence identities differ.",
        )
    require(
        scope.full_plan_sha256 == data.full_plan_sha256
        and scope.policy_implementation_sha256 == data.policy_implementation_sha256,
        "The scope identity links differ.",
    )
    require(
        scope.policy_implementation_sha256
        == scope_types.policy_implementation_sha256(),
        "The installed scope policy differs.",
    )
    require(
        scope.root == scope.request.root and scope.users == scope.request.users,
        "The scope request differs.",
    )
    require(
        scope.root in scope.users
        and scope.users == tuple(sorted(set(scope.users)))
        and bool(scope.users),
        "Invalid requested user partition.",
    )
    evidence = scope.request.root_evidence
    if isinstance(evidence, scope_types.LiftMain):
        require(
            evidence.lift_sha256 == data.lift_sha256
            and evidence.main_elf == scope.root,
            "The root evidence differs.",
        )
    else:
        require(
            evidence.request_sha256 == scope.request.intent_sha256,
            "The explicit root evidence differs.",
        )
    expected_registers = tuple(
        (name, 64) for name in ("rdi", "rsi", "rdx", "rcx", "rax", "rsp")
    )
    require(
        plan.registers == scope.registers == expected_registers,
        "The ordered register profile differs.",
    )
    require(
        not scope.contracts, "Termination contracts are unsupported in this profile."
    )
    limits, transport = scope.limits, data.transport_limits
    require(
        0 < data.original.bytes <= transport.original_bytes,
        "The original byte count exceeds its limit.",
    )
    inventories = (
        (len(plan.sites), limits.full_plan_sites),
        (len(plan.gaps), transport.gap_records),
        (len(scope.users), transport.users),
        (len(scope.routes), transport.routes),
        (len(scope.omitted), transport.omissions),
        (len(scope.gap_dispositions), transport.gap_records),
        (len(scope.guard_instructions), limits.guarded_instructions),
        (len(image.segments), transport.elf_segments),
        (len(image.dynamic), 65536),
        (
            sum(len(route.instruction_path) for route in scope.routes),
            transport.route_path_positions,
        ),
        (
            sum(
                len(guard.rule.positions)
                for guard in scope.guard_instructions
                if isinstance(guard.rule, scope_types.TransitInstruction)
            ),
            transport.route_memberships,
        ),
    )
    require(
        all(count <= bound for count, bound in inventories),
        "An inventory exceeds its lower bound.",
    )
    require(
        all(len(route.entries) <= limits.route_entries for route in scope.routes),
        "A route exceeds its entry bound.",
    )
    require(
        image.kind in (2, 3) and bool(image.segments), "Unsupported ELF image geometry."
    )
    for segment in image.segments:
        require(
            segment.file_size <= segment.memory_size
            and segment.file_offset + segment.file_size <= data.original.bytes
            and segment.va + segment.memory_size <= 1 << 64,
            "Invalid ELF segment geometry.",
        )
    executable = tuple(segment for segment in image.segments if segment.flags & 1)
    require(bool(executable), "No executable load segment.")
    geometry = data_types.Geometry(
        min(segment.va for segment in executable),
        max(segment.va + segment.file_size for segment in executable),
        min(segment.va for segment in image.segments),
        max(segment.va + segment.memory_size for segment in image.segments),
    )
    require(data.geometry == geometry, "The complete geometry differs from the image.")
    require(
        len(scope.gap_dispositions) == len(plan.gaps),
        "The complete gap inventory differs.",
    )
    for index, gap in enumerate(scope.gap_dispositions):
        require(
            gap.index == index and (gap.address, gap.reason) == plan.gaps[index],
            "The original gap index or record differs.",
        )
    routes = {route.sha256: route for route in scope.routes}
    require(len(routes) == len(scope.routes), "Duplicate logical routes.")
    sites = {site.address: site for site in plan.sites}
    require(len(sites) == len(plan.sites), "Duplicate plan sites.")
    for route in scope.routes:
        site = sites.get(route.call_site)
        require(
            site is not None
            and isinstance(site.transfer, plan_types.Call)
            and site.transfer.imported is not None,
            "A route has no call-specific binding.",
        )
        assert site is not None and isinstance(site.transfer, plan_types.Call)
        binding = site.transfer.imported
        assert binding is not None
        require(
            _canonical_identity(binding, 512 * 1024) == route.binding_sha256
            and binding.identity == route.request
            and binding.relocation_slot == route.slot,
            "The call-specific route binding differs.",
        )
    guards = {guard.address: guard for guard in scope.guard_instructions}
    require(len(guards) == len(scope.guard_instructions), "Duplicate guard addresses.")
    for route in scope.routes:
        cursor = 0
        for entry in route.entries:
            require(
                cursor < len(route.instruction_path)
                and route.instruction_path[cursor] == entry,
                "A route entry has no exact path position.",
            )
            count = 0
            byte_count = 0
            last_size = 0
            while cursor < len(route.instruction_path):
                address = route.instruction_path[cursor]
                guard = guards.get(address)
                require(guard is not None, "A route position has no guard.")
                assert guard is not None
                if guard.owner != entry:
                    break
                count += 1
                last_size = len(guard.witness_hex) // 2
                byte_count += last_size
                require(
                    count - 1 <= limits.thunk_neutral_instructions,
                    "A thunk exceeds its lower instruction limit.",
                )
                cursor += 1
            require(
                count > 0 and byte_count - last_size <= limits.thunk_neutral_bytes,
                "A thunk exceeds its lower neutral byte limit.",
            )
        require(
            cursor == len(route.instruction_path)
            and route.terminal
            == (
                route.instruction_path[-1]
                if route.instruction_path
                else route.call_site
            ),
            "The route path or terminal differs.",
        )
    positions: dict[int, list[tuple[str, int]]] = {}
    for identity, route in routes.items():
        for position, address in enumerate(route.instruction_path):
            positions.setdefault(address, []).append((identity, position))
    require(
        set(positions)
        == {
            guard.address
            for guard in scope.guard_instructions
            if isinstance(guard.rule, scope_types.TransitInstruction)
        },
        "The complete transit guard inventory differs.",
    )
    for guard in scope.guard_instructions:
        if isinstance(guard.rule, scope_types.TransitInstruction):
            require(
                guard.rule.positions == tuple(sorted(positions.get(guard.address, []))),
                "The complete route memberships differ.",
            )
    require(
        plan.scope == tuple(site.address for site in plan.sites if site.entry),
        "The complete entry inventory differs.",
    )
    continuation_users: dict[int, list[int]] = {}
    for site in plan.sites:
        if isinstance(site.transfer, plan_types.Call):
            continuation_users.setdefault(site.transfer.continuation, []).append(
                site.address
            )
    require(set(continuation_users) <= sites.keys(), "A continuation site is missing.")
    for site in plan.sites:
        require(
            site.continuation_of
            == tuple(sorted(continuation_users.get(site.address, []))),
            "The complete continuation users differ.",
        )

    def roles(site: plan_types.TraceSite | None) -> tuple[str, ...]:
        if site is None:
            return ()
        return tuple(
            sorted(
                (
                    *(("entry",) if site.entry else ()),
                    *(("continuation",) if site.continuation_of else ()),
                    *((site.transfer.kind,) if site.transfer is not None else ()),
                )
            )
        )

    require(
        tuple(address for address, _ in scope.dispositions) == tuple(sites),
        "The complete site disposition inventory differs.",
    )
    omitted = []
    for address, disposition in scope.dispositions:
        site = sites[address]
        if site.owner in scope.users:
            require(
                type(disposition) is scope_types.User
                and disposition.owner == site.owner,
                "A user disposition differs from its owner.",
            )
        elif address in positions:
            require(
                type(disposition) is scope_types.Transit
                and disposition.route_ids
                == tuple(sorted({identity for identity, _ in positions[address]})),
                "The complete disposition route identities differ.",
            )
        else:
            require(
                type(disposition) is scope_types.Omitted,
                "An omitted disposition has the wrong type.",
            )
            assert isinstance(disposition, scope_types.Omitted)
            omitted.append(
                scope_types.OmittedSite(
                    address,
                    site.owner,
                    sha256(bytes.fromhex(site.witness_hex)).hexdigest(),
                    roles(site),
                    disposition.reason,
                )
            )
    require(scope.omitted == tuple(omitted), "The complete omission metadata differs.")
    for guard in scope.guard_instructions:
        site = sites.get(guard.address)
        require(guard.full_roles == roles(site), "The complete guard roles differ.")
        if site is not None:
            require(
                guard.owner == site.owner and guard.witness_hex == site.witness_hex,
                "The guard and complete plan witness differ.",
            )


def render_header(
    data: CollectorData, *, limits: HeaderLimits = HeaderLimits()
) -> GeneratedHeader | CollectorRejected:
    """Validate and measure before materializing typed tables or generated source."""
    try:
        _limits(limits, HeaderLimits())
        require(type(data) is CollectorData, "Invalid collector data type.")
        measure = _Measure(limits)
        measure.reserve("collector_data", 1)
        measure.record("collector_data", data)
        _identities(data)
        logical = _canonical_identity(data, data.transport_limits.data_bytes)
        renderer = renderer_identity()
        native = sha256(native_bytes()).hexdigest()
        tables = _Tables()
        tables.records("collector_data", (data,))
        counts = tuple(
            (table, len(tables.octets) if table == "bytes" else len(tables.rows[table]))
            for table in TABLES
        )
        require(dict(counts) == measure.counts, "The measured table inventory differs.")
        output = bytearray(PREFIX.encode("ascii"))
        for table, count in counts:
            output.extend(declaration(table, count).encode("ascii"))
            if count == 0:
                output.extend(_empty_row(table).encode("ascii"))
            elif table == "bytes":
                for octet in tables.octets:
                    output.extend(f"    0x{octet:02x},\n".encode("ascii"))
            else:
                for row in tables.rows[table]:
                    output.extend(("    " + _cell_text(row) + ",\n").encode("ascii"))
            output.extend(SUFFIX.encode("ascii"))
        output.extend(DIRECTORY.encode("ascii"))
        for digest in (logical, renderer, native):
            output.extend(
                (
                    "    {"
                    + ", ".join(f"0x{octet:02x}" for octet in bytes.fromhex(digest))
                    + "},\n"
                ).encode("ascii")
            )
        output.extend(b"    {\n")
        for table, count in counts:
            output.extend(directory_entry(table, count).encode("ascii"))
        output.extend(b"    }\n};\n")
        require(len(output) == measure.source, "The measured source length differs.")
        raw = bytes(output)
        decoded = read_header(
            raw,
            source_bytes=limits.source_bytes,
            initializer_bytes=limits.initializer_bytes,
        )
        require(
            decoded.record == data.record(), "The independent complete decode differs."
        )
        return GeneratedHeader(
            raw,
            sha256(raw).hexdigest(),
            logical,
            renderer,
            native,
            counts,
            measure.storage,
        )
    except data_types._Refusal as error:
        return CollectorRejected(error.reason, error.detail)
    except (HeaderReadError, MappingError) as error:
        return CollectorRejected(
            "render_limit"
            if "limit" in str(error) or "bound" in str(error)
            else "input_type",
            str(error)[:512],
        )
