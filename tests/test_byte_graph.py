"""Synthetic structural controls do not establish live U5 capability."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_recovery_u1 import fixture, loc, op, raw_json

from phoenix.lift.byte_graph import (
    ByteGraph,
    ByteGraphError,
    ByteGraphFormatError,
    ByteGraphLimitError,
    ByteGraphLimits,
    parse_byte_graph,
)
from phoenix.lift.index import LiftIndex, parse_lift

BASE = 0x100100
PASS = "a" * 64


def wire(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def sequence(offset: int, index: int = 0) -> dict[str, Any]:
    return {"address": loc(BASE + offset), "index": index}


def stored(
    address: int, space: str, size: int, definition: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"address": loc(address, space), "size": size, "definition": definition}


def sample() -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Specify an ordinary bank and a separate ordered graph for one synthetic loop."""
    binary, document = fixture()
    function = document["functions"][0]
    function["instructions"] = [
        {
            "address": loc(BASE + i),
            "size": 1,
            "text": "synthetic",
            "pcode": [op(BASE + i, "COPY", [stored(0, "const", 8)])],
        }
        for i in range(6)
    ]
    function["blocks"] = [
        {"entry": loc(BASE), "ranges": [{"start": loc(BASE), "end": loc(BASE + 5)}]}
    ]
    source = "int f(void){/* µ */return 0;}\n"
    function["decompilation"]["raw_c"] = source
    function["decompilation"]["analyzed_pcode"] = [
        op(
            BASE,
            "COPY",
            [stored(0x10, "register", 8)],
            stored(0x20, "register", 8, sequence(0)),
        ),
        op(
            BASE + 1,
            "MULTIEQUAL",
            [stored(0, "const", 8), stored(0x28, "register", 8, sequence(3))],
            stored(0x28, "register", 8, sequence(1)),
        ),
        op(
            BASE + 1,
            "INT_LESS",
            [stored(0x28, "register", 8, sequence(1)), stored(0x10, "register", 8)],
            stored(0x100, "unique", 1, sequence(1, 1)),
            1,
        ),
        op(
            BASE + 1,
            "CBRANCH",
            [stored(BASE + 3, "ram", 8), stored(0x100, "unique", 1, sequence(1, 1))],
            index=2,
        ),
        op(
            BASE + 3,
            "INT_ADD",
            [stored(0x28, "register", 8, sequence(1)), stored(1, "const", 8)],
            stored(0x28, "register", 8, sequence(3)),
        ),
        op(BASE + 3, "BRANCH", [stored(BASE + 1, "ram", 8)], index=1),
        op(
            BASE + 5,
            "RETURN",
            [stored(0x30, "register", 8), stored(0x28, "register", 8, sequence(1))],
        ),
        op(
            BASE + 4,
            "COPY",
            [stored(0x40, "register", 8)],
            stored(0x200, "unique", 8, sequence(4)),
        ),
    ]
    function_key = {
        "binary_sha256": sha256(binary).hexdigest(),
        "ghidra_entry": hex(BASE),
    }

    def block_key(index: int) -> dict[str, Any]:
        return {"function": deepcopy(function_key), "pass_id": PASS, "index": index}

    def value_key(index: int) -> dict[str, Any]:
        return {"function": deepcopy(function_key), "pass_id": PASS, "local_id": index}

    def op_key(offset: int, index: int = 0, domain: str = "analyzed") -> dict[str, Any]:
        return {
            "function": deepcopy(function_key),
            "pass_id": PASS,
            "domain": domain,
            "sequence": sequence(offset, index),
        }

    def operation(
        offset: int,
        index: int,
        opcode: str,
        inputs: list[int],
        output: int | None = None,
    ) -> dict[str, Any]:
        return {
            "id": op_key(offset, index),
            "opcode": opcode,
            "inputs": [value_key(i) for i in inputs],
            "output": None if output is None else value_key(output),
        }

    def edge(index: int, reciprocal: int) -> dict[str, Any]:
        return {"other": block_key(index), "reciprocal_slot": reciprocal}

    def block(
        index: int,
        offset: int,
        incoming: list[dict[str, Any]],
        outgoing: list[dict[str, Any]],
        operations: list[dict[str, Any]],
        conditional: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": block_key(index),
            "start": hex(BASE + offset),
            "incoming": incoming,
            "outgoing": outgoing,
            "operations": operations,
            "true_slot": 1 if conditional else None,
            "false_slot": 0 if conditional else None,
        }

    values = [
        (0, 0x10, "register", 8, None, "input", None),
        (1, 0x20, "register", 8, op_key(0), "defined", None),
        (2, 0, "const", 8, None, "constant", "0x0"),
        (3, 0x28, "register", 8, op_key(1), "defined", None),
        (4, 0x28, "register", 8, op_key(3), "defined", None),
        (5, 0x100, "unique", 1, op_key(1, 1), "defined", None),
        (6, BASE + 3, "ram", 8, None, "unexplained", None),
        (7, 1, "const", 8, None, "constant", "0x1"),
        (8, BASE + 1, "ram", 8, None, "free", None),
        (9, 0x30, "register", 8, None, "input", None),
    ]
    graph = {
        "schema": 1,
        "binary_sha256": sha256(binary).hexdigest(),
        "lift_sha256": sha256(raw_json(document)).hexdigest(),
        "function": function_key,
        "pass_id": PASS,
        "raw_c_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "ram_space_id": 27,
        "ram_word_bytes": 1,
        "address_bits": 64,
        "byte_bits": 8,
        "endian": "little",
        "entry": block_key(10),
        "blocks": [
            block(10, 0, [], [edge(20, 0)], [operation(0, 0, "COPY", [0], 1)]),
            block(
                20,
                1,
                [edge(10, 0), edge(30, 0)],
                [edge(40, 0), edge(30, 0)],
                [
                    operation(1, 0, "MULTIEQUAL", [2, 4], 3),
                    operation(1, 1, "INT_LESS", [3, 0], 5),
                    operation(1, 2, "CBRANCH", [6, 5]),
                ],
                True,
            ),
            block(
                30,
                3,
                [edge(20, 1)],
                [edge(20, 1)],
                [operation(3, 0, "INT_ADD", [3, 7], 4), operation(3, 1, "BRANCH", [8])],
            ),
            block(40, 5, [edge(20, 0)], [], [operation(5, 0, "RETURN", [9, 3])]),
            block(50, 4, [], [], []),
        ],
        "values": [
            {
                "id": value_key(i),
                "storage": loc(address, space),
                "size_bytes": size,
                "definition": definition,
                "kind": kind,
                "bits": bits,
                "address_tied": False,
                "persistent": False,
                "unaffected": False,
            }
            for i, address, space, size, definition, kind, bits in values
        ],
        "excluded_dead": [op_key(4)],
        "raw_instruction_sites": [hex(BASE + i) for i in range(6)],
        "explicit_volatile_sites": [op_key(0, domain="raw"), op_key(0)],
        "export_gaps": [
            {"code": "source_unbound", "block": None, "operation": None, "value": None},
            {
                "code": "interface_unproved",
                "block": None,
                "operation": None,
                "value": value_key(0),
            },
        ],
    }
    return binary, document, graph


def bound(binary: bytes, document: dict[str, Any], graph: dict[str, Any]) -> LiftIndex:
    raw = raw_json(document)
    graph["lift_sha256"] = sha256(raw).hexdigest()
    return parse_lift(raw, binary)


def read_sample() -> tuple[ByteGraph, dict[str, Any], LiftIndex]:
    binary, document, graph = sample()
    lift = bound(binary, document, graph)
    return parse_byte_graph(wire(graph), lift), graph, lift


def test_exact_shapes_and_independent_wire_round_trip() -> None:
    graph, expected, lift = read_sample()
    assert graph.to_bytes() == wire(expected)
    assert graph.record() == expected
    assert graph.sha256 == sha256(wire(expected)).hexdigest()
    assert parse_byte_graph(graph.to_bytes(), lift) == graph
    assert [block.id.index for block in graph.blocks] == [10, 20, 30, 40, 50]
    assert [value.id.local_id for value in graph.values] == list(range(10))
    assert graph.values[3].storage == graph.values[4].storage
    assert graph.values[3].id != graph.values[4].id
    assert graph.values[3].definition != graph.values[4].definition
    assert [v.local_id for v in graph.blocks[1].operations[0].inputs] == [2, 4]
    assert [e.other.index for e in graph.blocks[1].incoming] == [10, 30]
    assert [e.other.index for e in graph.blocks[1].outgoing] == [40, 30]
    assert graph.blocks[4].operations == ()
    assert graph.values[6].kind == "unexplained"
    assert graph.values[8].kind == "free"
    assert (
        graph.explicit_volatile_sites[0].sequence
        == graph.explicit_volatile_sites[1].sequence
    )
    assert graph.explicit_volatile_sites[0] != graph.explicit_volatile_sites[1]
    assert len(graph.export_gaps) == 2
    assert {field.name for field in fields(graph)} == set(expected)


def test_records_have_no_mutable_children_or_caller_aliases() -> None:
    graph, original, _ = read_sample()
    saved = graph.to_bytes()
    original["blocks"][0]["operations"][0]["opcode"] = "CHANGED"
    record = graph.record()
    assert isinstance(record["blocks"], list)
    record["blocks"].clear()
    assert graph.to_bytes() == saved

    def check(value: object) -> None:
        if isinstance(value, tuple):
            for child in value:
                check(child)
        elif hasattr(value, "__dataclass_fields__"):
            for field in fields(value):  # type: ignore[arg-type]
                check(getattr(value, field.name))
            with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
                setattr(value, "unplanned", True)
        else:
            assert type(value) in (int, str, bool, type(None))

    check(graph)
    with pytest.raises(FrozenInstanceError):
        setattr(graph.values[0], "persistent", True)


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), True),
        (("schema",), 2),
        (("ram_word_bytes",), 2),
        (("address_bits",), 32),
        (("byte_bits",), 16),
        (("endian",), "big"),
        (("ram_space_id",), -1),
        (("ram_space_id",), True),
        (("ram_space_id",), 1.0),
        (("ram_space_id",), 2**32),
        (("pass_id",), "A" * 64),
        (("binary_sha256",), "b" * 64),
        (("lift_sha256",), "b" * 64),
        (("raw_c_sha256",), "b" * 64),
        (("function", "ghidra_entry"), hex(BASE + 1)),
        (("function", "binary_sha256"), "b" * 64),
        (("entry", "pass_id"), "b" * 64),
        (("entry", "index"), 99),
        (("entry", "function", "ghidra_entry"), hex(BASE + 0x40)),
        (("blocks", 0, "start"), hex(BASE + 1)),
        (("blocks", 4, "start"), hex(BASE + 100)),
        (("blocks", 0, "id", "index"), True),
        (("blocks", 0, "operations", 0, "id", "domain"), "raw"),
        (("blocks", 0, "operations", 0, "id", "domain"), "unknown"),
        (("blocks", 0, "operations", 0, "id", "pass_id"), "b" * 64),
        (("blocks", 0, "operations", 0, "id", "sequence", "index"), True),
        (("blocks", 0, "operations", 0, "id", "sequence", "index"), 1.0),
        (("blocks", 0, "operations", 0, "id", "sequence", "index"), 5),
        (("blocks", 0, "operations", 0, "opcode"), "STORE"),
        (("blocks", 0, "operations", 0, "output"), None),
        (("blocks", 0, "operations", 0, "inputs"), []),
        (("blocks", 0, "operations", 0, "inputs", 0, "local_id"), 900),
        (("values", 0, "kind"), "parameter"),
        (("values", 0, "kind"), "defined"),
        (("values", 0, "size_bytes"), 0),
        (("values", 0, "size_bytes"), True),
        (("values", 0, "size_bytes"), 1.0),
        (("values", 0, "size_bytes"), 4),
        (("values", 0, "storage", "space"), "unique"),
        (("values", 0, "storage", "offset"), "0x11"),
        (("values", 0, "bits"), "0x0"),
        (("values", 0, "address_tied"), 0),
        (("values", 0, "persistent"), "false"),
        (("values", 0, "unaffected"), None),
        (("values", 0, "id", "local_id"), -1),
        (("values", 0, "id", "local_id"), 1.0),
        (("values", 0, "id", "pass_id"), "b" * 64),
        (("values", 1, "definition"), None),
        (("values", 1, "kind"), "input"),
        (("values", 1, "definition", "domain"), "raw"),
        (("values", 2, "kind"), "input"),
        (("values", 2, "bits"), None),
        (("values", 2, "bits"), "0x00"),
        (("values", 2, "bits"), "0x1"),
        (("values", 2, "bits"), 0),
        (("values", 2, "storage", "space"), "register"),
        (("excluded_dead", 0, "domain"), "raw"),
        (("excluded_dead", 0, "pass_id"), "b" * 64),
        (("explicit_volatile_sites", 0, "sequence", "index"), 99),
        (("export_gaps", 0, "code"), "emit_anyway"),
        (("export_gaps", 1, "value", "local_id"), 99),
        (("blocks", 1, "incoming", 1, "reciprocal_slot"), 1),
        (("blocks", 1, "incoming", 1, "reciprocal_slot"), 32),
        (("blocks", 1, "incoming", 1, "reciprocal_slot"), True),
        (("blocks", 1, "outgoing", 0, "other", "index"), 99),
        (("blocks", 1, "true_slot"), 0),
        (("blocks", 1, "true_slot"), None),
        (("blocks", 1, "false_slot"), 1),
        (("blocks", 1, "false_slot"), True),
        (("blocks", 0, "true_slot"), 1),
    ],
)
def test_contradictions_and_exact_types_reject(
    path: tuple[str | int, ...], value: object
) -> None:
    _, graph, lift = read_sample()
    target: Any = graph
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "address",
    ["0X1", "0x01", "0xA", "1", "-0x1", "0x10000000000000000", True, 1, 1.0, None],
)
@pytest.mark.parametrize("site", ["entry", "start", "storage", "sequence", "raw"])
def test_all_address_sites_require_canonical_hex(address: object, site: str) -> None:
    _, graph, lift = read_sample()
    if site == "entry":
        graph["function"]["ghidra_entry"] = address
    elif site == "start":
        graph["blocks"][0]["start"] = address
    elif site == "storage":
        graph["values"][0]["storage"]["offset"] = address
    elif site == "sequence":
        graph["excluded_dead"][0]["sequence"]["address"]["offset"] = address
    else:
        graph["raw_instruction_sites"][0] = address
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("function",),
        ("entry",),
        ("values", 0),
        ("values", 0, "id"),
        ("values", 0, "storage"),
        ("blocks", 0),
        ("blocks", 0, "operations", 0),
        ("blocks", 0, "operations", 0, "id"),
        ("blocks", 0, "operations", 0, "id", "sequence"),
        ("blocks", 0, "outgoing", 0),
        ("export_gaps", 0),
    ],
)
@pytest.mark.parametrize("change", ["extra", "missing"])
def test_every_object_shape_is_closed(path: tuple[str | int, ...], change: str) -> None:
    _, graph, lift = read_sample()
    target: Any = graph
    for part in path:
        target = target[part]
    if change == "extra":
        target["unknown"] = 0
    else:
        del target[next(iter(target))]
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_active",
        "extra_active",
        "duplicate_active",
        "two_parents",
        "missing_dead",
        "duplicate_dead",
        "active_and_dead",
        "missing_value",
        "extra_value",
        "duplicate_value",
        "missing_block",
        "extra_duplicate_block",
        "duplicate_edge",
        "missing_edge",
        "raw_missing",
        "raw_extra",
        "raw_duplicate",
        "raw_reordered",
        "volatile_duplicate",
        "gap_duplicate",
        "phi_reordered",
        "phi_after_nonphi",
        "branch_nonterminal",
    ],
)
def test_complete_inventories_and_order_reject(fault: str) -> None:
    _, graph, lift = read_sample()
    blocks = graph["blocks"]
    if fault == "missing_active":
        blocks[0]["operations"].clear()
    elif fault == "extra_active":
        extra = deepcopy(blocks[0]["operations"][0])
        extra["id"]["sequence"]["index"] = 99
        blocks[0]["operations"].append(extra)
    elif fault == "duplicate_active":
        blocks[0]["operations"].append(deepcopy(blocks[0]["operations"][0]))
    elif fault == "two_parents":
        blocks[4]["operations"].append(deepcopy(blocks[0]["operations"][0]))
    elif fault == "missing_dead":
        graph["excluded_dead"].clear()
    elif fault == "duplicate_dead":
        graph["excluded_dead"] *= 2
    elif fault == "active_and_dead":
        graph["excluded_dead"].append(deepcopy(blocks[0]["operations"][0]["id"]))
    elif fault == "missing_value":
        graph["values"].pop()
    elif fault == "extra_value":
        extra = deepcopy(graph["values"][0])
        extra["id"]["local_id"] = 99
        graph["values"].append(extra)
    elif fault == "duplicate_value":
        graph["values"].append(deepcopy(graph["values"][0]))
    elif fault == "missing_block":
        blocks.pop(2)
    elif fault == "extra_duplicate_block":
        blocks.append(deepcopy(blocks[0]))
    elif fault == "duplicate_edge":
        blocks[0]["outgoing"] *= 2
    elif fault == "missing_edge":
        blocks[2]["incoming"].clear()
    elif fault == "raw_missing":
        graph["raw_instruction_sites"].pop()
    elif fault == "raw_extra":
        graph["raw_instruction_sites"].append(hex(BASE + 6))
    elif fault == "raw_duplicate":
        graph["raw_instruction_sites"].append(hex(BASE))
    elif fault == "raw_reordered":
        graph["raw_instruction_sites"].reverse()
    elif fault == "volatile_duplicate":
        graph["explicit_volatile_sites"] *= 2
    elif fault == "gap_duplicate":
        graph["export_gaps"] *= 2
    elif fault == "phi_reordered":
        blocks[1]["operations"][0]["inputs"].reverse()
    elif fault == "phi_after_nonphi":
        blocks[1]["operations"][0:2] = reversed(blocks[1]["operations"][0:2])
    else:
        blocks[1]["operations"][1:] = reversed(blocks[1]["operations"][1:])
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


def test_an_active_use_cannot_name_an_excluded_definition() -> None:
    binary, document, graph = sample()
    graph["values"][1]["storage"] = loc(0x200, "unique")
    graph["values"][1]["definition"] = deepcopy(graph["excluded_dead"][0])
    graph["excluded_dead"].append(graph["blocks"][0]["operations"].pop()["id"])
    graph["blocks"][3]["operations"][0]["inputs"].append(
        deepcopy(graph["values"][1]["id"])
    )
    document["functions"][0]["decompilation"]["analyzed_pcode"][6]["inputs"].append(
        stored(0x200, "unique", 8, sequence(4))
    )
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError, match="excluded"):
        parse_byte_graph(wire(graph), lift)


def test_equal_storage_cannot_replace_the_exact_output_id() -> None:
    _, graph, lift = read_sample()
    duplicate = deepcopy(graph["values"][3])
    duplicate["id"]["local_id"] = 100
    graph["values"].append(duplicate)
    graph["blocks"][3]["operations"][0]["inputs"][1] = duplicate["id"]
    with pytest.raises(ByteGraphFormatError, match="different definition output"):
        parse_byte_graph(wire(graph), lift)


def test_output_self_definition_must_match_the_ordinary_record() -> None:
    binary, document, graph = sample()
    document["functions"][0]["decompilation"]["analyzed_pcode"][0]["output"][
        "definition"
    ] = None
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError, match="ordinary operand"):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("status", ["timeout", "incomplete"])
def test_unavailable_raw_c_rejects(status: str) -> None:
    binary, document, graph = sample()
    document["functions"][0]["decompilation"]["status"] = status
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError, match="raw C"):
        parse_byte_graph(wire(graph), lift)


def test_exact_raw_c_bytes_are_bound() -> None:
    binary, document, graph = sample()
    document["functions"][0]["decompilation"]["raw_c"] += " "
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError, match="raw C"):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "size,bits", [(1, 255), (2, 65535), (4, 2**32 - 1), (8, 2**64 - 1), (16, 2**64 - 1)]
)
def test_exact_constant_bits_and_wide_storage(size: int, bits: int) -> None:
    binary, document, graph = sample()
    graph["values"][2].update(
        size_bytes=size, bits=hex(bits), storage=loc(bits, "const")
    )
    document["functions"][0]["decompilation"]["analyzed_pcode"][1]["inputs"][0] = (
        stored(bits, "const", size)
    )
    lift = bound(binary, document, graph)
    assert parse_byte_graph(wire(graph), lift).values[2].bits == hex(bits)
    if size < 8:
        graph["values"][2]["bits"] = hex(bits + 1)
        graph["values"][2]["storage"]["offset"] = hex(bits + 1)
        with pytest.raises(ByteGraphFormatError, match="constant bits"):
            parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("kind", ["input", "free", "unexplained"])
def test_definitionless_kind_is_preserved_without_authentication(kind: str) -> None:
    _, graph, lift = read_sample()
    graph["values"][0]["kind"] = kind
    graph["values"][0].update(address_tied=True, persistent=True, unaffected=True)
    parsed = parse_byte_graph(wire(graph), lift)
    assert parsed.values[0].kind == kind
    assert parsed.values[0].persistent
    assert parsed.values[0].unaffected
    assert parsed.values[0].address_tied


def test_coherent_dead_reclassification_is_not_authenticated_by_the_old_lift() -> None:
    _, graph, lift = read_sample()
    graph["excluded_dead"].append(graph["blocks"][0]["operations"].pop()["id"])
    graph["values"].pop(1)
    parsed = parse_byte_graph(wire(graph), lift)
    assert len(parsed.excluded_dead) == 2


def test_unknown_opcode_is_preserved_in_an_unreachable_block() -> None:
    binary, document, graph = sample()
    key = deepcopy(graph["excluded_dead"].pop())
    graph["blocks"][4]["operations"] = [
        {"id": key, "opcode": "FUTURE_OP", "inputs": [], "output": None}
    ]
    document["functions"][0]["decompilation"]["analyzed_pcode"][-1] = op(
        BASE + 4, "FUTURE_OP", []
    )
    lift = bound(binary, document, graph)
    assert (
        parse_byte_graph(wire(graph), lift).blocks[4].operations[0].opcode
        == "FUTURE_OP"
    )


def test_two_definitionless_objects_can_have_equal_storage() -> None:
    binary, document, graph = sample()
    graph["values"][9]["storage"] = deepcopy(graph["values"][0]["storage"])
    document["functions"][0]["decompilation"]["analyzed_pcode"][6]["inputs"][0] = (
        stored(0x10, "register", 8)
    )
    lift = bound(binary, document, graph)
    parsed = parse_byte_graph(wire(graph), lift)
    assert parsed.values[0].storage == parsed.values[9].storage
    assert parsed.values[0].id != parsed.values[9].id


@pytest.mark.parametrize(
    "change",
    [
        "missing_lf",
        "extra_lf",
        "spaces",
        "key_order",
        "bom",
        "duplicate",
        "nested_duplicate",
        "utf8",
        "nan",
        "truncated",
        "array",
        "deep",
    ],
)
def test_only_canonical_ascii_json_is_accepted(change: str) -> None:
    _, graph, lift = read_sample()
    raw = wire(graph)
    if change == "missing_lf":
        raw = raw[:-1]
    elif change == "extra_lf":
        raw += b"\n"
    elif change == "spaces":
        raw = json.dumps(graph, sort_keys=True).encode() + b"\n"
    elif change == "key_order":
        raw = json.dumps(graph, separators=(",", ":")).encode() + b"\n"
    elif change == "bom":
        raw = b"\xef\xbb\xbf" + raw
    elif change == "duplicate":
        raw = raw.replace(b'"schema":1', b'"schema":1,"schema":1')
    elif change == "nested_duplicate":
        raw = raw.replace(
            b'"space":"register"', b'"space":"register","space":"register"', 1
        )
    elif change == "utf8":
        raw = raw.replace(b'"input"', '"ínput"'.encode(), 1)
    elif change == "nan":
        raw = raw.replace(b'"ram_space_id":27', b'"ram_space_id":NaN')
    elif change == "truncated":
        raw = raw[:100]
    elif change == "array":
        raw = b"[]\n"
    else:
        raw = b'{"a":' + b"[" * 2000 + b"]" * 2000 + b"}\n"
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(raw, lift)


@pytest.mark.parametrize("name", [field.name for field in fields(ByteGraphLimits)])
@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", None])
def test_invalid_limits_reject(name: str, value: Any) -> None:
    with pytest.raises(ByteGraphLimitError):
        ByteGraphLimits(**{name: value})


@pytest.mark.parametrize("name", [field.name for field in fields(ByteGraphLimits)])
def test_raised_limits_reject(name: str) -> None:
    with pytest.raises(ByteGraphLimitError):
        ByteGraphLimits(**{name: getattr(ByteGraphLimits(), name) + 1})


def test_every_lower_limit_is_enforced_at_its_boundary() -> None:
    _, graph, lift = read_sample()
    raw = wire(graph)
    counts = {
        "max_bytes": len(raw),
        "max_blocks": 5,
        "max_operations": 8,
        "max_raw_operations": 6,
        "max_raw_instructions": 6,
        "max_inputs": 2,
        "max_values": 10,
        "max_references": 16,
        "max_gaps": 2,
    }
    assert (
        parse_byte_graph(raw, lift, limits=ByteGraphLimits(**counts)).to_bytes() == raw
    )
    for name, value in counts.items():
        with pytest.raises(ByteGraphLimitError):
            parse_byte_graph(raw, lift, limits=ByteGraphLimits(**{name: value - 1}))


def test_byte_limit_runs_before_json_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, lift = read_sample()

    def forbidden(raw: bytes) -> dict[str, object]:
        raise AssertionError("JSON parsing ran after the byte limit.")

    monkeypatch.setattr("phoenix.lift.byte_graph.load_json", forbidden)
    with pytest.raises(ByteGraphLimitError):
        parse_byte_graph(b"x" * (16 * 1024 * 1024 + 1), lift)
    with pytest.raises(ByteGraphLimitError):
        parse_byte_graph(b"{}", lift, limits=ByteGraphLimits(max_bytes=1))


@pytest.mark.parametrize("count", [32, 33])
def test_analyzed_block_profile_boundary(count: int) -> None:
    _, graph, lift = read_sample()
    for index in range(5, count):
        block = deepcopy(graph["blocks"][4])
        block["id"]["index"] = 50 + index
        graph["blocks"].append(block)
    if count == 32:
        assert len(parse_byte_graph(wire(graph), lift).blocks) == 32
    else:
        with pytest.raises(ByteGraphLimitError):
            parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("domain", ["raw", "active", "excluded"])
@pytest.mark.parametrize("count", [256, 257])
def test_complete_operation_profile_boundaries(domain: str, count: int) -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    if domain == "raw":
        function["instructions"][0]["pcode"] = [
            op(BASE, "COPY", [], index=i) for i in range(count - 5)
        ]
    else:
        bank = function["decompilation"]["analyzed_pcode"]
        for index in range(1, count - 7):
            bank.append(op(BASE + 4, "COPY", [], index=index))
            key = deepcopy(graph["excluded_dead"][0])
            key["sequence"]["index"] = index
            if domain == "excluded":
                graph["excluded_dead"].append(key)
            else:
                graph["blocks"][4]["operations"].append(
                    {"id": key, "opcode": "COPY", "inputs": [], "output": None}
                )
    lift = bound(binary, document, graph)
    if count == 256:
        parse_byte_graph(wire(graph), lift)
    else:
        with pytest.raises(ByteGraphLimitError):
            parse_byte_graph(wire(graph), lift)


def test_omitted_records_cannot_hide_over_limit_ordinary_banks() -> None:
    binary, document, graph = sample()
    bank = document["functions"][0]["decompilation"]["analyzed_pcode"]
    bank.extend(op(BASE + 4, "COPY", [], index=i) for i in range(1, 250))
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphLimitError, match="ordinary analyzed bank"):
        parse_byte_graph(wire(graph), lift)


def test_raw_block_limit_is_separate_from_analyzed_blocks() -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    function["blocks"] = [
        {
            "entry": loc(BASE + i),
            "ranges": [{"start": loc(BASE + i), "end": loc(BASE + i)}],
        }
        for i in range(6)
    ]
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphLimitError, match="raw block"):
        parse_byte_graph(wire(graph), lift, limits=ByteGraphLimits(max_blocks=5))


@given(
    st.permutations((0, 1, 2, 3, 4)),
    st.permutations(tuple(range(10))),
    st.integers(0, 100_000),
    st.integers(0, 100_000),
)
@settings(max_examples=60)
def test_block_and_value_renumbering_preserves_ordered_edge_meaning(
    block_order: list[int], value_order: list[int], block_delta: int, value_delta: int
) -> None:
    _, graph, lift = read_sample()
    graph["blocks"] = [graph["blocks"][i] for i in block_order]
    graph["values"] = [graph["values"][i] for i in value_order]

    def rename(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"function", "pass_id", "index"}:
                value["index"] += block_delta
            if set(value) == {"function", "pass_id", "local_id"}:
                value["local_id"] += value_delta
            for child in value.values():
                rename(child)
        elif isinstance(value, list):
            for child in value:
                rename(child)

    rename(graph)
    parsed = parse_byte_graph(wire(graph), lift)
    header = next(b for b in parsed.blocks if b.id.index == 20 + block_delta)
    assert [edge.other.index - block_delta for edge in header.incoming] == [10, 30]
    assert [edge.other.index - block_delta for edge in header.outgoing] == [40, 30]
    assert [v.local_id - value_delta for v in header.operations[0].inputs] == [2, 4]
    assert parsed.to_bytes() == wire(graph)


@given(st.binary(max_size=2000))
@settings(max_examples=100)
def test_arbitrary_bytes_have_only_controlled_failures(raw: bytes) -> None:
    _, _, lift = read_sample()
    with pytest.raises(ByteGraphError):
        parse_byte_graph(raw, lift)


def test_coherent_pass_rename_is_not_pass_authentication() -> None:
    _, graph, lift = read_sample()
    raw = wire(graph).replace(PASS.encode(), b"b" * 64)
    assert parse_byte_graph(raw, lift).pass_id == "b" * 64


def test_lower_limits_cannot_be_bypassed_by_replaced_lift_inventories() -> None:
    _, graph, lift = read_sample()
    function = lift.functions[lift.main]
    changed = replace(function, instructions=function.instructions * 50)
    with pytest.raises(ByteGraphLimitError, match="raw instruction"):
        parse_byte_graph(wire(graph), replace(lift, functions={lift.main: changed}))


def test_phi_predecessor_slot_permutation_preserves_the_explicit_pairing() -> None:
    binary, document, graph = sample()
    header = graph["blocks"][1]
    header["incoming"].reverse()
    header["operations"][0]["inputs"].reverse()
    graph["blocks"][0]["outgoing"][0]["reciprocal_slot"] = 1
    graph["blocks"][2]["outgoing"][0]["reciprocal_slot"] = 0
    document["functions"][0]["decompilation"]["analyzed_pcode"][1]["inputs"].reverse()
    lift = bound(binary, document, graph)
    parsed = parse_byte_graph(wire(graph), lift).blocks[1]
    assert [e.other.index for e in parsed.incoming] == [30, 10]
    assert [v.local_id for v in parsed.operations[0].inputs] == [4, 2]
    assert parsed.true_slot == 1
    assert parsed.false_slot == 0


@pytest.mark.parametrize(
    "fault",
    [
        "phi_arity",
        "phi_output",
        "conditional_arity",
        "conditional_output",
        "conditional_edges",
    ],
)
def test_declared_phi_and_conditional_shapes_reject(fault: str) -> None:
    binary, document, graph = sample()
    bank = document["functions"][0]["decompilation"]["analyzed_pcode"]
    header = graph["blocks"][1]
    if fault == "phi_arity":
        header["operations"][0]["inputs"].append(deepcopy(graph["values"][2]["id"]))
        bank[1]["inputs"].append(stored(0, "const", 8))
    elif fault == "phi_output":
        header["operations"][0]["output"] = None
        bank[1]["output"] = None
        for value in graph["values"]:
            if value["id"]["local_id"] == 3:
                value["kind"], value["definition"] = "unexplained", None
        for ordinary in bank:
            for operand in ordinary["inputs"]:
                if operand["definition"] == sequence(1):
                    operand["definition"] = None
    elif fault == "conditional_arity":
        header["operations"][2]["inputs"].append(deepcopy(graph["values"][5]["id"]))
        bank[3]["inputs"].append(stored(0x100, "unique", 1, sequence(1, 1)))
    elif fault == "conditional_output":
        value = deepcopy(graph["values"][1])
        value["id"]["local_id"] = 20
        value["definition"] = deepcopy(header["operations"][2]["id"])
        graph["values"].append(value)
        header["operations"][2]["output"] = deepcopy(value["id"])
        bank[3]["output"] = stored(0x20, "register", 8, sequence(1, 2))
    else:
        header["outgoing"].pop()
        graph["blocks"][2]["incoming"].clear()
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError, match="phi|conditional"):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("fault", ["block", "operation", "value", "owner", "raw_owner"])
def test_gap_references_must_resolve_without_adding_authority(fault: str) -> None:
    _, graph, lift = read_sample()
    gap = graph["export_gaps"][0]
    gap["block"] = deepcopy(graph["blocks"][0]["id"])
    gap["operation"] = deepcopy(graph["blocks"][0]["operations"][0]["id"])
    gap["value"] = deepcopy(graph["values"][0]["id"])
    parse_byte_graph(wire(graph), lift)
    if fault == "block":
        gap["block"]["index"] = 100
    elif fault == "operation":
        gap["operation"]["sequence"]["index"] = 100
    elif fault == "value":
        gap["value"]["local_id"] = 100
    elif fault == "owner":
        gap["block"] = deepcopy(graph["blocks"][1]["id"])
    else:
        gap["operation"]["domain"] = "raw"
    with pytest.raises(ByteGraphFormatError, match="gap"):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "path",
    [
        ("blocks",),
        ("values",),
        ("excluded_dead",),
        ("raw_instruction_sites",),
        ("explicit_volatile_sites",),
        ("export_gaps",),
        ("blocks", 0, "incoming"),
        ("blocks", 0, "outgoing"),
        ("blocks", 0, "operations"),
        ("blocks", 0, "operations", 0, "inputs"),
    ],
)
def test_array_fields_reject_wrong_types(path: tuple[str | int, ...]) -> None:
    _, graph, lift = read_sample()
    target: Any = graph
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = {}
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize(
    "field", ["binary_sha256", "lift_sha256", "pass_id", "raw_c_sha256"]
)
@pytest.mark.parametrize(
    "value", ["0" * 63, "A" * 64, "g" * 64, "0" * 65, True, 0, None]
)
def test_digest_fields_require_lowercase_sha256(field: str, value: object) -> None:
    _, graph, lift = read_sample()
    graph[field] = value
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("domain", ["raw", "excluded"])
def test_lower_input_bound_counts_unrepresented_ordinary_operands(domain: str) -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    operation = (
        function["instructions"][0]["pcode"][0]
        if domain == "raw"
        else function["decompilation"]["analyzed_pcode"][-1]
    )
    operation["inputs"] *= 3
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphLimitError, match="input count"):
        parse_byte_graph(wire(graph), lift, limits=ByteGraphLimits(max_inputs=2))


@pytest.mark.parametrize("count", [256, 257])
def test_raw_instructions_without_operations_still_have_a_bound(count: int) -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    function["ranges"] = [{"start": loc(BASE), "end": loc(BASE + count - 1)}]
    function["instructions"] = [
        {"address": loc(BASE + i), "size": 1, "text": "synthetic", "pcode": []}
        for i in range(count)
    ]
    document["functions"] = [function]
    graph["raw_instruction_sites"] = [hex(BASE + i) for i in range(count)]
    graph["explicit_volatile_sites"] = graph["explicit_volatile_sites"][1:]
    lift = bound(binary, document, graph)
    if count == 256:
        assert len(parse_byte_graph(wire(graph), lift).raw_instruction_sites) == count
    else:
        with pytest.raises(ByteGraphLimitError):
            parse_byte_graph(wire(graph), lift)


def test_raw_and_analyzed_banks_each_have_the_full_operation_budget() -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    function["instructions"][0]["pcode"] = [
        op(BASE, "COPY", [], index=i) for i in range(251)
    ]
    bank = function["decompilation"]["analyzed_pcode"]
    for index in range(1, 249):
        bank.append(op(BASE + 4, "COPY", [], index=index))
        key = deepcopy(graph["excluded_dead"][0])
        key["sequence"]["index"] = index
        graph["excluded_dead"].append(key)
    lift = bound(binary, document, graph)
    assert len(parse_byte_graph(wire(graph), lift).excluded_dead) == 249


def test_missing_output_value_rejects() -> None:
    _, graph, lift = read_sample()
    graph["blocks"][0]["operations"][0]["output"]["local_id"] = 100
    with pytest.raises(ByteGraphFormatError, match="output"):
        parse_byte_graph(wire(graph), lift)


def test_non_bytes_and_non_limits_fail_with_controlled_errors() -> None:
    _, graph, lift = read_sample()
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(bytearray(wire(graph)), lift)  # type: ignore[arg-type]
    with pytest.raises(ByteGraphLimitError):
        parse_byte_graph(wire(graph), lift, limits={})  # type: ignore[arg-type]


def test_escaped_surrogates_are_rejected_before_records_escape() -> None:
    binary, document, graph = sample()
    graph["blocks"][0]["operations"][0]["opcode"] = "\ud800"
    document["functions"][0]["decompilation"]["analyzed_pcode"][0]["opcode"] = "\ud800"
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)


@pytest.mark.parametrize("count", [32, 33])
def test_raw_block_profile_boundary(count: int) -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    function["ranges"] = [{"start": loc(BASE), "end": loc(BASE + count)}]
    function["blocks"] = [
        {
            "entry": loc(BASE + i),
            "ranges": [{"start": loc(BASE + i), "end": loc(BASE + i)}],
        }
        for i in range(count)
    ]
    lift = bound(binary, document, graph)
    if count == 32:
        parse_byte_graph(wire(graph), lift)
    else:
        with pytest.raises(ByteGraphLimitError, match="raw block"):
            parse_byte_graph(wire(graph), lift)


@given(
    st.sampled_from(
        (
            "schema",
            "pass_id",
            "blocks",
            "values",
            "ram_space_id",
            "entry",
            "export_gaps",
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
def test_structured_json_changes_never_escape_controlled_errors(
    field: str, replacement: object
) -> None:
    _, graph, lift = read_sample()
    graph[field] = replacement
    raw = wire(graph)
    try:
        parsed = parse_byte_graph(raw, lift)
    except ByteGraphError:
        return
    assert parsed.to_bytes() == raw


@pytest.mark.parametrize(
    "field", ["opcode", "storage_space", "sequence_space", "raw_c"]
)
def test_invalid_unicode_is_a_controlled_format_error(field: str) -> None:
    binary, document, graph = sample()
    function = document["functions"][0]
    bank = function["decompilation"]["analyzed_pcode"]
    if field == "opcode":
        graph["blocks"][0]["operations"][0]["opcode"] = "\udfff"
        bank[0]["opcode"] = "\udfff"
    elif field == "storage_space":
        graph["values"][0]["storage"]["space"] = "\udfff"
        bank[0]["inputs"][0]["address"]["space"] = "\udfff"
        bank[2]["inputs"][1]["address"]["space"] = "\udfff"
    elif field == "sequence_space":
        graph["excluded_dead"][0]["sequence"]["address"]["space"] = "\udfff"
        bank[-1]["sequence"]["address"]["space"] = "\udfff"
        bank[-1]["output"]["definition"]["address"]["space"] = "\udfff"
    else:
        function["decompilation"]["raw_c"] = "\udfff"
    lift = bound(binary, document, graph)
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)
