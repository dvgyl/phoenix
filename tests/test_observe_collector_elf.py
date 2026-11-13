"""Literal synthetic ELF controls. These are not Linux compiler trials."""

from dataclasses import FrozenInstanceError, dataclass, fields, replace
from hashlib import sha256
from struct import pack_into
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phoenix.observe import collector_elf
from phoenix.observe.collector_elf import (
    CollectorElf,
    InspectionLimits,
    InspectionRejected,
    Machine,
    read_collector_elf,
)

# Literal expectations are independent of the parser and the source renderer.
TABLE_SPEC = """
bytes 1
uints 8
strings 8
registers 16
plan_gaps 16
positions 16
dispositions 40
dynamic 24
original 16
geometry 32
transport_limits 88
trace_limits 48
capture_limits 112
import_id 48
import_binding 152
call 40
jump 8
return 8
trace_site 72
trace_plan 72
lift_main 24
explicit_entry 16
requested_scope 48
user 16
transit 16
omitted 16
omitted_site 40
transit_route 56
ordinary 16
local_direct 16
local_conditional 24
planned_roles 48
transit_instruction 16
reject 16
guard_instruction 88
dormant_outside_window 16
guard_reject 16
local_branch_guard 40
metadata_only 16
gap_record 88
exit_from_supported_bits 24
exact_signal 8
termination_contract 128
scope_selection 184
load_segment 56
elf_image 32
collector_data 112
"""
TABLES = tuple(
    (line.split()[0], int(line.split()[1])) for line in TABLE_SPEC.strip().splitlines()
)
PUBLIC = (
    "phoenix_collector_data_v1",
    "phoenix_collector_layout_v1",
    "qemu_plugin_install",
    "qemu_plugin_version",
)
BASE = 0x100000
SHOFF = 0x35000


@dataclass
class Fixture:
    data: bytearray
    machine: Machine
    sections: dict[str, int]
    dynamic_slots: dict[int, list[int]]
    local_symbols: dict[str, int]
    dynamic_symbols: dict[str, int]
    static_symbols: dict[str, int]
    table_offsets: tuple[int, ...]

    def put(self, offset: int, fmt: str, *values: int) -> None:
        pack_into("<" + fmt, self.data, offset, *values)

    def section(self, name: str, field_offset: int, fmt: str, value: int) -> None:
        self.put(SHOFF + 64 * self.sections[name] + field_offset, fmt, value)

    def program(self, index: int, field_offset: int, value: int) -> None:
        self.put(
            64 + index * 56 + field_offset, "I" if field_offset < 8 else "Q", value
        )

    def dynamic(self, tag: int, value: int) -> None:
        self.put(self.dynamic_slots[tag][0] + 8, "Q", value)

    def inspect(
        self, limits: InspectionLimits = InspectionLimits()
    ) -> CollectorElf | InspectionRejected:
        return read_collector_elf(bytes(self.data), machine=self.machine, limits=limits)


def fixture(machine: Machine = 62, *, shifted: bool = False) -> Fixture:
    """Build literal ELF fields without product serialization or native loading."""
    data = bytearray(0x36000)
    section_names = (
        "",
        ".dynstr",
        ".dynsym",
        ".hash",
        ".rela.dyn",
        ".rela.plt",
        ".gnu.version",
        ".rodata",
        ".text",
        ".data.rel.ro",
        ".dynamic",
        ".got",
        ".data",
        ".strtab",
        ".symtab",
        ".shstrtab",
    )
    sections = {name: i for i, name in enumerate(section_names)}
    dyn_names = ("", *PUBLIC, "external_function")
    static_names = (
        "",
        *("phoenix_" + name for name, _ in TABLES),
        *PUBLIC,
        "external_function",
    )

    def strings(names: tuple[str, ...]) -> tuple[bytes, dict[str, int]]:
        raw = bytearray(b"\0")
        offsets = {"": 0}
        for name in names:
            if name:
                offsets[name] = len(raw)
                raw.extend(name.encode("ascii") + b"\0")
        return bytes(raw), offsets

    dynstr, dyn_name = strings((*dyn_names, "libfirst.so", "libsecond.so"))
    strtab, static_name = strings(static_names)
    shstr, shname = strings(section_names)
    data[0x400 : 0x400 + len(dynstr)] = dynstr
    data[0x31000 : 0x31000 + len(strtab)] = strtab
    data[0x34000 : 0x34000 + len(shstr)] = shstr
    pack_into(
        "<16sHHIQQQIHHHHHH",
        data,
        0,
        b"\x7fELF\x02\x01\x01" + bytes(9),
        3,
        machine,
        1,
        0,
        64,
        SHOFF,
        0,
        64,
        56,
        6,
        64,
        len(section_names),
        15,
    )
    dynamic_rows = [
        (1, dyn_name["libfirst.so"]),
        (1, dyn_name["libsecond.so"]),
        (4, BASE + 0xC00),
        (5, BASE + 0x400),
        (6, BASE + 0x800),
        (10, len(dynstr)),
        (11, 24),
        (7, BASE + 0x1000),
        (8, 48 * 24),
        (9, 24),
        (23, BASE + 0x1500),
        (2, 24),
        (20, 7),
        (0x6FFFFFF9, 47),
        (0x6FFFFFF0, BASE + 0x1600),
        (30, 8),
        (0x6FFFFFFB, 1),
        (0, 0),
        (0, 0),
    ]
    programs = (
        (1, 4, 0, BASE, 0, 0x10000, 0x10000, 0x10000),
        (1, 5, 0x10000, BASE + 0x10000, 0, 0x10000, 0x10000, 0x10000),
        (1, 6, 0x20000, BASE + 0x20000, 0, 0x10000, 0x10000, 0x10000),
        (1, 6, 0x30000, BASE + 0x30000, 0, 0x1000, 0x1000, 0x10000),
        (
            2,
            6,
            0x20B00,
            BASE + 0x20B00,
            0,
            len(dynamic_rows) * 16,
            len(dynamic_rows) * 16,
            8,
        ),
        (0x6474E552, 4, 0x20000, BASE + 0x20000, 0, 0x10000, 0x10000, 1),
    )
    for i, row in enumerate(programs):
        pack_into("<IIQQQQQQ", data, 64 + i * 56, *row)
    layouts = (
        (0, 0, 0, 0, 0, 0, 0, 0, 0),
        (3, 2, BASE + 0x400, 0x400, len(dynstr), 0, 0, 1, 0),
        (11, 2, BASE + 0x800, 0x800, len(dyn_names) * 24, 1, 1, 8, 24),
        (5, 2, BASE + 0xC00, 0xC00, 4 * (3 + len(dyn_names)), 2, 0, 4, 4),
        (4, 2, BASE + 0x1000, 0x1000, 48 * 24, 2, 0, 8, 24),
        (4, 2, BASE + 0x1500, 0x1500, 24, 2, 11, 8, 24),
        (0x6FFFFFFF, 2, BASE + 0x1600, 0x1600, len(dyn_names) * 2, 2, 0, 2, 2),
        (1, 2, BASE + 0x2000, 0x2000, 0xE000, 0, 0, 8, 0),
        (1, 6, BASE + 0x10000, 0x10000, 16, 0, 0, 16, 0),
        (1, 3, BASE + 0x20000, 0x20000, 2728, 0, 0, 8, 0),
        (6, 3, BASE + 0x20B00, 0x20B00, len(dynamic_rows) * 16, 1, 0, 8, 16),
        (1, 3, BASE + 0x20E00, 0x20E00, 16, 0, 0, 8, 0),
        (1, 3, BASE + 0x30000, 0x30000, 16, 0, 0, 8, 0),
        (3, 0, 0, 0x31000, len(strtab), 0, 0, 1, 0),
        (2, 0, 0, 0x32000, len(static_names) * 24, 13, 48, 8, 24),
        (3, 0, 0, 0x34000, len(shstr), 0, 0, 1, 0),
    )
    for i, (name, layout) in enumerate(zip(section_names, layouts, strict=True)):
        pack_into("<IIQQQQIIQQ", data, SHOFF + i * 64, shname[name], *layout)
    public_shapes = (
        (1, 9, BASE + 0x20000, 2728),
        (1, 7, BASE + 0x2000, 40168),
        (2, 8, BASE + 0x10000, 16),
        (1, 12, BASE + 0x30000, 4),
    )
    dynamic_symbols: dict[str, int] = {}
    static_symbols: dict[str, int] = {}
    for i, (name, (kind, section, va, size)) in enumerate(
        zip(PUBLIC, public_shapes, strict=True), 1
    ):
        off = 0x800 + i * 24
        pack_into("<IBBHQQ", data, off, dyn_name[name], 16 + kind, 0, section, va, size)
        dynamic_symbols[name] = off
        off = 0x32000 + (47 + i) * 24
        pack_into(
            "<IBBHQQ", data, off, static_name[name], 16 + kind, 0, section, va, size
        )
        static_symbols[name] = off
    pack_into(
        "<IBBHQQ", data, 0x800 + 5 * 24, dyn_name["external_function"], 18, 0, 0, 0, 0
    )
    pack_into(
        "<IBBHQQ",
        data,
        0x32000 + 52 * 24,
        static_name["external_function"],
        18,
        0,
        0,
        0,
        0,
    )
    dynamic_symbols["external_function"] = 0x800 + 5 * 24
    static_symbols["external_function"] = 0x32000 + 52 * 24
    pack_into("<9I", data, 0xC00, 1, 6, 1, 0, 2, 3, 4, 5, 0)
    pack_into("<6H", data, 0x1600, 0, 1, 1, 1, 1, 1)
    dynamic_slots: dict[int, list[int]] = {}
    for i, (tag, value) in enumerate(dynamic_rows):
        off = 0x20B00 + i * 16
        pack_into("<qQ", data, off, tag, value)
        dynamic_slots.setdefault(tag, []).append(off)
    data[0x20000:0x20060] = b"\x11" * 32 + b"\x22" * 32 + b"\x33" * 32
    pack_into("<I", data, 0x30000, 4)
    table_offsets: list[int] = []
    local_symbols: dict[str, int] = {}
    cursor = 0xC000 + (0x800 if shifted else 0)
    for i, (name, size) in enumerate(TABLES):
        cursor = (cursor + 7) // 8 * 8
        count = 1 if i == 46 else 0
        symbol_offset = 0x32000 + (i + 1) * 24
        pack_into(
            "<IBBHQQ",
            data,
            symbol_offset,
            static_name["phoenix_" + name],
            1,
            0,
            7,
            BASE + cursor,
            size,
        )
        local_symbols[name] = symbol_offset
        pack_into(
            "<7Q",
            data,
            0x20060 + i * 56,
            i + 1,
            count,
            size,
            count * size,
            size,
            size,
            BASE + cursor,
        )
        pack_into(
            "<QQq",
            data,
            0x1000 + i * 24,
            BASE + 0x20090 + i * 56,
            8 if machine == 62 else 1027,
            BASE + cursor,
        )
        table_offsets.append(cursor)
        cursor += size
    pack_into(
        "<QQq",
        data,
        0x1000 + 47 * 24,
        BASE + 0x20E00,
        (5 << 32) | (6 if machine == 62 else 1025),
        0,
    )
    pack_into(
        "<QQq",
        data,
        0x1500,
        BASE + 0x20E08,
        (5 << 32) | (7 if machine == 62 else 1026),
        0,
    )
    return Fixture(
        data,
        machine,
        sections,
        dynamic_slots,
        local_symbols,
        dynamic_symbols,
        static_symbols,
        tuple(table_offsets),
    )


def accepted(f: Fixture, limits: InspectionLimits = InspectionLimits()) -> CollectorElf:
    result = f.inspect(limits)
    assert isinstance(result, CollectorElf), result
    return result


def rejected(
    f: Fixture, reason: str | None = None, limits: InspectionLimits = InspectionLimits()
) -> InspectionRejected:
    result = f.inspect(limits)
    assert isinstance(result, InspectionRejected), result
    assert len(result.detail) <= 512
    assert not hasattr(result, "raw")
    assert not hasattr(result, "symbols")
    if reason is not None:
        assert result.reason == reason, result
    return result


@pytest.mark.parametrize("machine", [62, 183])
def test_literal_complete_view(machine: Machine) -> None:
    f = fixture(machine)
    view = accepted(f)
    assert view.raw == bytes(f.data)
    assert view.machine == machine
    assert len(view.loads) == 4
    assert len(view.programs) == 6
    assert len(view.sections) == 16
    assert len(view.symbols) == 59
    assert len(view.relocations) == 49
    assert view.needed == (b"libfirst.so", b"libsecond.so")
    assert [e.name for e in view.exports] == sorted(PUBLIC)
    assert [s.index for s in view.sections] == list(range(16))
    assert [s.index for s in view.symbols if s.table_section == 2] == list(range(6))
    assert [r.place_va for r in view.relocations[:47]] == [
        BASE + 0x20090 + 56 * i for i in range(47)
    ]
    assert [r.addend for r in view.relocations[:47]] == [
        BASE + o for o in f.table_offsets
    ]
    assert view.dynamic[-2:] == (
        collector_elf.DynamicEntry(17, 0, 0),
        collector_elf.DynamicEntry(18, 0, 0),
    )
    with pytest.raises(FrozenInstanceError):
        view.machine = 62  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        view.symbols[0].name = b"changed"  # type: ignore[misc]


@pytest.mark.parametrize("machine", [62, 183])
def test_distinct_placement_and_stale_pointer_word(machine: Machine) -> None:
    one, two = fixture(machine), fixture(machine, shifted=True)
    a, b = accepted(one), accepted(two)
    assert a.exports == b.exports
    assert a.relocations != b.relocations
    original = bytes(one.data)
    one.put(0x20090, "Q", 0xFFFFFFFFFFFFFFFF)
    changed = accepted(one)
    assert changed.relocations == a.relocations
    assert sha256(changed.raw).digest() != sha256(original).digest()
    assert changed.raw[0x20000:0x20AA8] != original[0x20000:0x20AA8]
    assert not hasattr(changed, "trusted_pin")
    assert not hasattr(changed, "layout_approval")


@pytest.mark.parametrize(
    "offset,fmt,value",
    [
        (4, "B", 1),
        (5, "B", 2),
        (6, "B", 0),
        (7, "B", 2),
        (8, "B", 1),
        (15, "B", 1),
        (16, "H", 1),
        (16, "H", 2),
        (18, "H", 183),
        (20, "I", 2),
        (24, "Q", 1),
        (48, "I", 1),
        (52, "H", 63),
        (54, "H", 55),
        (56, "H", 0),
        (56, "H", 65535),
        (58, "H", 63),
        (60, "H", 0),
        (60, "H", 0xFF00),
        (62, "H", 0),
        (62, "H", 16),
        (32, "Q", (1 << 64) - 8),
        (40, "Q", (1 << 64) - 8),
        (40, "Q", 64),
        (32, "Q", 65),
    ],
)
def test_elf_envelope_rejections(offset: int, fmt: str, value: int) -> None:
    f = fixture()
    f.put(offset, fmt, value)
    rejected(f)


@pytest.mark.parametrize(
    "length", [*range(65), 119, 120, 399, 400, SHOFF, SHOFF + 1023]
)
def test_truncation(length: int) -> None:
    f = fixture()
    del f.data[length:]
    rejected(f)


@pytest.mark.parametrize(
    "index,offset,value",
    [
        (0, 0, 3),
        (0, 4, 12),
        (0, 32, 0x10001),
        (0, 48, 3),
        (0, 16, (1 << 64) - 0x8000),
        (1, 16, BASE + 0x8000),
        (1, 8, 0x8000),
        (0, 8, 0x10000),
        (0, 32, 0x36001),
        (5, 0, 0),
        (5, 40, 0xFFFF),
        (5, 16, BASE + 0x20008),
    ],
)
def test_program_rejections(index: int, offset: int, value: int) -> None:
    f = fixture()
    f.program(index, offset, value)
    rejected(f)


def test_huge_bss_is_not_allocated() -> None:
    f = fixture()
    f.program(3, 40, (1 << 63))
    assert accepted(f).loads[3].memsz == 1 << 63


@pytest.mark.parametrize(
    "name,offset,fmt,value",
    [
        (".rodata", 4, "I", 8),
        (".rodata", 8, "Q", 2 | 0x800),
        (".rodata", 8, "Q", 2 | 0x400),
        (".rodata", 8, "Q", 6),
        (".rodata", 8, "Q", 3),
        (".rodata", 16, "Q", BASE + 0x2008),
        (".rodata", 24, "Q", 0x2008),
        (".rodata", 32, "Q", 0xE008),
        (".rodata", 48, "Q", 3),
        (".dynsym", 40, "I", 99),
        (".dynsym", 56, "Q", 8),
        (".symtab", 56, "Q", 8),
        (".dynamic", 56, "Q", 8),
        (".dynstr", 8, "Q", 0x802),
        (".shstrtab", 4, "I", 1),
        (".rodata", 24, "Q", 64),
        (".gnu.version", 16, "Q", BASE + 0x1000),
    ],
)
def test_section_rejections(name: str, offset: int, fmt: str, value: int) -> None:
    f = fixture()
    f.section(name, offset, fmt, value)
    rejected(f)


@pytest.mark.parametrize("name", PUBLIC)
@pytest.mark.parametrize(
    "field,fmt,value",
    [
        (0, "I", 0),
        (4, "B", 0x21),
        (4, "B", 0x1A),
        (5, "B", 2),
        (6, "H", 0),
        (6, "H", 0xFFF1),
        (6, "H", 0xFFF2),
        (8, "Q", BASE + 0x30010),
        (16, "Q", 0),
    ],
)
def test_required_export_contract(name: str, field: int, fmt: str, value: int) -> None:
    f = fixture()
    f.put(f.dynamic_symbols[name] + field, fmt, value)
    rejected(f)


@pytest.mark.parametrize("name", PUBLIC)
def test_contradictory_mirror(name: str) -> None:
    f = fixture()
    f.put(f.static_symbols[name] + 16, "Q", 3)
    rejected(f, "export_contract")


@pytest.mark.parametrize("table", ["dyn", "static"])
def test_duplicate_required_name_including_undefined(table: str) -> None:
    f = fixture()
    symbol = f.dynamic_symbols if table == "dyn" else f.static_symbols
    target = symbol[PUBLIC[0]]
    name_offset = int.from_bytes(f.data[target : target + 4], "little")
    f.put(symbol["external_function"], "I", name_offset)
    rejected(f, "symbol_ambiguous")


@pytest.mark.parametrize("i", range(47))
def test_each_local_table_required(i: int) -> None:
    f = fixture()
    f.put(f.local_symbols[TABLES[i][0]], "I", 0)
    rejected(f, "symbol_missing")


@pytest.mark.parametrize("i", range(47))
@pytest.mark.parametrize("component", range(6))
def test_each_directory_scalar_is_checked(i: int, component: int) -> None:
    f = fixture()
    off = 0x20060 + i * 56 + component * 8
    value = int.from_bytes(f.data[off : off + 8], "little")
    f.put(off, "Q", value + 1)
    rejected(f, "directory_contract")


@pytest.mark.parametrize("i", range(47))
@pytest.mark.parametrize("machine", [62, 183])
def test_each_pointer_target_is_exact(i: int, machine: Machine) -> None:
    f = fixture(machine)
    f.put(0x1000 + i * 24 + 16, "q", BASE + f.table_offsets[i] + 1)
    rejected(f, "relocation_contract")


@pytest.mark.parametrize("i", range(47))
def test_each_pointer_is_required(i: int) -> None:
    f = fixture()
    f.put(0x1000 + i * 24, "Q", BASE + 0x30008)
    rejected(f, "relocation_contract")


@pytest.mark.parametrize("kind", [0, 1, 2, 5, 16, 37, 1027, 0xFFFFFFFF])
def test_wrong_or_unknown_relocation_width(kind: int) -> None:
    f = fixture()
    f.put(0x1008, "Q", kind)
    rejected(f, "relocation_contract")


@pytest.mark.parametrize(
    "offset,fmt,value",
    [
        (0x1010, "q", -1),
        (0x1010, "q", 0),
        (0x1010, "q", (1 << 63) - 1),
        (0x1008, "Q", (1 << 32) | 8),
        (0x1008, "Q", (1 << 32) | 6),
        (0x1000, "Q", BASE + 0x20091),
        (0x1018, "Q", BASE + 0x20090),
        (0x1000, "Q", BASE + 0x20088),
        (0x1000, "Q", BASE + 0xC000),
        (0x1000, "Q", BASE + 0x2000),
        (0x1000, "Q", BASE + 0x10000),
        (0x1000, "Q", BASE + 0x30FFC),
        (0x1000, "Q", (1 << 64) - 4),
        (0x1508, "Q", (6 << 32) | 7),
        (0x1508, "Q", 8),
    ],
)
def test_relocation_controls(offset: int, fmt: str, value: int) -> None:
    f = fixture()
    f.put(offset, fmt, value)
    rejected(f)


@pytest.mark.parametrize(
    "tag,value",
    [
        (4, BASE + 0xC04),
        (5, BASE + 0x401),
        (6, BASE + 0x818),
        (10, 3),
        (11, 23),
        (7, BASE + 0x1018),
        (8, 47 * 24),
        (9, 16),
        (23, BASE + 0x1508),
        (2, 48),
        (20, 17),
        (0x6FFFFFF9, 48),
        (0x6FFFFFF9, 49),
        (0x6FFFFFF0, BASE + 0x1602),
        (30, 12),
    ],
)
def test_dynamic_mismatches(tag: int, value: int) -> None:
    f = fixture()
    f.dynamic(tag, value)
    rejected(f)


@pytest.mark.parametrize(
    "tag",
    [
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
        15,
        29,
    ],
)
def test_forbidden_dynamic_tags(tag: int) -> None:
    f = fixture()
    f.put(f.dynamic_slots[0x6FFFFFFB][0], "qQ", tag, 0)
    rejected(f, "dynamic_contract")


@pytest.mark.parametrize(
    "mutation", ["duplicate", "tail", "no_null", "missing", "no_now"]
)
def test_dynamic_list_controls(mutation: str) -> None:
    f = fixture()
    if mutation == "duplicate":
        f.put(f.dynamic_slots[0x6FFFFFFB][0], "qQ", 4, BASE + 0xC00)
    elif mutation == "tail":
        f.put(f.dynamic_slots[0][1], "qQ", 1, 1)
    elif mutation == "no_null":
        for i, off in enumerate(f.dynamic_slots[0]):
            f.put(off, "qQ", 100 + i, 0)
    elif mutation == "missing":
        f.put(f.dynamic_slots[9][0], "q", 100)
    else:
        f.dynamic(30, 0)
        f.dynamic(0x6FFFFFFB, 0)
    rejected(f, "dynamic_contract")


@pytest.mark.parametrize(
    "offset,value",
    [
        (0xC00, 0),
        (0xC00, 262144),
        (0xC04, 5),
        (0xC08, 6),
        (0xC08, 0),
        (0xC0C, 1),
        (0xC10, 1),
        (0xC10, 6),
        (0xC20, 1),
    ],
)
def test_hash_controls(offset: int, value: int) -> None:
    f = fixture()
    f.put(offset, "I", value)
    rejected(f)


@pytest.mark.parametrize("i", [1, 2, 3, 4])
@pytest.mark.parametrize("version", [0, 2, 0x8001])
def test_required_export_versions(i: int, version: int) -> None:
    f = fixture()
    f.put(0x1600 + i * 2, "H", version)
    rejected(f, "export_contract")


def test_version_array_optional() -> None:
    f = fixture()
    f.section(".gnu.version", 4, "I", 1)
    f.put(f.dynamic_slots[0x6FFFFFF0][0], "qQ", 100, 123)
    view = accepted(f)
    assert all(s.version_index is None for s in view.symbols)
    assert collector_elf.DynamicEntry(14, 100, 123) in view.dynamic


@pytest.mark.parametrize(
    "mutation", ["wrong_count", "wrong_link", "wrong_entry", "missing_tag"]
)
def test_version_array_metadata(mutation: str) -> None:
    f = fixture()
    if mutation == "wrong_count":
        f.section(".gnu.version", 32, "Q", 10)
    elif mutation == "wrong_link":
        f.section(".gnu.version", 40, "I", 14)
    elif mutation == "wrong_entry":
        f.section(".gnu.version", 56, "Q", 1)
    else:
        f.put(f.dynamic_slots[0x6FFFFFF0][0], "qQ", 100, 0)
    rejected(f, "dynamic_contract")


@pytest.mark.parametrize("field", [f.name for f in fields(InspectionLimits)])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, None, "1", 1 << 64])
def test_every_limit_revalidated(field: str, value: object) -> None:
    limits = InspectionLimits()
    object.__setattr__(limits, field, value)
    result = read_collector_elf(b"", machine=62, limits=limits)
    assert result == InspectionRejected(
        "input_limit", "A limit is outside its installed bounds."
    )


@pytest.mark.parametrize("field", [f.name for f in fields(InspectionLimits)])
def test_missing_limit(field: str) -> None:
    limits = InspectionLimits()
    object.__delattr__(limits, field)
    result = read_collector_elf(b"", machine=62, limits=limits)
    assert result == InspectionRejected("input_limit", "A limit field is missing.")


@pytest.mark.parametrize("field", [f.name for f in fields(InspectionLimits)])
def test_each_raised_limit(field: str) -> None:
    limits = InspectionLimits()
    object.__setattr__(limits, field, getattr(limits, field) + 1)
    result = read_collector_elf(b"", machine=62, limits=limits)
    assert isinstance(result, InspectionRejected)
    assert result.reason == "input_limit"


@pytest.mark.parametrize("raw", [bytearray(), memoryview(b""), None, "", 0])
def test_raw_exact_type(raw: Any) -> None:
    result = read_collector_elf(raw, machine=62, limits=InspectionLimits())
    assert isinstance(result, InspectionRejected) and result.reason == "input_type"


@pytest.mark.parametrize("machine", [True, 62.0, 183.0, None, "62", 0, 1])
def test_machine_exact_type(machine: Any) -> None:
    result = read_collector_elf(b"", machine=machine, limits=InspectionLimits())
    assert isinstance(result, InspectionRejected) and result.reason == "input_type"


def test_limit_exact_type() -> None:
    class OtherLimits(InspectionLimits):
        pass

    invalid: tuple[object, ...] = (None, {}, OtherLimits())
    for value in invalid:
        result = read_collector_elf(
            b"", machine=62, limits=cast(InspectionLimits, value)
        )
        assert isinstance(result, InspectionRejected) and result.reason == "input_type"


@pytest.mark.parametrize(
    "field,minimum",
    [
        ("plugin_bytes", 0x36000),
        ("program_headers", 6),
        ("sections", 16),
        ("symbols", 59),
        ("relocations", 49),
        ("dynamic_entries", 19),
        ("hash_words", 9),
        ("nonbyte_rows", 1),
    ],
)
def test_capacity_boundary(field: str, minimum: int) -> None:
    f = fixture()
    limits = replace(InspectionLimits(), **{field: minimum})
    accepted(f, limits)
    if minimum > 1:
        rejected(f, "input_limit", replace(limits, **{field: minimum - 1}))


def test_all_unused_lower_limits_are_preserved() -> None:
    limits = replace(
        InspectionLimits(), logical_data_bytes=1, nesting=1, inspection_bytes=1
    )
    accepted(fixture(), limits)
    assert limits.logical_data_bytes == limits.nesting == limits.inspection_bytes == 1


@pytest.mark.parametrize("fault", [RuntimeError, AssertionError, TypeError, ValueError])
def test_internal_faults_remain_visible(
    monkeypatch: pytest.MonkeyPatch, fault: type[Exception]
) -> None:
    def broken(self: object) -> CollectorElf:
        raise fault("programming fault")

    monkeypatch.setattr(collector_elf._Reader, "read", broken)
    with pytest.raises(fault, match="programming fault"):
        fixture().inspect()


@given(st.binary(max_size=8192), st.sampled_from([62, 183]))
@settings(max_examples=150, deadline=None)
def test_arbitrary_bounded_bytes(raw: bytes, machine: Machine) -> None:
    result = read_collector_elf(raw, machine=machine, limits=InspectionLimits())
    assert isinstance(result, InspectionRejected)
    assert len(result.detail) <= 512


@given(
    st.integers(min_value=0, max_value=46),
    st.integers(min_value=1, max_value=7),
    st.sampled_from([62, 183]),
)
@settings(max_examples=100, deadline=None)
def test_structure_preserving_pointer_mutations(
    index: int, shift: int, machine: Machine
) -> None:
    f = fixture(machine)
    f.put(0x1000 + index * 24 + 16, "q", BASE + f.table_offsets[index] + shift)
    rejected(f, "relocation_contract")


@given(
    st.integers(min_value=0, max_value=46),
    st.integers(min_value=0, max_value=(1 << 64) - 1),
)
@settings(max_examples=50, deadline=None)
def test_rela_ignores_original_word(index: int, word: int) -> None:
    f = fixture()
    f.put(0x20090 + index * 56, "Q", word)
    view = accepted(f)
    assert view.relocations[index].addend == BASE + f.table_offsets[index]


def prefix_alias_fixture() -> Fixture:
    """Create disjoint exact loads whose rounded writable prefix aliases tables."""
    f = fixture()
    f.data[0xE000:0xEAA8] = f.data[0x20000:0x20AA8]
    f.data[0xF000:0xF130] = f.data[0x20B00:0x20C30]
    for tag, offsets in f.dynamic_slots.items():
        f.dynamic_slots[tag] = [offset - 0x11B00 for offset in offsets]
    f.program(0, 32, 0xD000)
    f.program(0, 40, 0xD000)
    f.section(".rodata", 32, "Q", 0xB000)
    for field, value in (
        (8, 0xD800),
        (16, BASE + 0x3D800),
        (32, 0x2800),
        (40, 0x2800),
        (48, 0x1000),
    ):
        f.program(2, field, value)
    f.program(3, 16, BASE + 0x50000)
    f.section(".data", 16, "Q", BASE + 0x50000)
    for symbols in (f.dynamic_symbols, f.static_symbols):
        f.put(symbols["qemu_plugin_version"] + 8, "Q", BASE + 0x50000)
        f.put(symbols["phoenix_collector_data_v1"] + 8, "Q", BASE + 0x3E000)
    f.section(".data.rel.ro", 16, "Q", BASE + 0x3E000)
    f.section(".data.rel.ro", 24, "Q", 0xE000)
    f.section(".dynamic", 16, "Q", BASE + 0x3F000)
    f.section(".dynamic", 24, "Q", 0xF000)
    f.section(".got", 16, "Q", BASE + 0x3F800)
    f.section(".got", 24, "Q", 0xF800)
    f.program(4, 8, 0xF000)
    f.program(4, 16, BASE + 0x3F000)
    for field, value in ((8, 0xE000), (16, BASE + 0x3E000), (32, 0x2000), (40, 0x2000)):
        f.program(5, field, value)
    for i in range(47):
        f.put(0x1000 + i * 24, "Q", BASE + 0x3E090 + i * 56)
    f.put(0x1000 + 47 * 24, "Q", BASE + 0x3F800)
    f.put(0x1500, "Q", BASE + 0x3F808)
    return f


def test_relro_protects_rounded_writable_prefix() -> None:
    view = accepted(prefix_alias_fixture())
    assert view.loads[2].offset == 0xD800
    assert view.exports[0].file_offset == 0xE000
    assert view.relocations[0].place_va == BASE + 0x3E090
    assert view.symbols[7].va == BASE + 0xC000


def test_relro_must_protect_prefix_for_every_candidate_granule() -> None:
    f = prefix_alias_fixture()
    f.program(5, 32, 0x1000)
    f.program(5, 40, 0x1000)
    error = rejected(f, "ambiguous_mapping")
    assert "RELRO" in error.detail


def test_page_alias_with_wrong_file_bytes() -> None:
    f = prefix_alias_fixture()
    # Shorten the code load so only page rounding creates the conflict.
    f.program(1, 32, 16)
    f.program(1, 40, 16)
    f.program(2, 16, BASE + 0x1D800)
    f.program(5, 16, BASE + 0x1E000)
    f.program(4, 16, BASE + 0x1F000)
    for name, va in (
        (".data.rel.ro", BASE + 0x1E000),
        (".dynamic", BASE + 0x1F000),
        (".got", BASE + 0x1F800),
    ):
        f.section(name, 16, "Q", va)
    error = rejected(f, "ambiguous_mapping")
    assert "Rounded load mappings" in error.detail


def test_readonly_directory_section_in_relro_load() -> None:
    f = fixture()
    f.section(".data.rel.ro", 8, "Q", 2)
    accepted(f)


@pytest.mark.parametrize("i", range(46))
def test_empty_table_requires_zero_physical_element(i: int) -> None:
    f = fixture()
    f.data[f.table_offsets[i] + TABLES[i][1] - 1] = 1
    rejected(f, "table_bounds")


def test_nonempty_table_semantics_and_witness_are_not_decoded() -> None:
    f = fixture()
    f.data[f.table_offsets[-1]] = 255
    f.data[0x2000] = 255
    f.data[0x20000] ^= 255
    accepted(f)


def test_empty_tables_must_not_share_storage() -> None:
    f = fixture()
    first = BASE + f.table_offsets[1]
    f.put(f.local_symbols["strings"] + 8, "Q", first)
    f.put(0x1000 + 2 * 24 + 16, "q", first)
    rejected(f, "storage_overlap")


@pytest.mark.parametrize(
    "target", [BASE + 0x30000, BASE + 0x20B00, BASE + 0x20000, BASE + 0x20AA8 - 8]
)
def test_unrelated_relocations_cannot_touch_protected_bytes(target: int) -> None:
    f = fixture()
    f.put(0x1000 + 47 * 24, "Q", target)
    rejected(f, "relocation_contract")


@pytest.mark.parametrize("kind", [6, 10])
def test_imported_tls_and_ifunc_are_rejected(kind: int) -> None:
    f = fixture()
    f.put(f.dynamic_symbols["external_function"] + 4, "B", 16 + kind)
    rejected(f)


@pytest.mark.parametrize("machine", [62, 183])
def test_unrelated_relative_relocation(machine: Machine) -> None:
    f = fixture(machine)
    f.put(0x1000 + 47 * 24 + 8, "Qq", 8 if machine == 62 else 1027, BASE + 0xC000)
    f.dynamic(0x6FFFFFF9, 48)
    accepted(f)


def test_symbol_and_relocation_input_order_is_retained() -> None:
    f = fixture()
    a, b = f.local_symbols["uints"], f.local_symbols["collector_data"]
    f.data[a : a + 24], f.data[b : b + 24] = f.data[b : b + 24], f.data[a : a + 24]
    f.data[0x1000:0x1018], f.data[0x1018:0x1030] = (
        f.data[0x1018:0x1030],
        f.data[0x1000:0x1018],
    )
    view = accepted(f)
    assert view.symbols[8].name == b"phoenix_collector_data"
    assert view.relocations[0].place_va == BASE + 0x20090 + 56
    assert view.relocations[1].place_va == BASE + 0x20090


def test_table_at_exact_section_and_file_end() -> None:
    f = fixture()
    root = f.table_offsets[-1]
    end = root + 112
    f.section(".rodata", 32, "Q", end - 0x2000)
    f.program(0, 32, end)
    f.program(0, 40, end)
    accepted(f)
    f.program(0, 32, end - 1)
    rejected(f, "ambiguous_mapping")


def test_bytes_table_has_byte_alignment() -> None:
    f = fixture()
    f.put(f.local_symbols["bytes"] + 8, "Q", BASE + 0xBFF1)
    f.put(0x1010, "q", BASE + 0xBFF1)
    f.put(0x20060 + 8, "5Q", 3, 1, 3, 1, 3)
    f.put(f.local_symbols["bytes"] + 16, "Q", 3)
    accepted(f)


def test_physical_data_limit_before_table_scan() -> None:
    minimum = 2728 + 40168 + sum(size for _, size in TABLES)
    f = fixture()
    accepted(f, replace(InspectionLimits(), physical_data_bytes=minimum))
    rejected(
        f, "input_limit", replace(InspectionLimits(), physical_data_bytes=minimum - 1)
    )


def test_string_table_and_name_lower_bounds() -> None:
    f = fixture()
    string_bytes = int.from_bytes(
        f.data[SHOFF + 13 * 64 + 32 : SHOFF + 13 * 64 + 40], "little"
    )
    longest = max(len("phoenix_" + name) for name, _ in TABLES)
    accepted(
        f,
        replace(
            InspectionLimits(),
            string_table_bytes=string_bytes,
            symbol_name_bytes=longest,
        ),
    )
    rejected(
        f,
        "input_limit",
        replace(InspectionLimits(), string_table_bytes=string_bytes - 1),
    )
    rejected(
        f, "input_limit", replace(InspectionLimits(), symbol_name_bytes=longest - 1)
    )


@pytest.mark.parametrize("name", ["scanned_bytes", "scalar_visits"])
def test_work_limits_apply_before_scan(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("A string scan started after the work limit.")

    monkeypatch.setattr(collector_elf._Strings, "__init__", forbidden)
    rejected(fixture(), "work_limit", replace(InspectionLimits(), **{name: 1}))


def test_plugin_limit_precedes_reader_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("The reader was allocated before the byte limit.")

    monkeypatch.setattr(collector_elf._Reader, "__init__", forbidden)
    rejected(fixture(), "input_limit", replace(InspectionLimits(), plugin_bytes=64))


def test_symbol_limit_precedes_dynamic_string_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError(
            "A dynamic string index was built before the symbol limit."
        )

    monkeypatch.setattr(collector_elf._Reader, "string_table", forbidden)
    rejected(fixture(), "input_limit", replace(InspectionLimits(), symbols=58))


def test_exact_plugin_cap() -> None:
    f = fixture()
    f.data.extend(bytes(33554432 - len(f.data)))
    accepted(f)
    f.data.append(0)
    rejected(f, "input_limit")


@pytest.mark.parametrize(
    "field,value", [(1, (1 << 64) - 1), (3, (1 << 64) - 1), (5, (1 << 64) - 1)]
)
def test_directory_integer_products_never_wrap(field: int, value: int) -> None:
    f = fixture()
    f.put(0x20060 + field * 8, "Q", value)
    rejected(f, "directory_contract")


def test_unsigned_address_end_may_equal_two_to_64() -> None:
    f = fixture()
    f.program(3, 40, (1 << 64) - (BASE + 0x30000))
    accepted(f)
    f.program(3, 40, (1 << 64) - (BASE + 0x30000) + 1)
    rejected(f, "malformed_elf")


def test_name_terminator_and_name_offset() -> None:
    f = fixture()
    f.data[0x31000] = 1
    rejected(f, "malformed_elf")
    f = fixture()
    size = int.from_bytes(f.data[SHOFF + 13 * 64 + 32 : SHOFF + 13 * 64 + 40], "little")
    f.data[0x31000 + size - 1] = 1
    rejected(f, "malformed_elf")
    f = fixture()
    f.put(f.local_symbols["uints"], "I", size)
    rejected(f, "malformed_elf")


def test_sysv_hash_checks_actual_bucket_membership() -> None:
    f = fixture()
    # ELF hashes modulo seven are 6, 2, 1, 1, and 0 for these five names.
    f.put(0xC00, "15I", 7, 6, 5, 3, 2, 0, 0, 0, 1, 0, 0, 0, 4, 0, 0)
    f.section(".hash", 32, "Q", 60)
    accepted(f)
    f.put(0xC08, "I", 1)
    f.put(0xC20, "I", 5)
    error = rejected(f, "dynamic_contract")
    assert "bucket" in error.detail


@pytest.mark.parametrize("kind", [9, 19, 0x60000001, 0x60000002, 0x6FFFFF00])
def test_non_rela_section_forms(kind: int) -> None:
    f = fixture()
    f.section(".rela.plt", 4, "I", kind)
    rejected(f, "relocation_contract")


@pytest.mark.parametrize(
    "field,fmt,value",
    [(40, "I", 14), (56, "Q", 8), (16, "Q", BASE + 0x1800), (8, "Q", 0), (44, "I", 8)],
)
def test_rela_section_runtime_agreement(field: int, fmt: str, value: int) -> None:
    f = fixture()
    f.section(".rela.dyn", field, fmt, value)
    rejected(f)


def test_unlisted_runtime_relocation_section() -> None:
    f = fixture()
    f.put(f.dynamic_slots[23][0], "qQ", 100, 0)
    f.put(f.dynamic_slots[2][0], "qQ", 101, 0)
    f.put(f.dynamic_slots[20][0], "qQ", 102, 0)
    rejected(f, "relocation_contract")


def test_missing_runtime_relocation_section() -> None:
    f = fixture()
    f.section(".rela.plt", 4, "I", 1)
    rejected(f, "relocation_contract")


def test_overlapping_runtime_ranges() -> None:
    f = fixture()
    f.dynamic(23, BASE + 0x1000)
    rejected(f, "relocation_contract")


def test_extra_public_export() -> None:
    f = fixture()
    f.put(f.dynamic_symbols["external_function"] + 6, "HQQ", 8, BASE + 0x10000, 1)
    rejected(f, "export_contract")


def test_missing_or_duplicate_symbol_tables() -> None:
    f = fixture()
    f.section(".symtab", 4, "I", 1)
    rejected(f, "symbol_missing")
    f = fixture()
    f.section(".symtab", 4, "I", 11)
    rejected(f, "dynamic_contract")


def test_duplicate_local_table_name() -> None:
    f = fixture()
    source = f.local_symbols["uints"]
    name = int.from_bytes(f.data[source : source + 4], "little")
    f.put(f.local_symbols["strings"], "I", name)
    rejected(f, "symbol_ambiguous")


def test_local_table_wrong_size_type_and_binding() -> None:
    for offset, fmt, value in ((16, "Q", 16), (4, "B", 2), (4, "B", 17)):
        f = fixture()
        f.put(f.local_symbols["uints"] + offset, fmt, value)
        rejected(f)


def test_version_integer_exact_bytes() -> None:
    f = fixture()
    f.put(0x30000, "I", 5)
    rejected(f, "export_contract")


def test_bss_only_symbol_and_one_past_pointer() -> None:
    f = fixture()
    f.program(0, 32, 0xC000)
    rejected(f, "ambiguous_mapping")
    f = fixture()
    f.put(0x1010, "q", BASE + f.table_offsets[0] + 1)
    rejected(f, "relocation_contract")


def test_non_utf8_names_remain_bytes() -> None:
    f = fixture()
    off = f.dynamic_symbols["external_function"]
    name_offset = int.from_bytes(f.data[off : off + 4], "little")
    f.data[0x400 + name_offset] = 255
    view = accepted(f)
    assert view.symbols[5].name == b"\xffxternal_function"


def test_string_indexes_are_built_once(monkeypatch: pytest.MonkeyPatch) -> None:
    original = collector_elf._Strings.__init__
    lengths: list[int] = []

    def counted(
        self: collector_elf._Strings, raw: memoryview, budget: collector_elf._Budget
    ) -> None:
        lengths.append(len(raw))
        original(self, raw, budget)

    monkeypatch.setattr(collector_elf._Strings, "__init__", counted)
    accepted(fixture())
    assert len(lengths) == 3


def test_read_has_no_io_or_process_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import io
    import os
    import socket
    import subprocess
    import time

    f = fixture()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("The pure reader attempted an external operation.")

    with monkeypatch.context() as context:
        for owner, name in (
            (builtins, "open"),
            (io, "open"),
            (os, "open"),
            (os, "getenv"),
            (os, "getpid"),
            (socket, "socket"),
            (subprocess, "Popen"),
            (time, "time"),
            (time, "monotonic"),
        ):
            context.setattr(owner, name, forbidden)
        result = f.inspect()
    assert isinstance(result, CollectorElf)


def test_direct_result_construction_grants_no_authority() -> None:
    view = accepted(fixture())
    fabricated = replace(view, raw=b"not ELF")
    assert isinstance(fabricated, CollectorElf)
    result = read_collector_elf(fabricated.raw, machine=62, limits=InspectionLimits())
    assert isinstance(result, InspectionRejected)
    assert not hasattr(fabricated, "approved")


def test_unknown_dynamic_tags_are_evidence_only() -> None:
    f = fixture()
    f.put(f.dynamic_slots[0x6FFFFFFB][0], "qQ", -123, (1 << 64) - 1)
    view = accepted(f)
    assert view.dynamic[16] == collector_elf.DynamicEntry(16, -123, (1 << 64) - 1)


def test_limits_are_snapshotted_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = collector_elf._Reader.read
    limits = replace(InspectionLimits(), scanned_bytes=1)

    def changed_caller(self: collector_elf._Reader) -> CollectorElf:
        object.__setattr__(limits, "scanned_bytes", 268435456)
        return original(self)

    monkeypatch.setattr(collector_elf._Reader, "read", changed_caller)
    rejected(fixture(), "work_limit", limits)


def test_exact_type_guards_do_not_invoke_caller_methods() -> None:
    class BytesSubclass(bytes):
        def __len__(self) -> int:
            raise AssertionError("The byte subclass was inspected.")

    class LimitsSubclass(InspectionLimits):
        def __getattribute__(self, name: str) -> Any:
            raise AssertionError("The limits subclass was inspected.")

    for raw, limits in (
        (BytesSubclass(b""), InspectionLimits()),
        (b"", LimitsSubclass()),
    ):
        result = read_collector_elf(raw, machine=62, limits=limits)
        assert isinstance(result, InspectionRejected)
        assert result.reason == "input_type"


def test_all_storage_is_reserved_before_table_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = collector_elf._Reader.object_span

    def guarded(
        self: collector_elf._Reader,
        symbol: collector_elf.Symbol,
        *,
        executable: bool = False,
    ) -> collector_elf.FileOffset:
        if symbol.binding == 0:
            raise AssertionError(
                "Table access preceded the complete storage reservation."
            )
        return original(self, symbol, executable=executable)

    monkeypatch.setattr(collector_elf._Reader, "object_span", guarded)
    minimum = 2728 + 40168 + sum(size for _, size in TABLES)
    rejected(
        fixture(),
        "input_limit",
        replace(InspectionLimits(), physical_data_bytes=minimum - 1),
    )


@pytest.mark.parametrize("tag", [0x6FFFFFFA, 0x6FFFFEF8, 0x6FFFFDF6])
def test_additional_relocation_metadata_is_rejected(tag: int) -> None:
    f = fixture()
    f.put(f.dynamic_slots[0x6FFFFFFB][0], "qQ", tag, 0)
    rejected(f, "dynamic_contract")


def split_readonly_fixture() -> Fixture:
    f = fixture()
    f.put(56, "H", 7)
    f.put(60, "H", 17)
    f.program(0, 32, 0xBFF0)
    f.program(0, 40, 0xBFF0)
    pack_into(
        "<IIQQQQQQ",
        f.data,
        64 + 6 * 56,
        1,
        4,
        0xC000,
        BASE + 0xC000,
        0,
        0x4000,
        0x4000,
        0x1000,
    )
    f.section(".rodata", 32, "Q", 0x9FF0)
    name = int.from_bytes(f.data[SHOFF + 7 * 64 : SHOFF + 7 * 64 + 4], "little")
    pack_into(
        "<IIQQQQIIQQ",
        f.data,
        SHOFF + 16 * 64,
        name,
        1,
        2,
        BASE + 0xC000,
        0xC000,
        0x4000,
        0,
        0,
        8,
        0,
    )
    for offset in f.local_symbols.values():
        f.put(offset + 6, "H", 16)
    return f


def test_coherent_readonly_page_overlap() -> None:
    view = accepted(split_readonly_fixture())
    assert len(view.loads) == 5
    assert len(view.sections) == 17


def test_zero_fill_cannot_replace_other_file_backed_bytes() -> None:
    f = split_readonly_fixture()
    f.program(0, 40, 0xBFF8)
    error = rejected(f, "ambiguous_mapping")
    assert "zero" in error.detail


def unsectioned_destination_fixture(machine: Machine, kind: str) -> Fixture:
    f = fixture(machine)
    f.data.extend(bytes(0x70000 - len(f.data)))
    f.put(56, "H", 7)
    if kind == "installer_page":
        f.program(1, 32, 64)
        f.program(1, 40, 64)
        pack_into(
            "<IIQQQQQQ",
            f.data,
            64 + 6 * 56,
            1,
            6,
            0x10800,
            BASE + 0x10800,
            0,
            0x800,
            0x800,
            0x1000,
        )
        f.put(0x1000 + 47 * 24, "Q", BASE + 0x10800)
        return f
    f.data[0x50000:0x50010] = f.data[0x30000:0x30010]
    f.program(3, 8, 0x50000)
    f.program(3, 16, BASE + 0x90000)
    f.section(".data", 16, "Q", BASE + 0x90000)
    f.section(".data", 24, "Q", 0x50000)
    for symbols in (f.dynamic_symbols, f.static_symbols):
        f.put(symbols["qemu_plugin_version"] + 8, "Q", BASE + 0x90000)
    f.program(2, 32, 0x28000)
    f.program(2, 40, 0x28000)
    offset = 0x58800 if kind == "file" else 0x48800
    flags = 5 if kind == "execute" else 4
    filesz = 0 if kind == "zero" else 0x800
    pack_into(
        "<IIQQQQQQ",
        f.data,
        64 + 6 * 56,
        1,
        flags,
        offset,
        BASE + 0x48800,
        0,
        filesz,
        0x800,
        0x1000,
    )
    f.put(0x1000 + 47 * 24, "Q", BASE + 0x41000)
    return f


@pytest.mark.parametrize("machine", [62, 183])
@pytest.mark.parametrize("kind", ["file", "execute", "zero", "installer_page"])
def test_unsectioned_runtime_write_checks_rounded_mapping(
    machine: Machine, kind: str
) -> None:
    rejected(unsectioned_destination_fixture(machine, kind), "ambiguous_mapping")


@pytest.mark.parametrize("machine", [62, 183])
def test_unsectioned_coherent_runtime_write_remains_supported(machine: Machine) -> None:
    view = accepted(unsectioned_destination_fixture(machine, "coherent"))
    assert view.relocations[47].place_va == BASE + 0x41000


def executable_section_fixture(
    machine: Machine, offset: int, size: int, flags: int, section_type: int
) -> Fixture:
    f = fixture(machine)
    f.section(".rela.plt", 44, "I", 0)
    f.put(0x1500, "Q", BASE + 0x20E80)
    f.section(".got", 4, "I", section_type)
    f.section(".got", 8, "Q", flags)
    f.section(".got", 16, "Q", BASE + 0x20E00 + offset)
    f.section(".got", 24, "Q", 0x20E00 + offset)
    f.section(".got", 32, "Q", size)
    f.section(".got", 48, "Q", 1)
    return f


@pytest.mark.parametrize("machine", [62, 183])
@pytest.mark.parametrize(
    "offset,size,flags,section_type,refuses",
    [
        (-1, 2, 6, 1, True),
        (7, 2, 6, 1, True),
        (2, 2, 6, 1, True),
        (-8, 24, 6, 1, True),
        (-8, 8, 6, 1, False),
        (8, 8, 6, 1, False),
        (0, 0, 6, 1, False),
        (4, 0, 6, 1, False),
        (0, 8, 4, 1, False),
        (0, 8, 3, 1, False),
        (32, 8, 6, 1, False),
        (0, 8, 6, 8, True),
    ],
)
def test_runtime_write_executable_section_contract(
    machine: Machine,
    offset: int,
    size: int,
    flags: int,
    section_type: int,
    refuses: bool,
) -> None:
    f = executable_section_fixture(machine, offset, size, flags, section_type)
    if refuses:
        rejected(f, "relocation_contract")
    else:
        accepted(f)


@pytest.mark.parametrize("machine", [62, 183])
@pytest.mark.parametrize("executable", [False, True])
def test_executable_section_query_at_unsigned_address_end(
    machine: Machine, executable: bool
) -> None:
    f = fixture(machine)
    start = (1 << 64) - 0x10000
    f.program(2, 16, start)
    f.program(4, 16, start + 0xB00)
    f.program(5, 16, start)
    f.section(".data.rel.ro", 16, "Q", start)
    f.section(".dynamic", 16, "Q", start + 0xB00)
    for symbols in (f.dynamic_symbols, f.static_symbols):
        f.put(symbols["phoenix_collector_data_v1"] + 8, "Q", start)
    for i in range(47):
        f.put(0x1000 + i * 24, "Q", start + 144 + 56 * i)
    f.put(0x1000 + 47 * 24, "Q", (1 << 64) - 8)
    f.section(".rela.plt", 44, "I", 0)
    f.put(0x1500, "Q", start + 0xE80)
    f.section(".got", 4, "I", 8)
    f.section(".got", 8, "Q", 6 if executable else 3)
    f.section(".got", 16, "Q", (1 << 64) - 8)
    f.section(".got", 32, "Q", 8)
    f.section(".got", 48, "Q", 1)
    if executable:
        rejected(f, "relocation_contract")
    else:
        view = accepted(f)
        assert view.relocations[47].place_va + 8 == 1 << 64
