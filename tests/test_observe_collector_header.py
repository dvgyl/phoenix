"""Public synthetic header controls. No target or compiler is executed."""

import io
import json
import re
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, fields, replace
from hashlib import sha256
from pathlib import Path
from struct import pack_into
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_observe_collector_data import (
    accepted,
    extra_users,
    shared,
    source,
    thaw,
)
from test_observe_scope import control
from test_recovery_u1 import fixture, loc, op, operand
from test_transfer_evidence import relative, thunk_case, write_thunk

from phoenix.observe import collector_header as writer
from phoenix.observe import collector_header_read as reader
from phoenix.observe.collector_data import (
    CollectorData,
    CollectorRejected,
    Geometry,
    Original,
    TransportLimits,
)
from phoenix.observe.collector_header import (
    GeneratedHeader,
    HeaderLimits,
    render_header,
)
from phoenix.observe.collector_header_read import HeaderReadError, read_header
from phoenix.observe.plan import Call
from phoenix.observe.scope import (
    CaptureLimits,
    MetadataOnly,
    ScopeSelection,
    Transit,
    TransitInstruction,
)
from phoenix.recover.addresses import ElfVA


def header(
    data: CollectorData, limits: HeaderLimits = HeaderLimits()
) -> GeneratedHeader:
    result = render_header(data, limits=limits)
    assert isinstance(result, GeneratedHeader), result
    return result


def repin(data: CollectorData, *, scope: ScopeSelection | None = None) -> CollectorData:
    selection = scope if scope is not None else data.scope
    return replace(data, scope=selection, scope_sha256=selection.sha256)


def complete(data: CollectorData) -> GeneratedHeader:
    result = header(data)
    decoded = read_header(result.raw)
    assert decoded.record == data.record()
    assert thaw(decoded.record) == json.loads(data.to_bytes())
    assert decoded.counts == result.counts
    assert decoded.initializer_bytes == result.initializer_bytes
    assert decoded.logical_data_sha256 == result.logical_data_sha256 == data.sha256
    return result


def table_source(raw: bytes, name: str) -> bytes:
    match = re.search(
        rb"static const [^\n]+ phoenix_" + name.encode() + rb"\[[^\n]+\n.*?\n};\n",
        raw,
        re.S,
    )
    assert match is not None
    return match[0]


def change_row(raw: bytes, table: str, old: bytes, new: bytes) -> bytes:
    block = table_source(raw, table)
    changed = block.replace(old, new, 1)
    assert changed != block
    return raw.replace(block, changed, 1)


@pytest.mark.parametrize("explicit", (False, True))
@pytest.mark.parametrize(
    "which", ("default", "shared", "omitted", "thunks", "guards", "bad_import")
)
def test_complete_logical_round_trip(which: str, explicit: bool) -> None:
    if which == "shared":
        supplied = source(*shared(), explicit=explicit)
    elif which == "omitted":
        supplied = source(*extra_users(), explicit=explicit)
    elif which == "thunks":
        thunk_binary, document = thunk_case(("f30f1efa", "90", "6690"))
        supplied = source(bytes(thunk_binary), document, explicit=explicit)
    elif which in ("guards", "bad_import"):
        binary, document = control(b"\x75\x03", "CBRANCH")
        if which == "bad_import":
            document["imports"][0]["name"] = "fread"
        supplied = source(binary, document, explicit=explicit)
    else:
        supplied = source(explicit=explicit)
    data = accepted(supplied.prepare())
    generated = complete(data)
    assert generated.relative_name == "generated/collector_data.h"
    assert generated.raw.decode("ascii").encode("ascii") == generated.raw
    assert b"\r" not in generated.raw and generated.raw.endswith(b"};\n")
    assert all(line.endswith(b"\n") for line in generated.raw.splitlines(keepends=True))
    assert b"static const uint8_t phoenix_bytes[" in generated.raw
    assert b'"fwrite"' not in generated.raw
    for forbidden in (
        b"__DATE__",
        b"__TIME__",
        b"#line",
        b"__asm",
        b"/Volumes/",
        b"/Users/",
    ):
        assert forbidden not in generated.raw


def test_shared_roles_imports_routes_and_complete_directory() -> None:
    data = accepted(source(*shared()).prepare())
    result = complete(data)
    record = cast(dict[str, Any], thaw(read_header(result.raw).record))
    plan, scope = record["full_plan"], record["scope"]
    assert plan["sites"][1]["continuation_of"] == [0x100]
    assert plan["sites"][1]["transfer"]["kind"] == "direct_call"
    assert len(scope["routes"]) == 2
    assert [r["call_site"] for r in scope["routes"]] == [0x100, 0x105]
    route_ids = [r.sha256 for r in data.scope.routes]
    positions = next(
        g["rule"]["positions"]
        for g in scope["guard_instructions"]
        if g["address"] == 0x140
    )
    assert positions == [[identity, 0] for identity in sorted(route_ids)]
    imported = plan["sites"][0]["transfer"]["imported"]
    binding = cast(Call, data.full_plan.sites[0].transfer).imported
    assert binding is not None
    assert imported == json.loads(json.dumps(asdict(binding)))
    assert imported["identity"]["needed_library"] is None
    assert imported["function"] == 0x100100
    assert imported["relocation_file_offset"] == 0xC00
    assert imported["symbol_index"] == 1
    assert scope["request"] == json.loads(json.dumps(asdict(data.scope.request)))
    assert scope["registers"] == [
        [name, 64] for name in ("rdi", "rsi", "rdx", "rcx", "rax", "rsp")
    ]
    assert result.raw.count(b"phoenix_collector_data_v1 = {") == 1
    inventory = result.raw.split(reader.DIRECTORY.encode(), 1)[1]
    for table, count in result.counts:
        assert reader.directory_entry(table, count).encode() in inventory
    assert dict(result.counts)["termination_contract"] == 0
    assert table_source(result.raw, "termination_contract").endswith(b"    {0},\n};\n")
    assert len(result.counts) == len(reader.TABLES)
    assert result.initializer_bytes == reader.DIRECTORY_BYTES + sum(
        count * reader.element_bytes(table) for table, count in result.counts
    )


@pytest.mark.parametrize(
    "data,opcode",
    ((b"\xeb\x03", "BRANCH"), (b"\x75\x03", "CBRANCH"), (b"\xf4", "COPY")),
)
def test_all_active_guard_metadata_survives(data: bytes, opcode: str) -> None:
    binary, document = control(data, opcode)
    original = accepted(source(binary, document).prepare())
    result = complete(original)
    decoded = cast(dict[str, Any], thaw(read_header(result.raw).record))
    assert (
        decoded["scope"]["guard_instructions"]
        == json.loads(original.scope.to_bytes())["guard_instructions"]
    )
    assert (
        decoded["scope"]["gap_dispositions"]
        == json.loads(original.scope.to_bytes())["gap_dispositions"]
    )


def with_text(data: CollectorData, text: str) -> CollectorData:
    gap = data.scope.gap_dispositions[0]
    return repin(
        data,
        scope=replace(
            data.scope,
            gap_dispositions=(
                replace(gap, disposition=MetadataOnly(text)),
                *data.scope.gap_dispositions[1:],
            ),
        ),
    )


@settings(max_examples=20, deadline=None)
@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"]), max_size=25))
def test_utf8_is_exact_data(text: str) -> None:
    data = with_text(accepted(source().prepare()), text)
    complete(data)


@pytest.mark.parametrize(
    "text",
    (
        '\x00"\\\n\xffé𝄞',
        "",
        "/* */ #include <evil.h>",
        "0x00, UINT64_C(0xffffffffffffffff)",
    ),
)
def test_high_bytes_nul_quotes_and_source_tokens_are_data(text: str) -> None:
    data = with_text(accepted(source().prepare()), text)
    result = complete(data)
    decoded = cast(dict[str, Any], thaw(read_header(result.raw).record))
    assert decoded["scope"]["gap_dispositions"][0]["disposition"]["reason"] == text
    assert text.encode("utf-8") not in result.raw or not text


def test_null_optional_fields_and_zero_count_slices() -> None:
    binary, document = fixture()
    document["imports"][0]["name"] = "fread"
    data = accepted(source(binary, document).prepare())
    call = cast(Call, data.full_plan.sites[0].transfer)
    assert call.imported is None and call.import_gaps
    complete(data)
    gap = data.scope.gap_dispositions[0]
    complete(
        repin(
            data,
            scope=replace(
                data.scope,
                gap_dispositions=(
                    replace(gap, elf=None),
                    *data.scope.gap_dispositions[1:],
                ),
            ),
        )
    )


@pytest.mark.parametrize("tag", (-1, -(1 << 63), 0, (1 << 63) - 1))
def test_exact_signed_dynamic_tags(tag: int) -> None:
    binary, document = fixture()
    image = bytearray(binary)
    # Replace an unused tag. This remains public synthetic ELF input.
    pack_into("<qQ", image, 0x800 + 12 * 16, tag, (1 << 64) - 1)
    pack_into("<qQ", image, 0x800 + 13 * 16, 0, 0)
    pack_into("<Q", image, 176 + 32, 14 * 16)
    pack_into("<Q", image, 176 + 40, 14 * 16)
    if tag == 0:
        pack_into("<qQ", image, 0x800 + 12 * 16, 0, 0)
    supplied = source(bytes(image), document)
    data = accepted(supplied.prepare())
    complete(data)
    if tag:
        assert data.image.dynamic[-1] == (tag, (1 << 64) - 1)


@pytest.mark.parametrize("base", (0, 0x400000))
def test_uint64_exclusive_end_uses_checked_size(base: int) -> None:
    binary, document = fixture(base=base)
    image = bytearray(binary)
    image[0x300:0x3A8] = image[64:232]
    pack_into("<Q", image, 32, 0x300)
    pack_into("<H", image, 56, 4)
    pack_into("<IIQQQQQQ", image, 0x3A8, 1, 6, 0x400, 2**64 - 16, 0, 0, 16, 1)
    data = accepted(source(bytes(image), document).prepare())
    assert data.geometry.load_memory_end_exclusive == 2**64
    if base:
        result = complete(data)
        geometry = cast(dict[str, Any], thaw(read_header(result.raw).record))[
            "geometry"
        ]
        assert geometry["load_memory_end_exclusive"] == 2**64
        assert b"UINT64_C(0xffffffffffc00000)" in table_source(result.raw, "geometry")
    else:
        refused = render_header(data)
        assert isinstance(refused, CollectorRejected)
        assert "not representable" in refused.detail


def test_determinism_and_actual_source_pins() -> None:
    data = accepted(source().prepare())
    result = complete(data)
    assert header(data) == result
    assert result.sha256 == sha256(result.raw).hexdigest()
    root = Path(__file__).resolve().parents[1]
    manifest = [
        (
            name,
            len((root / name).read_bytes()),
            sha256((root / name).read_bytes()).hexdigest(),
        )
        for name in (
            "phoenix/observe/collector_header.py",
            "phoenix/observe/collector_header_read.py",
        )
    ]
    assert (
        result.renderer_sha256
        == sha256(
            (json.dumps(manifest, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    )
    assert (
        result.native_source_sha256
        == sha256((root / reader.NATIVE_NAME).read_bytes()).hexdigest()
    )
    with pytest.raises(FrozenInstanceError):
        result.raw = b"changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        read_header(result.raw).record.entries = ()  # type: ignore[misc]


@pytest.mark.parametrize("which", ("renderer", "native"))
def test_source_identity_changes_with_actual_read_bytes(
    which: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = accepted(source().prepare())
    before = header(data)
    original = Path.open
    selected = "collector_header.py" if which == "renderer" else "collector_data_v1.h"

    def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
        stream = original(path, *args, **kwargs)
        if path.name == selected:
            with stream:
                raw = stream.read()
            return io.BytesIO(raw + b"\n")
        return stream

    monkeypatch.setattr(Path, "open", opened)
    after = header(data)
    assert after.raw != before.raw and after.sha256 != before.sha256
    assert after.logical_data_sha256 == before.logical_data_sha256
    assert getattr(
        after, which + "_sha256" if which == "renderer" else "native_source_sha256"
    ) != getattr(
        before, which + "_sha256" if which == "renderer" else "native_source_sha256"
    )


@pytest.mark.parametrize("field", ("source_bytes", "initializer_bytes"))
@pytest.mark.parametrize("bad", (True, False, 1.0, "1", None, 0, -1, "raised"))
def test_header_limits_require_exact_lower_integers(field: str, bad: Any) -> None:
    data = accepted(source().prepare())
    value = getattr(HeaderLimits(), field) + 1 if bad == "raised" else bad
    invalid = replace(HeaderLimits(), **{field: value})
    assert isinstance(render_header(data, limits=invalid), CollectorRejected)
    with pytest.raises(HeaderReadError, match="Invalid reader limits"):
        read_header(header(data).raw, **{field: value})


@pytest.mark.parametrize("field", ("source_bytes", "initializer_bytes"))
def test_exact_boundary_and_one_byte_lower(field: str) -> None:
    data = accepted(source(*shared()).prepare())
    original = header(data)
    boundary = (
        len(original.raw) if field == "source_bytes" else original.initializer_bytes
    )
    assert header(data, replace(HeaderLimits(), **{field: boundary})) == original
    read_header(original.raw, **{field: boundary})
    assert isinstance(
        render_header(data, limits=replace(HeaderLimits(), **{field: boundary - 1})),
        CollectorRejected,
    )
    with pytest.raises(HeaderReadError):
        read_header(original.raw, **{field: boundary - 1})


def bomb(*args: object, **kwargs: object) -> Any:
    raise AssertionError("Large materialization occurred before refusal.")


@pytest.mark.parametrize("field", ("source_bytes", "initializer_bytes"))
def test_lower_caps_refuse_before_table_materialization(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = accepted(source().prepare())
    baseline = header(data)
    boundary = (
        len(baseline.raw) if field == "source_bytes" else baseline.initializer_bytes
    )
    monkeypatch.setattr(writer, "_Tables", bomb)
    monkeypatch.setattr(writer, "_canonical_identity", bomb)
    assert isinstance(
        render_header(data, limits=replace(HeaderLimits(), **{field: boundary - 1})),
        CollectorRejected,
    )


def test_large_tuple_refuses_before_walking_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = accepted(source().prepare())
    # The shared tuple is small. Its repeated child must never be decoded.
    invalid = replace(
        data, image=replace(data.image, dynamic=cast(Any, (object(),) * 1000))
    )
    monkeypatch.setattr(writer, "_Tables", bomb)
    refused = render_header(invalid, limits=HeaderLimits(initializer_bytes=10000))
    assert isinstance(refused, CollectorRejected) and "byte limit" in refused.detail


@pytest.mark.parametrize(
    "field",
    (
        "original_bytes",
        "users",
        "routes",
        "omissions",
        "gap_records",
        "elf_segments",
        "route_path_positions",
        "route_memberships",
        "data_bytes",
    ),
)
def test_inherited_lower_transport_limits_remain_binding(field: str) -> None:
    supplied = source(*extra_users()) if field == "omissions" else source(*shared())
    data = accepted(supplied.prepare())
    if field == "users":
        supplied = source(*extra_users(), users=(0x100, 0x180))
        data = accepted(supplied.prepare())
    if field == "gap_records":
        binary, document = control(b"\x75\x03", "CBRANCH")
        data = accepted(source(binary, document).prepare())
    invalid = replace(
        data, transport_limits=replace(data.transport_limits, **{field: 1})
    )
    assert isinstance(render_header(invalid), CollectorRejected)


@pytest.mark.parametrize("bad", (True, False, 1.0, "1", None, 0, -1, "raised"))
@pytest.mark.parametrize("limit_type", (TransportLimits, CaptureLimits))
def test_every_inherited_limit_is_checked(limit_type: type[Any], bad: Any) -> None:
    data = accepted(source().prepare())
    for item in fields(limit_type):
        value = getattr(limit_type(), item.name) + 1 if bad == "raised" else bad
        limits = replace(limit_type(), **{item.name: value})
        changed = (
            replace(data, transport_limits=limits)
            if limit_type is TransportLimits
            else replace(data, scope=replace(data.scope, limits=limits))
        )
        assert isinstance(render_header(changed), CollectorRejected), item.name


@pytest.mark.parametrize(
    "field",
    (
        "address_proof_sha256",
        "full_plan_sha256",
        "scope_sha256",
        "lift_sha256",
        "policy_implementation_sha256",
    ),
)
def test_direct_records_do_not_bypass_identity_checks(field: str) -> None:
    data = accepted(source().prepare())
    changes: dict[str, Any] = {field: "0" * 64}
    assert isinstance(render_header(replace(data, **changes)), CollectorRejected)


@pytest.mark.parametrize("bad", (True, 1.0, -1, 2**64))
def test_direct_records_do_not_bypass_integer_shapes(bad: Any) -> None:
    data = accepted(source().prepare())
    invalid = replace(data, original=replace(data.original, bytes=bad))
    assert isinstance(render_header(invalid), CollectorRejected)


def test_unknown_record_variant_literal_and_mutable_children_are_refused() -> None:
    data = accepted(source().prepare())
    invalids = (
        replace(data, scope=cast(Any, object())),
        replace(
            data,
            full_plan=replace(
                data.full_plan, sites=cast(Any, list(data.full_plan.sites))
            ),
        ),
        replace(
            data,
            full_plan=replace(
                data.full_plan,
                sites=(replace(data.full_plan.sites[0], transfer=cast(Any, object())),),
            ),
        ),
        replace(
            data,
            scope=replace(
                data.scope,
                request=replace(data.scope.request, policy=cast(Any, "lazy")),
            ),
        ),
        replace(data, geometry=Geometry(cast(Any, True), 2, cast(Any, 1), 2)),
    )
    for invalid in invalids:
        assert isinstance(render_header(invalid), CollectorRejected)


def test_invalid_unicode_and_witness_are_refused_before_encoding() -> None:
    data = accepted(source().prepare())
    gap = data.scope.gap_dispositions[0]
    invalid_text = replace(
        data,
        scope=replace(
            data.scope,
            gap_dispositions=(replace(gap, disposition=MetadataOnly("\ud800")),),
        ),
    )
    assert isinstance(render_header(invalid_text), CollectorRejected)
    for text in ("", "0", "FF", "gg", "90 ", "00" * 16):
        plan = replace(
            data.full_plan,
            sites=(
                replace(data.full_plan.sites[0], witness_hex=text),
                *data.full_plan.sites[1:],
            ),
        )
        assert isinstance(
            render_header(replace(data, full_plan=plan)), CollectorRejected
        )


@pytest.mark.parametrize(
    "suffix", (b"x", b"\n", b"\r\n", b"\x00", b"static const int evil = 1;\n")
)
def test_reader_rejects_trailing_source(suffix: bytes) -> None:
    raw = header(accepted(source().prepare())).raw
    with pytest.raises(HeaderReadError):
        read_header(raw + suffix)


@pytest.mark.parametrize("table", reader.TABLES)
def test_reader_rejects_every_missing_duplicate_or_extra_table(table: str) -> None:
    raw = header(accepted(source().prepare())).raw
    block = table_source(raw, table)
    for changed in (
        raw.replace(block, b"", 1),
        raw.replace(block, block + block, 1),
        raw.replace(block, block.replace(b"phoenix_", b"unknown_", 1), 1),
    ):
        with pytest.raises(HeaderReadError):
            read_header(changed)


@pytest.mark.parametrize("table", reader.TABLES)
@pytest.mark.parametrize(
    "part", ("tag", "count", "width", "length", "physical", "reference")
)
def test_reader_validates_every_directory_entry(table: str, part: str) -> None:
    result = header(accepted(source().prepare()))
    count = dict(result.counts)[table]
    line = reader.directory_entry(table, count).encode()
    if part in ("tag", "count", "width", "length"):
        tokens = list(re.finditer(rb"UINT64_C\(0x[0-9a-f]{16}\)", line))
        selected = tokens[("tag", "count", "width", "length").index(part)]
        changed_line = (
            line[: selected.start()]
            + b"UINT64_C(0xffffffffffffffff)"
            + line[selected.end() :]
        )
    elif part == "physical":
        changed_line = line.replace(b"sizeof(", b"evil(", 1)
    else:
        changed_line = line.replace(b", phoenix_", b", unknown_", 1)
    assert changed_line != line
    with pytest.raises(HeaderReadError):
        read_header(result.raw.replace(line, changed_line, 1))


@pytest.mark.parametrize("table", ("bytes", "trace_site", "collector_data"))
def test_reader_rejects_changed_extents_and_extra_rows(table: str) -> None:
    raw = header(accepted(source().prepare())).raw
    block = table_source(raw, table)
    changed = re.sub(rb"\[[0-9]+\]", b"[9999999999]", block, count=1)
    with pytest.raises(HeaderReadError):
        read_header(raw.replace(block, changed, 1))
    with pytest.raises(HeaderReadError):
        read_header(raw.replace(block, block.replace(b"};\n", b"    {0},\n};\n"), 1))


@pytest.mark.parametrize("bad", (b"0X00", b"0x0A", b"0x0", b"256", b"-1", b"0x00u"))
def test_reader_rejects_noncanonical_byte_constants(bad: bytes) -> None:
    raw = header(accepted(source().prepare())).raw
    old = re.search(rb"0x[0-9a-f]{2}", table_source(raw, "bytes"))
    assert old is not None
    with pytest.raises(HeaderReadError):
        read_header(change_row(raw, "bytes", old[0], bad))


@pytest.mark.parametrize(
    "bad",
    (
        b"UINT64_C(0x10000000000000000)",
        b"UINT64_C(0xFFFFFFFFFFFFFFFF)",
        b"0",
        b"-1",
        b"UINT64_C(0x0000000000000000) + 0",
    ),
)
def test_reader_rejects_noncanonical_or_overflowing_integers(bad: bytes) -> None:
    raw = header(accepted(source().prepare())).raw
    old = re.search(rb"UINT64_C\(0x[0-9a-f]{16}\)", table_source(raw, "original"))
    assert old is not None
    with pytest.raises(HeaderReadError):
        read_header(change_row(raw, "original", old[0], bad))


@pytest.mark.parametrize(
    "table,needle,replacement",
    (
        ("original", b"{UINT64_C(0x", b"{.unknown = UINT64_C(0x"),
        ("uints", b"UINT64_C(0x0000000000000100)", b"UINT64_C(0x0000000000000101)"),
        (
            "collector_data",
            b"{UINT64_C(0x",
            b"{UINT64_C(0xffffffffffffffff), UINT64_C(0x",
        ),
        (
            "trace_site",
            b"UINT64_C(0x0000000000000001)",
            b"UINT64_C(0x0000000000000002)",
        ),
        ("call", b"{UINT64_C(0x0000000000000001)", b"{UINT64_C(0x0000000000000002)"),
    ),
)
def test_reader_rejects_corrupt_tags_slices_fields_and_data(
    table: str, needle: bytes, replacement: bytes
) -> None:
    raw = header(accepted(source().prepare())).raw
    with pytest.raises(HeaderReadError):
        read_header(change_row(raw, table, needle, replacement))


def test_reader_uses_no_writer_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    data = accepted(source(*shared()).prepare())
    result = header(data)
    monkeypatch.setattr(writer, "_Tables", bomb)
    monkeypatch.setattr(writer, "_Measure", bomb)
    monkeypatch.setattr(writer, "_members", bomb)
    monkeypatch.setattr(writer, "render_header", bomb)
    assert read_header(result.raw).record == data.record()


def test_reader_refuses_large_table_before_parsing_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = header(accepted(source().prepare())).raw
    block = table_source(raw, "bytes")
    changed = re.sub(rb"\[[0-9]+\]", b"[9999999999]", block, count=1)
    monkeypatch.setattr(reader, "_LineParser", bomb)
    with pytest.raises(HeaderReadError, match="byte bound"):
        read_header(raw.replace(block, changed, 1))


def test_fixed_native_source_bound_precedes_hashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.open

    def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "collector_data_v1.h":
            return io.BytesIO(b"x" * (reader.MAX_NATIVE + 1))
        return original(path, *args, **kwargs)

    data = accepted(source().prepare())
    monkeypatch.setattr(Path, "open", opened)
    assert isinstance(render_header(data), CollectorRejected)


def test_schema_has_fixed_declarations_for_every_record_and_table() -> None:
    native = reader.native_bytes().decode("ascii")
    for table, kind, declared in reader.SCHEMA:
        assert f"struct phoenix_{table}_v1 {{" in native
        if not kind.startswith("$"):
            assert sorted(item.name for item in fields(writer.CLASSES[kind])) == sorted(
                name for name, _ in declared
            )
        assert f"struct phoenix_{table}_slice_v1 {{" in native
    for table in reader.TABLES:
        assert f"PHOENIX_TABLE_{table.upper()}_V1" in native
    assert 'visibility("default"), used, retain' in native
    assert (
        "extern const struct phoenix_data_directory_v1 phoenix_collector_data_v1;"
        in native
    )
    assert "f_load_memory_size;" in native
    assert "f_load_memory_end_exclusive;" not in native
    assert "struct phoenix_signed_v1" in native


def test_shared_suffix_retains_different_call_bound_positions() -> None:
    binary, document = shared()
    image = bytearray(binary)
    image[0x105:0x10A] = relative(b"\xe8", 0x100105, 0x100148)
    document["functions"][0]["instructions"][1]["pcode"] = [
        op(0x100105, "CALL", [operand(0x100148)])
    ]
    document["call_edges"][1]["target"] = loc(0x100148)
    template = document["functions"].pop()
    for address, target in ((0x100140, 0x100148), (0x100148, 0x102500)):
        thunk = deepcopy(template)
        thunk["thunk_target"] = (
            loc(target) if address == 0x100140 else loc(1, "EXTERNAL")
        )
        raw = (
            relative(b"\xeb", address, target, 1)
            if address == 0x100140
            else relative(b"\xff\x25", address, target)
        )
        operation = op(
            address, "BRANCH" if address == 0x100140 else "BRANCHIND", [operand(target)]
        )
        write_thunk(image, thunk, address, (), raw, operation)
        document["functions"].append(thunk)
    data = accepted(source(bytes(image), document).prepare())
    result = complete(data)
    record = cast(dict[str, Any], thaw(read_header(result.raw).record))
    routes = data.scope.routes
    assert [route.instruction_path for route in routes] == [(0x140, 0x148), (0x148,)]
    positions = next(
        guard["rule"]["positions"]
        for guard in record["scope"]["guard_instructions"]
        if guard["address"] == 0x148
    )
    assert positions == sorted([[routes[0].sha256, 1], [routes[1].sha256, 0]])


def test_every_optional_import_field_is_typed_and_preserved() -> None:
    data = accepted(source().prepare())
    call = cast(Call, data.full_plan.sites[0].transfer)
    binding = call.imported
    assert binding is not None and binding.identity is not None
    # These are synthetic metadata changes. They do not assert an ELF fact.
    identity = replace(binding.identity, version=None, version_hidden=True)
    binding = replace(
        binding,
        function=None,
        identity=identity,
        relocation_file_offset=None,
        symbol_index=None,
    )
    plan = replace(
        data.full_plan,
        sites=(
            replace(data.full_plan.sites[0], transfer=replace(call, imported=binding)),
            *data.full_plan.sites[1:],
        ),
    )
    digest = sha256(
        (
            json.dumps(asdict(binding), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    ).hexdigest()
    route = replace(data.scope.routes[0], request=identity, binding_sha256=digest)
    scope = replace(
        data.scope,
        full_plan_sha256=plan.sha256,
        routes=(route,),
        dispositions=tuple(
            (
                address,
                replace(disposition, route_ids=(route.sha256,))
                if isinstance(disposition, Transit)
                else disposition,
            )
            for address, disposition in data.scope.dispositions
        ),
        guard_instructions=tuple(
            replace(guard, rule=TransitInstruction(((route.sha256, 0),)))
            if isinstance(guard.rule, TransitInstruction)
            else guard
            for guard in data.scope.guard_instructions
        ),
    )
    changed = repin(
        replace(data, full_plan=plan, full_plan_sha256=plan.sha256), scope=scope
    )
    generated = complete(changed)
    imported = cast(dict[str, Any], thaw(read_header(generated.raw).record))[
        "full_plan"
    ]["sites"][0]["transfer"]["imported"]
    assert imported["function"] is None
    assert (
        imported["relocation_file_offset"] is None and imported["symbol_index"] is None
    )
    assert imported["identity"]["version"] is None
    assert imported["identity"]["version_hidden"] is True
    assert imported["identity"]["needed_library"] is None


@pytest.mark.parametrize("field", ("thunk_neutral_instructions", "thunk_neutral_bytes"))
def test_lower_neutral_limits_are_enforced_on_direct_records(field: str) -> None:
    image, document = thunk_case(("6690", "90"))
    data = accepted(source(bytes(image), document).prepare())
    scope = replace(data.scope, limits=replace(data.scope.limits, **{field: 1}))
    assert isinstance(render_header(repin(data, scope=scope)), CollectorRejected)


@pytest.mark.parametrize("identity", (0, 1, 2))
def test_reader_checks_each_directory_identity(identity: int) -> None:
    raw = header(accepted(source().prepare())).raw
    prefix, directory = raw.split(reader.DIRECTORY.encode(), 1)
    lines = directory.splitlines(keepends=True)
    original = lines[identity]
    token = re.search(rb"0x[0-9a-f]{2}", original)
    assert token is not None
    replacement = b"0xff" if token[0] != b"0xff" else b"0x00"
    lines[identity] = original.replace(token[0], replacement, 1)
    with pytest.raises(HeaderReadError):
        read_header(prefix + reader.DIRECTORY.encode() + b"".join(lines))


@pytest.mark.parametrize(
    "value", (b"UINT64_C(0xffffffffffffffff)", b"UINT64_C(0x0000000000000001)")
)
def test_reader_checks_slice_offset_without_integer_wrap(value: bytes) -> None:
    raw = header(accepted(source().prepare())).raw
    changed = change_row(
        raw, "collector_data", b"{UINT64_C(0x0000000000000000),", b"{" + value + b","
    )
    with pytest.raises(HeaderReadError, match="slice"):
        read_header(changed)


@pytest.mark.parametrize(
    "value", (b"UINT64_C(0xffffffffffffffff)", b"UINT64_C(0x0000000000000041)")
)
def test_reader_checks_slice_count_without_integer_wrap(value: bytes) -> None:
    raw = header(accepted(source().prepare())).raw
    changed = change_row(
        raw, "collector_data", b", UINT64_C(0x0000000000000040)}", b", " + value + b"}"
    )
    with pytest.raises(HeaderReadError):
        read_header(changed)


@pytest.mark.parametrize("sign,magnitude", ((2, 1), (1, 0), (0, 2**63), (1, 2**63 + 1)))
def test_reader_checks_sign_and_magnitude(sign: int, magnitude: int) -> None:
    raw = header(accepted(source().prepare())).raw
    original = b"{UINT64_C(0x0000000000000000), UINT64_C(0x0000000000000005)}"
    altered = ("{" + reader.uint(sign) + ", " + reader.uint(magnitude) + "}").encode()
    with pytest.raises(HeaderReadError, match="signed dynamic tag"):
        read_header(change_row(raw, "dynamic", original, altered))


@pytest.mark.parametrize(
    "value", (None, "text", bytearray(b"text"), memoryview(b"text"), b"\xff")
)
def test_reader_rejects_invalid_byte_types_and_non_ascii(value: Any) -> None:
    with pytest.raises(HeaderReadError):
        read_header(value)


def test_renderer_rejects_new_record_classes_and_fields() -> None:
    data = accepted(source().prepare())

    class OtherOriginal(Original):
        pass

    unknown = OtherOriginal(data.original.sha256, data.original.bytes)
    assert isinstance(render_header(replace(data, original=unknown)), CollectorRejected)


def test_direct_geometry_and_canonical_links_are_checked() -> None:
    data = accepted(source().prepare())
    assert isinstance(
        render_header(
            replace(data, geometry=replace(data.geometry, load_memory_end_exclusive=3))
        ),
        CollectorRejected,
    )
    scope = replace(data.scope, root=ElfVA(data.scope.root + 1))
    assert isinstance(render_header(repin(data, scope=scope)), CollectorRejected)
    guard = next(
        guard
        for guard in data.scope.guard_instructions
        if isinstance(guard.rule, TransitInstruction)
    )
    changed = replace(guard, rule=TransitInstruction(()))
    scope = replace(
        data.scope,
        guard_instructions=tuple(
            changed if item == guard else item for item in data.scope.guard_instructions
        ),
    )
    assert isinstance(render_header(repin(data, scope=scope)), CollectorRejected)


def test_valid_lower_capture_and_transport_values_survive_exactly() -> None:
    capture = replace(
        CaptureLimits(),
        events=1,
        execution_callbacks=1,
        frames=1,
        receipt_bytes=1,
        translated_instructions=1,
        wire_bytes=1,
    )
    supplied = source(limits=capture)
    transport = replace(
        TransportLimits(),
        original_bytes=len(supplied.binary),
        lift_bytes=len(supplied.lift),
        mapping_bytes=len(supplied.mapping),
        users=1,
        routes=1,
        omissions=1,
        gap_records=1,
        elf_segments=2,
        route_path_positions=1,
        route_memberships=1,
        data_bytes=65536,
    )
    data = accepted(supplied.prepare(limits=capture, transport=transport))
    generated = complete(data)
    record = cast(dict[str, Any], thaw(read_header(generated.raw).record))
    assert record["scope"]["limits"] == asdict(capture)
    assert record["transport_limits"] == asdict(transport)


@pytest.mark.parametrize("name", ("collector_data_v1.h", "collector_header.py"))
def test_missing_fixed_sources_refuse(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = accepted(source().prepare())
    original = Path.open

    def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == name:
            raise OSError("Synthetic fixed source read failure.")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    result = render_header(data)
    assert isinstance(result, CollectorRejected) and "Cannot read" in result.detail


@pytest.mark.parametrize(
    "fault",
    (
        "route_ids",
        "continuation_users",
        "guard_roles",
        "omission_roles",
        "missing_disposition",
    ),
)
def test_complete_internal_references_are_checked(fault: str) -> None:
    supplied = (
        source(*extra_users()) if fault == "omission_roles" else source(*shared())
    )
    data = accepted(supplied.prepare())
    scope = data.scope
    if fault == "route_ids":
        scope = replace(
            scope,
            dispositions=tuple(
                (
                    address,
                    replace(disposition, route_ids=("0" * 64,))
                    if isinstance(disposition, Transit)
                    else disposition,
                )
                for address, disposition in scope.dispositions
            ),
        )
    elif fault == "continuation_users":
        plan = replace(
            data.full_plan,
            sites=tuple(
                replace(site, continuation_of=()) if site.continuation_of else site
                for site in data.full_plan.sites
            ),
        )
        data = replace(data, full_plan=plan, full_plan_sha256=plan.sha256)
        scope = replace(scope, full_plan_sha256=plan.sha256)
    elif fault == "guard_roles":
        scope = replace(
            scope,
            guard_instructions=(
                replace(scope.guard_instructions[0], full_roles=("unknown",)),
                *scope.guard_instructions[1:],
            ),
        )
    elif fault == "omission_roles":
        scope = replace(
            scope,
            omitted=(replace(scope.omitted[0], full_roles=()), *scope.omitted[1:]),
        )
    else:
        scope = replace(scope, dispositions=scope.dispositions[:-1])
    result = render_header(repin(data, scope=scope))
    assert isinstance(result, CollectorRejected)
