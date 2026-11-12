"""Pure controls use public synthetic ELF fixtures. They do not execute targets."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, dataclass, fields, replace
from hashlib import sha256
from struct import pack_into
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_observe_scope import control
from test_recovery_u1 import fixture, loc, mapping_wire, op, operand, raw_json
from test_transfer_evidence import relative, thunk_case, write_thunk

from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import parse_mapping
from phoenix.observe import collector_data
from phoenix.observe.collector_data import (
    CollectorData,
    CollectorRejected,
    FrozenRecord,
    RecordValue,
    TransportLimits,
    prepare_collector_data,
)
from phoenix.observe.plan import build_trace_plan
from phoenix.observe.scope import (
    CaptureLimits,
    ExplicitEntry,
    LiftMain,
    RequestedScope,
    ScopeSelection,
    select_scope,
)
from phoenix.recover.addresses import ElfVA, prove_addresses


@dataclass(frozen=True)
class Source:
    binary: bytes
    lift: bytes
    mapping: bytes
    plan: bytes
    scope: bytes
    requested: RequestedScope

    def prepare(
        self,
        limits: CaptureLimits = CaptureLimits(),
        transport: TransportLimits = TransportLimits(),
    ) -> CollectorData | CollectorRejected:
        return prepare_collector_data(
            self.binary,
            self.lift,
            self.mapping,
            self.plan,
            self.scope,
            self.requested,
            limits=limits,
            transport_limits=transport,
        )


def source(
    binary: bytes | None = None,
    document: dict[str, Any] | None = None,
    *,
    delta: int = 0x100000,
    limits: CaptureLimits = CaptureLimits(),
    users: tuple[int, ...] | None = None,
    explicit: bool = False,
) -> Source:
    if binary is None or document is None:
        binary, document = fixture(delta=delta)
    raw = raw_json(document)
    companion = mapping_wire(binary, raw, delta)
    companion["spans"] = [span for span in companion["spans"] if span["length"]]
    mapping_raw = raw_json(companion)
    lift = parse_lift(raw, binary)
    proof = prove_addresses(binary, lift, parse_mapping(mapping_raw, binary, raw))
    plan = build_trace_plan(binary, lift, proof)
    root = proof.to_elf(lift.main)
    requested = RequestedScope(
        root,
        tuple(ElfVA(user) for user in users) if users is not None else (root,),
        LiftMain(lift.lift_sha256, root),
    )
    if explicit:
        requested = replace(
            requested, root_evidence=ExplicitEntry(requested.intent_sha256)
        )
    selection = select_scope(binary, lift, proof, plan, requested, limits=limits)
    assert isinstance(selection, ScopeSelection), selection
    return Source(
        binary, raw, mapping_raw, plan.to_bytes(), selection.to_bytes(), requested
    )


def accepted(result: CollectorData | CollectorRejected) -> CollectorData:
    assert isinstance(result, CollectorData), result
    return result


def thaw(value: RecordValue) -> object:
    if isinstance(value, FrozenRecord):
        return {name: thaw(child) for name, child in value.entries}
    if isinstance(value, tuple):
        return [thaw(child) for child in value]
    return value


def shared() -> tuple[bytes, dict[str, Any]]:
    original, document = fixture()
    image = bytearray(original)
    image[0x105:0x10B] = relative(b"\xe8", 0x100105, 0x100140) + b"\xc3"
    root = document["functions"][0]
    call = deepcopy(root["instructions"][0])
    call.update(
        address=loc(0x100105), pcode=[op(0x100105, "CALL", [operand(0x100140)])]
    )
    resume = root["instructions"][1]
    resume.update(
        address=loc(0x10010A), pcode=[op(0x10010A, "RETURN", [operand(0, "register")])]
    )
    root["instructions"].insert(1, call)
    root["ranges"][0]["end"] = loc(0x10010A)
    edge = deepcopy(document["call_edges"][0])
    edge["site"] = loc(0x100105)
    document["call_edges"].append(edge)
    return bytes(image), document


def extra_users() -> tuple[bytes, dict[str, Any]]:
    binary, document = fixture()
    image = bytearray(binary)
    for address in (0x180, 0x190):
        image[address] = 0xC3
        function = deepcopy(document["functions"][0])
        function.update(
            entry=loc(0x100000 + address),
            ranges=[{"start": loc(0x100000 + address), "end": loc(0x100000 + address)}],
            instructions=[
                {
                    "address": loc(0x100000 + address),
                    "size": 1,
                    "text": "public control",
                    "pcode": [
                        op(0x100000 + address, "RETURN", [operand(0, "register")])
                    ],
                }
            ],
        )
        document["functions"].append(function)
    return bytes(image), document


@pytest.mark.parametrize("explicit", (False, True))
def test_complete_record_matches_both_canonical_source_records(explicit: bool) -> None:
    supplied = source(explicit=explicit)
    data = accepted(supplied.prepare())
    raw = data.to_bytes()
    decoded = json.loads(raw)
    assert decoded["full_plan"] == json.loads(supplied.plan)
    assert decoded["scope"] == json.loads(supplied.scope)
    assert decoded["original"] == {
        "sha256": sha256(supplied.binary).hexdigest(),
        "bytes": len(supplied.binary),
    }
    for field_name, raw_source in (
        ("lift_sha256", supplied.lift),
        ("full_plan_sha256", supplied.plan),
        ("scope_sha256", supplied.scope),
    ):
        assert decoded[field_name] == sha256(raw_source).hexdigest()
    assert (
        decoded["address_proof_sha256"] == decoded["full_plan"]["address_proof_sha256"]
    )
    assert (
        decoded["policy_implementation_sha256"]
        == decoded["scope"]["policy_implementation_sha256"]
    )
    assert decoded["schema"] == "phoenix-eager-collector-data-1"
    assert decoded["c_data_schema"] == "phoenix-eager-c-data-1"
    assert decoded["profile"] == "main-window-six-v1"
    assert decoded["transport_limits"] == asdict(TransportLimits())
    assert decoded["scope"]["contracts"] == []
    assert decoded["scope"]["transit_profile"] == "eager-only"
    assert decoded["scope"]["lazy_resolver"] == "unsupported"
    assert raw == (
        json.dumps(decoded, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")
    assert data.sha256 == sha256(raw).hexdigest()
    assert accepted(supplied.prepare()).to_bytes() == raw
    assert thaw(data.record()) == decoded
    with pytest.raises(FrozenInstanceError):
        data.geometry.load_memory_start = ElfVA(1)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        data.record().entries = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        data.full_plan.sites[0].entry = False  # type: ignore[misc]


def test_complete_import_bindings_shared_roles_and_call_bound_memberships() -> None:
    supplied = source(*shared())
    decoded = json.loads(accepted(supplied.prepare()).to_bytes())
    plan = decoded["full_plan"]
    scope = decoded["scope"]
    assert plan == json.loads(supplied.plan)
    assert scope == json.loads(supplied.scope)
    sites = {site["address"]: site for site in plan["sites"]}
    assert sites[0x105]["continuation_of"] == [0x100]
    assert sites[0x105]["transfer"]["kind"] == "direct_call"
    imported = sites[0x100]["transfer"]["imported"]
    assert set(imported) == {
        "site",
        "function",
        "identity",
        "relocation_slot",
        "relocation_kind",
        "thunk_path",
        "gap",
        "binary_sha256",
        "lift_sha256",
        "address_proof_sha256",
        "relocation_file_offset",
        "symbol_index",
    }
    assert imported["site"] == 0x100100 and imported["thunk_path"] == [0x100140]
    assert imported["relocation_slot"] == 0x2500
    assert imported["relocation_file_offset"] == 0xC00
    assert imported["symbol_index"] == 1
    assert imported["identity"] == {
        "symbol": "fwrite",
        "version": "GLIBC_2.2.5",
        "version_hidden": False,
        "needed_library": None,
    }
    assert len(scope["routes"]) == 2
    ids = {
        sha256(
            (json.dumps(route, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
        for route in scope["routes"]
    }
    assert len(ids) == 2
    transit = next(g for g in scope["guard_instructions"] if g["address"] == 0x140)
    assert transit["rule"]["positions"] == [[route_id, 0] for route_id in sorted(ids)]
    assert {r["call_site"] for r in scope["routes"]} == {0x100, 0x105}


def test_route_paths_and_omission_inventory_are_complete() -> None:
    binary, document = thunk_case(("f30f1efa", "90", "6690"))
    supplied = source(bytes(binary), document)
    decoded = json.loads(accepted(supplied.prepare()).to_bytes())
    assert decoded["scope"] == json.loads(supplied.scope)
    route = decoded["scope"]["routes"][0]
    assert route["instruction_path"] == [0x140, 0x144, 0x145, 0x147]
    assert route["entries"] == [0x140] and route["terminal"] == 0x147
    supplied = source(*extra_users())
    decoded = json.loads(accepted(supplied.prepare()).to_bytes())
    assert decoded["scope"] == json.loads(supplied.scope)
    assert {o["address"] for o in decoded["scope"]["omitted"]} == {0x180, 0x190}
    assert all(
        o["full_roles"] == ["entry", "return"] for o in decoded["scope"]["omitted"]
    )


@pytest.mark.parametrize("bad_import", (False, True))
def test_gaps_and_unsupported_active_guards_remain_data(bad_import: bool) -> None:
    binary, document = control(b"\x75\x03", "CBRANCH")
    document["functions"][0]["decompilation"]["analyzed_pcode"] = [
        op(0x100138, "COPY", [operand(0, "register")])
    ]
    if bad_import:
        document["imports"][0]["name"] = "fread"
    supplied = source(binary, document)
    decoded = json.loads(accepted(supplied.prepare()).to_bytes())
    assert decoded["full_plan"] == json.loads(supplied.plan)
    assert decoded["scope"] == json.loads(supplied.scope)
    gaps = decoded["scope"]["gap_dispositions"]
    assert len(gaps) > 1
    assert [g["index"] for g in gaps] == list(range(len(gaps)))
    assert all(g["domain"] == "ghidra" for g in gaps)
    assert any(g["address"] == 0x100105 and g["elf"] == 0x105 for g in gaps)
    assert any(g["disposition"]["kind"] == "guard_reject" for g in gaps)
    if bad_import:
        call = decoded["full_plan"]["sites"][0]["transfer"]
        assert call["imported"] is None
        assert call["import_gaps"] == ["conflicting_import_identity"]


def test_geometry_keeps_nonexecutables_memory_only_spans_and_uint64_end() -> None:
    binary, document = fixture()
    image = bytearray(binary)
    old_headers = bytes(image[64:232])
    image[0x300:0x3A8] = old_headers
    pack_into("<Q", image, 32, 0x300)
    pack_into("<H", image, 56, 4)
    pack_into("<IIQQQQQQ", image, 0x3A8, 1, 6, 0x400, 2**64 - 16, 0, 0, 16, 1)
    supplied = source(bytes(image), document)
    data = accepted(supplied.prepare())
    assert data.geometry.executable_file_start == 0
    assert data.geometry.executable_file_end_exclusive == 0x400
    assert data.geometry.load_memory_start == 0
    assert data.geometry.load_memory_end_exclusive == 2**64
    decoded = json.loads(data.to_bytes())
    assert decoded["image"]["entry"] == 0x100 and decoded["image"]["kind"] == 3
    assert decoded["image"]["segments"] == [
        {
            "index": 0,
            "va": 0,
            "file_offset": 0,
            "file_size": 0x400,
            "memory_size": 0x400,
            "flags": 5,
            "alignment": 1,
        },
        {
            "index": 1,
            "va": 0x2000,
            "file_offset": 0x800,
            "file_size": 0x600,
            "memory_size": 0x700,
            "flags": 6,
            "alignment": 1,
        },
        {
            "index": 3,
            "va": 2**64 - 16,
            "file_offset": 0x400,
            "file_size": 0,
            "memory_size": 16,
            "flags": 6,
            "alignment": 1,
        },
    ]
    assert decoded["image"]["dynamic"] == [
        [5, 0x2300],
        [10, 30],
        [6, 0x2200],
        [11, 24],
        [4, 0x2280],
        [7, 0x2400],
        [8, 24],
        [9, 24],
        [1, 8],
        [0x6FFFFFF0, 0x22C0],
        [0x6FFFFFFE, 0x2480],
        [0x6FFFFFFF, 1],
    ]
    assert decoded["image"]["segments"][-1]["file_size"] == 0
    assert decoded["image"]["segments"][-1]["memory_size"] == 16
    assert decoded["image"]["segments"][1]["flags"] == 6
    assert decoded["geometry"]["load_memory_end_exclusive"] == 2**64


@pytest.mark.parametrize("field_name", ("binary", "lift", "mapping", "plan", "scope"))
def test_each_raw_artifact_is_bound(field_name: str) -> None:
    supplied = source()
    if field_name == "binary":
        changed = supplied.binary + b"x"
    else:
        record = json.loads(getattr(supplied, field_name))
        if field_name == "lift":
            record["functions"][0]["instructions"][0]["text"] = "changed"
        elif field_name == "mapping":
            record["binary_sha256"] = "0" * 64
        elif field_name == "plan":
            record["sites"][0]["entry"] = False
        else:
            record["active_unlisted"] = "allow"
        changed = raw_json(record)
    changes: dict[str, Any] = {field_name: changed}
    assert isinstance(replace(supplied, **changes).prepare(), CollectorRejected)


@pytest.mark.parametrize("field_name", ("lift", "mapping", "plan", "scope"))
def test_duplicate_object_keys_are_not_accepted(field_name: str) -> None:
    supplied = source()
    raw: bytes = getattr(supplied, field_name)
    record = json.loads(raw)
    key = next(iter(record))
    changed = (
        b"{"
        + json.dumps(key).encode()
        + b":"
        + json.dumps(record[key]).encode()
        + b","
        + raw[1:]
    )
    changes: dict[str, Any] = {field_name: changed}
    assert isinstance(replace(supplied, **changes).prepare(), CollectorRejected)


@pytest.mark.parametrize("field_name", ("plan", "scope"))
@pytest.mark.parametrize("suffix", (b" ", b"\n", b"\r\n"))
def test_plan_and_scope_require_exact_canonical_bytes(
    field_name: str, suffix: bytes
) -> None:
    supplied = source()
    changed = getattr(supplied, field_name) + suffix
    changes: dict[str, Any] = {field_name: changed}
    assert isinstance(replace(supplied, **changes).prepare(), CollectorRejected)


def test_self_consistent_old_policy_certificate_is_rebuilt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phoenix.observe import scope

    binary, document = fixture()
    with monkeypatch.context() as patch:
        patch.setattr(scope, "policy_implementation_sha256", lambda: "d" * 64)
        old = source(binary, document)
    current = source(binary, document)
    assert old.plan == current.plan and old.scope != current.scope
    assert isinstance(old.prepare(), CollectorRejected)
    assert isinstance(replace(current, scope=old.scope).prepare(), CollectorRejected)
    assert accepted(current.prepare()).policy_implementation_sha256 != "d" * 64


def bomb(*args: object, **kwargs: object) -> Any:
    raise AssertionError("Parsing or hashing occurred before input refusal.")


def block_expensive_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collector_data, "parse_lift", bomb)
    monkeypatch.setattr(collector_data, "parse_mapping", bomb)
    monkeypatch.setattr(collector_data, "prove_addresses", bomb)
    monkeypatch.setattr(collector_data, "sha256", bomb)


@pytest.mark.parametrize("field_name", ("binary", "lift", "mapping", "plan", "scope"))
@pytest.mark.parametrize("value", (None, "bytes", bytearray(b"x"), memoryview(b"x")))
def test_exact_raw_types_refuse_before_work(
    field_name: str, value: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    result = replace(supplied, **{field_name: value}).prepare()
    assert isinstance(result, CollectorRejected) and result.reason == "input_type"


@pytest.mark.parametrize("limit_type", (CaptureLimits, TransportLimits))
@pytest.mark.parametrize("bad", (True, False, 1.0, "1", None, 0, -1, "raised"))
def test_every_limit_field_requires_exact_positive_lower_integer(
    limit_type: type[CaptureLimits] | type[TransportLimits],
    bad: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplied = source()
    maximum = limit_type()
    block_expensive_work(monkeypatch)
    for item in fields(maximum):
        value = getattr(maximum, item.name) + 1 if bad == "raised" else bad
        invalid = replace(maximum, **{item.name: value})
        if isinstance(invalid, CaptureLimits):
            result = supplied.prepare(limits=invalid)
        else:
            result = supplied.prepare(transport=invalid)
        assert isinstance(result, CollectorRejected), item.name
        assert result.reason == "input_limit", item.name
        assert len(result.detail) <= 512


@pytest.mark.parametrize(
    "field_name", ("original_bytes", "lift_bytes", "mapping_bytes")
)
def test_lower_input_byte_bounds_refuse_before_work(
    field_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    result = supplied.prepare(transport=replace(TransportLimits(), **{field_name: 1}))
    assert isinstance(result, CollectorRejected) and result.reason == "input_limit"


@pytest.mark.parametrize("field_name", ("full_plan_bytes", "scope_bytes"))
def test_lower_capture_byte_bounds_refuse_before_work(
    field_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    result = supplied.prepare(limits=replace(CaptureLimits(), **{field_name: 1}))
    assert isinstance(result, CollectorRejected) and result.reason == "input_limit"


@pytest.mark.parametrize("width", (1, 7))
def test_snapshot_width_is_exactly_eight_before_work(
    width: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    result = supplied.prepare(limits=replace(CaptureLimits(), snapshot_bytes=width))
    assert isinstance(result, CollectorRejected) and result.reason == "input_limit"


@pytest.mark.parametrize(
    "field_name",
    (
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
def test_every_lower_transport_inventory_bound_refuses_without_truncation(
    field_name: str,
) -> None:
    if field_name == "users":
        supplied = source(*extra_users(), users=(0x100, 0x180))
    elif field_name == "omissions":
        supplied = source(*extra_users())
    elif field_name == "gap_records":
        binary, document = control(b"\x75\x03", "CBRANCH")
        document["functions"][0]["decompilation"]["analyzed_pcode"] = [
            op(0x100138, "COPY", [operand(0, "register")])
        ]
        supplied = source(binary, document)
    else:
        supplied = source(*shared())
    assert isinstance(supplied.prepare(), CollectorData)
    result = supplied.prepare(transport=replace(TransportLimits(), **{field_name: 1}))
    assert isinstance(result, CollectorRejected)
    assert result.reason == (
        "render_limit" if field_name == "data_bytes" else "input_limit"
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "events",
        "wire_bytes",
        "frames",
        "execution_callbacks",
        "translated_instructions",
        "receipt_bytes",
    ),
)
def test_lower_live_limits_are_retained_as_static_data(field_name: str) -> None:
    limits = replace(CaptureLimits(), **{field_name: 1})
    supplied = source(limits=limits)
    data = accepted(supplied.prepare(limits=limits))
    assert json.loads(data.to_bytes())["scope"]["limits"] == asdict(limits)
    assert isinstance(supplied.prepare(), CollectorRejected)


@pytest.mark.parametrize("field_name", ("full_plan_sites", "guarded_instructions"))
def test_lower_static_capture_counts_refuse(field_name: str) -> None:
    result = source().prepare(limits=replace(CaptureLimits(), **{field_name: 1}))
    assert isinstance(result, CollectorRejected)


@pytest.mark.parametrize(
    "field_name", ("thunk_neutral_instructions", "thunk_neutral_bytes")
)
def test_lower_neutral_bounds_refuse(field_name: str) -> None:
    binary, document = thunk_case(("6690", "90"))
    result = source(bytes(binary), document).prepare(
        limits=replace(CaptureLimits(), **{field_name: 1})
    )
    assert isinstance(result, CollectorRejected)


def test_lower_route_entry_limit_refuses() -> None:
    binary, document = fixture()
    image = bytearray(binary)
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
    supplied = source(bytes(image), document)
    result = supplied.prepare(limits=replace(CaptureLimits(), route_entries=1))
    assert isinstance(result, CollectorRejected)


def test_exact_output_limit_and_incremental_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplied = source()
    baseline = accepted(supplied.prepare())
    bound = len(baseline.to_bytes())
    while True:
        data = accepted(
            supplied.prepare(transport=replace(TransportLimits(), data_bytes=bound))
        )
        size = len(data.to_bytes())
        if size == bound:
            break
        bound = size
    assert len(data.to_bytes()) == bound
    refused = supplied.prepare(
        transport=replace(TransportLimits(), data_bytes=bound - 1)
    )
    assert isinstance(refused, CollectorRejected) and refused.reason == "render_limit"
    original = collector_data._tokens
    seen = 0

    def guarded(value: object) -> Any:
        nonlocal seen
        for token in original(value):
            seen += 1
            assert seen < 5, (
                "The encoder traversed records after the bound was exceeded."
            )
            yield token

    monkeypatch.setattr(collector_data, "_tokens", guarded)
    refused = supplied.prepare(transport=replace(TransportLimits(), data_bytes=1))
    assert isinstance(refused, CollectorRejected) and refused.reason == "render_limit"


@settings(max_examples=20, deadline=None)
@given(
    st.integers(min_value=0, max_value=0x400000),
    st.integers(min_value=1, max_value=0x1000000),
)
def test_canonical_records_and_bindings_across_rebases(base: int, delta: int) -> None:
    binary, document = fixture(base=base, delta=delta)
    supplied = source(binary, document, delta=delta)
    data = accepted(supplied.prepare())
    decoded = json.loads(data.to_bytes())
    assert decoded["full_plan"] == json.loads(supplied.plan)
    assert decoded["scope"] == json.loads(supplied.scope)
    assert data.geometry.executable_file_start == base
    assert data.geometry.executable_file_end_exclusive == base + 0x400
    assert accepted(supplied.prepare()).sha256 == data.sha256
    assert isinstance(
        replace(supplied, binary=binary + b"x").prepare(), CollectorRejected
    )


@settings(max_examples=20, deadline=None)
@given(st.text(min_size=1, max_size=40))
def test_lift_text_change_requires_new_mapping_plan_and_scope(label: str) -> None:
    binary, document = fixture()
    original = source(binary, document)
    document["functions"][0]["name"] = label
    changed = source(binary, document)
    assert changed.lift != original.lift
    assert changed.plan != original.plan and changed.scope != original.scope
    assert isinstance(replace(original, lift=changed.lift).prepare(), CollectorRejected)
    assert accepted(changed.prepare()).lift_sha256 == sha256(changed.lift).hexdigest()


@pytest.mark.parametrize("field_name", ("binary", "lift", "mapping", "plan", "scope"))
def test_empty_inputs_refuse_before_work(
    field_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    changes: dict[str, Any] = {field_name: b""}
    result = replace(supplied, **changes).prepare()
    assert isinstance(result, CollectorRejected) and result.reason == "input_limit"


def test_record_types_are_exact_before_work(monkeypatch: pytest.MonkeyPatch) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    invalid: Any = object()
    for result in (
        supplied.prepare(limits=invalid),
        supplied.prepare(transport=invalid),
        replace(supplied, requested=invalid).prepare(),
    ):
        assert isinstance(result, CollectorRejected) and result.reason == "input_type"


@pytest.mark.parametrize(
    "changes",
    (
        {"root": True},
        {"root": 256.0},
        {"root": -1},
        {"root": 2**64},
        {"users": [256]},
        {"users": (True,)},
        {"users": (256.0,)},
        {"users": (-1,)},
        {"users": (2**64,)},
        {"root_evidence": None},
        {"root_evidence": LiftMain("0" * 64, cast(Any, True))},
        {"root_evidence": LiftMain("0" * 64, cast(Any, 256.0))},
        {"root_evidence": LiftMain("bad", ElfVA(256))},
        {"root_evidence": ExplicitEntry("bad")},
    ),
)
def test_request_children_refuse_exact_type_or_range_errors_before_work(
    changes: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    supplied = source()
    block_expensive_work(monkeypatch)
    requested = replace(supplied.requested, **changes)
    result = replace(supplied, requested=requested).prepare()
    assert isinstance(result, CollectorRejected) and result.reason == "input_type"


@pytest.mark.parametrize("users", ((), (0x100, 0x100), (0x180, 0x100), (0x180,)))
def test_bad_request_partition_is_not_accepted(users: tuple[int, ...]) -> None:
    supplied = source()
    requested = replace(supplied.requested, users=tuple(ElfVA(user) for user in users))
    assert isinstance(
        replace(supplied, requested=requested).prepare(), CollectorRejected
    )


def test_subclasses_do_not_replace_exact_boundary_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OtherBytes(bytes):
        pass

    class OtherLimits(TransportLimits):
        pass

    class OtherCapture(CaptureLimits):
        pass

    class OtherRequest(RequestedScope):
        pass

    supplied = source()
    block_expensive_work(monkeypatch)
    requested = OtherRequest(
        supplied.requested.root,
        supplied.requested.users,
        supplied.requested.root_evidence,
    )
    results = (
        replace(supplied, binary=OtherBytes(supplied.binary)).prepare(),
        supplied.prepare(transport=OtherLimits()),
        supplied.prepare(limits=OtherCapture()),
        replace(supplied, requested=requested).prepare(),
    )
    assert all(isinstance(result, CollectorRejected) for result in results)


def test_source_failure_is_bounded_and_coding_errors_remain_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phoenix.lift.mapping import MappingError

    supplied = source()

    def invalid_source(*args: object) -> Any:
        raise MappingError("x" * 1000)

    monkeypatch.setattr(collector_data, "parse_lift", invalid_source)
    result = supplied.prepare()
    assert isinstance(result, CollectorRejected)
    assert result.reason == "static_reconstruction" and len(result.detail) == 512

    def coding_error(*args: object) -> Any:
        raise RuntimeError("Visible coding error.")

    monkeypatch.setattr(collector_data, "parse_lift", coding_error)
    with pytest.raises(RuntimeError, match="Visible coding error"):
        supplied.prepare()


def test_valid_lower_transport_limits_are_preserved_exactly() -> None:
    supplied = source()
    lower = TransportLimits(
        original_bytes=len(supplied.binary),
        lift_bytes=len(supplied.lift),
        mapping_bytes=len(supplied.mapping),
        users=1,
        routes=1,
        omissions=1,
        gap_records=len(json.loads(supplied.plan)["gaps"]),
        elf_segments=2,
        route_path_positions=1,
        route_memberships=1,
        data_bytes=65536,
    )
    data = accepted(supplied.prepare(transport=lower))
    assert data.transport_limits == lower
    assert json.loads(data.to_bytes())["transport_limits"] == asdict(lower)
    assert data.sha256 != accepted(supplied.prepare()).sha256


def test_default_transport_maxima_match_the_approved_contract() -> None:
    assert asdict(TransportLimits()) == {
        "original_bytes": 16 * 1024 * 1024,
        "lift_bytes": 64 * 1024 * 1024,
        "mapping_bytes": 64 * 1024 * 1024,
        "users": 4096,
        "routes": 4096,
        "omissions": 4096,
        "gap_records": 65536,
        "elf_segments": 1024,
        "route_path_positions": 1179648,
        "route_memberships": 1179648,
        "data_bytes": 16 * 1024 * 1024,
    }


def test_policy_identity_uses_installed_nine_file_algorithm() -> None:
    from pathlib import Path

    names = (
        "phoenix/observe/scope.py",
        "phoenix/observe/plan.py",
        "phoenix/recover/addresses.py",
        "phoenix/recover/imports.py",
        "phoenix/recover/plan.py",
        "phoenix/recover/transfers.py",
        "phoenix/lift/index.py",
        "phoenix/lift/mapping.py",
        "phoenix/lift/evidence.py",
    )
    root = Path(__file__).resolve().parents[1]
    sources = [[name, sha256((root / name).read_bytes()).hexdigest()] for name in names]
    raw = (json.dumps(sources, sort_keys=True, separators=(",", ":")) + "\n").encode()
    assert (
        accepted(source().prepare()).policy_implementation_sha256
        == sha256(raw).hexdigest()
    )


@pytest.mark.parametrize("section", ("full_plan", "scope"))
def test_each_nested_logical_field_is_required(section: str) -> None:
    supplied = source(*shared())
    artifact = supplied.plan if section == "full_plan" else supplied.scope
    original = json.loads(artifact)

    def dictionaries(value: Any, path: tuple[Any, ...] = ()) -> Any:
        if isinstance(value, dict):
            for key, child in value.items():
                yield path, key
                yield from dictionaries(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from dictionaries(child, (*path, index))

    for path, key in dictionaries(original):
        changed = deepcopy(original)
        selected = changed
        for component in path:
            selected = selected[component]
        del selected[key]
        raw = (
            json.dumps(changed, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        changes: dict[str, Any] = {"plan" if section == "full_plan" else "scope": raw}
        assert isinstance(replace(supplied, **changes).prepare(), CollectorRejected), (
            path,
            key,
        )


def test_shared_suffix_keeps_distinct_route_positions() -> None:
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
    supplied = source(bytes(image), document)
    data = accepted(supplied.prepare())
    scope = json.loads(data.to_bytes())["scope"]
    assert scope == json.loads(supplied.scope)
    routes = scope["routes"]
    assert [route["instruction_path"] for route in routes] == [[0x140, 0x148], [0x148]]
    positions = []
    for route, position in zip(routes, (1, 0), strict=True):
        raw = (json.dumps(route, sort_keys=True, separators=(",", ":")) + "\n").encode()
        positions.append([sha256(raw).hexdigest(), position])
    guard = next(g for g in scope["guard_instructions"] if g["address"] == 0x148)
    assert guard["rule"]["positions"] == sorted(positions)
    for limit_name in ("route_path_positions", "route_memberships"):
        result = supplied.prepare(
            transport=replace(TransportLimits(), **{limit_name: 2})
        )
        assert isinstance(result, CollectorRejected) and result.reason == "input_limit"


def test_unmapped_omitted_gap_preserves_null_elf_and_original_index() -> None:
    binary, document = fixture()
    extra = deepcopy(document["functions"][0])
    extra.update(
        entry=loc(0x100170), ranges=[{"start": loc(0x100170), "end": loc(0x100180)}]
    )
    extra["instructions"] = [
        {
            "address": loc(0x100180),
            "size": 1,
            "text": "public control",
            "pcode": [op(0x100180, "BRANCH", [operand(0x100180)])],
        }
    ]
    document["functions"].append(extra)
    image = bytearray(binary)
    image[0x180] = 0xF4
    binary = bytes(image)
    raw = raw_json(document)
    companion = mapping_wire(binary, raw)
    template = companion["spans"][0]
    companion["spans"] = [companion["spans"][1]]
    for start, end in ((0, 0x170), (0x171, 0x400)):
        digest = sha256(binary[start:end]).hexdigest()
        companion["spans"].append(
            dict(
                template,
                ghidra_start=hex(0x100000 + start),
                length=end - start,
                source_start=start,
                source_end=end - 1,
                memory_sha256=digest,
                original_sha256=digest,
            )
        )
    mapping_raw = raw_json(companion)
    lift = parse_lift(raw, binary)
    proof = prove_addresses(binary, lift, parse_mapping(mapping_raw, binary, raw))
    plan = build_trace_plan(binary, lift, proof)
    request = RequestedScope(
        ElfVA(0x100), (ElfVA(0x100),), LiftMain(lift.lift_sha256, ElfVA(0x100))
    )
    scope = select_scope(binary, lift, proof, plan, request)
    assert isinstance(scope, ScopeSelection)
    supplied = Source(
        binary, raw, mapping_raw, plan.to_bytes(), scope.to_bytes(), request
    )
    decoded = json.loads(accepted(supplied.prepare()).to_bytes())
    assert decoded["full_plan"] == json.loads(supplied.plan)
    assert decoded["scope"] == json.loads(supplied.scope)
    gap = next(
        g for g in decoded["scope"]["gap_dispositions"] if g["address"] == 0x100170
    )
    assert gap["elf"] is None and gap["domain"] == "ghidra"
    assert decoded["full_plan"]["gaps"][gap["index"]] == [gap["address"], gap["reason"]]
    assert gap["disposition"]["kind"] == "dormant_outside_window"
