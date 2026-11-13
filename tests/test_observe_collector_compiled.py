"""Synthetic consistency controls. These inputs are not native compiler trials."""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from pathlib import Path
from struct import pack_into, unpack_from
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_observe_collector_elf import BASE, Fixture, fixture
from test_observe_collector_layout import _fields, _members, _tables, _types

from phoenix.observe import collector_compiled as compiled
from phoenix.observe import collector_elf as elf
from phoenix.observe import collector_layout as layout

PROFILES = {62: "linux-x86_64-lp64-le-rela-1", 183: "linux-aarch64-lp64-le-rela-1"}
SPECS = {tag: tuple(f for f in _fields() if f[0] == tag) for tag in range(1, 48)}
NAMES = {name: tag for tag, name, _, _, _ in _tables()}
SIZES = {tag: size for tag, _, _, size, _ in _tables()}
KINDS = {tag: kind for tag, _, _, _, kind in _tables()}
MAXIMA = {
    11: (
        16777216,
        1024,
        65536,
        67108864,
        67108864,
        4096,
        16777216,
        1179648,
        1179648,
        4096,
        4096,
    ),
    12: (10000, 1000000, 64, 8, 1000000, 8388608),
    13: (
        10000,
        1000000,
        64,
        524288,
        4096,
        65536,
        65536,
        32,
        8388608,
        8,
        32,
        8,
        1000000,
        8388608,
    ),
}


def witness(machine: int) -> bytes:
    words = [0x50484F454E49584C, 1, machine, 8, 8, 1, 100, 653, 47]
    sizes = {number: size for number, _, size, _ in _types()}
    for number, _, size, alignment in _types():
        words.extend((number, size, alignment))
    for number, owner, _, offset, size, alignment, code, extent in _members():
        words.extend((owner, number, offset, size, alignment, code, extent))
    for tag, _, element, _, _ in _tables():
        words.extend((tag, element, sizes[element]))
    return b"".join(n.to_bytes(8, "little") for n in words)


def sample(tag: int = 47) -> Any:
    def value(descriptor: str) -> Any:
        if descriptor.startswith("o:") or descriptor.startswith("v0:"):
            return None
        if descriptor.startswith("v:"):
            return sample(NAMES[descriptor[2:].split(",")[0]])
        if descriptor.startswith("r:"):
            return sample(NAMES[descriptor[2:]])
        if descriptor.startswith("a:"):
            return []
        if descriptor.startswith("e:"):
            return descriptor[2:].split("|")[0]
        if descriptor.startswith("n:"):
            return int(descriptor[2:])
        if descriptor == "h":
            return "a" * 64
        if descriptor == "w":
            return "90"
        if descriptor == "s":
            return "f"
        if descriptor == "b":
            return False
        return 0

    record = {name: value(desc) for _, name, _, _, desc in SPECS[tag]}
    if tag in MAXIMA:
        record = dict(zip(record, MAXIMA[tag], strict=True))
    if KINDS[tag] == "scalar":
        return record["value"]
    if KINDS[tag] == "pair":
        return list(record.values())
    return record


class Cells:
    def __init__(self) -> None:
        self.rows: dict[int, list[bytearray]] = {tag: [] for tag in range(1, 48)}
        self.blob = bytearray()

    def reserve(self, tag: int, values: list[Any]) -> tuple[int, int]:
        begin = len(self.rows[tag])
        self.rows[tag].extend(bytearray(SIZES[tag]) for _ in values)
        for index, value in enumerate(values, begin):
            self.row(tag, index, value)
        return begin, len(values)

    def row(self, tag: int, index: int, value: Any) -> None:
        entries = SPECS[tag]
        if KINDS[tag] == "scalar":
            value = {"value": value}
        elif KINDS[tag] == "pair":
            value = dict(zip((f[1] for f in entries), value, strict=True))
        for _, name, _, offset, descriptor in entries:
            self.cell(self.rows[tag][index], offset, descriptor, value[name], value)

    def cell(
        self, row: bytearray, offset: int, desc: str, value: Any, previous: Any
    ) -> None:
        if desc.startswith("o:"):
            pack_into("<Q", row, offset, int(value is not None))
            if value is not None:
                self.cell(row, offset + 8, desc[2:], value, previous)
        elif desc.startswith(("v:", "v0:")):
            choices = desc.split(":", 1)[1].split(",")
            if value is None:
                return
            name = value.get(
                "kind",
                "exact_signal" if "signal" in value else "exit_from_supported_bits",
            )
            if name in ("direct_call", "indirect_call"):
                name = "call"
            if name == "indirect_jump":
                name = "jump"
            index = choices.index(name)
            pack_into("<Q", row, offset, index + 1)
            self.cell(row, offset + 8 * (index + 1), "r:" + name, value, previous)
        elif desc.startswith(("a:", "r:")):
            target = NAMES[desc[2:]]
            begin, count = self.reserve(
                target, value if desc.startswith("a:") else [value]
            )
            pack_into("<II", row, offset, begin, count)
        elif desc in ("s", "h", "w") or desc.startswith("e:"):
            raw = bytes.fromhex(value) if desc == "w" else value.encode("utf-8")
            pack_into("<II", row, offset, len(self.blob), len(raw))
            self.blob.extend(raw)
        elif desc == "i":
            pack_into("<QQ", row, offset, int(value < 0), abs(value))
        else:
            if desc.startswith("end:"):
                value -= previous[desc[4:]]
            pack_into("<Q", row, offset, value)


def built(
    record: Any = None, machine: elf.Machine = 62, placement: int = 0
) -> tuple[Fixture, compiled.ExpectedCollector]:
    record = sample() if record is None else record
    cells = Cells()
    cells.reserve(47, [record])
    f = fixture(machine)
    f.data[0x2000 : 0x2000 + 40168] = witness(machine)
    expected_raw = (
        json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")
    f.data[0x20000:0x20060] = (
        sha256(expected_raw).digest() + b"\x22" * 32 + b"\x33" * 32
    )
    cursor = 0xBD00 + placement
    offsets = []
    for tag in range(1, 48):
        cursor = (cursor + 7) // 8 * 8
        raw = bytes(cells.blob) if tag == 1 else b"".join(cells.rows[tag])
        count = len(cells.blob) if tag == 1 else len(cells.rows[tag])
        storage = raw if count else bytes(SIZES[tag])
        assert cursor + len(storage) <= 0x10000
        f.data[cursor : cursor + len(storage)] = storage
        f.put(
            0x20060 + (tag - 1) * 56,
            "6Q",
            tag,
            count,
            SIZES[tag],
            count * SIZES[tag],
            SIZES[tag],
            len(storage),
        )
        name = _tables()[tag - 1][1]
        f.put(f.local_symbols[name] + 8, "QQ", BASE + cursor, len(storage))
        f.put(0x1000 + (tag - 1) * 24 + 16, "q", BASE + cursor)
        offsets.append(cursor)
        cursor += len(storage)
    f.table_offsets = tuple(offsets)
    return f, compiled.ExpectedCollector(expected_raw, "22" * 32, "33" * 32)


def read(
    f: Fixture,
    expected: compiled.ExpectedCollector,
    limits: elf.InspectionLimits = elf.InspectionLimits(),
) -> compiled.LogicalReadback | elf.InspectionRejected:
    return compiled._readback(
        bytes(f.data),
        expected=expected,
        profile=cast(layout.ProfileId, PROFILES[f.machine]),
        limits=limits,
    )


def good(
    f: Fixture,
    expected: compiled.ExpectedCollector,
    limits: elf.InspectionLimits = elf.InspectionLimits(),
) -> compiled.LogicalReadback:
    result = read(f, expected, limits)
    assert isinstance(result, compiled.LogicalReadback), result
    assert result.logical_raw == expected.logical_raw
    assert result.logical_raw is not expected.logical_raw
    assert result.elf.raw == bytes(f.data)
    assert result.logical_sha256 == sha256(result.logical_raw).hexdigest()
    return result


def bad(
    f: Fixture,
    expected: compiled.ExpectedCollector,
    reason: str,
    limits: elf.InspectionLimits = elf.InspectionLimits(),
) -> None:
    result = read(f, expected, limits)
    assert isinstance(result, elf.InspectionRejected), result
    assert result.reason == reason
    assert len(result.detail) <= 512
    assert not hasattr(result, "logical_raw")
    assert not hasattr(result, "inspection_raw")


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("placement", (0, 128, 512))
def test_complete_synthetic(machine: elf.Machine, placement: int) -> None:
    f, expected = built(machine=machine, placement=placement)
    result = good(f, expected)
    assert len(result.directory.tables) == 47
    assert len(result.elf.dynamic) == 19
    assert len(result.elf.relocations) == 49
    assert result.elf.dynamic[-1].tag == result.elf.dynamic[-1].value == 0


@pytest.mark.parametrize("machine", (62, 183))
def test_public_raw_reconstruction(
    machine: elf.Machine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_observe_collector_data import accepted, source

    from phoenix.observe import collector_data, collector_header, collector_header_read

    data = accepted(source().prepare())
    expected_raw = data.to_bytes()
    f, expected = built(json.loads(expected_raw), machine)
    assert expected.logical_raw == expected_raw

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A source helper was called.")

    for module in (collector_data, collector_header, collector_header_read):
        for name, item in vars(module).copy().items():
            if callable(item) and not isinstance(item, type):
                monkeypatch.setattr(module, name, unavailable)
    good(f, expected)


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("position", range(5021))
def test_every_witness_word(machine: elf.Machine, position: int) -> None:
    f, expected = built(machine=machine)
    f.data[0x2000 + position * 8] ^= 1
    bad(f, expected, "layout_mismatch")


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("tag", range(1, 48))
@pytest.mark.parametrize("component", (0, 8, 16, 24, 32, 40))
def test_directory_scalars(machine: elf.Machine, tag: int, component: int) -> None:
    f, expected = built(machine=machine)
    offset = 0x20060 + (tag - 1) * 56 + component
    f.put(offset, "Q", unpack_from("<Q", f.data, offset)[0] + 1)
    bad(f, expected, "directory_contract")


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("tag", range(1, 48))
@pytest.mark.parametrize("component", ("addend", "symbol", "kind", "duplicate"))
def test_pointer_inventory(machine: elf.Machine, tag: int, component: str) -> None:
    f, expected = built(machine=machine)
    offset = 0x1000 + (tag - 1) * 24
    if component == "addend":
        f.put(offset + 16, "q", BASE + f.table_offsets[tag - 1] + 1)
    elif component == "symbol":
        f.put(offset + 8, "Q", (1 << 32) | (8 if machine == 62 else 1027))
    elif component == "kind":
        f.put(offset + 8, "Q", 0)
    else:
        f.put(0x1000 + 47 * 24, "Q", BASE + 0x20090 + (tag - 1) * 56)
    bad(f, expected, "relocation_contract")


@pytest.mark.parametrize("tag", range(1, 48))
def test_pointer_words_are_not_authority(tag: int) -> None:
    f, expected = built()
    f.put(0x20090 + (tag - 1) * 56, "Q", 0xDEADBEEF)
    good(f, expected)


@pytest.mark.parametrize("tag", range(1, 48))
def test_empty_storage_or_symbol_extent(tag: int) -> None:
    f, expected = built()
    count = unpack_from("<Q", f.data, 0x20068 + (tag - 1) * 56)[0]
    if not count:
        f.data[f.table_offsets[tag - 1]] = 1
        bad(f, expected, "table_bounds")
    else:
        name = _tables()[tag - 1][1]
        offset = f.local_symbols[name] + 16
        f.put(offset, "Q", unpack_from("<Q", f.data, offset)[0] + 1)
        bad(f, expected, "export_contract")


@pytest.mark.parametrize("tag", (11, 12, 13))
@pytest.mark.parametrize("delta", (0, 1))
def test_all_retained_limit_fields(tag: int, delta: int) -> None:
    for i, maximum in enumerate(MAXIMA[tag]):
        f, expected = built()
        f.put(f.table_offsets[tag - 1] + 8 * i, "Q", 0 if delta == 0 else maximum + 1)
        bad(f, expected, "input_limit")


@pytest.mark.parametrize(
    "offset,reason",
    ((0, "logical_mismatch"), (32, "source_identity"), (64, "source_identity")),
)
def test_directory_identities(offset: int, reason: str) -> None:
    f, expected = built()
    f.data[0x20000 + offset] ^= 1
    bad(f, expected, reason)


@pytest.mark.parametrize("change", ("space", "newline", "float", "extra", "order"))
def test_noncanonical_expected(change: str) -> None:
    f, expected = built()
    raw = expected.logical_raw
    if change == "space":
        raw = raw.replace(b":", b": ", 1)
    elif change == "newline":
        raw += b"\n"
    elif change == "float":
        raw = raw.replace(b":0", b":0.0", 1)
    elif change == "extra":
        raw = b'{"extra":0,' + raw[1:]
    else:
        raw = json.dumps(json.loads(raw), sort_keys=False, indent=1).encode() + b"\n"
    bad(f, replace(expected, logical_raw=raw), "logical_mismatch")


def test_work_boundaries_and_complete_u1_debit() -> None:
    f, expected = built()
    result = good(f, expected)
    for name, exact in (
        ("scanned_bytes", result.usage.scanned_upper),
        ("scalar_visits", result.usage.scalar_upper),
    ):
        good(f, expected, replace(elf.InspectionLimits(), **{name: exact}))
        bad(
            f,
            expected,
            "work_limit",
            replace(elf.InspectionLimits(), **{name: exact - 1}),
        )
    for nesting in range(1, 33):
        outcome = read(f, expected, replace(elf.InspectionLimits(), nesting=nesting))
        if isinstance(outcome, compiled.LogicalReadback):
            assert nesting > 1
            bad(
                f,
                expected,
                "work_limit",
                replace(elf.InspectionLimits(), nesting=nesting - 1),
            )
            break
    else:
        raise AssertionError("No supported nesting limit.")


def test_output_cap_counts_final_lf() -> None:
    f, expected = built()
    good(
        f,
        expected,
        replace(elf.InspectionLimits(), logical_data_bytes=len(expected.logical_raw)),
    )
    bad(
        f,
        expected,
        "input_limit",
        replace(
            elf.InspectionLimits(), logical_data_bytes=len(expected.logical_raw) - 1
        ),
    )


@pytest.mark.parametrize("field_name", ("full_plan_bytes", "scope_bytes", "data_bytes"))
def test_subtree_caps(field_name: str) -> None:
    record = sample()
    target = (
        record
        if field_name == "data_bytes"
        else record["full_plan" if field_name == "full_plan_bytes" else "scope"]
    )
    limits = (
        record["transport_limits"]
        if field_name == "data_bytes"
        else record["scope"]["limits"]
    )
    for _ in range(5):
        limits[field_name] = len(
            (json.dumps(target, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
    f, expected = built(record)
    good(f, expected)
    limits[field_name] -= 1
    f, expected = built(record)
    bad(f, expected, "record_limit")


@pytest.mark.parametrize("fault", (RuntimeError, AssertionError, TypeError, ValueError))
@pytest.mark.parametrize(
    "helper", ("_check_witness", "_canonical_bytes", "_compare_complete")
)
def test_visible_faults(
    monkeypatch: pytest.MonkeyPatch, fault: type[Exception], helper: str
) -> None:
    f, expected = built()

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise fault("visible")

    monkeypatch.setattr(compiled, helper, fail)
    with pytest.raises(fault, match="visible"):
        read(f, expected)


def test_frozen_transaction_and_absent_public_wrapper() -> None:
    f, expected = built()
    result = good(f, expected)
    for value in (
        result,
        result.directory,
        result.directory.tables[0],
        result.usage,
        result.elf,
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    assert not hasattr(compiled, "inspect_compiled_data")
    assert not hasattr(compiled, "CompiledDataInspection")
    assert not hasattr(compiled, "_encode_inspection")


def test_input_types_and_missing_fields() -> None:
    f, expected = built()
    for raw in (bytearray(f.data), memoryview(bytes(f.data)), object()):
        result = compiled._readback(
            cast(bytes, raw), expected=expected, profile="linux-x86_64-lp64-le-rela-1"
        )
        assert (
            isinstance(result, elf.InspectionRejected) and result.reason == "input_type"
        )
    for name in ("logical_raw", "renderer_sha256", "native_source_sha256"):
        changed = replace(expected)
        object.__delattr__(changed, name)
        bad(f, changed, "input_type")
    for item in fields(elf.InspectionLimits):
        for value in (True, 0, -1, 1.0, getattr(elf.InspectionLimits(), item.name) + 1):
            bad(
                f,
                expected,
                "input_limit",
                replace(elf.InspectionLimits(), **{item.name: cast(int, value)}),
            )


def test_import_declarations() -> None:
    tree = ast.parse(Path(compiled.__file__).read_text())
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports <= {
        "__future__",
        "bisect",
        "collections.abc",
        "dataclasses",
        "hashlib",
        "struct",
        "types",
        "typing",
        "phoenix.observe",
    }
    assert {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } == {"json"}


def test_u1_positive_is_u2_negative() -> None:
    f = fixture()
    assert isinstance(f.inspect(), elf.CollectorElf)
    bad(f, compiled.ExpectedCollector(b"{}\n", "22" * 32, "33" * 32), "layout_mismatch")


def thaw(value: compiled.LogicalValue) -> Any:
    if type(value) is compiled.LogicalObject:
        return {key: thaw(child) for key, child in value.entries}
    if type(value) is tuple:
        return [thaw(child) for child in value]
    return value


def private_rows(tag: int, value: Any) -> compiled._Decoder:
    cells = Cells()
    cells.reserve(tag, [value])
    raw = bytearray()
    tables = []
    for number, name, _, size, _ in _tables():
        content = bytes(cells.blob) if number == 1 else b"".join(cells.rows[number])
        count = len(content) // size
        storage = content or bytes(size)
        offset = len(raw)
        raw.extend(storage)
        tables.append(
            compiled.TableSpan(
                number,
                name,
                count,
                size,
                count * size,
                size,
                len(storage),
                0,
                0,
                elf.ElfVa(offset),
                elf.FileOffset(offset),
                elf.Rela(0, 0, elf.FileOffset(0), elf.ElfVa(0), 8, 0, offset),
            )
        )
    export = elf.Export("private", 0, 0, 0, elf.ElfVa(0), elf.FileOffset(0), 0, 0, 1, 0)
    directory = compiled.DirectoryView(
        export, bytes(32), bytes(32), bytes(32), tuple(tables)
    )
    lower = compiled._Lower(
        *(
            dict(zip((f[1] for f in SPECS[t]), MAXIMA[t], strict=True))
            for t in (11, 12, 13)
        )
    )
    decoder = compiled._Decoder(
        memoryview(bytes(raw)),
        layout._definition(PROFILES[62]),
        directory,
        compiled.WorkBudget(elf.InspectionLimits()),
        compiled.CursorState(),
        lower,
    )
    decoder.claim(tag, 0, 1, record=True)
    return decoder


def decode_private(tag: int, value: Any) -> Any:
    decoder = private_rows(tag, value)
    actual = decoder.decode_row(tag, 0, 1)
    assert [t.count for t in decoder.directory.tables] == decoder.state.cursors
    return thaw(actual)


@pytest.mark.parametrize("tag", range(2, 48))
def test_every_logical_row_kind(tag: int) -> None:
    assert decode_private(tag, sample(tag)) == sample(tag)


def active(desc: str) -> Any:
    if desc.startswith("o:"):
        return active(desc[2:])
    if desc.startswith(("v:", "v0:")):
        return sample(NAMES[desc.split(":", 1)[1].split(",")[0]])
    if desc.startswith("r:"):
        return sample(NAMES[desc[2:]])
    if desc.startswith("a:"):
        return [sample(NAMES[desc[2:]])]
    if desc.startswith("e:"):
        return desc[2:].split("|")[-1]
    if desc.startswith("n:"):
        return int(desc[2:])
    return {"s": '\0"\\\nÿé𝄞', "h": "c" * 64, "w": "00ff80", "i": -1, "b": True}.get(
        desc, 7
    )


def changed_field(tag: int, name: str, value: Any) -> Any:
    record = sample(tag)
    if KINDS[tag] == "scalar":
        return value
    if KINDS[tag] == "pair":
        record[next(i for i, f in enumerate(SPECS[tag]) if f[1] == name)] = value
    else:
        record[name] = value
        if tag == 10 and name.endswith("_start"):
            record[name.removesuffix("_start") + "_end_exclusive"] = value
    return record


@pytest.mark.parametrize("tag,name,native,offset,desc", _fields())
def test_every_field_active(
    tag: int, name: str, native: str, offset: int, desc: str
) -> None:
    if (tag, name) == (44, "contracts"):
        record = changed_field(tag, name, active(desc))
        decoder = private_rows(tag, record)
        with pytest.raises(compiled._DecodeRefusal) as error:
            decoder.decode_row(tag, 0, 1)
        assert error.value.result.reason == "logical_shape"
        return
    record = changed_field(tag, name, active(desc))
    assert decode_private(tag, record) == record


_VARIANTS = [
    (tag, name, desc, choice)
    for tag, name, _, _, desc in _fields()
    if desc.startswith(("v:", "v0:"))
    for choice in desc.split(":", 1)[1].split(",")
]


@pytest.mark.parametrize("tag,name,desc,choice", _VARIANTS)
def test_all_active_variants(tag: int, name: str, desc: str, choice: str) -> None:
    record = changed_field(tag, name, sample(NAMES[choice]))
    assert decode_private(tag, record) == record


@pytest.mark.parametrize(
    "tag,name,native,offset,desc",
    [f for f in _fields() if f[4].startswith(("o:", "v:", "v0:"))],
)
def test_all_tag_and_inactive_cells(
    tag: int, name: str, native: str, offset: int, desc: str
) -> None:
    value = sample(tag)
    decoder = private_rows(tag, value)
    start, _ = decoder.row_span(tag, 0)
    raw = bytearray(decoder.raw)
    pack_into("<Q", raw, start + offset, 100)
    invalid = replace(decoder, raw=memoryview(bytes(raw)), state=compiled.CursorState())
    invalid.claim(tag, 0, 1, record=True)
    with pytest.raises(compiled._DecodeRefusal) as error:
        invalid.decode_row(tag, 0, 1)
    assert error.value.result.reason == "logical_shape"
    if desc.startswith("o:"):
        widths = (
            [(8, 4), (12, 4)]
            if desc[2:] in ("s", "h") or desc[2:].startswith("r:")
            else [(8, 8)]
        )
    else:
        choices = desc.split(":", 1)[1].split(",")
        first = 0 if desc.startswith("v0:") else 1
        widths = [
            (8 + i * 8 + j, 4) for i in range(first, len(choices)) for j in (0, 4)
        ]
    for relative, width in widths:
        raw = bytearray(decoder.raw)
        pack_into("<I" if width == 4 else "<Q", raw, start + offset + relative, 1)
        invalid = replace(
            decoder, raw=memoryview(bytes(raw)), state=compiled.CursorState()
        )
        invalid.claim(tag, 0, 1, record=True)
        with pytest.raises(compiled._DecodeRefusal) as error:
            invalid.decode_row(tag, 0, 1)
        assert error.value.result.reason == "logical_shape"


@pytest.mark.parametrize(
    "sign,magnitude,result",
    [
        (0, 0, 0),
        (1, 1, -1),
        (0, (1 << 63) - 1, (1 << 63) - 1),
        (1, 1 << 63, -(1 << 63)),
        (1, 0, None),
        (2, 1, None),
        (0, 1 << 63, None),
        (1, (1 << 63) + 1, None),
    ],
)
def test_signed_literal_edges(sign: int, magnitude: int, result: int | None) -> None:
    decoder = private_rows(8, [0, 18446744073709551615])
    start, _ = decoder.row_span(8, 0)
    raw = bytearray(decoder.raw)
    raw[start : start + 16] = sign.to_bytes(8, "little") + magnitude.to_bytes(
        8, "little"
    )
    decoder = replace(decoder, raw=memoryview(bytes(raw)))
    if result is None:
        with pytest.raises(compiled._DecodeRefusal) as error:
            decoder.decode_row(8, 0, 1)
        assert error.value.result.reason == "logical_shape"
    else:
        assert thaw(decoder.decode_row(8, 0, 1)) == [result, 18446744073709551615]


def test_endpoint_exact_upper_bound() -> None:
    value = {
        "executable_file_start": (1 << 64) - 16,
        "executable_file_end_exclusive": 1 << 64,
        "load_memory_start": 0,
        "load_memory_end_exclusive": 0,
    }
    assert decode_private(10, value) == value
    decoder = private_rows(10, value)
    raw = bytearray(decoder.raw)
    raw[decoder.row_span(10, 0)[0] + 8] = 17
    with pytest.raises(compiled._DecodeRefusal) as error:
        replace(decoder, raw=memoryview(bytes(raw))).decode_row(10, 0, 1)
    assert error.value.result.reason == "logical_shape"


@pytest.mark.parametrize(
    "raw", (b"\xff", b"\xc0\x80", b"\xed\xa0\x80", b"\xf4\x90\x80\x80", b"\xc3")
)
def test_utf8_rejections(raw: bytes) -> None:
    decoder = private_rows(3, "x" * len(raw))
    changed = bytearray(decoder.raw)
    changed[: len(raw)] = raw
    with pytest.raises(compiled._DecodeRefusal) as error:
        replace(decoder, raw=memoryview(bytes(changed))).decode_row(3, 0, 1)
    assert error.value.result.reason == "logical_shape"


def test_literal_import_id_and_text_encoding() -> None:
    record = {
        "needed_library": None,
        "symbol": "f",
        "version": "",
        "version_hidden": True,
    }
    decoder = private_rows(14, record)
    start, end = decoder.row_span(14, 0)
    assert decoder.raw[start:end].tobytes() == bytes.fromhex(
        "00000000000000000000000000000000"
        "00000000010000000100000000000000"
        "01000000000000000100000000000000"
    )
    logical = decoder.decode_row(14, 0, 1)
    actual = compiled._canonical_bytes(
        cast(compiled.LogicalObject, logical), decoder.lower, decoder.budget
    )
    assert (
        actual
        == b'{"needed_library":null,"symbol":"f","version":"","version_hidden":true}\n'
    )
    text = compiled.LogicalObject((("text", '\0"\\\nÿé𝄞'),))
    assert (
        compiled._canonical_bytes(text, decoder.lower, decoder.budget)
        == b'{"text":"\\u0000\\"\\\\\\n\\u00ff\\u00e9\\ud834\\udd1e"}\n'
    )
    empty = compiled.LogicalObject(
        (("array", ()), ("bool", True), ("object", compiled.LogicalObject(())))
    )
    assert (
        compiled._canonical_bytes(empty, decoder.lower, decoder.budget)
        == b'{"array":[],"bool":true,"object":{}}\n'
    )


@pytest.mark.parametrize("change", ("reuse", "gap", "empty", "trailing", "extra_row"))
def test_cursor_exhaustion_controls(change: str) -> None:
    record = sample()
    record["full_plan"]["scope"] = [3, 4]
    f, expected = built(record)
    root = f.table_offsets[46]
    if change in ("reuse", "gap"):
        original = unpack_from("<I", f.data, root + 24)[0]
        f.put(root + 24, "I", original - 1 if change == "reuse" else original + 1)
    elif change == "empty":
        f.put(f.table_offsets[43] + 176, "I", 0)
    else:
        tag = 1 if change == "trailing" else 2
        offset = 0x20060 + (tag - 1) * 56
        count = unpack_from("<Q", f.data, offset + 8)[0] + 1
        size = SIZES[tag]
        f.put(offset + 8, "5Q", count, size, count * size, size, count * size)
        f.put(f.local_symbols[_tables()[tag - 1][1]] + 16, "Q", count * size)
        if change == "extra_row":
            old = f.table_offsets[1]
            new = 0xF800
            f.data[new : new + count * size] = f.data[
                old : old + (count - 1) * size
            ] + bytes(size)
            f.put(f.local_symbols["uints"] + 8, "Q", BASE + new)
            f.put(0x1000 + 24 + 16, "q", BASE + new)
    bad(f, expected, "table_bounds")


@pytest.mark.parametrize("tag,name,native,offset,desc", _fields())
def test_every_field_size_preserving_mutation(
    tag: int, name: str, native: str, offset: int, desc: str
) -> None:
    decoder = private_rows(tag, sample(tag))
    row = decoder.row_span(tag, 0)
    changed = bytearray(decoder.raw)
    reason: str | None
    if desc.startswith(("o:", "v:", "v0:")) or desc == "b":
        pack_into("<Q", changed, row[0] + offset, 100)
        reason = "logical_shape"
    elif desc in ("u", "i") or desc.startswith(("n:", "end:")):
        current = unpack_from("<Q", changed, row[0] + offset)[0]
        pack_into("<Q", changed, row[0] + offset, current + 1)
        reason = "logical_shape" if desc == "i" or desc.startswith("n:") else None
    else:
        pack_into("<I", changed, row[0] + offset, 0xFFFFFFFF)
        reason = "table_bounds"
    mutated = replace(decoder, raw=memoryview(bytes(changed)))
    if reason is not None:
        with pytest.raises(compiled._DecodeRefusal) as error:
            mutated.decode_row(tag, 0, 1)
        assert error.value.result.reason == reason
    else:
        assert thaw(mutated.decode_row(tag, 0, 1)) != sample(tag)


@pytest.mark.parametrize(
    "tag,name,native,offset,desc", [f for f in _fields() if f[4].startswith("r:")]
)
@pytest.mark.parametrize("count", (0, 2))
def test_record_reference_counts(
    tag: int, name: str, native: str, offset: int, desc: str, count: int
) -> None:
    decoder = private_rows(tag, sample(tag))
    row = decoder.row_span(tag, 0)
    raw = bytearray(decoder.raw)
    pack_into("<I", raw, row[0] + offset + 4, count)
    with pytest.raises(compiled._DecodeRefusal) as error:
        replace(decoder, raw=memoryview(bytes(raw))).decode_row(tag, 0, 1)
    assert error.value.result.reason == (
        "logical_shape" if count == 0 else "table_bounds"
    )


@pytest.mark.parametrize("value", ("A" * 64, "a" * 63, "a" * 65, "a" * 63 + "\0"))
def test_digest_text_shape(value: str) -> None:
    decoder = private_rows(9, {"bytes": 0, "sha256": value})
    with pytest.raises(compiled._DecodeRefusal) as error:
        decoder.decode_row(9, 0, 1)
    assert error.value.result.reason == "logical_shape"


@pytest.mark.parametrize("value", ("", "00" * 16))
def test_witness_text_length(value: str) -> None:
    record = sample(19)
    record["witness_hex"] = value
    decoder = private_rows(19, record)
    with pytest.raises(compiled._DecodeRefusal) as error:
        decoder.decode_row(19, 0, 1)
    assert error.value.result.reason == "logical_shape"


@pytest.mark.parametrize("value", ("Return", "ret", "return\0"))
def test_exact_literal(value: str) -> None:
    decoder = private_rows(18, {"kind": value})
    with pytest.raises(compiled._DecodeRefusal) as error:
        decoder.decode_row(18, 0, 1)
    assert error.value.result.reason == "logical_shape"


def test_absent_and_present_empty_option_after_byte_cursor() -> None:
    for version in (None, ""):
        record = {
            "needed_library": None,
            "symbol": "abcdefg",
            "version": version,
            "version_hidden": False,
        }
        decoder = private_rows(14, record)
        row = decoder.row_span(14, 0)
        assert unpack_from("<II", decoder.raw, row[0] + 32) == (
            (0, 0) if version is None else (7, 0)
        )
        assert thaw(decoder.decode_row(14, 0, 1)) == record
        assert decoder.state.cursors[0] == 7


def test_complete_comparison_detects_unused_metadata_and_order() -> None:
    record = sample()
    record["full_plan"]["scope"] = [1, 2]
    record["scope"]["gap_dispositions"] = [sample(40)]
    record["scope"]["gap_dispositions"][0]["disposition"] = {
        "kind": "metadata_only",
        "reason": "old",
    }
    _, expected = built(record)
    record["scope"]["gap_dispositions"][0]["disposition"]["reason"] = "new"
    f, _ = built(record)
    bad(f, expected, "logical_mismatch")
    record["scope"]["gap_dispositions"][0]["disposition"]["reason"] = "old"
    record["full_plan"]["scope"].reverse()
    f, _ = built(record)
    bad(f, expected, "logical_mismatch")


def test_witness_and_u1_refusal_order(monkeypatch: pytest.MonkeyPatch) -> None:
    f, expected = built()
    f.data[0x2000] ^= 1
    f.put(0x20060, "Q", 0)
    bad(f, expected, "directory_contract")
    f, expected = built()
    f.data[0x2000] ^= 1

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Logical traversal started.")

    monkeypatch.setattr(compiled._Decoder, "root", forbidden)
    bad(f, expected, "layout_mismatch")


def test_profile_and_zero_allowance_precede_u1(monkeypatch: pytest.MonkeyPatch) -> None:
    f, expected = built()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("U1 started.")

    monkeypatch.setattr(elf, "read_collector_elf", forbidden)
    for profile, reason in ((object(), "input_type"), ("unknown", "layout_mismatch")):
        result = compiled._readback(
            bytes(f.data), expected=expected, profile=cast(layout.ProfileId, profile)
        )
        assert isinstance(result, elf.InspectionRejected) and result.reason == reason
    bad(
        f,
        expected,
        "work_limit",
        replace(elf.InspectionLimits(), scanned_bytes=128 + 2 * len(PROFILES[62])),
    )


def test_preflight_limit_failure_before_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    f, expected = built()
    f.put(f.table_offsets[10], "Q", 0)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A row was allocated before preflight.")

    monkeypatch.setattr(compiled._Decoder, "decode_row", forbidden)
    bad(f, expected, "input_limit")


def test_shared_uint_table_has_no_route_specific_cap() -> None:
    record = sample()
    record["full_plan"]["scope"] = list(range(50))
    record["scope"]["limits"]["route_entries"] = 1
    record["transport_limits"]["route_path_positions"] = 1
    record["transport_limits"]["route_memberships"] = 1
    good(*built(record))


def test_pure_readback_external_operations_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins
    import io
    import os
    import socket
    import subprocess
    import time

    f, expected = built()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("External operation during readback.")

    with monkeypatch.context() as guard:
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
            guard.setattr(owner, name, forbidden)
        result = read(f, expected)
    assert isinstance(result, compiled.LogicalReadback)


def test_actual_import_closure(tmp_path: Path) -> None:
    import subprocess
    import sys

    f, expected = built()
    binary = tmp_path / "input.bin"
    logical = tmp_path / "expected.json"
    binary.write_bytes(bytes(f.data))
    logical.write_bytes(expected.logical_raw)
    prefix = tmp_path / "absent-bytecode"
    root = Path(__file__).resolve().parents[1]
    script = r"""
import builtins, hashlib, importlib, json, pathlib, sys
raw = pathlib.Path(sys.argv[1]).read_bytes()
expected_raw = pathlib.Path(sys.argv[2]).read_bytes()
original = builtins.__import__
allowed = {'phoenix', 'phoenix.observe', 'phoenix.observe.collector_elf',
           'phoenix.observe.collector_layout', 'phoenix.observe.collector_compiled'}
def checked(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split('.')[0] in {'ctypes', 'subprocess', 'socket'}:
        raise AssertionError('Forbidden dependency')
    if name.startswith('phoenix') and name not in allowed:
        raise AssertionError('Forbidden product import')
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = checked
module = importlib.import_module('phoenix.observe.collector_compiled')
expectation = module.ExpectedCollector(expected_raw, '22'*32, '33'*32)
result = module._readback(raw, expected=expectation,
                          profile='linux-x86_64-lp64-le-rela-1')
assert isinstance(result, module.LogicalReadback), result
assert result.logical_raw == expected_raw
closure = {}
for name, loaded in tuple(sys.modules.items()):
    if name == 'phoenix' or name.startswith('phoenix.'):
        path = pathlib.Path(loaded.__file__).resolve()
        closure[name] = [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
assert set(closure) == allowed
print(json.dumps(closure))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-S", "-c", script, str(binary), str(logical)],
        cwd=root,
        env={
            "PYTHONPATH": str(root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(prefix),
            "TMPDIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    for name, (path, digest) in json.loads(result.stdout).items():
        expected_path = root.joinpath(*name.split("."))
        expected_path = (
            expected_path / "__init__.py"
            if name in ("phoenix", "phoenix.observe")
            else expected_path.with_suffix(".py")
        )
        assert path == str(expected_path)
        assert digest == sha256(expected_path.read_bytes()).hexdigest()
    assert not prefix.exists()


def routed_record() -> Any:
    record = sample()
    scope = record["scope"]
    route_a, route_b = sample(28), sample(28)
    route_a.update(
        entries=[0x140, 0x148], instruction_path=[0x140, 0x148], terminal=0x148
    )
    route_b.update(entries=[0x148], instruction_path=[0x148], terminal=0x148)
    route_b["binding_sha256"] = "b" * 64
    guards = [sample(35), sample(35)]
    for i, address in enumerate((0x140, 0x148)):
        guards[i].update(
            address=address,
            owner=address,
            rule={
                "kind": "transit_instruction",
                "positions": [["a" * 64, 0]]
                if i == 0
                else [["a" * 64, 1], ["b" * 64, 0]],
            },
        )
    scope.update(routes=[route_a, route_b], guard_instructions=guards)
    return record


def test_shared_route_suffix_and_positions() -> None:
    record = routed_record()
    result = good(*built(record))
    actual = json.loads(result.logical_raw)
    assert actual["scope"]["guard_instructions"][1]["rule"]["positions"] == [
        ["a" * 64, 1],
        ["b" * 64, 0],
    ]
    assert actual["scope"]["routes"][1]["instruction_path"] == [0x148]


@pytest.mark.parametrize(
    "limit,exact",
    (("route_path_positions", 3), ("route_memberships", 3), ("routes", 2)),
)
def test_call_wide_route_limits(limit: str, exact: int) -> None:
    record = routed_record()
    record["transport_limits"][limit] = exact
    good(*built(record))
    record["transport_limits"][limit] -= 1
    bad(*built(record), "input_limit")


@pytest.mark.parametrize(
    "limit,exact",
    (
        ("thunk_neutral_instructions", 2),
        ("thunk_neutral_bytes", 5),
        ("route_entries", 1),
    ),
)
def test_neutral_groups_and_lower_caps(limit: str, exact: int) -> None:
    record = sample()
    guards = [sample(35) for _ in range(3)]
    for i, size in enumerate((3, 2, 1)):
        guards[i].update(address=0x140 + 8 * i, owner=0x140, witness_hex="90" * size)
    route = sample(28)
    route.update(
        entries=[0x140], instruction_path=[0x140, 0x148, 0x150], terminal=0x150
    )
    record["scope"].update(routes=[route], guard_instructions=guards)
    record["scope"]["limits"][limit] = exact
    good(*built(record))
    if exact > 1:
        record["scope"]["limits"][limit] -= 1
        bad(*built(record), "input_limit")


@pytest.mark.parametrize(
    "change", ("missing", "duplicate", "empty", "start", "trailing")
)
def test_route_owner_group_refusals(change: str) -> None:
    record = routed_record()
    scope = record["scope"]
    if change == "missing":
        scope["guard_instructions"].pop()
    elif change == "duplicate":
        scope["guard_instructions"][1]["address"] = 0x140
    elif change == "empty":
        scope["guard_instructions"][0]["owner"] = 0
    elif change == "start":
        scope["routes"][0]["entries"][0] = 0
    else:
        scope["routes"][0]["entries"].pop()
    bad(*built(record), "logical_shape")


@pytest.mark.parametrize(
    "where,field,cap_path",
    (
        ("full_plan", "sites", ("scope", "limits", "full_plan_sites")),
        ("full_plan", "gaps", ("transport_limits", "gap_records")),
        ("scope", "users", ("transport_limits", "users")),
        ("scope", "omitted", ("transport_limits", "omissions")),
        ("scope", "gap_dispositions", ("transport_limits", "gap_records")),
        ("scope", "guard_instructions", ("scope", "limits", "guarded_instructions")),
        ("image", "segments", ("transport_limits", "elf_segments")),
    ),
)
def test_lower_inventory_caps(
    where: str, field: str, cap_path: tuple[str, ...]
) -> None:
    record = sample()
    owner = {"full_plan": 20, "scope": 44, "image": 46}[where]
    descriptor = next(f[4] for f in SPECS[owner] if f[1] == field)
    target = NAMES[descriptor[2:]]
    record[where][field] = [sample(target), sample(target)]
    if target == 35:
        record[where][field][1]["address"] = 1
    cap = record
    for key in cap_path[:-1]:
        cap = cap[key]
    cap[cap_path[-1]] = 2
    good(*built(record))
    cap[cap_path[-1]] = 1
    bad(*built(record), "input_limit")


@pytest.mark.parametrize("part", ("root", "full_plan", "scope"))
def test_caps_stop_before_large_string_escape(
    part: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoder = private_rows(47, sample())
    leaf = compiled.LogicalObject((("a", "Z" * 10000),))
    root = leaf if part == "root" else compiled.LogicalObject(((part, leaf),))
    lower = decoder.lower
    if part == "root":
        lower = replace(lower, transport={**lower.transport, "data_bytes": 30})
    else:
        lower = replace(
            lower,
            capture={
                **lower.capture,
                "full_plan_bytes" if part == "full_plan" else "scope_bytes": 30,
            },
        )
    original = json.dumps
    visits = 0

    def checked(value: Any, **kwargs: Any) -> str:
        nonlocal visits
        if value == "Z":
            visits += 1
            assert visits <= 30
        return original(value, **kwargs)

    monkeypatch.setattr(json, "dumps", checked)
    with pytest.raises(compiled._DecodeRefusal) as error:
        compiled._canonical_bytes(root, lower, decoder.budget)
    assert error.value.result.reason == "record_limit"
    assert 0 < visits < 30


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("placement", (0, 128))
@pytest.mark.parametrize("versions", (False, True))
def test_u1_debit_formula(
    machine: elf.Machine,
    placement: int,
    versions: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, _ = built(machine=machine, placement=placement)
    if not versions:
        f.section(".gnu.version", 4, "I", 1)
        f.put(f.dynamic_slots[0x6FFFFFF0][0], "qQ", 100, 0)
    observed = []
    original = elf._Reader.read

    def counted(reader: elf._Reader) -> elf.CollectorElf:
        result = original(reader)
        observed.append((reader.budget.scanned, reader.budget.scalars))
        return result

    monkeypatch.setattr(elf._Reader, "read", counted)
    view = f.inspect()
    assert isinstance(view, elf.CollectorElf)
    budget = compiled.WorkBudget(elf.InspectionLimits())
    compiled._debit_u1(view, budget)
    assert budget.scalars == observed[0][1]
    assert budget.scanned >= observed[0][0]
    assert isinstance(
        f.inspect(
            replace(
                elf.InspectionLimits(),
                scanned_bytes=observed[0][0],
                scalar_visits=observed[0][1],
            )
        ),
        elf.CollectorElf,
    )


@pytest.mark.parametrize(
    "kind,reason",
    (
        ("format", "unsupported_elf"),
        ("truncated", "malformed_elf"),
        ("mapping", "ambiguous_mapping"),
        ("missing", "symbol_missing"),
        ("duplicate", "symbol_ambiguous"),
        ("dynamic", "dynamic_contract"),
        ("overlap", "storage_overlap"),
    ),
)
def test_u1_refusals_pass_through(kind: str, reason: str) -> None:
    f, expected = built()
    if kind == "format":
        f.data[4] = 1
    elif kind == "truncated":
        del f.data[-4096:]
    elif kind == "mapping":
        f.program(0, 4, 5)
    elif kind == "missing":
        f.put(f.local_symbols["uints"], "I", 0)
    elif kind == "duplicate":
        name = unpack_from("<I", f.data, f.local_symbols["uints"])[0]
        f.put(f.local_symbols["strings"], "I", name)
    elif kind == "dynamic":
        f.dynamic(4, 0)
    else:
        f.put(f.local_symbols["strings"] + 8, "Q", BASE + f.table_offsets[1])
        f.put(0x1000 + 2 * 24 + 16, "q", BASE + f.table_offsets[1])
    bad(f, expected, reason)


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize(
    "family", ("shared", "omitted", "explicit", "guards", "neutral")
)
def test_public_complete_families(machine: elf.Machine, family: str) -> None:
    from test_observe_collector_data import accepted, extra_users, shared, source
    from test_observe_scope import control
    from test_transfer_evidence import thunk_case

    if family == "shared":
        prepared = source(*shared())
    elif family == "omitted":
        prepared = source(*extra_users())
    elif family == "explicit":
        prepared = source(explicit=True)
    elif family == "guards":
        prepared = source(*control(b"\x75\x03", "CBRANCH"))
    else:
        binary, document = thunk_case(("f30f1efa", "90", "6690"))
        prepared = source(bytes(binary), document)
    data = accepted(prepared.prepare())
    record = json.loads(data.to_bytes())
    result = good(*built(record, machine))
    actual = json.loads(result.logical_raw)
    for key, raw in (
        ("full_plan", data.full_plan.to_bytes()),
        ("scope", data.scope.to_bytes()),
    ):
        assert (
            json.dumps(actual[key], sort_keys=True, separators=(",", ":")) + "\n"
        ).encode() == raw


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("tag", range(1, 48))
@pytest.mark.parametrize(
    "component", ("name", "duplicate", "value", "short", "long", "type", "binding")
)
def test_all_local_symbol_contracts(
    machine: elf.Machine, tag: int, component: str
) -> None:
    f, expected = built(machine=machine)
    name = _tables()[tag - 1][1]
    symbol = f.local_symbols[name]
    if component == "name":
        f.put(symbol, "I", 0)
        reason = "symbol_missing"
    elif component == "duplicate":
        f.put(
            f.static_symbols["external_function"],
            "I",
            unpack_from("<I", f.data, symbol)[0],
        )
        reason = "symbol_ambiguous"
    elif component == "value":
        shifted = f.table_offsets[tag - 1] + 8
        f.put(symbol + 8, "Q", BASE + shifted)
        count = unpack_from("<Q", f.data, 0x20068 + (tag - 1) * 56)[0]
        reason = (
            "table_bounds"
            if count == 0 and any(f.data[shifted : shifted + SIZES[tag]])
            else "relocation_contract"
        )
    elif component in ("short", "long"):
        size = unpack_from("<Q", f.data, symbol + 16)[0]
        f.put(symbol + 16, "Q", size + (1 if component == "long" else -1))
        reason = "export_contract"
    elif component == "type":
        f.put(symbol + 4, "B", 2)
        reason = "export_contract"
    else:
        f.put(symbol + 4, "B", 17)
        reason = "malformed_elf"
    bad(f, expected, reason)


@pytest.mark.parametrize("machine", (62, 183))
@pytest.mark.parametrize("tag", range(1, 48))
@pytest.mark.parametrize("component", ("missing", "end", "shifted"))
def test_remaining_pointer_contracts(
    machine: elf.Machine, tag: int, component: str
) -> None:
    f, expected = built(machine=machine)
    offset = 0x1000 + (tag - 1) * 24
    if component == "missing":
        f.put(offset, "Q", BASE + 0x30008)
    elif component == "shifted":
        f.put(offset, "Q", BASE + 0x20091 + (tag - 1) * 56)
    else:
        storage = unpack_from("<Q", f.data, 0x20060 + (tag - 1) * 56 + 40)[0]
        f.put(offset + 16, "q", BASE + f.table_offsets[tag - 1] + storage)
    bad(f, expected, "relocation_contract")


def test_unused_static_names_do_not_define_tables() -> None:
    f, expected = built()
    static = f.static_symbols["external_function"]
    name_offset = unpack_from("<I", f.data, static)[0]
    f.data[0x31000 + name_offset : 0x31000 + name_offset + 17] = b"phoenix_unrelated"
    good(f, expected)


def test_physical_row_and_inspection_reductions() -> None:
    f, expected = built()
    result = good(f, expected)
    physical = 2728 + 40168 + sum(t.storage_bytes for t in result.directory.tables)
    rows = sum(t.count for t in result.directory.tables[1:])
    for name, minimum in (
        ("physical_data_bytes", physical),
        ("nonbyte_rows", rows),
        ("plugin_bytes", len(f.data)),
        ("program_headers", 6),
        ("sections", 16),
        ("symbols", 59),
        ("dynamic_entries", 19),
        ("relocations", 49),
        ("hash_words", 9),
    ):
        good(f, expected, replace(elf.InspectionLimits(), **{name: minimum}))
        bad(
            f,
            expected,
            "input_limit",
            replace(elf.InspectionLimits(), **{name: minimum - 1}),
        )
    limits = replace(elf.InspectionLimits(), inspection_bytes=1)
    assert good(f, expected, limits).limits == limits


def test_preflight_does_not_claim_ownership() -> None:
    f, expected = built()
    result = good(f, expected)
    budget = compiled.WorkBudget(elf.InspectionLimits())
    lower = compiled._peek_lower_limits(
        bytes(f.data), result.directory, layout._definition(PROFILES[62]), budget
    )
    state = compiled.CursorState()
    decoder = compiled._Decoder(
        memoryview(bytes(f.data)),
        layout._definition(PROFILES[62]),
        result.directory,
        budget,
        state,
        lower,
    )
    used = budget.scalars
    decoder.root()
    assert used == 41
    assert budget.scalars > used
    assert state.cursors == [t.count for t in result.directory.tables]


def test_each_scalar_fits_owning_row() -> None:
    budget = compiled.WorkBudget(elf.InspectionLimits())
    with pytest.raises(compiled._DecodeRefusal) as error:
        compiled._cell(memoryview(bytes(32)), 0, 4, 0, 8, budget)
    assert error.value.result.reason == "table_bounds"
    assert budget.scanned == budget.scalars == 0


def test_hash_does_not_start_after_budget_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, expected = built()
    result = good(f, expected)
    budget = compiled.WorkBudget(
        replace(elf.InspectionLimits(), scanned_bytes=len(result.logical_raw))
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Hash started after exhausted comparison allowance.")

    monkeypatch.setattr(compiled, "sha256", forbidden)
    with pytest.raises(compiled._DecodeRefusal) as error:
        compiled._compare_complete(
            result.logical_raw, expected, result.directory, budget
        )
    assert error.value.result.reason == "work_limit"


def test_f1_and_o1_are_still_applied() -> None:
    from test_observe_collector_elf import (
        executable_section_fixture,
        unsectioned_destination_fixture,
    )

    for machine in (62, 183):
        expected = compiled.ExpectedCollector(b"{}\n", "22" * 32, "33" * 32)
        for kind in ("file", "execute", "zero", "installer_page"):
            bad(
                unsectioned_destination_fixture(machine, kind),
                expected,
                "ambiguous_mapping",
            )
        bad(
            executable_section_fixture(machine, 0, 8, 6, 8),
            expected,
            "relocation_contract",
        )


def test_empty_load_does_not_hide_file_backed_table() -> None:
    f, expected = built()
    f.put(56, "H", 7)
    offset = f.table_offsets[0]
    pack_into("<IIQQQQQQ", f.data, 64 + 6 * 56, 1, 4, offset, BASE + offset, 0, 0, 0, 8)
    assert isinstance(f.inspect(), elf.CollectorElf)
    good(f, expected)


@given(st.text(max_size=80))
@settings(max_examples=75, deadline=None)
def test_text_round_trip_property(text: str) -> None:
    assert decode_private(3, text) == text
    decoder = private_rows(3, text)
    value = compiled.LogicalObject((("text", text),))
    actual = compiled._canonical_bytes(value, decoder.lower, decoder.budget)
    assert (
        actual
        == (
            json.dumps({"text": text}, ensure_ascii=True, separators=(",", ":")) + "\n"
        ).encode()
    )


@given(st.binary(max_size=4096))
@settings(max_examples=75, deadline=None)
def test_bounded_arbitrary_plugin_bytes(raw: bytes) -> None:
    result = compiled._readback(
        raw,
        expected=compiled.ExpectedCollector(b"{}\n", "22" * 32, "33" * 32),
        profile="linux-x86_64-lp64-le-rela-1",
    )
    assert isinstance(result, elf.InspectionRejected)
    assert len(result.detail) <= 512


@given(st.lists(st.integers(min_value=0, max_value=(1 << 64) - 1), max_size=10))
@settings(max_examples=50, deadline=None)
def test_ordered_uint_slice_property(values: list[int]) -> None:
    value = sample(19)
    value["continuation_of"] = values
    assert decode_private(19, value) == value


def test_one_immutable_input_and_one_public_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, expected = built()
    raw = bytes(f.data)
    original = elf.read_collector_elf
    seen = []

    def checked(
        actual: bytes, *, machine: elf.Machine, limits: elf.InspectionLimits
    ) -> elf.CollectorElf | elf.InspectionRejected:
        assert actual is raw
        seen.append(limits)
        return original(actual, machine=machine, limits=limits)

    monkeypatch.setattr(elf, "read_collector_elf", checked)
    limits = replace(elf.InspectionLimits(), symbol_name_bytes=64, inspection_bytes=1)
    result = compiled._readback(
        raw, expected=expected, profile="linux-x86_64-lp64-le-rela-1", limits=limits
    )
    assert isinstance(result, compiled.LogicalReadback)
    assert result.elf.raw is raw
    assert len(seen) == 1
    assert seen[0].scanned_bytes < limits.scanned_bytes
    assert seen[0].symbol_name_bytes == 64 and seen[0].inspection_bytes == 1
    assert result.limits == limits
    fake = replace(result.elf, raw=b"fabricated")
    rejection = compiled._readback(
        cast(bytes, fake), expected=expected, profile="linux-x86_64-lp64-le-rela-1"
    )
    assert (
        isinstance(rejection, elf.InspectionRejected)
        and rejection.reason == "input_type"
    )
    assert len(seen) == 1


@pytest.mark.parametrize("machine", (62, 183))
def test_all_lower_values_are_retained(machine: elf.Machine) -> None:
    record = sample()
    for limits in (
        record["transport_limits"],
        record["full_plan"]["limits"],
        record["scope"]["limits"],
    ):
        for name, value in limits.items():
            if name != "snapshot_bytes":
                limits[name] = value - 1
    good(*built(record, machine))


@pytest.mark.parametrize("part", ("full_plan", "scope"))
def test_snapshot_width_cannot_be_lowered(part: str) -> None:
    record = sample()
    record[part]["limits"]["snapshot_bytes"] = 7
    bad(*built(record), "input_limit")


def test_request_users_and_route_entries_lower_bounds() -> None:
    record = routed_record()
    record["scope"]["request"]["users"] = [0x140, 0x148]
    record["transport_limits"]["users"] = 2
    record["scope"]["limits"]["route_entries"] = 2
    good(*built(record))
    record["transport_limits"]["users"] = 1
    bad(*built(record), "input_limit")
    record["transport_limits"]["users"] = 2
    record["scope"]["limits"]["route_entries"] = 1
    bad(*built(record), "input_limit")


@pytest.mark.parametrize(
    "owner,offset,child,limit_group,limit_name,cap",
    (
        (20, 64, 19, "capture", "full_plan_sites", 1),
        (23, 40, 2, "transport", "users", 1),
        (28, 16, 2, "capture", "route_entries", 1),
        (46, 0, 8, None, None, 65536),
    ),
)
def test_count_refusal_precedes_child_rows(
    owner: int,
    offset: int,
    child: int,
    limit_group: str | None,
    limit_name: str | None,
    cap: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoder = private_rows(owner, sample(owner))
    lower = decoder.lower
    if limit_group is not None:
        assert limit_name is not None
        lower = replace(
            lower,
            **{limit_group: {**getattr(lower, limit_group), limit_name: cap}},
        )
    raw = bytearray(decoder.raw)
    row = decoder.row_span(owner, 0)
    pack_into("<I", raw, row[0] + offset + 4, cap + 1)
    decoder = replace(decoder, raw=memoryview(bytes(raw)), lower=lower)
    original = compiled._Decoder.decode_row

    def checked(
        reader: compiled._Decoder, tag: int, index: int, depth: int
    ) -> compiled.LogicalValue:
        assert tag != child, "A child row was decoded before its count limit."
        return original(reader, tag, index, depth)

    monkeypatch.setattr(compiled._Decoder, "decode_row", checked)
    with pytest.raises(compiled._DecodeRefusal) as error:
        decoder.decode_row(owner, 0, 1)
    assert error.value.result.reason == "input_limit"


@pytest.mark.parametrize("machine", (62, 183))
def test_same_width_geometry_size_swap(machine: elf.Machine) -> None:
    record = sample()
    record["geometry"] = {
        "executable_file_start": 10,
        "executable_file_end_exclusive": 13,
        "load_memory_start": 20,
        "load_memory_end_exclusive": 25,
    }
    f, expected = built(record, machine)
    offset = f.table_offsets[9]
    f.data[offset + 8 : offset + 16], f.data[offset + 24 : offset + 32] = (
        f.data[offset + 24 : offset + 32],
        f.data[offset + 8 : offset + 16],
    )
    bad(f, expected, "logical_mismatch")


def test_same_width_directory_length_swap() -> None:
    f, expected = built()
    entry = 0x20060 + 56
    assert unpack_from("<Q", f.data, entry + 24)[0] == 0
    assert unpack_from("<Q", f.data, entry + 40)[0] == 8
    f.data[entry + 24 : entry + 32], f.data[entry + 40 : entry + 48] = (
        f.data[entry + 40 : entry + 48],
        f.data[entry + 24 : entry + 32],
    )
    bad(f, expected, "directory_contract")


@pytest.mark.parametrize("kind", ("memberships", "users"))
def test_same_width_ordered_record_swap(kind: str) -> None:
    record = routed_record()
    site = sample(19)
    site["continuation_of"] = [0x140, 0x148]
    record["full_plan"]["sites"] = [site]
    _, expected = built(record)
    if kind == "memberships":
        record["scope"]["guard_instructions"][1]["rule"]["positions"].reverse()
    else:
        site["continuation_of"].reverse()
    f, _ = built(record)
    bad(f, expected, "logical_mismatch")


def test_unconsumed_alignment_gap_is_not_logical_state() -> None:
    f, expected = built()
    before = good(f, expected)
    assert f.table_offsets[0] >= 0xBD00
    assert 0x2000 + 40168 < 0xBCFF < f.table_offsets[0]
    f.data[0xBCFF] ^= 1
    after = good(f, expected)
    assert before.logical_raw == after.logical_raw
    assert before.elf.raw != after.elf.raw
    assert sha256(before.elf.raw).digest() != sha256(after.elf.raw).digest()


def test_shared_string_table_has_no_route_specific_cap() -> None:
    decoder = private_rows(25, {"kind": "transit", "route_ids": ["a" * 64, "b" * 64]})
    lower = replace(
        decoder.lower,
        transport={**decoder.lower.transport, "route_memberships": 1, "routes": 1},
    )
    actual = replace(decoder, lower=lower).decode_row(25, 0, 1)
    assert thaw(actual) == {"kind": "transit", "route_ids": ["a" * 64, "b" * 64]}


def test_image_dynamic_installed_count_boundary() -> None:
    decoder = private_rows(46, sample(46))
    decoder.count_limit(46, "dynamic", 65536)
    with pytest.raises(compiled._DecodeRefusal) as error:
        decoder.count_limit(46, "dynamic", 65537)
    assert error.value.result.reason == "input_limit"
