"""Read the test-only collector ELF contract from immutable bytes.

A result proves bounded representation consistency only. It grants no layout,
build, cache, or runtime authority. No code from the input is loaded or executed.
"""

from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, fields
from struct import Struct
from typing import Literal, NewType, NoReturn

FileOffset = NewType("FileOffset", int)
ElfVa = NewType("ElfVa", int)
Machine = Literal[62, 183]
InspectionReason = Literal[
    "input_type",
    "input_limit",
    "unsupported_elf",
    "malformed_elf",
    "ambiguous_mapping",
    "symbol_missing",
    "symbol_ambiguous",
    "export_contract",
    "dynamic_contract",
    "relocation_contract",
    "layout_mismatch",
    "directory_contract",
    "storage_overlap",
    "table_bounds",
    "logical_shape",
    "logical_mismatch",
    "source_identity",
    "work_limit",
    "record_limit",
]


@dataclass(frozen=True, slots=True)
class InspectionLimits:
    plugin_bytes: int = 33554432
    program_headers: int = 1024
    sections: int = 4096
    symbols: int = 131072
    string_table_bytes: int = 4194304
    symbol_name_bytes: int = 4096
    dynamic_entries: int = 4096
    relocations: int = 262144
    hash_words: int = 262144
    physical_data_bytes: int = 33554432
    logical_data_bytes: int = 16777216
    nonbyte_rows: int = 4194304
    scalar_visits: int = 8388608
    scanned_bytes: int = 268435456
    nesting: int = 32
    inspection_bytes: int = 65536


@dataclass(frozen=True, slots=True)
class InspectionRejected:
    reason: InspectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class ElfHeader:
    osabi: int
    machine: Machine
    phoff: FileOffset
    shoff: FileOffset
    phnum: int
    shnum: int
    shstrndx: int


@dataclass(frozen=True, slots=True)
class ProgramHeader:
    index: int
    type: int
    flags: int
    offset: FileOffset
    va: ElfVa
    physical_address: int
    filesz: int
    memsz: int
    align: int


@dataclass(frozen=True, slots=True)
class LoadSpan:
    index: int
    flags: int
    offset: FileOffset
    va: ElfVa
    filesz: int
    memsz: int
    align: int


@dataclass(frozen=True, slots=True)
class Section:
    index: int
    name: bytes
    type: int
    flags: int
    va: ElfVa
    offset: FileOffset
    size: int
    link: int
    info: int
    align: int
    entsize: int


@dataclass(frozen=True, slots=True)
class Symbol:
    table_section: int
    index: int
    name: bytes
    binding: int
    type: int
    visibility: int
    section_index: int
    va: ElfVa
    bytes: int
    version_index: int | None


@dataclass(frozen=True, slots=True)
class DynamicEntry:
    index: int
    tag: int
    value: int


@dataclass(frozen=True, slots=True)
class Rela:
    table_section: int
    index: int
    file_offset: FileOffset
    place_va: ElfVa
    type: int
    symbol_index: int
    addend: int
    width: Literal[8] = 8


@dataclass(frozen=True, slots=True)
class Export:
    name: str
    dynamic_symbol_index: int
    static_symbol_index: int
    section_index: int
    va: ElfVa
    file_offset: FileOffset
    bytes: int
    binding: int
    type: int
    visibility: int


@dataclass(frozen=True, slots=True)
class CollectorElf:
    raw: bytes
    machine: Machine
    loads: tuple[LoadSpan, ...]
    sections: tuple[Section, ...]
    symbols: tuple[Symbol, ...]
    dynamic: tuple[DynamicEntry, ...]
    relocations: tuple[Rela, ...]
    needed: tuple[bytes, ...]
    exports: tuple[Export, ...]
    header: ElfHeader
    programs: tuple[ProgramHeader, ...]


# These are fixed physical contracts, not a logical decoder or layout approval.
_TABLES: tuple[tuple[bytes, int], ...] = (
    (b"bytes", 1),
    (b"uints", 8),
    (b"strings", 8),
    (b"registers", 16),
    (b"plan_gaps", 16),
    (b"positions", 16),
    (b"dispositions", 40),
    (b"dynamic", 24),
    (b"original", 16),
    (b"geometry", 32),
    (b"transport_limits", 88),
    (b"trace_limits", 48),
    (b"capture_limits", 112),
    (b"import_id", 48),
    (b"import_binding", 152),
    (b"call", 40),
    (b"jump", 8),
    (b"return", 8),
    (b"trace_site", 72),
    (b"trace_plan", 72),
    (b"lift_main", 24),
    (b"explicit_entry", 16),
    (b"requested_scope", 48),
    (b"user", 16),
    (b"transit", 16),
    (b"omitted", 16),
    (b"omitted_site", 40),
    (b"transit_route", 56),
    (b"ordinary", 16),
    (b"local_direct", 16),
    (b"local_conditional", 24),
    (b"planned_roles", 48),
    (b"transit_instruction", 16),
    (b"reject", 16),
    (b"guard_instruction", 88),
    (b"dormant_outside_window", 16),
    (b"guard_reject", 16),
    (b"local_branch_guard", 40),
    (b"metadata_only", 16),
    (b"gap_record", 88),
    (b"exit_from_supported_bits", 24),
    (b"exact_signal", 8),
    (b"termination_contract", 128),
    (b"scope_selection", 184),
    (b"load_segment", 56),
    (b"elf_image", 32),
    (b"collector_data", 112),
)
_EXPORTS = (
    (b"phoenix_collector_data_v1", 1, 2728),
    (b"phoenix_collector_layout_v1", 1, 40168),
    (b"qemu_plugin_install", 2, None),
    (b"qemu_plugin_version", 1, 4),
)
# Test-only candidates. ADR0041 records the missing Linux approval gate.
_PAGE_GRANULES = (4096, 16384, 65536)
_U64_END = 1 << 64
_EHDR = Struct("<16sHHIQQQIHHHHHH")
_PHDR = Struct("<IIQQQQQQ")
_SHDR = Struct("<IIQQQQIIQQ")
_SYM = Struct("<IBBHQQ")
_DYN = Struct("<qQ")
_RELA = Struct("<QQq")
_U16 = Struct("<H")
_DIR = Struct("<QQQQQQQ")


class _Refusal(Exception):
    def __init__(self, reason: InspectionReason, detail: str):
        self.result = InspectionRejected(reason, detail)


def _fail(reason: InspectionReason, detail: str) -> NoReturn:
    raise _Refusal(reason, detail)


def _require(ok: bool, reason: InspectionReason, detail: str) -> None:
    if not ok:
        _fail(reason, detail)


def _end(start: int, size: int, reason: InspectionReason = "malformed_elf") -> int:
    _require(
        0 <= start < _U64_END and 0 <= size < _U64_END,
        reason,
        "Invalid unsigned range.",
    )
    end = start + size
    _require(end <= _U64_END, reason, "The unsigned range overflows.")
    return end


def _power(value: int) -> bool:
    return value == 0 or value & (value - 1) == 0


def _disjoint(spans: list[tuple[int, int]], reason: InspectionReason) -> None:
    previous = 0
    for start, end in sorted((a, b) for a, b in spans if a < b):
        _require(start >= previous, reason, "Positive-length ranges overlap.")
        previous = end


@dataclass(slots=True)
class _Budget:
    limits: InspectionLimits
    scanned: int = 0
    scalars: int = 0

    def scan(self, amount: int) -> None:
        _require(
            amount <= self.limits.scanned_bytes - self.scanned,
            "work_limit",
            "The byte-scan limit is exceeded.",
        )
        self.scanned += amount

    def scalar(self, amount: int) -> None:
        _require(
            amount <= self.limits.scalar_visits - self.scalars,
            "work_limit",
            "The scalar-visit limit is exceeded.",
        )
        self.scalars += amount


class _Strings:
    def __init__(self, raw: memoryview, budget: _Budget):
        _require(
            0 < len(raw) <= budget.limits.string_table_bytes,
            "input_limit",
            "Invalid string-table size.",
        )
        budget.scan(len(raw))
        _require(
            raw[0] == raw[-1] == 0,
            "malformed_elf",
            "A string table must start and end with NUL.",
        )
        self.raw = raw
        self.budget = budget
        self.nuls = array("I", (i for i, byte in enumerate(raw) if byte == 0))

    def name(self, offset: int) -> bytes:
        _require(
            0 <= offset < len(self.raw),
            "malformed_elf",
            "A string offset is outside its table.",
        )
        end = self.nuls[bisect_left(self.nuls, offset)]
        size = end - offset
        _require(
            size <= self.budget.limits.symbol_name_bytes,
            "input_limit",
            "A name exceeds its byte limit.",
        )
        self.budget.scan(size * 2)
        return bytes(self.raw[offset:end])


@dataclass(frozen=True, slots=True)
class _MappedInterval:
    start: int
    end: int
    file_bias: int | None
    executable: bool
    zero_fill: bool


@dataclass(frozen=True, slots=True)
class _PageMap:
    intervals: tuple[_MappedInterval, ...]
    starts: tuple[int, ...]

    def check(self, va: int, offset: int, size: int, executable: bool) -> None:
        current, end = va, va + size
        i = bisect_right(self.starts, current) - 1
        while current < end:
            _require(
                0 <= i < len(self.intervals),
                "ambiguous_mapping",
                "A rounded mapping is missing.",
            )
            interval = self.intervals[i]
            _require(
                interval.start <= current < interval.end,
                "ambiguous_mapping",
                "A rounded mapping has a hole.",
            )
            _require(
                not interval.zero_fill,
                "ambiguous_mapping",
                "A page mapping can zero consumed bytes.",
            )
            _require(
                interval.file_bias == offset - va,
                "ambiguous_mapping",
                "Rounded load mappings disagree on file bytes.",
            )
            _require(
                executable or not interval.executable,
                "ambiguous_mapping",
                "A rounded executable mapping covers data.",
            )
            current = min(end, interval.end)
            i += 1


def _page_map(loads: list[LoadSpan], granule: int) -> _PageMap:
    # Sweep once. Section queries then visit only intersecting intervals.
    events: list[tuple[int, int | None, int, int, int]] = []
    for load in loads:
        if not load.memsz:
            continue
        start = load.va // granule * granule
        end = (load.va + load.memsz + granule - 1) // granule * granule
        if load.filesz:
            file_end = (load.va + load.filesz + granule - 1) // granule * granule
            bias = load.offset - load.va
            execute = int(bool(load.flags & 1))
            events.extend(
                ((start, bias, execute, 0, 1), (file_end, bias, execute, 0, -1))
            )
        if load.memsz > load.filesz:
            zero_start = load.va + load.filesz if load.filesz else start
            events.extend(((zero_start, None, 0, 1, 1), (end, None, 0, 1, -1)))
    events.sort(key=lambda event: event[0])
    active: dict[int, int] = {}
    execute_count = zero_count = previous = 0
    intervals: list[_MappedInterval] = []
    for position, event_bias, execute, zero, change in events:
        if position > previous and (active or zero_count):
            intervals.append(
                _MappedInterval(
                    previous,
                    position,
                    next(iter(active)) if len(active) == 1 else None,
                    bool(execute_count),
                    bool(zero_count),
                )
            )
        if event_bias is not None:
            count = active.get(event_bias, 0) + change
            if count:
                active[event_bias] = count
            else:
                del active[event_bias]
        execute_count += execute * change
        zero_count += zero * change
        previous = position
    return _PageMap(tuple(intervals), tuple(interval.start for interval in intervals))


class _Reader:
    def __init__(self, raw: bytes, machine: Machine, limits: InspectionLimits):
        self.raw = raw
        self.view = memoryview(raw)
        self.machine = machine
        self.limits = limits
        self.budget = _Budget(limits)
        self.loads: list[LoadSpan] = []
        self.programs: list[ProgramHeader] = []
        self.sections: list[Section] = []
        self.strings: dict[int, _Strings] = {}
        self.load_starts: list[int] = []
        self.page_maps: tuple[_PageMap, ...] = ()
        self.sorted_loads: list[LoadSpan] = []
        self.dynamic: list[DynamicEntry] = []
        self.tags: dict[int, int] = {}
        self.needed: list[bytes] = []
        self.symbols: list[Symbol] = []
        self.symbol_tables: dict[int, list[Symbol]] = {}
        self.names: dict[int, dict[bytes, list[Symbol]]] = {}
        self.relocations: list[Rela] = []
        self.relocation_map: dict[int, Rela] = {}
        self.exports: list[Export] = []
        self.metadata: list[tuple[int, int]] = []
        self.relro: ProgramHeader | None = None

    def span(self, offset: int, size: int) -> memoryview:
        end = _end(offset, size)
        _require(end <= len(self.raw), "malformed_elf", "A file span is truncated.")
        return self.view[offset:end]

    def unpack(self, layout: Struct, offset: int) -> tuple[int, ...]:
        self.span(offset, layout.size)
        self.budget.scan(layout.size)
        self.budget.scalar(
            {
                "<IIQQQQQQ": 8,
                "<IIQQQQIIQQ": 10,
                "<IBBHQQ": 6,
                "<qQ": 2,
                "<QQq": 3,
                "<H": 1,
                "<I": 1,
                "<II": 2,
                "<QQQQQQQ": 7,
            }[layout.format]
        )
        # Every format used here contains integers only. EHDR is read separately.
        values: tuple[int, ...] = layout.unpack_from(self.view, offset)
        return values

    def file_span(self, va: int, size: int) -> tuple[FileOffset, LoadSpan]:
        end = _end(va, size, "ambiguous_mapping")
        i = bisect_right(self.load_starts, va) - 1
        _require(i >= 0, "ambiguous_mapping", "A range has no load mapping.")
        load = self.sorted_loads[i]
        _require(
            size > 0 and load.va <= va < end <= load.va + load.filesz,
            "ambiguous_mapping",
            "A range is not wholly file-backed.",
        )
        _require(
            bool(load.flags & 4), "ambiguous_mapping", "A mapping is not readable."
        )
        return FileOffset(load.offset + va - load.va), load

    def page_mapping(self, va: int, offset: int, size: int, executable: bool) -> None:
        for page_map in self.page_maps:
            page_map.check(va, offset, size, executable)

    def string_table(self, index: int) -> _Strings:
        if index not in self.strings:
            section = self.sections[index]
            _require(
                section.type == 3 and not section.flags & 0xC00,
                "malformed_elf",
                "Invalid consumed string table.",
            )
            self.strings[index] = _Strings(
                self.span(section.offset, section.size), self.budget
            )
        return self.strings[index]

    def envelope(self) -> ElfHeader:
        self.span(0, 64)
        self.budget.scan(64)
        self.budget.scalar(14)
        (
            ident,
            kind,
            machine,
            version,
            entry,
            phoff,
            shoff,
            flags,
            ehsize,
            phentsize,
            phnum,
            shentsize,
            shnum,
            shstrndx,
        ) = _EHDR.unpack_from(self.view)
        _require(
            ident[:7] == b"\x7fELF\x02\x01\x01"
            and ident[7] in (0, 3)
            and ident[8:] == bytes(8),
            "unsupported_elf",
            "Unsupported ELF identity.",
        )
        _require(
            kind == 3
            and machine == self.machine
            and version == 1
            and entry == 0
            and flags == 0,
            "unsupported_elf",
            "Unsupported ELF type, machine, entry, version, or flags.",
        )
        _require(
            ehsize == 64 and phentsize == 56 and shentsize == 64,
            "malformed_elf",
            "Invalid ELF table entry size.",
        )
        _require(
            0 < phnum < 65535 and 0 < shnum < 0xFF00 and 0 < shstrndx < shnum,
            "unsupported_elf",
            "Missing or extended ELF table numbering.",
        )
        _require(
            phnum <= self.limits.program_headers and shnum <= self.limits.sections,
            "input_limit",
            "An ELF table count exceeds its limit.",
        )
        self.span(phoff, phnum * 56)
        self.span(shoff, shnum * 64)
        _require(
            phoff % 8 == shoff % 8 == 0,
            "malformed_elf",
            "An ELF metadata table is not aligned.",
        )
        self.metadata = [
            (0, 64),
            (phoff, phoff + phnum * 56),
            (shoff, shoff + shnum * 64),
        ]
        _disjoint(self.metadata, "storage_overlap")
        for i in range(phnum):
            t, f, off, va, pa, fs, ms, align = self.unpack(_PHDR, phoff + i * 56)
            self.span(off, fs)
            _end(va, ms)
            _require(
                fs <= ms and _power(align),
                "malformed_elf",
                "Invalid program size or alignment.",
            )
            _require(t != 3, "unsupported_elf", "PT_INTERP is not permitted.")
            program = ProgramHeader(
                i, t, f, FileOffset(off), ElfVa(va), pa, fs, ms, align
            )
            self.programs.append(program)
            if t == 1:
                _require(
                    f & ~7 == 0 and (align <= 1 or va % align == off % align),
                    "malformed_elf",
                    "Invalid load flags or congruence.",
                )
                self.loads.append(
                    LoadSpan(i, f, FileOffset(off), ElfVa(va), fs, ms, align)
                )
            if t == 0x6474E552:
                _require(
                    self.relro is None and ms > 0,
                    "ambiguous_mapping",
                    "Duplicate or empty RELRO segment.",
                )
                self.relro = program
        _require(bool(self.loads), "ambiguous_mapping", "There is no load segment.")
        _disjoint([(p.va, p.va + p.memsz) for p in self.loads], "ambiguous_mapping")
        _disjoint(
            [(p.offset, p.offset + p.filesz) for p in self.loads], "ambiguous_mapping"
        )
        for load in self.loads:
            _require(
                all(load.va % g == load.offset % g for g in _PAGE_GRANULES),
                "ambiguous_mapping",
                "A load is not congruent for a candidate granule.",
            )
        self.sorted_loads = sorted(
            (p for p in self.loads if p.memsz), key=lambda p: p.va
        )
        self.load_starts = [p.va for p in self.sorted_loads]
        self.page_maps = tuple(_page_map(self.loads, g) for g in _PAGE_GRANULES)
        headers: list[tuple[int, ...]] = []
        for i in range(shnum):
            row = self.unpack(_SHDR, shoff + i * 64)
            name, t, f, va, off, size, link, info, align, entsize = row
            _require(
                link < shnum and _power(align),
                "malformed_elf",
                "Invalid section link or alignment.",
            )
            _end(va, size)
            if t != 8:
                self.span(off, size)
            _require(
                entsize == 0 or size % entsize == 0,
                "malformed_elf",
                "A section has a partial entry.",
            )
            _require(
                align <= 1 or (off % align == 0 and (not f & 2 or va % align == 0)),
                "malformed_elf",
                "A section is not aligned.",
            )
            if f & 0x40:
                _require(info < shnum, "malformed_elf", "Invalid section info link.")
            if i == 0:
                _require(not any(row), "unsupported_elf", "Section zero is not empty.")
            elif t == 0:
                _fail("unsupported_elf", "Extra null sections are not supported.")
            headers.append(row)
        _disjoint(
            self.metadata + [(r[4], r[4] + r[5]) for r in headers[1:] if r[1] != 8],
            "storage_overlap",
        )
        _disjoint(
            [(r[3], r[3] + r[5]) for r in headers if r[2] & 2], "ambiguous_mapping"
        )
        names = headers[shstrndx]
        _require(
            names[1] == 3 and not names[2] & 0xC00,
            "malformed_elf",
            "Invalid section-name table.",
        )
        name_table = _Strings(self.span(names[4], names[5]), self.budget)
        self.strings[shstrndx] = name_table
        for i, row in enumerate(headers):
            n, t, f, va, off, size, link, info, align, entsize = row
            section = Section(
                i,
                name_table.name(n),
                t,
                f,
                ElfVa(va),
                FileOffset(off),
                size,
                link,
                info,
                align,
                entsize,
            )
            self.sections.append(section)
            if f & 2 and t != 8 and size:
                mapped, _ = self.file_span(va, size)
                self.page_mapping(va, off, size, bool(f & 4))
                _require(
                    mapped == off,
                    "ambiguous_mapping",
                    "Section and load file offsets differ.",
                )
        if self.relro is not None:
            offset, load = self.file_span(self.relro.va, self.relro.filesz)
            _require(
                offset == self.relro.offset
                and self.relro.filesz == self.relro.memsz
                and load.flags & 2 != 0
                and load.flags & 1 == 0,
                "ambiguous_mapping",
                "RELRO does not match writable data.",
            )
        return ElfHeader(
            ident[7],
            self.machine,
            FileOffset(phoff),
            FileOffset(shoff),
            phnum,
            shnum,
            shstrndx,
        )

    def one_section(self, kind: int, reason: InspectionReason) -> Section:
        matches = [s for s in self.sections if s.type == kind]
        _require(
            len(matches) == 1, reason, "A required section is missing or duplicated."
        )
        return matches[0]

    def consumed(self, section: Section) -> None:
        _require(
            section.size > 0 and section.flags & 2 != 0 and section.flags & 0xC04 == 0,
            "malformed_elf",
            "Invalid consumed section flags or size.",
        )
        off, load = self.file_span(section.va, section.size)
        _require(
            off == section.offset and load.flags & 1 == 0,
            "ambiguous_mapping",
            "Invalid consumed data mapping.",
        )

    def dynamic_metadata(self) -> tuple[Section, Section]:
        dynsym = self.one_section(11, "dynamic_contract")
        symtab = self.one_section(2, "symbol_missing")
        dynamic = self.one_section(6, "dynamic_contract")
        self.consumed(dynamic)
        self.consumed(dynsym)
        _require(
            dynamic.entsize == 16 and dynsym.entsize == symtab.entsize == 24,
            "malformed_elf",
            "Invalid dynamic or symbol entry size.",
        )
        programs = [p for p in self.programs if p.type == 2]
        _require(len(programs) == 1, "dynamic_contract", "PT_DYNAMIC is not unique.")
        p = programs[0]
        _require(
            (p.offset, p.va, p.filesz, p.memsz)
            == (dynamic.offset, dynamic.va, dynamic.size, dynamic.size),
            "dynamic_contract",
            "PT_DYNAMIC and its section differ.",
        )
        _require(
            dynamic.size // 16 <= self.limits.dynamic_entries,
            "input_limit",
            "The dynamic entry limit is exceeded.",
        )
        _require(
            dynamic.link == dynsym.link,
            "dynamic_contract",
            "Dynamic and symbol string tables differ.",
        )
        counts = [s.size // 24 for s in (dynsym, symtab)]
        _require(
            all(0 < n <= 65536 for n in counts) and sum(counts) <= self.limits.symbols,
            "input_limit",
            "The symbol count exceeds its limit.",
        )
        strings = self.string_table(dynsym.link)
        self.consumed(self.sections[dynsym.link])
        # REL, RELR, text relocations, GNU hashing, and Android packed forms.
        forbidden = {
            17,
            18,
            19,
            22,
            35,
            36,
            37,
            0x6FFFFEF5,
            0x6000000F,
            0x60000010,
            0x60000011,
            0x60000012,
            0x6FFFE000,
            0x6FFFE001,
            0x6FFFE003,
            0x6FFFFFFA,
            0x6FFFFEF8,
            0x6FFFFDF6,
            15,
            29,
        }
        terminated = False
        for i in range(dynamic.size // 16):
            tag, value = self.unpack(_DYN, dynamic.offset + i * 16)
            self.dynamic.append(DynamicEntry(i, tag, value))
            if terminated or tag == 0:
                _require(tag == value == 0, "dynamic_contract", "Invalid DT_NULL tail.")
                terminated = True
                continue
            _require(tag not in forbidden, "dynamic_contract", "Forbidden dynamic tag.")
            if tag == 1:
                name = strings.name(value)
                _require(bool(name), "dynamic_contract", "Empty dependency name.")
                self.needed.append(name)
            else:
                _require(
                    tag not in self.tags,
                    "dynamic_contract",
                    "A singleton dynamic tag is duplicated.",
                )
                self.tags[tag] = value
        _require(terminated, "dynamic_contract", "DT_NULL is missing.")
        for tag, expected in (
            (5, self.sections[dynsym.link].va),
            (10, self.sections[dynsym.link].size),
            (6, dynsym.va),
            (11, 24),
        ):
            _require(
                self.tags.get(tag) == expected,
                "dynamic_contract",
                "Dynamic symbol or string metadata differs.",
            )
        _require(
            not self.tags.get(30, 0) & 4,
            "dynamic_contract",
            "DF_TEXTREL is not permitted.",
        )
        _require(
            24 in self.tags
            or bool(self.tags.get(30, 0) & 8)
            or bool(self.tags.get(0x6FFFFFFB, 0) & 1),
            "dynamic_contract",
            "Immediate binding is required.",
        )
        _require(
            24 not in self.tags or self.tags[24] == 0,
            "dynamic_contract",
            "Invalid DT_BIND_NOW value.",
        )
        for tag in (14, 0x7FFFFFFD, 0x7FFFFFFF):
            if tag in self.tags:
                strings.name(self.tags[tag])
        return dynsym, symtab

    def read_symbols(self, dynsym: Section, symtab: Section) -> None:
        counts = [s.size // 24 for s in (dynsym, symtab)]
        _require(
            all(0 < n <= 65536 for n in counts) and sum(counts) <= self.limits.symbols,
            "input_limit",
            "The symbol count exceeds its limit.",
        )
        versions = [s for s in self.sections if s.type == 0x6FFFFFFF]
        _require(len(versions) <= 1, "dynamic_contract", "Duplicate version arrays.")
        version: Section | None = versions[0] if versions else None
        if version is None:
            _require(
                0x6FFFFFF0 not in self.tags,
                "dynamic_contract",
                "DT_VERSYM has no section.",
            )
        else:
            self.consumed(version)
            _require(
                version.link == dynsym.index
                and version.entsize == 2
                and version.size == counts[0] * 2
                and self.tags.get(0x6FFFFFF0) == version.va,
                "dynamic_contract",
                "Version array metadata differs.",
            )
        for table in sorted((dynsym, symtab), key=lambda s: s.index):
            _require(
                not table.flags & 0xC00 and table.info <= table.size // 24,
                "malformed_elf",
                "Invalid symbol table flags or local boundary.",
            )
            names = self.string_table(table.link)
            rows: list[Symbol] = []
            index: dict[bytes, list[Symbol]] = {}
            for i in range(table.size // 24):
                n, info, other, section, va, size = self.unpack(
                    _SYM, table.offset + i * 24
                )
                _end(va, size)
                _require(
                    other & ~3 == 0
                    and (section < len(self.sections) or section in (0xFFF1, 0xFFF2)),
                    "malformed_elf",
                    "Invalid symbol visibility or section index.",
                )
                _require(
                    (info >> 4 == 0) == (i < table.info),
                    "malformed_elf",
                    "The symbol local boundary differs.",
                )
                _require(info & 15 != 10, "export_contract", "IFUNC is not permitted.")
                vi = (
                    self.unpack(_U16, version.offset + i * 2)[0]
                    if table == dynsym and version is not None
                    else None
                )
                name = names.name(n)
                symbol = Symbol(
                    table.index,
                    i,
                    name,
                    info >> 4,
                    info & 15,
                    other,
                    section,
                    ElfVa(va),
                    size,
                    vi,
                )
                if i == 0:
                    _require(
                        (n, info, other, section, va, size) == (0, 0, 0, 0, 0, 0)
                        and vi in (None, 0),
                        "malformed_elf",
                        "The null symbol is not empty.",
                    )
                rows.append(symbol)
                index.setdefault(name, []).append(symbol)
                self.symbols.append(symbol)
            self.symbol_tables[table.index] = rows
            self.names[table.index] = index

    def hash_table(self, dynsym: Section) -> None:
        section = self.one_section(5, "dynamic_contract")
        self.consumed(section)
        _require(
            section.link == dynsym.index
            and section.entsize == 4
            and self.tags.get(4) == section.va
            and section.size >= 8,
            "dynamic_contract",
            "SysV hash metadata differs.",
        )
        buckets, chains = self.unpack(Struct("<II"), section.offset)
        _require(
            buckets > 0 and chains == len(self.symbol_tables[dynsym.index]),
            "dynamic_contract",
            "Invalid SysV hash dimensions.",
        )
        words = 2 + buckets + chains
        _require(
            words <= self.limits.hash_words,
            "input_limit",
            "The SysV hash word limit is exceeded.",
        )
        _require(
            words * 4 == section.size, "dynamic_contract", "The SysV hash size differs."
        )
        self.budget.scan((buckets + chains) * 8)
        self.budget.scalar(buckets + chains)
        values = tuple(
            v[0]
            for v in Struct("<I").iter_unpack(
                self.span(section.offset + 8, (buckets + chains) * 4)
            )
        )
        heads, links = values[:buckets], values[buckets:]
        _require(
            all(v < chains for v in values) and links[0] == 0,
            "dynamic_contract",
            "A SysV hash index is invalid.",
        )
        rows = self.symbol_tables[dynsym.index]
        seen: set[int] = set()
        for bucket, head in enumerate(heads):
            current = head
            while current:
                _require(
                    current not in seen,
                    "dynamic_contract",
                    "A SysV chain cycles or shares a symbol.",
                )
                seen.add(current)
                name = rows[current].name
                self.budget.scan(len(name))
                value = 0
                for byte in name:
                    value = (value << 4) + byte
                    high = value & 0xF0000000
                    value ^= high >> 24
                    value &= ~high
                _require(
                    value % buckets == bucket,
                    "dynamic_contract",
                    "A symbol belongs to another SysV bucket.",
                )
                current = links[current]
        _require(
            seen == set(range(1, chains)),
            "dynamic_contract",
            "A dynamic symbol is unreachable through SysV hashing.",
        )

    def named(self, table: Section, name: bytes) -> Symbol:
        rows = self.names[table.index].get(name, [])
        _require(bool(rows), "symbol_missing", "A fixed symbol is missing.")
        _require(len(rows) == 1, "symbol_ambiguous", "A fixed symbol is duplicated.")
        return rows[0]

    def object_span(self, symbol: Symbol, *, executable: bool = False) -> FileOffset:
        _require(
            0 < symbol.section_index < len(self.sections) and symbol.bytes > 0,
            "export_contract",
            "A consumed symbol has no ordinary storage.",
        )
        section = self.sections[symbol.section_index]
        _require(
            section.type == 1
            and section.flags & 2 != 0
            and not section.flags & 0xC00
            and bool(section.flags & 4) == executable,
            "export_contract",
            "A consumed symbol has invalid section storage.",
        )
        _require(
            section.va <= symbol.va
            and symbol.va + symbol.bytes <= section.va + section.size,
            "export_contract",
            "A symbol exceeds its section.",
        )
        offset, load = self.file_span(symbol.va, symbol.bytes)
        _require(
            offset == section.offset + symbol.va - section.va
            and bool(load.flags & 1) == executable,
            "ambiguous_mapping",
            "A symbol mapping differs from its section.",
        )
        return offset

    def readonly(
        self, va: int, offset: int, size: int, *, directory: bool = False
    ) -> None:
        _, own = self.file_span(va, size)
        section_write = any(
            s.va <= va and va + size <= s.va + s.size and s.flags & 3 == 3
            for s in self.sections
            if s.size
        )
        if own.flags & 2 or section_write:
            _require(
                directory
                and self.relro is not None
                and self.relro.va <= va
                and va + size <= self.relro.va + self.relro.memsz,
                "ambiguous_mapping",
                "Consumed data is writable outside RELRO.",
            )
        for granule in _PAGE_GRANULES:
            for load in self.loads:
                if not load.flags & 2 or not load.memsz:
                    continue
                start = load.va // granule * granule
                end = ((load.va + load.memsz + granule - 1) // granule) * granule
                overlaps: list[tuple[int, int]] = []
                if max(start, va) < min(end, va + size):
                    overlaps.append((max(start, va), min(end, va + size)))
                if load.filesz:
                    file_start = load.offset // granule * granule
                    file_end = (
                        (load.offset + load.filesz + granule - 1) // granule
                    ) * granule
                    a, b = max(offset, file_start), min(offset + size, file_end)
                    if a < b:
                        overlaps.append(
                            (start + a - file_start, start + b - file_start)
                        )
                for a, b in overlaps:
                    relro = self.relro
                    _require(
                        relro is not None,
                        "ambiguous_mapping",
                        "A writable page alias is not protected.",
                    )
                    assert relro is not None
                    protected_start = relro.va // granule * granule
                    protected_end = (relro.va + relro.memsz) // granule * granule
                    _require(
                        protected_start <= a < b <= protected_end,
                        "ambiguous_mapping",
                        "A writable page alias escapes RELRO.",
                    )

    def required_objects(self, dynsym: Section, symtab: Section) -> list[Symbol]:
        required_names = {name for name, _, _ in _EXPORTS}
        for row in self.symbol_tables[dynsym.index][1:]:
            if row.section_index != 0 and row.binding != 0 and row.visibility in (0, 3):
                _require(
                    row.name in required_names,
                    "export_contract",
                    "An extra public export is not permitted.",
                )
        objects: list[Symbol] = []
        for name, kind, size in _EXPORTS:
            dynamic = self.named(dynsym, name)
            static = self.named(symtab, name)
            _require(
                dynamic.binding == 1
                and dynamic.visibility == 0
                and dynamic.type == kind
                and dynamic.version_index in (None, 1)
                and (size is None or dynamic.bytes == size),
                "export_contract",
                "A required export violates its contract.",
            )
            _require(
                (
                    dynamic.va,
                    dynamic.bytes,
                    dynamic.type,
                    dynamic.binding,
                    dynamic.visibility,
                    dynamic.section_index,
                )
                == (
                    static.va,
                    static.bytes,
                    static.type,
                    static.binding,
                    static.visibility,
                    static.section_index,
                ),
                "export_contract",
                "The export mirrors differ.",
            )
            offset = self.object_span(dynamic, executable=kind == 2)
            if kind != 2:
                _require(
                    dynamic.va % (4 if size == 4 else 8) == 0,
                    "export_contract",
                    "A consumed object is not aligned.",
                )
            if name in (b"phoenix_collector_data_v1", b"phoenix_collector_layout_v1"):
                self.readonly(
                    dynamic.va,
                    offset,
                    dynamic.bytes,
                    directory=name == b"phoenix_collector_data_v1",
                )
            if name == b"qemu_plugin_version":
                self.budget.scan(4)
                _require(
                    bytes(self.span(offset, 4)) == b"\x04\0\0\0",
                    "export_contract",
                    "The plugin version is not 4.",
                )
            self.exports.append(
                Export(
                    name.decode("ascii"),
                    dynamic.index,
                    static.index,
                    dynamic.section_index,
                    dynamic.va,
                    offset,
                    dynamic.bytes,
                    dynamic.binding,
                    dynamic.type,
                    dynamic.visibility,
                )
            )
            objects.append(dynamic)
        return objects

    def runtime_relocations(self, dynsym: Section) -> None:
        executable_sections = tuple(
            sorted(
                (s.va, s.va + s.size)
                for s in self.sections
                if s.size and s.flags & 2 and s.flags & 4
            )
        )
        executable_starts = tuple(start for start, _ in executable_sections)
        sections = [s for s in self.sections if s.type == 4]
        _require(
            not any(
                s.type in (9, 19, 0x60000001, 0x60000002, 0x6FFFFF00)
                for s in self.sections
            ),
            "relocation_contract",
            "An unsupported relocation section is present.",
        )
        _require(
            sum(s.size // 24 for s in sections) <= self.limits.relocations,
            "input_limit",
            "The relocation count exceeds its limit.",
        )
        ranges: list[tuple[int, int, bool]] = []
        for address_tag, size_tag, entry_tag, entry_value, plt in (
            (7, 8, 9, 24, False),
            (23, 2, 20, 7, True),
        ):
            present = [tag in self.tags for tag in (address_tag, size_tag, entry_tag)]
            if any(present):
                _require(
                    all(present)
                    and self.tags[entry_tag] == entry_value
                    and self.tags[size_tag] > 0
                    and self.tags[size_tag] % 24 == 0,
                    "dynamic_contract",
                    "Incomplete dynamic RELA metadata.",
                )
                ranges.append((self.tags[address_tag], self.tags[size_tag], plt))
        _require(
            any(not plt for _, _, plt in ranges),
            "dynamic_contract",
            "DT_RELA is required.",
        )
        _disjoint([(a, _end(a, n)) for a, n, _ in ranges], "relocation_contract")
        matched: set[int] = set()
        relative_kind, glob_kind, jump_kind = (
            (8, 6, 7) if self.machine == 62 else (1027, 1025, 1026)
        )
        main_rows: list[Rela] = []
        for section in sections:
            self.consumed(section)
            _require(
                section.entsize == 24
                and section.link == dynsym.index
                and (section.info == 0 or section.info < len(self.sections)),
                "relocation_contract",
                "Invalid RELA entry size or link.",
            )
            candidates = [
                (i, plt)
                for i, (a, n, plt) in enumerate(ranges)
                if a == section.va and n == section.size
            ]
            _require(
                len(candidates) == 1 and candidates[0][0] not in matched,
                "relocation_contract",
                "A RELA section has no unique runtime range.",
            )
            range_index, plt = candidates[0]
            matched.add(range_index)
            offset, _ = self.file_span(section.va, section.size)
            _require(
                offset == section.offset,
                "relocation_contract",
                "Runtime and section RELA offsets differ.",
            )
            for i in range(section.size // 24):
                where, info, addend = self.unpack(_RELA, section.offset + i * 24)
                kind, symbol_index = info & 0xFFFFFFFF, info >> 32
                _require(
                    kind in (relative_kind, glob_kind, jump_kind),
                    "relocation_contract",
                    "Unsupported relocation kind or width.",
                )
                _require(
                    (kind == relative_kind and symbol_index == 0 and addend >= 0)
                    or (
                        kind in (glob_kind, jump_kind)
                        and 0 < symbol_index < len(self.symbol_tables[dynsym.index])
                    ),
                    "relocation_contract",
                    "Invalid relocation symbol or addend.",
                )
                if kind != relative_kind:
                    symbol = self.symbol_tables[dynsym.index][symbol_index]
                    _require(
                        symbol.type in (0, 1, 2)
                        and symbol.binding in (1, 2)
                        and symbol.section_index < len(self.sections),
                        "relocation_contract",
                        "Unsupported relocation symbol type.",
                    )
                _require(
                    not plt or kind == jump_kind,
                    "relocation_contract",
                    "A PLT relocation is not JUMP_SLOT.",
                )
                offset, load = self.file_span(where, 8)
                _require(
                    where % 8 == 0 and not load.flags & 1 and bool(load.flags & 2),
                    "relocation_contract",
                    "Invalid relocation destination.",
                )
                self.page_mapping(where, offset, 8, False)
                executable_index = bisect_left(executable_starts, where + 8) - 1
                _require(
                    executable_index < 0
                    or executable_sections[executable_index][1] <= where,
                    "relocation_contract",
                    "A relocation touches allocated executable section bytes.",
                )
                if section.info:
                    target = self.sections[section.info]
                    _require(
                        target.va <= where and where + 8 <= target.va + target.size,
                        "relocation_contract",
                        "A relocation exceeds its target section.",
                    )
                _require(
                    where not in self.relocation_map,
                    "relocation_contract",
                    "A relocation destination is duplicated.",
                )
                row = Rela(
                    section.index,
                    i,
                    FileOffset(section.offset + i * 24),
                    ElfVa(where),
                    kind,
                    symbol_index,
                    addend,
                )
                self.relocations.append(row)
                self.relocation_map[where] = row
                if not plt:
                    main_rows.append(row)
        _require(
            len(matched) == len(ranges),
            "relocation_contract",
            "A runtime relocation range has no section.",
        )
        _disjoint(
            [(r.place_va, r.place_va + 8) for r in self.relocations],
            "relocation_contract",
        )
        count = self.tags.get(0x6FFFFFF9, 0)
        _require(
            count <= len(main_rows)
            and all(r.type == relative_kind for r in main_rows[:count]),
            "relocation_contract",
            "Invalid DT_RELACOUNT.",
        )

    def tables(self, symtab: Section, objects: list[Symbol]) -> None:
        directory = self.exports[0]
        table_objects: list[Symbol] = []
        physical = 2728 + 40168
        _require(
            physical <= self.limits.physical_data_bytes,
            "input_limit",
            "The physical data limit is exceeded.",
        )
        rows = 0
        pointers: set[int] = set()
        dimensions: list[tuple[int, int]] = []
        for i, (_, element) in enumerate(_TABLES):
            tag, count, logical_element, logical, native_element, storage, _ = (
                self.unpack(_DIR, directory.file_offset + 96 + i * 56)
            )
            _require(
                tag == i + 1
                and logical_element == native_element == element
                and count < 1 << 32
                and logical == count * element
                and storage == max(1, count) * element,
                "directory_contract",
                "Invalid table tag or dimensions.",
            )
            _require(
                i != 46 or count == 1,
                "directory_contract",
                "The root table must have one row.",
            )
            if i:
                _require(
                    count <= self.limits.nonbyte_rows - rows,
                    "input_limit",
                    "The table row limit is exceeded.",
                )
                rows += count
            _require(
                storage <= self.limits.physical_data_bytes - physical,
                "input_limit",
                "The physical data limit is exceeded.",
            )
            physical += storage
            dimensions.append((count, storage))
        for i, ((name, _), (count, storage)) in enumerate(
            zip(_TABLES, dimensions, strict=True)
        ):
            symbol = self.named(symtab, b"phoenix_" + name)
            _require(
                symbol.binding == 0 and symbol.type == 1 and symbol.bytes == storage,
                "export_contract",
                "A local table symbol violates its contract.",
            )
            _require(
                i == 0 or symbol.va % 8 == 0,
                "export_contract",
                "A table is not aligned.",
            )
            offset = self.object_span(symbol)
            self.readonly(symbol.va, offset, storage)
            if count == 0:
                self.budget.scan(storage)
                _require(
                    not any(self.span(offset, storage)),
                    "table_bounds",
                    "Empty table storage is not zero.",
                )
            place = directory.va + 144 + i * 56
            relocation = self.relocation_map.get(place)
            _require(
                relocation is not None,
                "relocation_contract",
                "A directory pointer relocation is missing.",
            )
            assert relocation is not None
            _require(
                relocation.type == (8 if self.machine == 62 else 1027)
                and relocation.symbol_index == 0
                and relocation.addend == symbol.va,
                "relocation_contract",
                "A directory pointer has the wrong target.",
            )
            pointers.add(place)
            table_objects.append(symbol)
        all_objects = objects + table_objects
        object_files = [
            (int(self.object_span(s, executable=s.type == 2)), s.bytes)
            for s in all_objects
        ]
        _disjoint(
            [(o, o + n) for o, n in object_files] + self.metadata, "storage_overlap"
        )
        _disjoint([(s.va, s.va + s.bytes) for s in all_objects], "storage_overlap")
        metadata_sections = [
            s
            for s in self.sections
            if s.type in (2, 3, 4, 5, 6, 11, 17, 0x6FFFFFFD, 0x6FFFFFFE, 0x6FFFFFFF)
        ]
        _disjoint(
            [(o, o + n) for o, n in object_files]
            + [(s.offset, s.offset + s.size) for s in metadata_sections],
            "storage_overlap",
        )
        protected = sorted((s.va, s.va + s.bytes) for s in all_objects)
        starts = [a for a, _ in protected]
        metadata = sorted(
            self.metadata
            + [(s.offset, s.offset + s.size) for s in metadata_sections if s.size]
        )
        for relocation in self.relocations:
            place = relocation.place_va
            i = bisect_right(starts, place + 7) - 1
            if i >= 0 and protected[i][1] > place:
                _require(
                    place in pointers,
                    "relocation_contract",
                    "A relocation touches protected object bytes.",
                )
            offset, _ = self.file_span(place, 8)
            # A metadata write could change later loader interpretation.
            j = bisect_right(metadata, (offset + 7, _U64_END)) - 1
            _require(
                j < 0 or metadata[j][1] <= offset,
                "relocation_contract",
                "A relocation touches ELF metadata.",
            )

    def read(self) -> CollectorElf:
        header = self.envelope()
        dynsym, symtab = self.dynamic_metadata()
        self.read_symbols(dynsym, symtab)
        self.hash_table(dynsym)
        objects = self.required_objects(dynsym, symtab)
        self.runtime_relocations(dynsym)
        self.tables(symtab, objects)
        return CollectorElf(
            self.raw,
            self.machine,
            tuple(self.loads),
            tuple(self.sections),
            tuple(self.symbols),
            tuple(self.dynamic),
            tuple(self.relocations),
            tuple(self.needed),
            tuple(self.exports),
            header,
            tuple(self.programs),
        )


def read_collector_elf(
    raw: bytes, *, machine: Machine, limits: InspectionLimits
) -> CollectorElf | InspectionRejected:
    """Return a passive view or the first bounded format refusal.

    Revalidate caller limits on every call. Direct record construction grants no
    authority. Unexpected programming exceptions are not format refusals.
    """
    if type(raw) is not bytes or type(machine) is not int or machine not in (62, 183):
        return InspectionRejected(
            "input_type", "Expected immutable bytes and machine 62 or 183."
        )
    if type(limits) is not InspectionLimits:
        return InspectionRejected("input_type", "Expected exact InspectionLimits.")
    maximum = InspectionLimits()
    values: dict[str, int] = {}
    for field in fields(InspectionLimits):
        try:
            value = getattr(limits, field.name)
        except AttributeError:
            return InspectionRejected("input_limit", "A limit field is missing.")
        if type(value) is not int or not 0 < value <= getattr(maximum, field.name):
            return InspectionRejected(
                "input_limit", "A limit is outside its installed bounds."
            )
        values[field.name] = value
    checked_limits = InspectionLimits(**values)
    if len(raw) > checked_limits.plugin_bytes:
        return InspectionRejected("input_limit", "The plugin byte limit is exceeded.")
    try:
        return _Reader(raw, machine, checked_limits).read()
    except _Refusal as refusal:
        return refusal.result
