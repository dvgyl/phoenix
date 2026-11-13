"""Private compiled-data consistency. No result grants source or runtime authority."""

from __future__ import annotations

import json
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from hashlib import sha256
from struct import Struct
from types import MappingProxyType
from typing import NoReturn, cast

from phoenix.observe import collector_elf as elf_module
from phoenix.observe import collector_layout as layout


@dataclass(frozen=True, slots=True)
class ExpectedCollector:
    logical_raw: bytes
    renderer_sha256: str
    native_source_sha256: str


type LogicalValue = None | bool | int | str | tuple[LogicalValue, ...] | LogicalObject


@dataclass(frozen=True, slots=True)
class LogicalObject:
    entries: tuple[tuple[str, LogicalValue], ...]


@dataclass(frozen=True, slots=True)
class TableSpan:
    tag: int
    name: str
    count: int
    logical_element_bytes: int
    logical_bytes: int
    element_bytes: int
    storage_bytes: int
    section_index: int
    static_symbol_index: int
    va: elf_module.ElfVa
    file_offset: elf_module.FileOffset
    pointer_relocation: elf_module.Rela


@dataclass(frozen=True, slots=True)
class DirectoryView:
    export: elf_module.Export
    data_digest: bytes
    renderer_digest: bytes
    native_digest: bytes
    tables: tuple[TableSpan, ...]


@dataclass(frozen=True, slots=True)
class WorkUsage:
    scanned_upper: int
    scalar_upper: int


@dataclass(frozen=True, slots=True)
class LogicalReadback:
    logical_raw: bytes
    logical_sha256: str
    directory: DirectoryView
    witness_export: elf_module.Export
    elf: elf_module.CollectorElf
    limits: elf_module.InspectionLimits
    usage: WorkUsage


class _DecodeRefusal(Exception):
    def __init__(self, result: elf_module.InspectionRejected):
        self.result = result


def _refuse(reason: elf_module.InspectionReason, detail: str) -> NoReturn:
    raise _DecodeRefusal(elf_module.InspectionRejected(reason, detail))


def _require(ok: bool, reason: elf_module.InspectionReason, detail: str) -> None:
    if not ok:
        _refuse(reason, detail)


@dataclass(slots=True)
class WorkBudget:
    limits: elf_module.InspectionLimits
    scanned: int = 0
    scalars: int = 0

    def scan(self, amount: int) -> None:
        assert amount >= 0
        _require(
            amount <= self.limits.scanned_bytes - self.scanned,
            "work_limit",
            "The byte-scan limit is exceeded.",
        )
        self.scanned += amount

    def scalar(self, amount: int = 1) -> None:
        assert amount >= 0
        _require(
            amount <= self.limits.scalar_visits - self.scalars,
            "work_limit",
            "The scalar-visit limit is exceeded.",
        )
        self.scalars += amount

    def depth(self, depth: int) -> None:
        _require(
            depth <= self.limits.nesting, "work_limit", "The nesting limit is exceeded."
        )


@dataclass(slots=True)
class CursorState:
    cursors: list[int] = field(default_factory=lambda: [0] * 47)
    route_paths: int = 0
    route_memberships: int = 0


@dataclass(frozen=True, slots=True)
class _Indexes:
    exports: Mapping[str, elf_module.Export]
    symbols: Mapping[bytes, elf_module.Symbol]
    sections: Mapping[int, elf_module.Section]
    relocations: Mapping[int, elf_module.Rela]
    loads: tuple[elf_module.LoadSpan, ...]
    starts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Lower:
    transport: Mapping[str, int]
    trace: Mapping[str, int]
    capture: Mapping[str, int]


_U32 = Struct("<I")
_U64 = Struct("<Q")


def _checked_inputs(
    raw: bytes,
    expected: ExpectedCollector,
    profile: layout.ProfileId,
    limits: elf_module.InspectionLimits,
) -> tuple[ExpectedCollector, layout.LayoutDefinition, WorkBudget]:
    _require(
        type(raw) is bytes
        and type(expected) is ExpectedCollector
        and type(profile) is str
        and type(limits) is elf_module.InspectionLimits,
        "input_type",
        "Expected exact immutable input records.",
    )
    values: dict[str, int] = {}
    maximum = elf_module.InspectionLimits()
    for item in fields(elf_module.InspectionLimits):
        try:
            value = getattr(limits, item.name)
        except AttributeError:
            _refuse("input_limit", "A limit field is missing.")
        _require(
            type(value) is int and 0 < value <= getattr(maximum, item.name),
            "input_limit",
            "A limit is outside its installed bounds.",
        )
        values[item.name] = value
    checked = elf_module.InspectionLimits(**values)
    try:
        logical = expected.logical_raw
        renderer = expected.renderer_sha256
        native = expected.native_source_sha256
    except AttributeError:
        _refuse("input_type", "An expected field is missing.")
    _require(
        type(logical) is bytes and type(renderer) is str and type(native) is str,
        "input_type",
        "Expected exact bytes and digest strings.",
    )
    _require(
        len(raw) <= checked.plugin_bytes and len(logical) <= checked.logical_data_bytes,
        "input_limit",
        "An input byte limit is exceeded.",
    )
    budget = WorkBudget(checked)
    for digest in (renderer, native):
        _require(len(digest) == 64, "source_identity", "Invalid expected digest.")
        budget.scan(64)
        _require(
            all(c in "0123456789abcdef" for c in digest),
            "source_identity",
            "Invalid expected digest.",
        )
    _require(len(profile) <= 32, "layout_mismatch", "Unknown candidate profile ID.")
    budget.scan(2 * len(profile))
    _require(
        profile in ("linux-x86_64-lp64-le-rela-1", "linux-aarch64-lp64-le-rela-1"),
        "layout_mismatch",
        "Unknown candidate profile ID.",
    )
    return (
        ExpectedCollector(logical, renderer, native),
        layout._definition(profile),
        budget,
    )


def _read_elf(
    raw: bytes, definition: layout.LayoutDefinition, budget: WorkBudget
) -> elf_module.CollectorElf:
    scans = budget.limits.scanned_bytes - budget.scanned
    scalars = budget.limits.scalar_visits - budget.scalars
    _require(scans > 0 and scalars > 0, "work_limit", "No ELF work allowance remains.")
    result = elf_module.read_collector_elf(
        raw,
        machine=definition.machine,
        limits=replace(budget.limits, scanned_bytes=scans, scalar_visits=scalars),
    )
    if isinstance(result, elf_module.InspectionRejected):
        raise _DecodeRefusal(result)
    return result


def _debit_u1(view: elf_module.CollectorElf, budget: WorkBudget) -> None:
    scalar = (
        14
        + 8 * len(view.programs)
        + 10 * len(view.sections)
        + 2 * len(view.dynamic)
        + 6 * len(view.symbols)
        + sum(s.size // 2 for s in view.sections if s.type == 0x6FFFFFFF)
        + sum(s.size // 4 for s in view.sections if s.type == 5)
        + 3 * len(view.relocations)
        + 47 * 7
    )
    scan = (
        2 * len(view.raw)
        + 2 * sum(len(s.name) for s in view.sections)
        + 3 * sum(len(s.name) for s in view.symbols)
        + 2 * sum(len(n) for n in view.needed)
        + 6 * budget.limits.symbol_name_bytes
    )
    budget.scalar(scalar)
    budget.scan(scan)


def _index_view(
    view: elf_module.CollectorElf,
    definition: layout.LayoutDefinition,
    budget: WorkBudget,
) -> _Indexes:
    sections = {s.index: s for s in view.sections}
    exports = {}
    for export in view.exports:
        budget.scan(len(export.name))
        _require(export.name not in exports, "symbol_ambiguous", "Duplicate export.")
        exports[export.name] = export
    budget.scan(sum(2 * (8 + len(t.name)) for t in definition.tables))
    required = frozenset(
        ("phoenix_" + t.name).encode("ascii") for t in definition.tables
    )
    symbols = {}
    for symbol in view.symbols:
        if sections[symbol.table_section].type == 2:
            budget.scan(2 * len(symbol.name))
            if symbol.name in required:
                _require(
                    symbol.name not in symbols,
                    "symbol_ambiguous",
                    "A fixed symbol is duplicated.",
                )
                symbols[symbol.name] = symbol
    relocations: dict[int, elf_module.Rela] = {
        int(r.place_va): r for r in view.relocations
    }
    loads = tuple(
        sorted((load for load in view.loads if load.memsz), key=lambda load: load.va)
    )
    return _Indexes(
        MappingProxyType(exports),
        MappingProxyType(symbols),
        MappingProxyType(sections),
        MappingProxyType(relocations),
        loads,
        tuple(load.va for load in loads),
    )


def _cell(
    raw: memoryview, start: int, end: int, position: int, width: int, budget: WorkBudget
) -> int:
    _require(
        start <= position <= end and width <= end - position,
        "table_bounds",
        "A cell exceeds its owning row.",
    )
    budget.scalar()
    budget.scan(width)
    return cast(int, (_U32 if width == 4 else _U64).unpack_from(raw, position)[0])


def _check_witness(
    view: elf_module.CollectorElf,
    indexes: _Indexes,
    definition: layout.LayoutDefinition,
    budget: WorkBudget,
) -> elf_module.Export:
    witness = indexes.exports["phoenix_collector_layout_v1"]
    _require(witness.bytes == 40168, "layout_mismatch", "Invalid witness size.")
    raw = memoryview(view.raw)
    for i, expected in enumerate(layout._expected_witness(definition)):
        actual = _cell(
            raw,
            witness.file_offset,
            witness.file_offset + witness.bytes,
            witness.file_offset + 8 * i,
            8,
            budget,
        )
        _require(actual == expected, "layout_mismatch", "A witness word differs.")
    return witness


def _read_directory(
    view: elf_module.CollectorElf,
    indexes: _Indexes,
    definition: layout.LayoutDefinition,
    budget: WorkBudget,
) -> DirectoryView:
    export = indexes.exports["phoenix_collector_data_v1"]
    raw = memoryview(view.raw)
    start, end = export.file_offset, export.file_offset + export.bytes
    _require(export.bytes == 2728, "directory_contract", "Invalid directory size.")
    budget.scan(96)
    identities = tuple(
        bytes(raw[start + i * 32 : start + (i + 1) * 32]) for i in range(3)
    )
    dimensions = []
    physical, rows = 2728 + 40168, 0
    _require(
        physical <= budget.limits.physical_data_bytes,
        "input_limit",
        "The physical data limit is exceeded.",
    )
    for i, table in enumerate(definition.tables):
        values = tuple(
            _cell(raw, start, end, start + 96 + i * 56 + j * 8, 8, budget)
            for j in range(6)
        )
        tag, count, logical_element, logical, element, storage = values
        _require(
            tag == table.tag
            and count < 1 << 32
            and logical_element == table.logical_element_bytes
            and logical == count * logical_element
            and element == definition.types[table.element_type - 1].bytes
            and storage == max(1, count) * element
            and (tag != 47 or count == 1),
            "directory_contract",
            "Invalid independent table dimensions.",
        )
        physical += storage
        rows += count if tag != 1 else 0
        _require(
            physical <= budget.limits.physical_data_bytes
            and rows <= budget.limits.nonbyte_rows,
            "input_limit",
            "The physical data or row limit is exceeded.",
        )
        dimensions.append(values)
    tables = []
    files: list[tuple[int, int]] = [(start, end)]
    virtual = [(export.va, export.va + export.bytes)]
    witness = indexes.exports["phoenix_collector_layout_v1"]
    files.append((witness.file_offset, witness.file_offset + witness.bytes))
    virtual.append((witness.va, witness.va + witness.bytes))
    for i, table in enumerate(definition.tables):
        tag, count, logical_element, logical, element, storage = dimensions[i]
        budget.scan(2 * (8 + len(table.name)))
        name = ("phoenix_" + table.name).encode("ascii")
        symbol = indexes.symbols.get(name)
        _require(
            symbol is not None, "symbol_missing", "A fixed table symbol is missing."
        )
        assert symbol is not None
        _require(
            symbol.binding == 0 and symbol.type == 1 and symbol.bytes == storage,
            "export_contract",
            "A local table extent or type differs.",
        )
        section = indexes.sections[symbol.section_index]
        offset = section.offset + symbol.va - section.va
        load_index = bisect_right(indexes.starts, symbol.va) - 1
        _require(load_index >= 0, "ambiguous_mapping", "A table has no load.")
        load = indexes.loads[load_index]
        _require(
            section.va <= symbol.va
            and symbol.va + storage <= section.va + section.size
            and load.va <= symbol.va
            and symbol.va + storage <= load.va + load.filesz
            and offset == load.offset + symbol.va - load.va
            and 0 <= offset <= len(raw)
            and storage <= len(raw) - offset,
            "ambiguous_mapping",
            "A table mapping differs.",
        )
        place = export.va + 144 + i * 56
        relocation = indexes.relocations.get(place)
        _require(
            relocation is not None,
            "relocation_contract",
            "A pointer relocation is missing.",
        )
        assert relocation is not None
        _require(
            relocation.width == 8
            and relocation.type == (8 if view.machine == 62 else 1027)
            and relocation.symbol_index == 0
            and relocation.addend == symbol.va,
            "relocation_contract",
            "A directory pointer differs.",
        )
        if count == 0:
            if tag == 1:
                budget.scalar()
                budget.scan(1)
                _require(raw[offset] == 0, "table_bounds", "Empty storage is not zero.")
            else:
                for spec in definition.field_specs[i]:
                    for position, width in layout._leaf_cells(
                        spec.descriptor, spec.offset
                    ):
                        value = _cell(
                            raw,
                            offset,
                            offset + storage,
                            offset + position,
                            width,
                            budget,
                        )
                        _require(
                            value == 0, "table_bounds", "Empty storage is not zero."
                        )
        tables.append(
            TableSpan(
                tag,
                table.name,
                count,
                logical_element,
                logical,
                element,
                storage,
                section.index,
                symbol.index,
                symbol.va,
                elf_module.FileOffset(offset),
                relocation,
            )
        )
        files.append((offset, offset + storage))
        virtual.append((symbol.va, symbol.va + storage))
    for spans in (files, virtual):
        previous = 0
        for begin, finish in sorted(spans):
            _require(begin >= previous, "storage_overlap", "Physical objects overlap.")
            previous = finish
    return DirectoryView(
        export, identities[0], identities[1], identities[2], tuple(tables)
    )


@dataclass(frozen=True, slots=True)
class _Decoder:
    raw: memoryview
    definition: layout.LayoutDefinition
    directory: DirectoryView
    budget: WorkBudget
    state: CursorState
    lower: _Lower

    def row_span(self, tag: int, index: int) -> tuple[int, int]:
        table = self.directory.tables[tag - 1]
        _require(
            0 <= index < table.count, "table_bounds", "A row is outside its table."
        )
        start = table.file_offset + index * table.element_bytes
        return start, start + table.element_bytes

    def integer(self, row: tuple[int, int], offset: int, width: int = 8) -> int:
        return _cell(self.raw, row[0], row[1], row[0] + offset, width, self.budget)

    def zero(
        self, row: tuple[int, int], offset: int, descriptor: layout.Descriptor
    ) -> None:
        for position, width in layout._leaf_cells(descriptor, offset):
            _require(
                self.integer(row, position, width) == 0,
                "logical_shape",
                "An inactive semantic cell is not zero.",
            )

    def claim(
        self, tag: int, offset: int, count: int, *, record: bool = False
    ) -> range:
        table = self.directory.tables[tag - 1]
        _require(
            offset <= table.count and count <= table.count - offset,
            "table_bounds",
            "A slice is outside its table.",
        )
        _require(
            not record or count == 1,
            "logical_shape",
            "A record reference needs one row.",
        )
        _require(
            offset == self.state.cursors[tag - 1],
            "table_bounds",
            "A slice does not start at its ownership cursor.",
        )
        self.state.cursors[tag - 1] = offset + count
        return range(offset, offset + count)

    def count_limit(self, tag: int, name: str, count: int) -> None:
        transport, capture = self.lower.transport, self.lower.capture
        caps = {
            (20, "sites"): capture["full_plan_sites"],
            (20, "gaps"): transport["gap_records"],
            (23, "users"): transport["users"],
            (44, "users"): transport["users"],
            (44, "routes"): transport["routes"],
            (44, "omitted"): transport["omissions"],
            (44, "gap_dispositions"): transport["gap_records"],
            (44, "guard_instructions"): capture["guarded_instructions"],
            (46, "segments"): transport["elf_segments"],
            (46, "dynamic"): layout.IMAGE_DYNAMIC_MAXIMUM,
            (28, "entries"): capture["route_entries"],
        }
        cap = caps.get((tag, name))
        _require(
            cap is None or count <= cap,
            "input_limit",
            "A retained inventory cap is exceeded.",
        )
        if (tag, name) == (44, "contracts"):
            _require(
                count == 0, "logical_shape", "Main-window contracts must be empty."
            )
        if (tag, name) == (28, "instruction_path"):
            _require(
                count <= transport["route_path_positions"] - self.state.route_paths,
                "input_limit",
                "The route path limit is exceeded.",
            )
            self.state.route_paths += count
        if (tag, name) == (33, "positions"):
            _require(
                count <= transport["route_memberships"] - self.state.route_memberships,
                "input_limit",
                "The route membership limit is exceeded.",
            )
            self.state.route_memberships += count

    def value(
        self,
        descriptor: layout.Descriptor,
        row: tuple[int, int],
        offset: int,
        previous: Mapping[str, LogicalValue],
        depth: int,
        owner: int,
        name: str,
    ) -> LogicalValue:
        self.budget.depth(depth)
        match descriptor:
            case layout.Option(payload=payload):
                tag = self.integer(row, offset)
                _require(tag in (0, 1), "logical_shape", "Invalid option tag.")
                if tag == 0:
                    self.zero(row, offset + 8, payload)
                    return None
                return self.value(
                    payload, row, offset + 8, previous, depth + 1, owner, name
                )
            case layout.Variant(nullable=nullable, target_tags=tags):
                tag = self.integer(row, offset)
                _require(
                    (0 if nullable else 1) <= tag <= len(tags),
                    "logical_shape",
                    "Invalid variant tag.",
                )
                for i, target in enumerate(tags, 1):
                    if i != tag:
                        self.zero(
                            row, offset + i * 8, layout.TableSlice(target, "record")
                        )
                if tag == 0:
                    return None
                return self.value(
                    layout.TableSlice(tags[tag - 1], "record"),
                    row,
                    offset + tag * 8,
                    previous,
                    depth + 1,
                    owner,
                    name,
                )
            case layout.TableSlice(target_tag=target, mode=mode):
                begin = self.integer(row, offset, 4)
                count = self.integer(row, offset + 4, 4)
                self.count_limit(owner, name, count)
                claimed = self.claim(target, begin, count, record=mode == "record")
                if mode == "record":
                    return self.decode_row(target, begin, depth + 1)
                return tuple(
                    self.decode_row(target, index, depth + 1) for index in claimed
                )
            case layout.TextSlice(kind=kind, literals=literals):
                begin = self.integer(row, offset, 4)
                count = self.integer(row, offset + 4, 4)
                self.claim(1, begin, count)
                _require(
                    kind != "witness" or 1 <= count <= 15,
                    "logical_shape",
                    "Invalid instruction witness length.",
                )
                _require(
                    kind != "digest" or count == 64,
                    "logical_shape",
                    "Invalid digest length.",
                )
                start = self.directory.tables[0].file_offset + begin
                raw = self.raw[start : start + count]
                if kind == "witness":
                    self.budget.scan(count + count * 2)
                    return raw.hex()
                self.budget.scan(count)
                copied = bytes(raw)
                self.budget.scan(count)
                try:
                    text = copied.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    _refuse("logical_shape", "Invalid UTF-8 text.")
                if kind == "digest":
                    self.budget.scan(count)
                    _require(
                        all(c in "0123456789abcdef" for c in text),
                        "logical_shape",
                        "Invalid digest text.",
                    )
                if kind == "literal":
                    self.budget.scan(count * len(literals))
                    _require(text in literals, "logical_shape", "Invalid literal text.")
                return text
            case layout.Signed64():
                sign, magnitude = (
                    self.integer(row, offset),
                    self.integer(row, offset + 8),
                )
                _require(
                    sign in (0, 1)
                    and magnitude <= (1 << 63) - (1 - sign)
                    and not (sign == 1 and magnitude == 0),
                    "logical_shape",
                    "Invalid signed value.",
                )
                return -magnitude if sign else magnitude
            case (
                layout.UInt64()
                | layout.Boolean64()
                | layout.ExactNumber()
                | layout.EndFrom()
            ):
                value = self.integer(row, offset)
                if isinstance(descriptor, layout.Boolean64):
                    _require(value in (0, 1), "logical_shape", "Invalid Boolean value.")
                    return bool(value)
                if isinstance(descriptor, layout.ExactNumber):
                    _require(
                        value == descriptor.value,
                        "logical_shape",
                        "Invalid fixed number.",
                    )
                if isinstance(descriptor, layout.EndFrom):
                    value += cast(int, previous[descriptor.prior_name])
                    _require(
                        value <= 1 << 64,
                        "logical_shape",
                        "An endpoint exceeds unsigned range.",
                    )
                return value
        raise TypeError("Invalid installed descriptor.")

    def decode_row(self, tag: int, index: int, depth: int) -> LogicalValue:
        self.budget.depth(depth)
        row = self.row_span(tag, index)
        output: dict[str, LogicalValue] = {}
        for spec in self.definition.field_specs[tag - 1]:
            self.budget.scan(len(spec.logical_name))
            output[spec.logical_name] = self.value(
                spec.descriptor,
                row,
                spec.offset,
                output,
                depth + 1,
                tag,
                spec.logical_name,
            )
        kind = self.definition.tables[tag - 1].record_kind
        if kind == "scalar":
            return output["value"]
        if kind == "pair":
            return tuple(output.values())
        assert kind == "object"
        return LogicalObject(tuple(sorted(output.items())))

    def root(self) -> LogicalObject:
        self.claim(47, 0, 1, record=True)
        root = self.decode_row(47, 0, 1)
        assert type(root) is LogicalObject
        for table in self.directory.tables:
            _require(
                self.state.cursors[table.tag - 1] == table.count,
                "table_bounds",
                "A table has unconsumed logical storage.",
            )
        return root


def _peek_lower_limits(
    raw: bytes,
    directory: DirectoryView,
    definition: layout.LayoutDefinition,
    budget: WorkBudget,
) -> _Lower:
    view = memoryview(raw)

    def row(tag: int, index: int) -> tuple[int, int]:
        table = directory.tables[tag - 1]
        _require(
            0 <= index < table.count,
            "table_bounds",
            "A limit reference is outside its table.",
        )
        start = table.file_offset + index * table.element_bytes
        return start, start + table.element_bytes

    def reference(parent: tuple[int, int], offset: int, target: int) -> tuple[int, int]:
        begin = _cell(view, *parent, parent[0] + offset, 4, budget)
        count = _cell(view, *parent, parent[0] + offset + 4, 4, budget)
        table = directory.tables[target - 1]
        _require(
            begin <= table.count and count <= table.count - begin,
            "table_bounds",
            "A limit slice is outside its table.",
        )
        _require(count == 1, "logical_shape", "A limit reference needs one row.")
        return row(target, begin)

    root = row(47, 0)
    transport = reference(root, 104, 11)
    plan = reference(root, 16, 20)
    trace = reference(plan, 32, 12)
    scope = reference(root, 88, 44)
    capture = reference(scope, 88, 13)
    results = []
    for span, tag, maxima in (
        (transport, 11, layout.TRANSPORT_MAXIMA),
        (trace, 12, layout.TRACE_MAXIMA),
        (capture, 13, layout.CAPTURE_MAXIMA),
    ):
        values = {}
        for spec, (name, maximum) in zip(
            definition.field_specs[tag - 1], maxima, strict=True
        ):
            assert spec.logical_name == name
            value = _cell(view, *span, span[0] + spec.offset, 8, budget)
            _require(
                0 < value <= maximum and (name != "snapshot_bytes" or value == 8),
                "input_limit",
                "A retained limit is outside its installed bounds.",
            )
            values[name] = value
        results.append(MappingProxyType(values))
    return _Lower(results[0], results[1], results[2])


def _get(record: LogicalValue, name: str, budget: WorkBudget) -> LogicalValue:
    assert type(record) is LogicalObject
    for key, value in record.entries:
        budget.scan(len(key))
        if key == name:
            return value
    raise KeyError(name)


def _check_retained_limits(
    root: LogicalObject, lower: _Lower, budget: WorkBudget
) -> None:
    original = _get(root, "original", budget)
    size = cast(int, _get(original, "bytes", budget))
    budget.scalar()
    _require(
        size <= lower.transport["original_bytes"],
        "input_limit",
        "The original byte cap is exceeded.",
    )
    scope = _get(root, "scope", budget)
    guards = cast(tuple[LogicalValue, ...], _get(scope, "guard_instructions", budget))
    guard_map: dict[int, tuple[int, int]] = {}
    for guard in guards:
        address = cast(int, _get(guard, "address", budget))
        owner = cast(int, _get(guard, "owner", budget))
        witness = cast(str, _get(guard, "witness_hex", budget))
        budget.scalar(2)
        _require(
            address not in guard_map, "logical_shape", "A guard address is ambiguous."
        )
        guard_map[address] = (owner, len(witness) // 2)
    routes = cast(tuple[LogicalValue, ...], _get(scope, "routes", budget))
    for route in routes:
        entries = cast(tuple[int, ...], _get(route, "entries", budget))
        path = cast(tuple[int, ...], _get(route, "instruction_path", budget))
        cursor = 0
        for entry in entries:
            budget.scalar()
            _require(
                cursor < len(path) and path[cursor] == entry,
                "logical_shape",
                "A route owner group does not start at its entry.",
            )
            count = byte_count = last_size = 0
            while cursor < len(path):
                budget.scalar()
                guard = guard_map.get(path[cursor])
                _require(
                    guard is not None, "logical_shape", "A route position has no guard."
                )
                assert guard is not None
                if guard[0] != entry:
                    break
                count += 1
                last_size = guard[1]
                byte_count += last_size
                cursor += 1
                _require(
                    count - 1 <= lower.capture["thunk_neutral_instructions"],
                    "input_limit",
                    "The neutral instruction cap is exceeded.",
                )
            _require(count > 0, "logical_shape", "A route owner group is empty.")
            _require(
                byte_count - last_size <= lower.capture["thunk_neutral_bytes"],
                "input_limit",
                "The neutral byte cap is exceeded.",
            )
        _require(
            cursor == len(path), "logical_shape", "A route path has no owner group."
        )


def _canonical_bytes(root: LogicalObject, lower: _Lower, budget: WorkBudget) -> bytes:
    output = bytearray()
    active: list[tuple[int, int]] = []
    cap = min(budget.limits.logical_data_bytes, lower.transport["data_bytes"])

    def append(token: str) -> None:
        count = len(token)
        _require(
            count + 1 <= cap - len(output),
            "record_limit",
            "The logical byte cap is exceeded.",
        )
        for begin, maximum in active:
            _require(
                len(output) - begin + count + 1 <= maximum,
                "record_limit",
                "A subtree byte cap is exceeded.",
            )
        budget.scan(count * 2)
        output.extend(token.encode("ascii"))

    def string(value: str) -> None:
        append('"')
        for character in value:
            budget.scan(16)
            append(json.dumps(character, ensure_ascii=True)[1:-1])
        append('"')

    def visit(value: LogicalValue, depth: int, subtree: int | None = None) -> None:
        budget.depth(depth)
        budget.scalar()
        if subtree is not None:
            active.append((len(output), subtree))
        if type(value) is LogicalObject:
            append("{")
            for i, (key, child) in enumerate(value.entries):
                if i:
                    append(",")
                string(key)
                append(":")
                bound = None
                if value is root and key in ("full_plan", "scope"):
                    bound = lower.capture[
                        "full_plan_bytes" if key == "full_plan" else "scope_bytes"
                    ]
                visit(child, depth + 1, bound)
            append("}")
        elif type(value) is tuple:
            append("[")
            for i, child in enumerate(value):
                if i:
                    append(",")
                visit(child, depth + 1)
            append("]")
        elif type(value) is str:
            string(value)
        elif value is None:
            append("null")
        elif type(value) is bool:
            append("true" if value else "false")
        elif type(value) is int:
            budget.scan(21)
            append(str(value))
        else:
            raise TypeError("Invalid internal logical value.")
        if subtree is not None:
            active.pop()

    visit(root, 1)
    _require(len(output) < cap, "record_limit", "No space remains for the final LF.")
    budget.scan(1)
    output.append(10)
    budget.scan(len(output))
    return bytes(output)


def _compare_complete(
    actual: bytes,
    expected: ExpectedCollector,
    directory: DirectoryView,
    budget: WorkBudget,
) -> str:
    budget.scan(max(len(actual), len(expected.logical_raw)))
    _require(
        actual == expected.logical_raw,
        "logical_mismatch",
        "The complete logical bytes differ.",
    )
    budget.scan(len(actual))
    digest = sha256(actual).digest()
    budget.scan(32)
    _require(
        digest == directory.data_digest,
        "logical_mismatch",
        "The directory data digest differs.",
    )
    for text, stored in (
        (expected.renderer_sha256, directory.renderer_digest),
        (expected.native_source_sha256, directory.native_digest),
    ):
        budget.scan(64 + 32 + 32)
        _require(
            bytes.fromhex(text) == stored,
            "source_identity",
            "A directory source identity differs.",
        )
    budget.scan(32 + 64)
    return digest.hex()


def _readback(
    plugin_raw: bytes,
    *,
    expected: ExpectedCollector,
    profile: layout.ProfileId,
    limits: elf_module.InspectionLimits = elf_module.InspectionLimits(),
) -> LogicalReadback | elf_module.InspectionRejected:
    try:
        checked, definition, budget = _checked_inputs(
            plugin_raw, expected, profile, limits
        )
        view = _read_elf(plugin_raw, definition, budget)
        _debit_u1(view, budget)
        indexes = _index_view(view, definition, budget)
        witness = _check_witness(view, indexes, definition, budget)
        directory = _read_directory(view, indexes, definition, budget)
        lower = _peek_lower_limits(plugin_raw, directory, definition, budget)
        decoder = _Decoder(
            memoryview(plugin_raw), definition, directory, budget, CursorState(), lower
        )
        root = decoder.root()
        _check_retained_limits(root, lower, budget)
        actual = _canonical_bytes(root, lower, budget)
        digest = _compare_complete(actual, checked, directory, budget)
        return LogicalReadback(
            actual,
            digest,
            directory,
            witness,
            view,
            budget.limits,
            WorkUsage(budget.scanned, budget.scalars),
        )
    except _DecodeRefusal as refusal:
        return refusal.result
