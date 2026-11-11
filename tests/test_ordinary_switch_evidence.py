from hashlib import sha256
from typing import Any

import pytest
from test_recovery_u1 import fixture, loc, op, raw_json

from phoenix.lift.index import LiftIndex, parse_lift
from phoenix.lift.mapping import MappingError
from phoenix.lift.switch_source import parse_ordinary_source

_ENTRY = 0x100100
_SOURCE = "/* 📘 */ ".encode() + (
    b"uint f(uint p){switch(p&1){case 0: out=2; break; default: out=3;} return out;}"
)


def proposal() -> tuple[LiftIndex, dict[str, Any]]:
    binary, document = fixture()
    function = document["functions"][0]
    function["decompilation"]["raw_c"] = _SOURCE.decode("utf-8")
    function["decompilation"]["analyzed_pcode"] = [
        op(_ENTRY, "INT_AND", [], index=1),
        op(_ENTRY, "BRANCHIND", [], index=2),
        op(_ENTRY + 5, "COPY", [], index=3),
        op(_ENTRY + 5, "RETURN", [], index=4),
    ]
    lift = parse_lift(raw_json(document), binary)

    def reference(address: int, index: int, opcode: str) -> dict[str, Any]:
        return {"address": loc(address), "index": index, "opcode": opcode}

    jump = reference(_ENTRY, 2, "BRANCHIND")
    selector = reference(_ENTRY, 1, "INT_AND")
    case = reference(_ENTRY + 5, 3, "COPY")
    finish = reference(_ENTRY + 5, 4, "RETURN")
    storage = {"address": loc(0x38, "register"), "size": 4}

    def marker(
        kind: str,
        token: bytes,
        operation: dict[str, Any],
        *,
        value: str | None = None,
        block: dict[str, Any] | None = None,
        parameter: dict[str, Any] | None = None,
        after: bytes = b"",
    ) -> dict[str, Any]:
        start = _SOURCE.index(after + token) + len(after)
        return {
            "start": start,
            "end": start + len(token),
            "kind": kind,
            "value": value,
            "operation": operation,
            "block": block,
            "parameter": parameter,
        }

    arm = {
        "index": 1,
        "entry": loc(_ENTRY + 5),
        "indirect_entries": [jump],
        "successors": [2],
    }
    join = {
        "index": 2,
        "entry": loc(_ENTRY + 5),
        "indirect_entries": [],
        "successors": [],
    }
    record = {
        "schema_version": 1,
        "binary_sha256": lift.binary_sha256,
        "lift_sha256": lift.lift_sha256,
        "bodies": [
            {
                "function": loc(_ENTRY),
                "source_sha256": sha256(_SOURCE).hexdigest(),
                "source_bytes": len(_SOURCE),
                "markers": [
                    marker("switch", b"switch", jump),
                    marker(
                        "parameter",
                        b"p",
                        selector,
                        parameter={
                            "ordinal": 0,
                            "storage": [storage],
                            "operand": storage,
                            "definition": None,
                        },
                        after=b"switch(",
                    ),
                    marker("case", b"0", case, value="0", block=arm),
                    marker("default", b"default", case, block=arm),
                    marker("return", b"return", finish, block=join),
                ],
            }
        ],
        "gaps": [],
    }
    return lift, record


def test_ordinary_evidence_resolves_exact_operations_and_source_spans() -> None:
    lift, document = proposal()
    raw = raw_json(document)
    artifact = parse_ordinary_source(raw, lift)
    (body,) = artifact.bodies
    assert artifact.sha256 == sha256(raw).hexdigest()
    assert body.source_sha256 == sha256(_SOURCE).hexdigest()
    assert [_SOURCE[m.start : m.end] for m in body.markers] == [
        b"switch",
        b"p",
        b"0",
        b"default",
        b"return",
    ]
    switch, parameter, case, default, finish = body.markers
    assert parameter.parameter is not None
    assert parameter.parameter.storage == (parameter.parameter.operand,)
    assert case.block is not None and finish.block is not None
    assert case.block == default.block
    assert case.block.indirect_entries == (switch.operation,)
    assert case.block.successors == (finish.block.index,)
    assert case.value == 0 and default.value is None


@pytest.mark.parametrize(
    "fault", ["identity", "operation", "span", "block", "owner", "value", "type", "gap"]
)
def test_ordinary_evidence_rejects_inconsistent_records(fault: str) -> None:
    lift, document = proposal()
    (body,) = document["bodies"]
    markers = body["markers"]
    if fault == "identity":
        document["lift_sha256"] = "0" * 64
    elif fault == "operation":
        markers[1]["operation"]["index"] = 800
    elif fault == "span":
        markers[2]["start"] = markers[1]["start"]
    elif fault == "block":
        markers[2]["block"] = {**markers[2]["block"], "successors": [3]}
    elif fault == "owner":
        markers[2]["block"]["entry"] = loc(0x100140)
    elif fault == "value":
        markers[2]["value"] = "00"
    elif fault == "type":
        document["schema_version"] = True
    else:
        document["gaps"] = [
            {"function": body["function"], "reason": "ordinary_source_limit"}
        ]
    with pytest.raises(MappingError):
        parse_ordinary_source(raw_json(document), lift)


@pytest.mark.parametrize("fault", ["digest", "length", "split-utf8"])
def test_ordinary_evidence_binds_the_exact_utf8_source(fault: str) -> None:
    lift, document = proposal()
    (body,) = document["bodies"]
    switch = body["markers"][0]
    if fault == "digest":
        body["source_sha256"] = "0" * 64
    elif fault == "length":
        body["source_bytes"] += 1
    else:
        switch["start"] = _SOURCE.index("📘".encode()) + 1
    with pytest.raises(MappingError, match="source|token"):
        parse_ordinary_source(raw_json(document), lift)


def test_lower_reader_retains_source_slices_without_proving_c_tokens() -> None:
    lift, document = proposal()
    switch = document["bodies"][0]["markers"][0]
    switch["start"] += 1
    parsed = parse_ordinary_source(raw_json(document), lift)
    (body,) = parsed.bodies
    assert body.source == _SOURCE
    marker = body.markers[0]
    assert body.source[marker.start : marker.end] == b"witch"
    assert marker.kind == "switch"
