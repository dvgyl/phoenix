from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from typing import Any

import pytest
from test_ordinary_switch_evidence import proposal
from test_recovery_u1 import fixture, raw_json

from phoenix.generate.switch_binding import (
    BoundSwitchSource,
    SourceConflict,
    SourceGap,
    admit_switch_source,
)
from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import GhidraVA
from phoenix.lift.switch_source import OrdinarySourceObservation, parse_ordinary_source

_BASE = (
    "uint f(uint param){switch(param & 1u){case 0:param=2;break;"
    "default:param=3;}return param;}"
)
_CONTEXTS = (
    ("switch", "switch("),
    ("param", "param &"),
    ("0", "0:"),
    ("default", "default:"),
    ("return", "return param"),
)


def observation(
    source: str = _BASE,
    overrides: tuple[tuple[int, str, str], ...] = (),
) -> OrdinarySourceObservation:
    _, record = proposal()
    choices = list(_CONTEXTS)
    for index, spelling, context in overrides:
        choices[index] = spelling, context
    (body,) = record["bodies"]
    for marker, (spelling, context) in zip(body["markers"], choices, strict=True):
        start = len(source[: source.index(context)].encode("utf-8"))
        marker.update(start=start, end=start + len(spelling.encode("utf-8")))
    binary, document = fixture()
    decompilation = document["functions"][0]["decompilation"]
    decompilation["raw_c"] = source
    operations: list[dict[str, Any]] = []
    for marker in body["markers"]:
        if marker["kind"] == "default":
            continue
        reference = marker["operation"]
        operations.append(
            {
                "sequence": {
                    "address": reference["address"],
                    "index": reference["index"],
                },
                "opcode": reference["opcode"],
                "output": None,
                "inputs": [],
            }
        )
    decompilation["analyzed_pcode"] = operations
    lift = parse_lift(raw_json(document), binary)
    record["lift_sha256"] = lift.lift_sha256
    raw = source.encode("utf-8")
    body.update(source_sha256=sha256(raw).hexdigest(), source_bytes=len(raw))
    return parse_ordinary_source(raw_json(record), lift).bodies[0]


@pytest.mark.parametrize(
    ("source", "overrides"),
    [
        (
            _BASE.replace("param", "paramé"),
            ((1, "param", "paramé &"), (4, "return", "return paramé")),
        ),
        (
            _BASE.replace("param", "param\\\neter"),
            ((1, "param", "param\\\neter &"), (4, "return", "return param\\\neter")),
        ),
        (_BASE.replace("case 0:", "case (int)1.0:"), ((2, "1", "1.0:"),)),
        (_BASE.replace("case 0:", "case (int)'0':"), ((2, "0", "0':"),)),
        (
            _BASE.replace("{switch", '{const char *s="switch";switch'),
            ((0, "switch", 'switch"'),),
        ),
        ("#define UNUSED 1\n" + _BASE, ()),
    ],
)
def test_unsupported_c_cannot_become_bound_source(
    source: str, overrides: tuple[tuple[int, str, str], ...]
) -> None:
    observed = observation(source, overrides)
    admitted = admit_switch_source(observed)
    assert isinstance(admitted, SourceGap)
    assert admitted.reason == "syntax_unsupported"


@pytest.mark.parametrize("fault", ["partial", "comment", "value", "missing", "extra"])
def test_parseable_source_with_false_markers_is_a_conflict(fault: str) -> None:
    source = "/* switch */" + _BASE
    original = observation(source)
    markers = list(original.markers)
    if fault == "partial":
        markers[1] = replace(markers[1], end=markers[1].end - 1)
    elif fault == "comment":
        markers[0] = replace(markers[0], start=3, end=9)
    elif fault == "value":
        markers[2] = replace(markers[2], value=7)
    elif fault == "missing":
        del markers[2]
    else:
        markers.insert(3, deepcopy(markers[2]))
    observed = replace(original, markers=tuple(markers))
    admitted = admit_switch_source(observed)
    assert isinstance(admitted, SourceConflict)
    assert admitted.reason == "marker_correspondence"


def test_one_source_gap_does_not_remove_another_bound_function() -> None:
    supported = observation("/* é📘 */\r\n" + _BASE)
    unsupported = replace(
        observation("#define UNUSED 1\n" + _BASE), function=GhidraVA(42)
    )
    admitted = tuple(admit_switch_source(body) for body in (supported, unsupported))
    assert isinstance(admitted[0], BoundSwitchSource)
    assert admitted[0].source == supported.source
    assert isinstance(admitted[1], SourceGap)


def test_source_capacity_error_remains_a_limit_gap() -> None:
    source = _BASE.replace("param & 1u", "(" * 40 + "param & 1u" + ")" * 40)
    observed = observation(source)
    admitted = admit_switch_source(observed)
    assert isinstance(admitted, SourceGap) and admitted.reason == "limit_exceeded"
