from dataclasses import replace
from hashlib import sha256
from typing import Any

import pytest
from test_recovery_switches import BASE, constant, location, switch_fixture
from test_recovery_u1 import loc, op, raw_json

from phoenix.generate.checked_switch import emit_checked_switch
from phoenix.generate.switch_source import SwitchSourceError
from phoenix.lift.switch_graph import parse_switch_graph
from phoenix.lift.switch_source import parse_ordinary_source

_SOURCE = (
    b"uint original(uint select){switch(select&3){"
    b"case 0:case 1:result = 11;break;default:result = 22;}return result;}"
)
_REGISTER = {"address": loc(0x38, "register"), "size": 4}


def _function(function: dict[str, Any]) -> None:
    function["decompilation"]["raw_c"] = _SOURCE.decode("ascii")
    function["decompilation"]["analyzed_pcode"] = [
        op(
            BASE + 0x100, "INT_AND", [{**_REGISTER, "definition": None}, constant(3, 4)]
        ),
        op(BASE + 0x116, "BRANCHIND", []),
        op(BASE + 0x118, "COPY", []),
        op(BASE + 0x120, "COPY", []),
        op(BASE + 0x119, "RETURN", []),
    ]
    function["blocks"] = [
        {
            "entry": location(offset),
            "ranges": [{"start": location(offset), "end": location(offset)}],
        }
        for offset in (0x118, 0x119, 0x120)
    ]


def _reference(offset: int, opcode: str) -> dict[str, Any]:
    return {"address": location(offset), "index": 0, "opcode": opcode}


def _marker(
    kind: str,
    token: bytes,
    operation: dict[str, Any],
    *,
    after: bytes = b"",
    value: str | None = None,
    block: dict[str, Any] | None = None,
    parameter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start = _SOURCE.index(after + token) + len(after)
    return {
        "kind": kind,
        "start": start,
        "end": start + len(token),
        "operation": operation,
        "value": value,
        "block": block,
        "parameter": parameter,
    }


def _artifact(binary_sha256: str, lift_sha256: str) -> dict[str, Any]:
    switch = _reference(0x116, "BRANCHIND")
    case_block = {
        "index": 1,
        "entry": location(0x118),
        "indirect_entries": [switch],
        "successors": [3],
    }
    default_block = {**case_block, "index": 2, "entry": location(0x120)}
    join = {
        "index": 3,
        "entry": location(0x119),
        "indirect_entries": [],
        "successors": [],
    }
    return {
        "schema_version": 1,
        "binary_sha256": binary_sha256,
        "lift_sha256": lift_sha256,
        "gaps": [],
        "bodies": [
            {
                "function": location(0x100),
                "source_sha256": sha256(_SOURCE).hexdigest(),
                "source_bytes": len(_SOURCE),
                "markers": [
                    _marker("switch", b"switch", switch),
                    _marker(
                        "parameter",
                        b"select",
                        _reference(0x100, "INT_AND"),
                        after=b"switch(",
                        parameter={
                            "ordinal": 0,
                            "storage": [_REGISTER],
                            "operand": _REGISTER,
                            "definition": None,
                        },
                    ),
                    _marker(
                        "case",
                        b"0",
                        _reference(0x118, "COPY"),
                        after=b"case ",
                        value="0",
                        block=case_block,
                    ),
                    _marker(
                        "case",
                        b"1",
                        _reference(0x118, "COPY"),
                        after=b"case ",
                        value="1",
                        block=case_block,
                    ),
                    _marker(
                        "default",
                        b"default",
                        _reference(0x120, "COPY"),
                        block=default_block,
                    ),
                    _marker(
                        "return", b"return", _reference(0x119, "RETURN"), block=join
                    ),
                ],
            },
        ],
    }


@pytest.mark.parametrize(
    "fault", [None, "label", "arm", "join", "selector", "operation"]
)
def test_checked_switch_keeps_stacked_labels_and_rejects_conflicts(
    fault: str | None,
) -> None:
    binary, lift, proof, raw_graph = switch_fixture(
        "duplicate", prepare_function=_function
    )
    graph = parse_switch_graph(raw_json(raw_graph), lift)
    artifact = _artifact(lift.binary_sha256, lift.lift_sha256)
    markers = artifact["bodies"][0]["markers"]
    if fault == "label":
        markers[3]["value"] = "2"
    elif fault == "arm":
        markers[3]["block"] = {**markers[4]["block"]}
    elif fault == "join":
        markers[4]["block"] = {**markers[4]["block"], "successors": [7]}
    elif fault == "selector":
        markers[1]["parameter"]["ordinal"] = 1
    (body,) = parse_ordinary_source(raw_json(artifact), lift).bodies
    if fault == "operation":
        marker = body.markers[2]
        changed = replace(marker, operation=replace(marker.operation, opcode="INT_ADD"))
        body = replace(body, markers=(*body.markers[:2], changed, *body.markers[3:]))
    if fault is not None:
        with pytest.raises(SwitchSourceError, match="ordinary"):
            emit_checked_switch(binary, lift, proof, graph, body)
        return
    emitted = emit_checked_switch(binary, lift, proof, graph, body)
    assert emitted.cases == (0, 1)
    assert emitted.source == (
        b"uint original(uint select){switch(((uint32_t)(select) & 3u)){"
        b"case 0u:case 1u:result = 11;break;default:result = 22;}return result;}"
    )
