from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from struct import pack_into
from typing import Any

import pytest
from test_lift_evidence import proposal, wire
from test_recovery_u1 import fixture, loc, mapping_wire, op, raw_json

from phoenix.lift.evidence import Address, JumpEvidence
from phoenix.lift.index import LiftIndex, parse_lift
from phoenix.lift.mapping import MappingError, parse_mapping
from phoenix.lift.switch_graph import parse_switch_graph
from phoenix.recover.addresses import AddressProof, prove_addresses
from phoenix.recover.switches import recover_switch

BASE = 0x100000


def location(offset: int) -> dict[str, str]:
    return loc(BASE + offset)


def constant(value: int, size: int) -> dict[str, Any]:
    return {"address": loc(value, "const"), "size": size, "definition": None}


def value(address: int, space: str, size: int, site: int, index: int) -> dict[str, Any]:
    return {
        "address": loc(address, space),
        "size": size,
        "definition": {"address": location(site), "index": index},
    }


def normalized() -> list[dict[str, Any]]:
    register = {"address": loc(0x38, "register"), "size": 4, "definition": None}
    mask = value(0x38, "register", 4, 0x100, 1)
    extend = value(0x38, "register", 8, 0x100, 2)
    less = value(0x100, "unique", 1, 0x106, 3)
    scale = value(0x200, "unique", 8, 0x10F, 5)
    pointer = value(0x300, "unique", 8, 0x10F, 6)
    loaded = value(0x400, "unique", 4, 0x10F, 7)
    signed = value(0x10, "register", 8, 0x10F, 8)
    target = value(0x10, "register", 8, 0x113, 9)
    table = constant(BASE + 0x1000, 8)
    return [
        {
            "index": 0,
            "start": location(0x100),
            "successors": [2, 1],
            "true_out": 1,
            "false_out": 2,
            "operations": [
                op(BASE + 0x100, "INT_AND", [register, constant(3, 4)], mask, 1),
                op(BASE + 0x100, "INT_ZEXT", [mask], extend, 2),
                op(BASE + 0x106, "INT_LESS", [mask, constant(2, 4)], less, 3),
                op(BASE + 0x106, "CBRANCH", [constant(0, 1), less], index=4),
            ],
        },
        {
            "index": 1,
            "start": location(0x108),
            "successors": [3, 4],
            "true_out": None,
            "false_out": None,
            "operations": [
                op(BASE + 0x10F, "INT_MULT", [extend, constant(4, 8)], scale, 5),
                op(BASE + 0x10F, "INT_ADD", [scale, table], pointer, 6),
                op(BASE + 0x10F, "LOAD", [constant(433, 4), pointer], loaded, 7),
                op(BASE + 0x10F, "INT_SEXT", [loaded], signed, 8),
                op(BASE + 0x113, "INT_ADD", [signed, table], target, 9),
                op(BASE + 0x116, "BRANCHIND", [target], index=10),
            ],
        },
        *(
            {
                "index": index,
                "start": location(address),
                "successors": [],
                "true_out": None,
                "false_out": None,
                "operations": [],
            }
            for index, address in ((2, 0x120), (3, 0x118), (4, 0x119))
        ),
    ]


def switch_fixture(
    layout: str = "normal",
    *,
    prepare_function: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[bytes, LiftIndex, AddressProof, dict[str, Any]]:
    original, document = fixture()
    binary = bytearray(original)
    program_headers = 0x280
    binary[program_headers : program_headers + 168] = original[64:232]
    pack_into("<Q", binary, 32, program_headers)
    pack_into("<H", binary, 56, 4)
    pack_into(
        "<IIQQQQQQ",
        binary,
        program_headers + 168,
        1,
        6 if layout == "mutable" else 4,
        0x400,
        0x1000,
        0,
        0x40,
        0x40,
        1,
    )
    second = {"duplicate": 0x118, "interior": 0x101}.get(layout, 0x119)
    pack_into("<ii", binary, 0x400, 0x118 - 0x1000, second - 0x1000)
    if layout == "alternate":
        pack_into("<ii", binary, 0x408, 0x119 - 0x1008, 0x118 - 0x1008)
    if layout == "relocated":
        pack_into("<Q", binary, 0xC00, 0x1000)
    if layout == "textrel":
        pack_into("<QQ", binary, program_headers + 2 * 56 + 32, 14 * 16, 14 * 16)
        pack_into("<qQ", binary, 0x800 + 12 * 16, 22, 0)
    if layout == "writable-code":
        pack_into("<I", binary, program_headers + 4, 7)
    bypass = layout in ("reentry", "raw-reentry", "unreported-reentry")
    instructions = []
    for offset, text, branch in (
        (0x100, "83e703", None),
        (0x103, "83ff01", None),
        (0x106, "7718", "CBRANCH"),
        (0x108, "488d0df10e0000", None),
        (0x10F, "486314b9", None),
        (0x113, "4801ca", None),
        (0x116, "ffe2", "BRANCHIND"),
        (0x118, "c3", None),
        (0x119, "c3", None),
        (0x120, "ebe6" if bypass else "c3", None),
    ):
        data = bytes.fromhex(text)
        binary[offset : offset + len(data)] = data
        instructions.append(
            {
                "address": location(offset),
                "size": len(data),
                "text": "unused",
                "pcode": [] if branch is None else [op(BASE + offset, branch, [])],
            }
        )
    if layout in ("raw-reentry", "unreported-reentry"):
        reported = 0x108 if layout == "raw-reentry" else 0x118
        instructions[-1]["pcode"] = [
            op(
                BASE + 0x120,
                "BRANCH",
                [{"address": location(reported), "size": 8, "definition": None}],
            )
        ]
    function = document["functions"][0]
    function["instructions"] = instructions
    function["ranges"] = [
        {
            "start": location(0x100),
            "end": location(0x121 if bypass else 0x120),
        }
    ]
    function["flow_edges"] = [
        {
            "from_block": location(0x100),
            "to_block": location(target),
            "site": location(0x106),
            "target": location(target),
            "kind": kind,
        }
        for target, kind in ((0x108, "FALL_THROUGH"), (0x120, "CONDITIONAL_JUMP"))
    ]
    if layout == "reentry":
        function["flow_edges"].append(
            {
                "from_block": location(0x120),
                "to_block": location(0x108),
                "site": location(0x120),
                "target": location(0x108),
                "kind": "UNCONDITIONAL_JUMP",
            }
        )
    function["static_evidence"] = wire(
        replace(
            proposal(),
            jump_tables=(
                JumpEvidence(
                    Address("ram", hex(BASE + 0x116)),
                    tuple(
                        Address("ram", hex(BASE + target))
                        for target in (0x118, second, 0x120)
                    ),
                    (0, 1),
                ),
            ),
        )
    )
    if layout == "external-proposal":
        document["functions"][1]["static_evidence"] = wire(
            replace(
                proposal(),
                jump_tables=(
                    JumpEvidence(
                        Address("ram", hex(BASE + 0x140)),
                        (Address("ram", hex(BASE + 0x108)),),
                        (0,),
                    ),
                ),
            )
        )
    document["call_edges"] = []
    if prepare_function is not None:
        prepare_function(function)
    data = bytes(binary)
    raw = raw_json(document)
    lift = parse_lift(raw, data)
    mapping = parse_mapping(raw_json(mapping_wire(data, raw)), data, raw)
    proof = prove_addresses(data, lift, mapping)
    blocks = normalized()
    if layout == "duplicate":
        blocks[1]["successors"] = [3]
    graph = {
        "schema_version": 1,
        "binary_sha256": lift.binary_sha256,
        "lift_sha256": lift.lift_sha256,
        "style": "normalize",
        "memory_space_id": 433,
        "function": location(0x100),
        "blocks": blocks,
    }
    return data, lift, proof, graph


@pytest.mark.parametrize("layout", ["normal", "duplicate"])
def test_switch_preserves_each_label_and_the_default(layout: str) -> None:
    binary, lift, proof, document = switch_fixture(layout)
    graph = parse_switch_graph(raw_json(document), lift)
    plan = recover_switch(graph, binary, lift, proof)
    second = 0x118 if layout == "duplicate" else 0x119
    assert [(case.selector, case.target) for case in plan.cases] == [
        (0, 0x118),
        (1, second),
    ]
    assert plan.default == 0x120 and plan.table == 0x1000
    assert plan.table_sha256 == sha256(binary[0x400:0x408]).hexdigest()


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        ("mutable", "read-only"),
        ("interior", "instruction witness"),
        ("relocated", "relocation could change"),
    ],
)
def test_switch_refuses_unproved_table_or_destination(
    layout: str, message: str
) -> None:
    binary, lift, proof, document = switch_fixture(layout)
    with pytest.raises(MappingError, match=message):
        recover_switch(
            parse_switch_graph(raw_json(document), lift), binary, lift, proof
        )


@pytest.mark.parametrize("change", ["direction", "bound", "predecessor", "table"])
def test_switch_refuses_contradictory_graph_or_bytes(change: str) -> None:
    binary, lift, proof, document = switch_fixture()
    guard, dispatch, default, *_ = document["blocks"]
    if change == "direction":
        guard["true_out"], guard["false_out"] = guard["false_out"], guard["true_out"]
    elif change == "bound":
        guard["operations"][2]["inputs"][1] = constant(3, 4)
    elif change == "predecessor":
        default["successors"] = [dispatch["index"]]
    else:
        modified = bytearray(binary)
        modified[0x400] ^= 1
        binary = bytes(modified)
    graph = parse_switch_graph(raw_json(document), lift)
    with pytest.raises(MappingError):
        recover_switch(graph, binary, lift, proof)


@pytest.mark.parametrize(
    "change", ["duplicate-block", "duplicate-op", "dangling", "identity"]
)
def test_graph_reader_rejects_ambiguous_or_unbound_evidence(change: str) -> None:
    _, lift, _, document = switch_fixture()
    blocks = document["blocks"]
    if change == "duplicate-block":
        blocks[1]["index"] = blocks[0]["index"]
    elif change == "duplicate-op":
        blocks[1]["operations"][0]["sequence"] = blocks[0]["operations"][0]["sequence"]
    elif change == "dangling":
        blocks[1]["successors"].append(511)
    else:
        document["lift_sha256"] = "0" * 64
    with pytest.raises(MappingError):
        parse_switch_graph(raw_json(document), lift)


@pytest.mark.parametrize(
    "conflict", ["alternate", "reentry", "raw-reentry", "register", "load"]
)
def test_switch_refuses_a_graph_that_disagrees_with_raw_dispatch(
    conflict: str,
) -> None:
    binary, lift, proof, document = switch_fixture(conflict)
    guard, dispatch, *_ = document["blocks"]
    if conflict == "alternate":
        dispatch["operations"][1]["inputs"][1] = constant(BASE + 0x1008, 8)
        dispatch["operations"][4]["inputs"][1] = constant(BASE + 0x1008, 8)
    elif conflict == "register":
        for operation in guard["operations"] + dispatch["operations"]:
            for operand in [operation["output"], *operation["inputs"]]:
                if operand is not None and operand["address"] == loc(0x38, "register"):
                    operand["address"] = loc(0, "register")
    elif conflict == "load":
        load = dispatch["operations"][2]
        load["sequence"]["address"] = location(0x120)
        load["output"]["definition"]["address"] = location(0x120)
        dispatch["operations"][3]["inputs"][0]["definition"]["address"] = location(
            0x120
        )
    with pytest.raises(MappingError):
        recover_switch(
            parse_switch_graph(raw_json(document), lift), binary, lift, proof
        )


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        ("unreported-reentry", "original relative transfer"),
        ("external-proposal", "proposed indirect transfer"),
        ("textrel", "relocation could change"),
        ("writable-code", "in writable memory"),
    ],
)
def test_switch_checks_admitted_entries_and_instruction_immutability(
    layout: str, message: str
) -> None:
    binary, lift, proof, document = switch_fixture(layout)
    with pytest.raises(MappingError, match=message):
        recover_switch(
            parse_switch_graph(raw_json(document), lift), binary, lift, proof
        )
