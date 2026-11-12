"""Public synthetic controls for source observations. No emission is authorized."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_byte_graph import BASE, bound, sample, wire

from phoenix.lift.byte_graph import ByteGraph, parse_byte_graph
from phoenix.lift.byte_source import (
    ByteSourceError,
    ByteSourceLimits,
    parse_byte_source,
)
from phoenix.lift.index import LiftIndex


def source_sample() -> tuple[dict[str, Any], LiftIndex, ByteGraph]:
    binary, document, graph_raw = sample()
    lift = bound(binary, document, graph_raw)
    graph = parse_byte_graph(wire(graph_raw), lift)
    source = document["functions"][0]["decompilation"]["raw_c"].encode("utf-8")
    raw = {
        "schema": 1,
        "function": deepcopy(graph_raw["function"]),
        "pass_id": graph_raw["pass_id"],
        "lift_sha256": graph_raw["lift_sha256"],
        "raw_c_sha256": sha256(source).hexdigest(),
        "raw_c_bytes": len(source),
        "source_status": "exact_printer_bytes",
        "tokens": [
            {
                "ordinal": index,
                "span": {"start": start, "end": end},
                "kind": "synthetic",
                "text_sha256": sha256(source[start:end]).hexdigest(),
                "operation": deepcopy(graph_raw["blocks"][0]["operations"][0]["id"]),
                "value": deepcopy(graph_raw["values"][0]["id"]),
                "formal_ordinal": 0,
                "symbol_storage": [
                    {
                        "address": {"space": "register", "offset": "0x10"},
                        "size": 8,
                        "register": "RDI",
                        "stack_offset": None,
                    }
                ],
            }
            for index, (start, end) in enumerate(((0, 3), (3, len(source))))
        ],
        "gaps": [],
    }
    return raw, lift, graph


def test_complete_independent_wire_round_trip_and_immutability() -> None:
    raw, lift, graph = source_sample()
    parsed = parse_byte_source(wire(raw), lift, graph)
    assert parsed.record() == raw
    assert parsed.to_bytes() == wire(raw)
    assert parsed.sha256 == sha256(wire(raw)).hexdigest()
    assert parsed.tokens[0].symbol_storage[0].register == "RDI"
    with pytest.raises(FrozenInstanceError):
        parsed.tokens[0].ordinal = 9  # type: ignore[misc]
    raw["tokens"][0]["span"]["end"] = 2
    assert parsed.tokens[0].span.end == 3
    copy = parsed.record()
    assert json.loads(parsed.to_bytes()) != raw and copy == json.loads(
        parsed.to_bytes()
    )


@pytest.mark.parametrize(
    "field",
    ["schema", "function", "pass_id", "lift_sha256", "raw_c_sha256", "raw_c_bytes"],
)
def test_identity_changes_reject(field: str) -> None:
    raw, lift, graph = source_sample()
    raw[field] = {
        "schema": True,
        "function": {"binary_sha256": "0" * 64, "ghidra_entry": hex(BASE)},
        "pass_id": "0" * 64,
        "lift_sha256": "0" * 64,
        "raw_c_sha256": "0" * 64,
        "raw_c_bytes": raw["raw_c_bytes"] + 1,
    }[field]
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


@pytest.mark.parametrize(
    "fault",
    [
        "overlap",
        "reverse",
        "empty",
        "past_end",
        "split_utf8",
        "hash",
        "ordinal",
        "operation",
        "value",
        "pass",
        "domain",
        "formal",
        "kind",
    ],
)
def test_token_contradictions_reject(fault: str) -> None:
    raw, lift, graph = source_sample()
    token = raw["tokens"][1]
    if fault == "overlap":
        token["span"]["start"] = 2
    elif fault == "reverse":
        raw["tokens"].reverse()
    elif fault == "empty":
        token["span"]["end"] = 3
    elif fault == "past_end":
        token["span"]["end"] += 1
    elif fault == "split_utf8":
        token["span"]["start"] = 16
    elif fault == "hash":
        token["text_sha256"] = "0" * 64
    elif fault == "ordinal":
        token["ordinal"] = 0
    elif fault == "operation":
        token["operation"]["sequence"]["index"] = 999
    elif fault == "value":
        token["value"]["local_id"] = 999
    elif fault == "pass":
        token["value"]["pass_id"] = "0" * 64
    elif fault == "domain":
        token["operation"]["domain"] = "raw"
    elif fault == "formal":
        token["formal_ordinal"] = True
    else:
        token["kind"] = "\udfff"
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


@pytest.mark.parametrize("fault", ["size", "stack", "register", "wrap", "extra"])
def test_storage_contradictions_reject(fault: str) -> None:
    raw, lift, graph = source_sample()
    piece = raw["tokens"][0]["symbol_storage"][0]
    if fault == "size":
        piece["size"] = 0
    elif fault == "stack":
        piece["stack_offset"] = 1
    elif fault == "register":
        piece["register"] = ""
    elif fault == "wrap":
        piece["address"]["offset"] = hex(2**64 - 1)
    else:
        piece["extra"] = True
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


def test_stack_storage_and_null_associations_are_retained() -> None:
    raw, lift, graph = source_sample()
    token = raw["tokens"][0]
    token.update(operation=None, value=None, formal_ordinal=None)
    token["symbol_storage"] = [
        {
            "address": {"space": "stack", "offset": hex(2**64 - 8)},
            "size": 8,
            "register": None,
            "stack_offset": -8,
        }
    ]
    assert parse_byte_source(wire(raw), lift, graph).record() == raw


def test_unavailable_requires_explicit_gap_and_no_tokens() -> None:
    raw, lift, graph = source_sample()
    raw["source_status"] = "unavailable"
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)
    raw["tokens"] = []
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)
    raw["gaps"] = [
        {"code": "source_unbound", "block": None, "operation": None, "value": None}
    ]
    assert parse_byte_source(wire(raw), lift, graph).record() == raw


@pytest.mark.parametrize("fault", ["duplicate", "code", "block", "value", "owner"])
def test_gap_contradictions_reject(fault: str) -> None:
    raw, lift, graph = source_sample()
    graph_record = cast(dict[str, Any], graph.record())
    gap: dict[str, Any] = {
        "code": "source_unbound",
        "block": None,
        "operation": None,
        "value": None,
    }
    raw["gaps"] = [gap]
    if fault == "duplicate":
        raw["gaps"].append(deepcopy(gap))
    elif fault == "code":
        gap["code"] = "invented"
    elif fault == "block":
        gap["block"] = {
            "function": raw["function"],
            "pass_id": raw["pass_id"],
            "index": 999,
        }
    elif fault == "value":
        gap["value"] = {
            "function": raw["function"],
            "pass_id": raw["pass_id"],
            "local_id": 999,
        }
    else:
        gap["block"] = graph_record["blocks"][1]["id"]
        gap["operation"] = deepcopy(raw["tokens"][0]["operation"])
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


def test_raw_gap_reference_and_excluded_analyzed_reference_are_retained() -> None:
    raw, lift, graph = source_sample()
    key = deepcopy(raw["tokens"][0]["operation"])
    key["domain"] = "raw"
    raw["gaps"] = [
        {"code": "unsupported_opcode", "block": None, "operation": key, "value": None}
    ]
    assert parse_byte_source(wire(raw), lift, graph).record() == raw
    raw["gaps"][0]["operation"] = cast(dict[str, Any], graph.record())["excluded_dead"][
        0
    ]
    assert parse_byte_source(wire(raw), lift, graph).record() == raw


@pytest.mark.parametrize("member", [f.name for f in fields(ByteSourceLimits)])
@pytest.mark.parametrize("invalid", [0, -1, True, 1.0, None])
def test_invalid_limits_reject(member: str, invalid: Any) -> None:
    with pytest.raises(ByteSourceError):
        ByteSourceLimits(**{member: invalid})


@pytest.mark.parametrize("member", [f.name for f in fields(ByteSourceLimits)])
def test_raised_limits_reject(member: str) -> None:
    with pytest.raises(ByteSourceError):
        ByteSourceLimits(**{member: getattr(ByteSourceLimits(), member) + 1})


def test_exact_lower_boundaries() -> None:
    raw, lift, graph = source_sample()
    raw["gaps"] = [
        {"code": "interface_unproved", "block": None, "operation": None, "value": None}
    ]
    limits = ByteSourceLimits(
        max_bytes=len(wire(raw)),
        max_source_bytes=raw["raw_c_bytes"],
        max_tokens=2,
        max_storage_pieces=1,
        max_gaps=1,
    )
    assert parse_byte_source(wire(raw), lift, graph, limits=limits).record() == raw
    for member in ("max_bytes", "max_source_bytes", "max_tokens"):
        with pytest.raises(ByteSourceError):
            parse_byte_source(
                wire(raw),
                lift,
                graph,
                limits=replace(limits, **{member: getattr(limits, member) - 1}),
            )
    raw["gaps"].append(
        {"code": "source_unbound", "block": None, "operation": None, "value": None}
    )
    with pytest.raises(ByteSourceError):
        parse_byte_source(
            wire(raw), lift, graph, limits=replace(limits, max_bytes=65536)
        )


def test_byte_limit_precedes_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    import phoenix.lift.byte_source as source_module

    raw, lift, graph = source_sample()

    def fail(_: object) -> None:
        pytest.fail("Parsing occurred before the byte limit.")

    monkeypatch.setattr(source_module, "load_json", fail)
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph, limits=ByteSourceLimits(max_bytes=1))


@pytest.mark.parametrize(
    "payload",
    [
        b"{}",
        b"\xff",
        b"[" * 1100,
        b'{"schema":1,"schema":1}',
        b'{"schema":' + b"9" * 5000 + b"}",
    ],
)
def test_malformed_wire_has_controlled_failure(payload: bytes) -> None:
    _, lift, graph = source_sample()
    with pytest.raises(ByteSourceError):
        parse_byte_source(payload, lift, graph)


def test_noncanonical_unknown_and_mutable_inputs_reject() -> None:
    raw, lift, graph = source_sample()
    for bad in (json.dumps(raw).encode(), wire(raw) + b"\n", bytearray(wire(raw))):
        with pytest.raises(ByteSourceError):
            parse_byte_source(bad, lift, graph)  # type: ignore[arg-type]
    raw["extra"] = None
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


def test_missing_tokens_are_not_authenticated_by_old_evidence() -> None:
    raw, lift, graph = source_sample()
    raw["tokens"] = []
    assert parse_byte_source(wire(raw), lift, graph).tokens == ()


def test_lower_piece_limit_counts_every_retained_piece() -> None:
    raw, lift, graph = source_sample()
    piece = deepcopy(raw["tokens"][0]["symbol_storage"][0])
    piece["address"]["offset"] = "0x18"
    raw["tokens"][0]["symbol_storage"].append(piece)
    assert len(parse_byte_source(wire(raw), lift, graph).tokens[0].symbol_storage) == 2
    with pytest.raises(ByteSourceError):
        parse_byte_source(
            wire(raw), lift, graph, limits=ByteSourceLimits(max_storage_pieces=1)
        )


def test_utf8_source_limit_precedes_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    import phoenix.lift.byte_source as source_module

    raw, lift, graph = source_sample()

    def fail(_: object) -> None:
        pytest.fail("Hashing occurred after the source byte limit failed.")

    monkeypatch.setattr(source_module, "sha256", fail)
    with pytest.raises(ByteSourceError):
        parse_byte_source(
            wire(raw),
            lift,
            graph,
            limits=ByteSourceLimits(max_source_bytes=raw["raw_c_bytes"] - 1),
        )


@pytest.mark.parametrize(
    "error_type",
    [ValueError, RuntimeError, TypeError, OverflowError, RecursionError, UnicodeError],
)
@pytest.mark.parametrize("site", ["source", "token"])
def test_hashing_coding_error_is_not_a_wire_rejection(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    site: str,
) -> None:
    import phoenix.lift.byte_source as source_module

    raw, lift, graph = source_sample()

    calls = 0

    def fail(data: bytes) -> Any:
        nonlocal calls
        calls += 1
        if calls == (1 if site == "source" else 2):
            raise error_type("Coding-error sentinel.")
        return sha256(data)

    monkeypatch.setattr(source_module, "sha256", fail)
    with pytest.raises(error_type, match="Coding-error sentinel") as error:
        parse_byte_source(wire(raw), lift, graph)
    assert type(error.value) is error_type


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_json_numbers_reject(number: float) -> None:
    raw, lift, graph = source_sample()
    raw["raw_c_bytes"] = number
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("tokens", 0),
        ("tokens", 0, "span"),
        ("tokens", 0, "symbol_storage", 0),
        ("tokens", 0, "operation"),
        ("tokens", 0, "value"),
    ],
)
@pytest.mark.parametrize("fault", ["extra", "missing"])
def test_every_record_shape_is_closed(path: tuple[str | int, ...], fault: str) -> None:
    raw, lift, graph = source_sample()
    target: Any = raw
    for key in path:
        target = target[key]
    if fault == "extra":
        target["extra"] = None
    else:
        target.pop(next(iter(target)))
    with pytest.raises(ByteSourceError):
        parse_byte_source(wire(raw), lift, graph)


@given(
    st.sampled_from(
        (
            "schema",
            "function",
            "pass_id",
            "raw_c_bytes",
            "tokens",
            "gaps",
            "source_status",
        )
    ),
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=40),
        lambda children: (
            st.lists(children, max_size=4)
            | st.dictionaries(st.text(max_size=10), children, max_size=4)
        ),
        max_leaves=12,
    ),
)
@settings(max_examples=150)
def test_structured_replacements_have_controlled_failures(
    field: str, value: object
) -> None:
    raw, lift, graph = source_sample()
    raw[field] = value
    encoded = wire(raw)
    try:
        result = parse_byte_source(encoded, lift, graph)
    except ByteSourceError:
        return
    assert result.to_bytes() == encoded


@given(st.binary(max_size=2000))
@settings(max_examples=100)
def test_arbitrary_bytes_do_not_escape_controlled_failure(payload: bytes) -> None:
    _, lift, graph = source_sample()
    try:
        result = parse_byte_source(payload, lift, graph)
    except ByteSourceError:
        return
    assert result.to_bytes() == payload
