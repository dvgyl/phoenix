import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phoenix.lift.byte_graph import ByteGraphFormatError, parse_byte_graph
from phoenix.lift.byte_graph_v2 import (
    ByteGraphV2,
    ByteGraphV2Error,
    ByteGraphV2FormatError,
    ByteGraphV2LimitError,
    ByteGraphV2Limits,
    parse_byte_graph_v2,
    parse_pass_record,
)
from phoenix.lift.index import LiftIndex, parse_lift


def wire(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def address(offset: int, space: str = "ram") -> dict[str, Any]:
    return {"space": space, "offset": hex(offset)}


def sequence(offset: int, index: int = 7) -> dict[str, Any]:
    return {"address": address(offset), "index": index}


def operand(
    offset: int, space: str, definition: object = None, size: int = 8
) -> dict[str, Any]:
    return {"address": address(offset, space), "size": size, "definition": definition}


def detached_fixture_record(value: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(wire(value))
    assert isinstance(result, dict)
    return result


def sample() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    function = {
        "binary_sha256": sha256(b"synthetic observation").hexdigest(),
        "ghidra_entry": "0x1000",
    }
    pass_record = {
        "schema": 1,
        "profile": "ordinary-byte-adapter/1",
        "function": function,
        "call_ordinal": 0,
        "ghidra_version": "12.2",
        "ghidra_revision": "8ca9077040cc43cd790babcfccf19475622a3e9a",
        "java_runtime_version": "25.0.5+8-LTS",
        "language_id": "x86:LE:64:default",
        "compiler_spec_id": "gcc",
        "simplification_style": "decompile",
        "configured_options": None,
        "timeout_seconds": 60,
        "printer_transformer": "ghidra.program.model.symbol.IllegalCharCppTransformer",
        "line_separator": "\n",
        "source_manifest_sha256": "a" * 64,
        "tool_manifest_sha256": "b" * 64,
    }
    pass_id = sha256(wire(pass_record)).hexdigest()
    scope = {"function": function, "pass_id": pass_id}
    b0, b1 = ({**scope, "index": i} for i in (0, 1))
    v0, v1, v2, v3 = ({**scope, "local_id": i} for i in (0, 1, 2, 3))
    o0 = {**scope, "domain": "analyzed", "sequence": sequence(0x1010)}
    o1 = {**scope, "domain": "analyzed", "sequence": sequence(0x1020)}
    source = "int f(void) { return 0; }\n"
    document = {
        "schema_version": 1,
        "image_base": address(0x1000),
        "main": {
            "entry": address(0x1000),
            "startup": address(0x1000),
            "setup": address(0x1000),
            "call": address(0x1000),
        },
        "functions": [
            {
                "entry": address(0x1000),
                "name": "untrusted",
                "thunk_target": None,
                "signature": {
                    "calling_convention": None,
                    "return_type": "int",
                    "parameters": [],
                    "variadic": False,
                },
                "ranges": [{"start": address(0x1000), "end": address(0x1020)}],
                "instructions": [
                    {
                        "address": address(0x1000),
                        "size": 1,
                        "text": "synthetic",
                        "pcode": [],
                    },
                    {
                        "address": address(0x1010),
                        "size": 1,
                        "text": "synthetic",
                        "pcode": [
                            {
                                "sequence": sequence(0x1010),
                                "opcode": "COPY",
                                "output": None,
                                "inputs": [operand(0x10, "register")],
                            }
                        ],
                    },
                    {
                        "address": address(0x1020),
                        "size": 1,
                        "text": "synthetic",
                        "pcode": [],
                    },
                ],
                "blocks": [
                    {
                        "entry": address(0x1000),
                        "ranges": [{"start": address(0x1000), "end": address(0x1020)}],
                    }
                ],
                "flow_edges": [],
                "decompilation": {
                    "status": "ok",
                    "diagnostic": None,
                    "raw_c": source,
                    "statements": [],
                    "analyzed_pcode": [
                        {
                            "sequence": sequence(0x1010),
                            "opcode": "COPY",
                            "output": operand(0x20, "unique", sequence(0x1010)),
                            "inputs": [
                                operand(0x10, "register"),
                                operand(0x10, "register"),
                                operand(0x10, "register"),
                            ],
                        },
                        {
                            "sequence": sequence(0x1020),
                            "opcode": "INT_ADD",
                            "output": None,
                            "inputs": [operand(0x10, "register")],
                        },
                    ],
                },
            }
        ],
        "imports": [],
        "strings": [],
        "data_references": [],
        "call_edges": [],
    }
    common = {
        "size_bytes": 8,
        "definition": None,
        "bits": None,
        "is_constant": False,
        "is_input": True,
        "is_free": False,
        "address_tied": False,
        "persistent": False,
        "unaffected": False,
    }
    graph = {
        "schema": 2,
        "profile": "ordinary-byte-adapter/1",
        "binary_sha256": function["binary_sha256"],
        "lift_sha256": sha256(wire(document)).hexdigest(),
        "function": function,
        "pass_id": pass_id,
        "raw_c_sha256": sha256(source.encode()).hexdigest(),
        "ram_space_id": -27,
        "ram_word_bytes": 1,
        "address_bits": 64,
        "byte_bits": 8,
        "endian": "little",
        "entry": {
            "ordinary_entry": address(0x1000),
            "analyzed_block": b0,
            "selection": "pinned_native_index_zero",
            "native_entry_address": None,
        },
        "blocks": [
            {
                "id": b0,
                "cover_min": address(0x1010),
                "cover_max": address(0x1020),
                "incoming": [],
                "outgoing": [],
                "operations": [o0],
            },
            {
                "id": b1,
                "cover_min": None,
                "cover_max": None,
                "incoming": [],
                "outgoing": [],
                "operations": [],
            },
        ],
        "operations": [
            {
                "id": o0,
                "opcode": "COPY",
                "output": v2,
                "inputs": [v0, v1, v0],
                "java_is_dead": True,
                "parent": b0,
                "java_order": 0,
            },
            {
                "id": o1,
                "opcode": "INT_ADD",
                "output": None,
                "inputs": [v1],
                "java_is_dead": False,
                "parent": None,
                "java_order": -1,
            },
        ],
        "values": [
            {**common, "id": v0, "storage": address(0x10, "register")},
            {
                **common,
                "id": v1,
                "storage": address(0x10, "register"),
                "address_tied": True,
                "persistent": True,
                "unaffected": True,
            },
            {
                **common,
                "id": v2,
                "storage": address(0x20, "unique"),
                "definition": o0,
                "is_input": False,
            },
            {
                **common,
                "id": v3,
                "storage": address(0x30, "unique"),
                "is_input": False,
                "is_free": True,
            },
        ],
        "raw_instruction_sites": [address(0x1000), address(0x1010), address(0x1020)],
        "raw_operation_keys": [
            {**scope, "domain": "raw", "sequence": sequence(0x1010)}
        ],
        "explicit_volatile_sites": [],
        "native_inventory": {
            "operation_flags": "not_exported",
            "operation_bank": "not_exported",
            "removed_operations": "not_exported",
            "block_cover_ranges": "not_exported",
        },
        "gaps": [
            {
                "code": code,
                "block": None,
                "operation": None,
                "value": None,
                "item_ordinal": None,
            }
            for code in (
                "native_state_unavailable",
                "native_inventory_unavailable",
                "native_cover_unavailable",
                "entry_effect_binding_unproved",
                "memory_effects_unproved",
            )
        ]
        + [
            {
                "code": "unowned_operation",
                "block": None,
                "operation": o1,
                "value": None,
                "item_ordinal": None,
            },
            {
                "code": "ssa_unbound",
                "block": None,
                "operation": None,
                "value": v3,
                "item_ordinal": None,
            },
        ],
    }
    return (
        detached_fixture_record(document),
        detached_fixture_record(graph),
        detached_fixture_record(pass_record),
    )


def bind(document: dict[str, Any], graph: dict[str, Any]) -> LiftIndex:
    raw = wire(document)
    graph["lift_sha256"] = sha256(raw).hexdigest()
    graph["gaps"].sort(key=wire)
    return parse_lift(raw, b"synthetic observation")


def read(
    document: dict[str, Any],
    graph: dict[str, Any],
    pass_record: dict[str, Any],
    **kwargs: Any,
) -> ByteGraphV2:
    lift = bind(document, graph)
    return parse_byte_graph_v2(
        wire(graph),
        lift=lift,
        pass_record=parse_pass_record(wire(pass_record)),
        **kwargs,
    )


def test_literal_inventory_and_canonical_bytes() -> None:
    document, graph, pass_record = sample()
    parsed = read(document, graph, pass_record)
    assert parsed.record() == graph
    assert parsed.to_bytes() == wire(graph)
    assert parsed.sha256 == sha256(wire(graph)).hexdigest()
    assert parsed.entry.ordinary_entry.offset == 0x1000
    assert parsed.blocks[0].cover_min is not None
    assert parsed.blocks[0].cover_min.offset == 0x1010
    assert parsed.entry.native_entry_address is None
    assert [v.id.local_id for v in parsed.values] == [0, 1, 2, 3]
    assert parsed.values[0].storage == parsed.values[1].storage
    assert parsed.values[0].id != parsed.values[1].id
    assert [v.local_id for v in parsed.operations[0].inputs] == [0, 1, 0]
    assert parsed.operations[0].java_is_dead is True
    assert parsed.operations[1].java_is_dead is False
    assert parsed.operations[1].parent is None
    assert parsed.blocks[1].operations == ()
    assert parsed.raw_operation_keys[0].sequence == parsed.operations[0].id.sequence
    assert parsed.raw_operation_keys[0] != parsed.operations[0].id
    assert [a.offset for a in parsed.raw_instruction_sites] == [0x1000, 0x1010, 0x1020]
    assert set(parsed.record()) == set(graph)
    assert "excluded_dead" not in parsed.record()
    assert not hasattr(parsed, "emit") and not hasattr(parsed, "verified")


def test_immutable_result_and_detached_wire_records() -> None:
    document, graph, pass_record = sample()
    parsed = read(document, graph, pass_record)
    expected = parsed.to_bytes()
    graph["operations"][0]["java_is_dead"] = False
    copy = parsed.record()
    assert isinstance(copy["values"], list)
    copy["values"].clear()
    assert parsed.to_bytes() == expected
    with pytest.raises(FrozenInstanceError):
        setattr(parsed.operations[0], "java_is_dead", False)


def test_noncanonical_json_has_one_canonical_result() -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    raw = json.dumps(graph, indent=2).encode()
    parsed = parse_byte_graph_v2(
        raw, lift=lift, pass_record=parse_pass_record(wire(pass_record))
    )
    assert parsed.to_bytes() == wire(graph)
    assert parsed.sha256 != sha256(raw).hexdigest()


def test_new_schema_does_not_enter_old_reader() -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(wire(graph), lift)
    graph["schema"] = 1
    with pytest.raises(ByteGraphV2FormatError):
        parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
        )


def gap(
    code: str, *, operation: object = None, value: object = None, block: object = None
) -> dict[str, Any]:
    return {
        "code": code,
        "block": block,
        "operation": operation,
        "value": value,
        "item_ordinal": None,
    }


def mutate(record: dict[str, Any], path: tuple[str | int, ...], value: object) -> None:
    target: Any = record
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), True),
        (("schema",), 1),
        (("schema",), 2.0),
        (("profile",), "ordinary-byte-adapter/2"),
        (("ram_word_bytes",), 2),
        (("address_bits",), 32),
        (("byte_bits",), 16),
        (("endian",), "big"),
        (("ram_space_id",), True),
        (("ram_space_id",), 2**31),
        (("ram_space_id",), -(2**31) - 1),
        (("function", "ghidra_entry"), "0x1001"),
        (("function", "binary_sha256"), "c" * 64),
        (("pass_id",), "c" * 64),
        (("binary_sha256",), "c" * 64),
        (("lift_sha256",), "c" * 64),
        (("raw_c_sha256",), "c" * 64),
        (("entry", "ordinary_entry", "offset"), "0x1010"),
        (("entry", "ordinary_entry", "space"), "other"),
        (("entry", "analyzed_block", "index"), 1),
        (("entry", "native_entry_address"), {"space": "ram", "offset": "0x1010"}),
        (("entry", "selection"), "minimum"),
        (("blocks", 0, "cover_max"), None),
        (("blocks", 0, "cover_max", "offset"), "0x100f"),
        (("blocks", 0, "cover_max", "space"), "other"),
        (("blocks", 0, "id", "index"), 1),
        (("blocks", 1), None),
        (("blocks", 1, "id", "index"), 2),
        (("blocks", 0, "operations"), []),
        (("operations", 0, "java_is_dead"), 1),
        (("operations", 0, "java_order"), 1),
        (("operations", 0, "parent"), None),
        (
            (
                "operations",
                1,
                "parent",
            ),
            {"index": 0},
        ),
        (("operations", 1, "java_order"), 2**31),
        (("operations", 1, "java_order"), -(2**31) - 1),
        (("operations", 0, "id", "domain"), "raw"),
        (("operations", 0, "id", "domain"), "unknown"),
        (("operations", 0, "id", "sequence", "index"), 1_000_001),
        (("operations", 0, "opcode"), "STORE"),
        (("operations", 0, "output"), None),
        (("operations", 0, "inputs", 0), None),
        (("operations", 0, "inputs", 0, "local_id"), 99),
        (("operations", 0, "output", "local_id"), 99),
        (("values", 2, "definition"), None),
        (("values", 2, "definition", "domain"), "raw"),
        (("values", 2, "definition", "sequence", "index"), 99),
        (("values", 0, "size_bytes"), 0),
        (("values", 0, "size_bytes"), 65537),
        (("values", 0, "size_bytes"), True),
        (("values", 0, "size_bytes"), 4),
        (("values", 0, "bits"), "0x1"),
        (("values", 0, "storage", "offset"), "0x11"),
        (("values", 0, "storage", "space"), "unique"),
        (("values", 0, "id", "local_id"), -1),
        (("values", 0, "id", "local_id"), 2**32),
        (("native_inventory", "operation_flags"), "alive"),
        (("native_inventory", "operation_bank"), "complete"),
        (("native_inventory", "removed_operations"), "none"),
        (("native_inventory", "block_cover_ranges"), []),
        (("gaps", 0, "item_ordinal"), 0),
        (("gaps", 0, "code"), "proved"),
    ],
)
def test_contradictory_records_refuse(
    path: tuple[str | int, ...], value: object
) -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    mutate(graph, path, value)
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
        )


@pytest.mark.parametrize(
    "owner",
    [
        ("entry", "analyzed_block"),
        ("blocks", 0, "id"),
        ("blocks", 0, "operations", 0),
        ("operations", 0, "id"),
        ("operations", 0, "parent"),
        ("operations", 0, "output"),
        ("operations", 0, "inputs", 0),
        ("values", 0, "id"),
        ("values", 2, "definition"),
        ("raw_operation_keys", 0),
    ],
)
@pytest.mark.parametrize(
    "identity,replacement",
    [
        ("pass_id", "c" * 64),
        ("function", {"binary_sha256": "c" * 64, "ghidra_entry": "0x1000"}),
        ("function", {"binary_sha256": "a" * 64, "ghidra_entry": "0x1001"}),
    ],
)
def test_foreign_keys_refuse(
    owner: tuple[str | int, ...], identity: str, replacement: object
) -> None:
    document, graph, pass_record = sample()
    mutate(graph, (*owner, identity), replacement)
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)


@pytest.mark.parametrize(
    "flag",
    ["is_constant", "is_input", "is_free", "address_tied", "persistent", "unaffected"],
)
@pytest.mark.parametrize("value", [None, 0, 1, "false", [], 1.0])
def test_actual_value_booleans_required(flag: str, value: object) -> None:
    document, graph, pass_record = sample()
    graph["values"][0][flag] = value
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("function",),
        ("entry",),
        ("entry", "ordinary_entry"),
        ("entry", "analyzed_block"),
        ("blocks", 0),
        ("operations", 0),
        ("operations", 0, "id"),
        ("operations", 0, "id", "sequence"),
        ("operations", 0, "inputs", 0),
        ("values", 0),
        ("values", 0, "storage"),
        ("gaps", 0),
        ("native_inventory",),
    ],
)
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_closed_shapes(path: tuple[str | int, ...], change: str) -> None:
    document, graph, pass_record = sample()
    target: Any = graph
    for part in path:
        target = target[part]
    if change == "missing":
        target.pop(next(iter(target)))
    else:
        target["extra"] = None
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)


@pytest.mark.parametrize(
    "path",
    [
        ("blocks",),
        ("operations",),
        ("values",),
        ("raw_instruction_sites",),
        ("raw_operation_keys",),
        ("explicit_volatile_sites",),
        ("gaps",),
        ("blocks", 0, "incoming"),
        ("blocks", 0, "outgoing"),
        ("blocks", 0, "operations"),
        ("operations", 0, "inputs"),
    ],
)
def test_array_types(path: tuple[str | int, ...]) -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    mutate(graph, path, {})
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
        )


@pytest.mark.parametrize(
    "field",
    [
        "blocks",
        "operations",
        "values",
        "raw_instruction_sites",
        "raw_operation_keys",
        "gaps",
    ],
)
@pytest.mark.parametrize("change", ["missing", "duplicate", "reversed"])
def test_rosters_and_order(field: str, change: str) -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    if change == "missing":
        graph[field].pop(0)
    elif change == "duplicate":
        graph[field].append(deepcopy(graph[field][0]))
    else:
        graph[field].reverse()
    if field == "values" and change == "reversed":
        parsed = parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
        )
        assert [v.id.local_id for v in parsed.values] == [3, 2, 1, 0]
    elif field == "raw_operation_keys" and change == "reversed":
        assert (
            parse_byte_graph_v2(
                wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
            ).record()
            == graph
        )
    else:
        with pytest.raises(ByteGraphV2Error):
            parse_byte_graph_v2(
                wire(graph), lift=lift, pass_record=parse_pass_record(wire(pass_record))
            )


@pytest.mark.parametrize(
    "code",
    [
        "native_state_unavailable",
        "native_inventory_unavailable",
        "native_cover_unavailable",
        "entry_effect_binding_unproved",
        "memory_effects_unproved",
        "ssa_unbound",
        "unowned_operation",
    ],
)
def test_each_required_gap_cannot_be_removed(code: str) -> None:
    document, graph, pass_record = sample()
    graph["gaps"] = [g for g in graph["gaps"] if g["code"] != code]
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, pass_record)


@pytest.mark.parametrize("same_entry", [False, True])
@pytest.mark.parametrize("dead", [False, True])
def test_coherent_fabrication_stays_an_observation(
    same_entry: bool, dead: bool
) -> None:
    document, graph, pass_record = sample()
    graph["operations"][0]["java_is_dead"] = dead
    if same_entry:
        graph["blocks"][0]["cover_min"] = address(0x1000)
    parsed = read(document, graph, pass_record)
    assert parsed.operations[0].java_is_dead is dead
    assert parsed.entry.native_entry_address is None
    assert {g.code for g in parsed.gaps} >= {
        "entry_effect_binding_unproved",
        "memory_effects_unproved",
        "native_state_unavailable",
    }
    assert set(parsed.record()) == set(graph)
    assert type(parsed) is ByteGraphV2
    with pytest.raises(ByteGraphFormatError):
        parse_byte_graph(parsed.to_bytes(), bind(document, graph))


def test_actual_empty_entry_and_disconnected_operation() -> None:
    document, graph, pass_record = sample()
    entry, disconnected = graph["blocks"]
    disconnected["operations"] = entry["operations"]
    entry.update(operations=[], cover_min=None, cover_max=None)
    graph["operations"][0]["parent"] = disconnected["id"]
    parsed = read(document, graph, pass_record)
    assert parsed.blocks[0].operations == ()
    assert parsed.blocks[0].cover_min is None
    assert len(parsed.blocks[1].operations) == 1
    assert parsed.operations[0].java_is_dead is True


def phi_sample(
    edges: list[tuple[int, int]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document, graph, pass_record = sample()
    scope = {"function": graph["function"], "pass_id": graph["pass_id"]}
    count = 1 + max(max(edge) for edge in edges)
    graph["blocks"] = [
        {
            "id": {**scope, "index": i},
            "cover_min": None,
            "cover_max": None,
            "incoming": [],
            "outgoing": [],
            "operations": [],
        }
        for i in range(count)
    ]
    for origin, target in edges:
        left, right = graph["blocks"][origin], graph["blocks"][target]
        i, j = len(left["outgoing"]), len(right["incoming"])
        left["outgoing"].append({"other": deepcopy(right["id"]), "reciprocal_slot": j})
        right["incoming"].append({"other": deepcopy(left["id"]), "reciprocal_slot": i})
    owner = graph["blocks"][-1]
    operation = graph["operations"][0]
    operation.update(
        opcode="MULTIEQUAL",
        parent=owner["id"],
        inputs=[
            deepcopy(graph["values"][i % 2]["id"])
            for i in range(len(owner["incoming"]))
        ],
    )
    owner["operations"] = [operation["id"]]
    ordinary = document["functions"][0]["decompilation"]["analyzed_pcode"][0]
    ordinary.update(
        opcode="MULTIEQUAL",
        inputs=[operand(0x10, "register") for _ in owner["incoming"]],
    )
    return document, graph, pass_record


@pytest.mark.parametrize(
    "edges",
    [[(0, 1), (0, 2), (1, 3), (2, 3)], [(0, 1), (1, 1)], [(0, 1), (0, 1)], [(0, 0)]],
)
def test_phi_slots_diamond_loop_parallel_and_self(edges: list[tuple[int, int]]) -> None:
    document, graph, pass_record = phi_sample(edges)
    parsed = read(document, graph, pass_record)
    block = parsed.blocks[-1]
    assert [v.local_id for v in parsed.operations[0].inputs] == [
        i % 2 for i in range(len(block.incoming))
    ]
    assert parsed.record() == graph
    assert not any(g.code == "phi_binding_unproved" for g in parsed.gaps)


def test_phi_permutation_changes_observed_pairing_with_equal_storage() -> None:
    document, graph, pass_record = phi_sample([(0, 1), (0, 1)])
    first = read(document, graph, pass_record)
    graph["operations"][0]["inputs"].reverse()
    second = read(document, graph, pass_record)
    assert [v.local_id for v in first.operations[0].inputs] == [0, 1]
    assert [v.local_id for v in second.operations[0].inputs] == [1, 0]
    assert first.sha256 != second.sha256
    graph["blocks"][1]["incoming"].reverse()
    for edge in graph["blocks"][0]["outgoing"]:
        edge["reciprocal_slot"] = 1 - edge["reciprocal_slot"]
    third = read(document, graph, pass_record)
    assert [e.reciprocal_slot for e in third.blocks[1].incoming] == [1, 0]
    assert third.sha256 != second.sha256


def test_phi_arity_is_preserved_with_required_gap() -> None:
    document, graph, pass_record = phi_sample([(0, 1), (0, 1)])
    graph["operations"][0]["inputs"].pop()
    document["functions"][0]["decompilation"]["analyzed_pcode"][0]["inputs"].pop()
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, pass_record)
    graph["gaps"].append(
        gap("phi_binding_unproved", operation=graph["operations"][0]["id"])
    )
    parsed = read(document, graph, pass_record)
    assert len(parsed.operations[0].inputs) == 1 and len(parsed.blocks[1].incoming) == 2


@pytest.mark.parametrize("side", ["incoming", "outgoing"])
@pytest.mark.parametrize(
    "change",
    ["missing", "wrong_slot", "foreign", "other_slot", "duplicate", "wrong_shape"],
)
def test_reciprocal_slots_checked_both_directions(side: str, change: str) -> None:
    document, graph, pass_record = phi_sample([(0, 1), (0, 1)])
    block = graph["blocks"][1 if side == "incoming" else 0]
    if change == "missing":
        block[side].pop()
    elif change == "wrong_slot":
        block[side][0]["reciprocal_slot"] = 2
    elif change == "other_slot":
        block[side][0]["reciprocal_slot"] = 1
    elif change == "foreign":
        block[side][0]["other"]["pass_id"] = "c" * 64
    elif change == "duplicate":
        block[side][1] = deepcopy(block[side][0])
    else:
        block[side][0]["extra"] = 0
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)


def test_two_owners_and_equal_storage_wrong_definition_refuse() -> None:
    document, graph, pass_record = sample()
    graph["blocks"][1]["operations"] = deepcopy(graph["blocks"][0]["operations"])
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)
    document, graph, pass_record = sample()
    extra = deepcopy(graph["values"][2])
    extra["id"]["local_id"] = 100
    graph["values"].append(extra)
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, pass_record)


@pytest.mark.parametrize("domain", ["raw", "analyzed"])
def test_unknown_opcode_requires_its_exact_gap(domain: str) -> None:
    document, graph, pass_record = sample()
    if domain == "raw":
        document["functions"][0]["instructions"][1]["pcode"][0]["opcode"] = "FUTURE_OP"
        key = graph["raw_operation_keys"][0]
    else:
        document["functions"][0]["decompilation"]["analyzed_pcode"][0]["opcode"] = (
            "FUTURE_OP"
        )
        graph["operations"][0]["opcode"] = "FUTURE_OP"
        key = graph["operations"][0]["id"]
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, pass_record)
    graph["gaps"].append(gap("unsupported_opcode", operation=key))
    assert read(document, graph, pass_record).record() == graph


@pytest.mark.parametrize("field", ["is_input", "is_free"])
def test_conflicting_value_flags_are_kept_with_gap(field: str) -> None:
    document, graph, pass_record = sample()
    graph["values"][2][field] = True
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, pass_record)
    graph["gaps"].append(gap("ssa_unbound", value=graph["values"][2]["id"]))
    parsed = read(document, graph, pass_record)
    assert getattr(parsed.values[2], field) is True
    assert parsed.values[2].definition is not None


@pytest.mark.parametrize(
    "size,bits",
    [(1, 255), (2, 65535), (8, 2**64 - 1), (16, 2**64 - 1), (65536, 2**64 - 1)],
)
def test_constant_widths_and_actual_free_flag(size: int, bits: int) -> None:
    document, graph, pass_record = sample()
    graph["values"][3].update(
        storage=address(bits, "const"),
        size_bytes=size,
        bits=hex(bits),
        is_constant=True,
        is_free=True,
    )
    parsed = read(document, graph, pass_record)
    assert parsed.values[3].bits == hex(bits)
    assert parsed.values[3].is_free is True
    if size < 8:
        graph["values"][3].update(
            storage=address(bits + 1, "const"), bits=hex(bits + 1)
        )
        with pytest.raises(ByteGraphV2FormatError):
            read(document, graph, pass_record)


@pytest.mark.parametrize(
    "bad",
    ["0X0", "0x00", "0xA", "-0x1", "0x10000000000000000", "0x", "1", 0, True, None],
)
@pytest.mark.parametrize(
    "path",
    [
        ("entry", "ordinary_entry", "offset"),
        ("blocks", 0, "cover_min", "offset"),
        ("values", 3, "storage", "offset"),
        ("operations", 0, "id", "sequence", "address", "offset"),
        ("raw_instruction_sites", 0, "offset"),
    ],
)
def test_unsigned_hex_boundaries(path: tuple[str | int, ...], bad: object) -> None:
    document, graph, pass_record = sample()
    mutate(graph, path, bad)
    with pytest.raises(ByteGraphV2Error):
        read(document, graph, pass_record)


@pytest.mark.parametrize("name", [f.name for f in fields(ByteGraphV2Limits)])
@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", None])
def test_invalid_limits(name: str, value: Any) -> None:
    with pytest.raises(ByteGraphV2LimitError):
        ByteGraphV2Limits(**{name: value})


@pytest.mark.parametrize("name", [f.name for f in fields(ByteGraphV2Limits)])
def test_hard_limits_cannot_be_raised(name: str) -> None:
    with pytest.raises(ByteGraphV2LimitError):
        ByteGraphV2Limits(**{name: getattr(ByteGraphV2Limits(), name) + 1})


def test_each_reduced_bound_accepts_exact_and_rejects_one_over() -> None:
    document, graph, pass_record = phi_sample([(0, 1), (0, 1)])
    lift = bind(document, graph)
    raw = wire(graph)
    counts = {
        "max_graph_bytes": len(raw),
        "max_source_bytes": len(
            document["functions"][0]["decompilation"]["raw_c"].encode()
        ),
        "max_blocks": 2,
        "max_operations": 2,
        "max_raw_instructions": 3,
        "max_inputs": 2,
        "max_values": 4,
        "max_references": 4,
        "max_edges": 2,
        "max_gaps": 7,
    }
    for name, count in counts.items():
        assert (
            parse_byte_graph_v2(
                raw,
                lift=lift,
                pass_record=parse_pass_record(wire(pass_record)),
                limits=ByteGraphV2Limits(**{name: count}),
            ).record()
            == graph
        )
        with pytest.raises(ByteGraphV2LimitError):
            parse_byte_graph_v2(
                raw,
                lift=lift,
                pass_record=parse_pass_record(wire(pass_record)),
                limits=ByteGraphV2Limits(**{name: count - 1}),
            )


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"{} trailing",
        b"[]",
        b'{"schema":2,"schema":2}',
        b"\xef\xbb\xbf{}",
        b'{"schema":NaN}',
        b'{"schema":Infinity}',
        b'{"schema":-Infinity}',
        b'{"schema":2.0}',
        b'{"schema":' + b"9" * 5000 + b"}",
    ],
)
def test_malformed_json_has_finite_error(raw: bytes) -> None:
    document, graph, pass_record = sample()
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            raw,
            lift=bind(document, graph),
            pass_record=parse_pass_record(wire(pass_record)),
        )


def test_nested_duplicate_key_and_surrogates_refuse() -> None:
    document, graph, pass_record = sample()
    lift = bind(document, graph)
    raw = wire(graph).replace(b'"space":"ram"', b'"space":"ram","space":"ram"', 1)
    with pytest.raises(ByteGraphV2FormatError):
        parse_byte_graph_v2(
            raw, lift=lift, pass_record=parse_pass_record(wire(pass_record))
        )
    for value in ("\ud800", "\udfff"):
        graph["values"][3]["storage"]["space"] = value
        with pytest.raises(ByteGraphV2FormatError):
            read(document, graph, pass_record)


@pytest.mark.parametrize(
    "name",
    [
        "schema",
        "profile",
        "ghidra_version",
        "ghidra_revision",
        "java_runtime_version",
        "language_id",
        "compiler_spec_id",
        "simplification_style",
        "configured_options",
        "timeout_seconds",
        "printer_transformer",
        "line_separator",
        "call_ordinal",
        "source_manifest_sha256",
        "tool_manifest_sha256",
    ],
)
def test_pass_fields_are_checked(name: str) -> None:
    _, _, record = sample()
    record[name] = "wrong"
    with pytest.raises(ByteGraphV2Error):
        parse_pass_record(wire(record))


def test_pass_constructor_does_not_bypass_checks() -> None:
    document, graph, record = sample()
    parsed = parse_pass_record(wire(record))
    assert parsed.to_bytes() == wire(record)
    assert parsed.sha256 == graph["pass_id"]
    forged = replace(parsed)
    object.__setattr__(forged, "timeout_seconds", True)
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph),
            lift=bind(document, graph),
            pass_record=forged,
        )


@given(st.lists(st.booleans(), min_size=7, max_size=7), st.integers(4, 2**32 - 1))
@settings(max_examples=50)
def test_round_trips_keep_flags_and_unused_identity(
    flags: list[bool], local_id: int
) -> None:
    document, graph, record = sample()
    graph["operations"][0]["java_is_dead"] = flags[0]
    for name, flag in zip(
        ("is_input", "is_free", "address_tied", "persistent", "unaffected"),
        flags[1:6],
        strict=True,
    ):
        graph["values"][3][name] = flag
    graph["values"][3]["id"]["local_id"] = local_id
    graph["gaps"][-1]["value"]["local_id"] = local_id
    first = read(document, graph, record)
    second = parse_byte_graph_v2(
        first.to_bytes(),
        lift=bind(document, graph),
        pass_record=parse_pass_record(wire(record)),
    )
    assert second == first and second.record() == graph
    assert second.operations[0].java_is_dead is flags[0]
    assert second.values[3].id.local_id == local_id


@given(
    st.sampled_from(
        (
            "schema",
            "entry",
            "blocks",
            "operations",
            "values",
            "gaps",
            "native_inventory",
        )
    ),
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=32),
        lambda c: (
            st.lists(c, max_size=3)
            | st.dictionaries(st.text(max_size=8), c, max_size=3)
        ),
        max_leaves=10,
    ),
)
@settings(max_examples=120)
def test_bounded_mutations_never_escape_finite_errors(
    field: str, replacement: object
) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    graph[field] = replacement
    try:
        result = parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(record))
        )
    except ByteGraphV2Error:
        return
    assert result.record() == graph


@given(st.binary(max_size=1500))
@settings(max_examples=80)
def test_arbitrary_bytes_have_finite_errors(raw: bytes) -> None:
    document, graph, record = sample()
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            raw, lift=bind(document, graph), pass_record=parse_pass_record(wire(record))
        )


def expanded(
    domain: str, count: int
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document, graph, record = sample()
    ordinary = document["functions"][0]
    if domain == "blocks":
        for index in range(2, count):
            block = deepcopy(graph["blocks"][1])
            block["id"]["index"] = index
            graph["blocks"].append(block)
    elif domain == "listing_blocks":
        ordinary["blocks"] = [
            {"entry": address(0x1000 + i), "ranges": []} for i in range(count)
        ]
    elif domain == "instructions":
        ordinary["ranges"] = [{"start": address(0x1000), "end": address(0x2000)}]
        ordinary["instructions"] = [
            {
                "address": address(0x1000 + i),
                "size": 1,
                "text": "synthetic",
                "pcode": [],
            }
            for i in range(count)
        ]
        graph["raw_instruction_sites"] = [address(0x1000 + i) for i in range(count)]
        graph["raw_operation_keys"] = []
    elif domain == "raw":
        ordinary["instructions"][1]["pcode"] = [
            {
                "sequence": sequence(0x1010, i),
                "opcode": "COPY",
                "output": None,
                "inputs": [],
            }
            for i in range(count)
        ]
        key = graph["raw_operation_keys"][0]
        graph["raw_operation_keys"] = [
            {**key, "sequence": sequence(0x1010, i)} for i in range(count)
        ]
    elif domain == "analyzed":
        for index in range(2, count):
            op = deepcopy(graph["operations"][1])
            op["id"]["sequence"]["index"] = index + 7
            op.update(parent=graph["blocks"][1]["id"], java_order=index - 2)
            graph["operations"].append(op)
            graph["blocks"][1]["operations"].append(op["id"])
            ordinary["decompilation"]["analyzed_pcode"].append(
                {
                    "sequence": sequence(0x1020, index + 7),
                    "opcode": "INT_ADD",
                    "output": None,
                    "inputs": [operand(0x10, "register")],
                }
            )
    elif domain == "inputs":
        graph["operations"][0]["inputs"] = [
            deepcopy(graph["values"][0]["id"]) for _ in range(count)
        ]
        ordinary["decompilation"]["analyzed_pcode"][0]["inputs"] = [
            operand(0x10, "register") for _ in range(count)
        ]
    elif domain == "values":
        for index in range(4, count):
            value = deepcopy(graph["values"][0])
            value["id"]["local_id"] = index
            graph["values"].append(value)
    elif domain == "edges":
        graph["blocks"][0]["outgoing"] = [
            {"other": deepcopy(graph["blocks"][1]["id"]), "reciprocal_slot": i}
            for i in range(count)
        ]
        graph["blocks"][1]["incoming"] = [
            {"other": deepcopy(graph["blocks"][0]["id"]), "reciprocal_slot": i}
            for i in range(count)
        ]
    elif domain == "gaps":
        for index in range(count - 7):
            value = deepcopy(graph["values"][0])
            value["id"]["local_id"] = index + 4
            graph["values"].append(value)
            graph["gaps"].append(gap("interface_unproved", value=value["id"]))
    elif domain == "functions":
        for index in range(1, count):
            function = deepcopy(ordinary)
            function.update(
                entry=address(0x3000 + index), ranges=[], instructions=[], blocks=[]
            )
            function["decompilation"]["analyzed_pcode"] = []
            document["functions"].append(function)
    else:
        raise AssertionError(domain)
    return document, graph, record


@pytest.mark.parametrize(
    "domain,limit",
    [
        ("blocks", 32),
        ("listing_blocks", 32),
        ("instructions", 256),
        ("raw", 256),
        ("analyzed", 256),
        ("inputs", 256),
        ("edges", 1024),
        ("gaps", 256),
        ("functions", 32),
    ],
)
@pytest.mark.parametrize("extra", [0, 1])
def test_hard_inventory_boundaries(domain: str, limit: int, extra: int) -> None:
    document, graph, record = expanded(domain, limit + extra)
    if domain == "inputs" and extra:
        document["functions"][0]["decompilation"]["analyzed_pcode"][0]["inputs"].pop()
    if extra:
        with pytest.raises(ByteGraphV2LimitError):
            read(document, graph, record)
    else:
        assert read(document, graph, record).record() == graph


def test_unused_values_have_an_independent_reduced_limit() -> None:
    document, graph, record = expanded("values", 257)
    assert (
        len(
            read(
                document, graph, record, limits=ByteGraphV2Limits(max_values=257)
            ).values
        )
        == 257
    )
    with pytest.raises(ByteGraphV2LimitError):
        read(document, graph, record, limits=ByteGraphV2Limits(max_values=256))


def test_full_value_count_is_also_subject_to_graph_byte_cap() -> None:
    document, graph, record = expanded("values", 65792)
    lift = bind(document, graph)
    raw = wire(graph)
    assert len(raw) > 16 * 1024 * 1024
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(raw, lift=lift, pass_record=parse_pass_record(wire(record)))
    graph["values"].append(deepcopy(graph["values"][-1]))
    graph["values"][-1]["id"]["local_id"] += 1
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(record))
        )


@pytest.mark.parametrize("domain", ["raw", "analyzed"])
def test_repeated_reference_limit_counts_every_slot_and_output(domain: str) -> None:
    document, graph, record = sample()
    ordinary = document["functions"][0]
    if domain == "raw":
        ordinary["instructions"][1]["pcode"] = [
            {
                "sequence": sequence(0x1010, i),
                "opcode": "COPY",
                "output": operand(0x20, "register"),
                "inputs": [operand(0x10, "register")] * 256,
            }
            for i in range(256)
        ]
        base = graph["raw_operation_keys"][0]
        graph["raw_operation_keys"] = [
            {**base, "sequence": sequence(0x1010, i)} for i in range(256)
        ]
    else:
        base = graph["operations"][0]
        graph["operations"] = []
        graph["blocks"][0]["operations"] = []
        graph["values"] = [graph["values"][0], graph["values"][1], graph["values"][3]]
        graph["gaps"] = [g for g in graph["gaps"] if g["code"] != "unowned_operation"]
        ordinary["decompilation"]["analyzed_pcode"] = []
        for i in range(256):
            key = {**base["id"], "sequence": sequence(0x1010, i)}
            value = deepcopy(graph["values"][0])
            value.update(
                id={**value["id"], "local_id": i + 10},
                storage=address(0x200 + i, "unique"),
                definition=key,
                is_input=False,
            )
            graph["values"].append(value)
            graph["operations"].append(
                {
                    **base,
                    "id": key,
                    "inputs": [graph["values"][0]["id"]] * 256,
                    "output": value["id"],
                    "java_order": i,
                }
            )
            graph["blocks"][0]["operations"].append(key)
            ordinary["decompilation"]["analyzed_pcode"].append(
                {
                    "sequence": sequence(0x1010, i),
                    "opcode": "COPY",
                    "output": operand(0x200 + i, "unique", sequence(0x1010, i)),
                    "inputs": [operand(0x10, "register")] * 256,
                }
            )
    parsed = read(document, graph, record)
    assert parsed.record() == graph
    with pytest.raises(ByteGraphV2LimitError):
        read(document, graph, record, limits=ByteGraphV2Limits(max_references=65791))


@pytest.mark.parametrize("extra", [0, 1])
def test_graph_hard_byte_boundary(extra: int) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    raw = wire(graph)
    raw += b" " * (16 * 1024 * 1024 - len(raw) + extra)
    if extra:
        with pytest.raises(ByteGraphV2LimitError):
            parse_byte_graph_v2(
                raw, lift=lift, pass_record=parse_pass_record(wire(record))
            )
    else:
        assert parse_byte_graph_v2(
            raw, lift=lift, pass_record=parse_pass_record(wire(record))
        ).to_bytes() == wire(graph)


@pytest.mark.parametrize("extra", [0, 1])
def test_source_hard_byte_boundary(extra: int) -> None:
    document, graph, record = sample()
    source = "µ" * (512 * 1024) + "a" * extra
    document["functions"][0]["decompilation"]["raw_c"] = source
    graph["raw_c_sha256"] = sha256(source.encode()).hexdigest()
    if extra:
        with pytest.raises(ByteGraphV2LimitError):
            read(document, graph, record)
    else:
        assert read(document, graph, record).raw_c_sha256 == graph["raw_c_sha256"]


def json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((json_depth(child) for child in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((json_depth(child) for child in value), default=0)
    return 0


def test_json_depth_exact_reduced_and_hard_boundaries() -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    depth = json_depth(graph)
    assert (
        parse_byte_graph_v2(
            wire(graph),
            lift=lift,
            pass_record=parse_pass_record(wire(record)),
            limits=ByteGraphV2Limits(max_json_depth=depth),
        ).record()
        == graph
    )
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(
            wire(graph),
            lift=lift,
            pass_record=parse_pass_record(wire(record)),
            limits=ByteGraphV2Limits(max_json_depth=depth - 1),
        )
    with pytest.raises(ByteGraphV2FormatError):
        parse_byte_graph_v2(
            b"[" * 32 + b"0" + b"]" * 32,
            lift=lift,
            pass_record=parse_pass_record(wire(record)),
        )
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(
            b"[" * 33 + b"0" + b"]" * 33,
            lift=lift,
            pass_record=parse_pass_record(wire(record)),
        )


@pytest.mark.parametrize(
    "path",
    [
        ("values", 3, "storage", "space"),
        ("blocks", 0, "cover_min", "space"),
        ("operations", 0, "id", "sequence", "address", "space"),
    ],
)
def test_space_utf8_length_bound(path: tuple[str | int, ...]) -> None:
    document, graph, record = sample()
    if path == ("values", 3, "storage", "space"):
        mutate(graph, path, "µ" * 64)
        assert read(document, graph, record).values[3].storage.space == "µ" * 64
    mutate(graph, path, "µ" * 64 + "x")
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)


@pytest.mark.parametrize("bad", ["", "a-b", "é", "9OP", "A" * 65])
def test_opcode_identifier_bound(bad: str) -> None:
    document, graph, record = sample()
    graph["operations"][0]["opcode"] = bad
    document["functions"][0]["decompilation"]["analyzed_pcode"][0]["opcode"] = bad
    graph["gaps"].append(
        gap("unsupported_opcode", operation=graph["operations"][0]["id"])
    )
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)


def test_exact_scalar_edges() -> None:
    document, graph, record = sample()
    graph["ram_space_id"] = -(2**31)
    graph["operations"][1]["java_order"] = -(2**31)
    graph["values"][3]["storage"] = address(2**64 - 1, "unused")
    graph["values"][3]["size_bytes"] = 65536
    graph["values"][3]["id"]["local_id"] = 2**32 - 1
    graph["gaps"][-1]["value"]["local_id"] = 2**32 - 1
    assert read(document, graph, record).values[3].storage.offset == 2**64 - 1
    graph["ram_space_id"] = 2**31 - 1
    graph["operations"][1]["java_order"] = 2**31 - 1
    assert read(document, graph, record).operations[1].java_order == 2**31 - 1


def test_pass_ordinal_bound_and_crlf_identity() -> None:
    document, graph, record = expanded("functions", 32)
    first = document["functions"].pop(0)
    document["functions"].append(first)
    record.update(call_ordinal=31, line_separator="\r\n")
    old_pass = graph["pass_id"]
    new_pass = sha256(wire(record)).hexdigest()
    graph = json.loads(wire(graph).replace(old_pass.encode(), new_pass.encode()))
    assert read(document, graph, record).pass_id == new_pass
    record["call_ordinal"] = 32
    with pytest.raises(ByteGraphV2Error):
        parse_pass_record(wire(record))


def test_supplementary_unicode_is_preserved_without_normalization() -> None:
    document, graph, record = sample()
    graph["values"][3]["storage"]["space"] = "é_e\u0301_😀"
    parsed = read(document, graph, record)
    assert parsed.values[3].storage.space == "é_e\u0301_😀"
    assert parsed.to_bytes().isascii()
    assert b"\\ud83d\\ude00" in parsed.to_bytes()


def test_direct_volatile_observations_keep_domains_and_require_resolution() -> None:
    document, graph, record = sample()
    graph["explicit_volatile_sites"] = [
        graph["operations"][0]["id"],
        graph["raw_operation_keys"][0],
    ]
    parsed = read(document, graph, record)
    assert [key.domain for key in parsed.explicit_volatile_sites] == ["analyzed", "raw"]
    assert any(g.code == "memory_effects_unproved" for g in parsed.gaps)
    graph["explicit_volatile_sites"].append(
        deepcopy(graph["explicit_volatile_sites"][0])
    )
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)


def test_reference_gaps_must_resolve_and_match_ownership() -> None:
    document, graph, record = sample()
    graph["gaps"].append(
        gap(
            "cfg_unclosed",
            block=graph["blocks"][0]["id"],
            operation=graph["operations"][0]["id"],
        )
    )
    assert read(document, graph, record).record() == graph
    graph["gaps"].append(
        gap(
            "cfg_unclosed",
            block=graph["blocks"][1]["id"],
            operation=graph["operations"][0]["id"],
        )
    )
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)


def test_supplied_lift_limits_cannot_be_hidden_by_graph_omission() -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    function = lift.functions[lift.main]
    for changed in (
        replace(function, instructions=function.instructions * 100),
        replace(function, analyzed=function.analyzed * 200),
        replace(function, blocks=function.blocks * 33),
    ):
        with pytest.raises(ByteGraphV2LimitError):
            parse_byte_graph_v2(
                wire(graph),
                lift=replace(lift, functions={lift.main: changed}),
                pass_record=parse_pass_record(wire(record)),
            )


def test_listing_range_and_edge_bounds_are_applied() -> None:
    document, graph, record = sample()
    function = document["functions"][0]
    function["ranges"] = [
        {"start": address(0x1000), "end": address(0x1010)},
        {"start": address(0x1020), "end": address(0x1030)},
    ]
    function["blocks"][0]["ranges"] = deepcopy(function["ranges"])
    assert read(document, graph, record).record() == graph
    lift = bind(document, graph)
    current = lift.functions[lift.main]
    altered = replace(current, ranges=current.ranges * 129)
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(
            wire(graph),
            lift=replace(lift, functions={lift.main: altered}),
            pass_record=parse_pass_record(wire(record)),
        )
    function["flow_edges"] = [
        {
            "from_block": address(0x1000),
            "to_block": address(0x1000),
            "site": address(0x1010),
            "target": address(0x1000),
            "kind": "UNCONDITIONAL_JUMP",
        }
    ] * 2
    assert (
        read(document, graph, record, limits=ByteGraphV2Limits(max_edges=2)).record()
        == graph
    )
    with pytest.raises(ByteGraphV2LimitError):
        read(document, graph, record, limits=ByteGraphV2Limits(max_edges=1))


def test_non_bytes_limits_pass_and_lift_are_controlled() -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    parsed_pass = parse_pass_record(wire(record))
    for kwargs in (
        {"raw_bytes": bytearray(wire(graph)), "lift": lift, "pass_record": parsed_pass},
        {"raw_bytes": wire(graph), "lift": None, "pass_record": parsed_pass},
        {"raw_bytes": wire(graph), "lift": lift, "pass_record": None},
        {
            "raw_bytes": wire(graph),
            "lift": lift,
            "pass_record": parsed_pass,
            "limits": {},
        },
    ):
        with pytest.raises(ByteGraphV2Error):
            parse_byte_graph_v2(**kwargs)


@pytest.mark.parametrize("side", ["raw", "analyzed"])
def test_supplied_lift_over_limit_inputs_are_checked(side: str) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    function = lift.functions[lift.main]
    if side == "analyzed":
        operation = function.analyzed[0]
        function = replace(
            function,
            analyzed=(
                replace(operation, inputs=(operation.inputs[0],) * 257),
                *function.analyzed[1:],
            ),
        )
    else:
        instruction = function.instructions[1]
        operation = instruction.pcode[0]
        instruction = replace(
            instruction,
            pcode=(replace(operation, inputs=(operation.inputs[0],) * 257),),
        )
        function = replace(
            function,
            instructions=(
                function.instructions[0],
                instruction,
                function.instructions[2],
            ),
        )
    with pytest.raises(ByteGraphV2LimitError):
        parse_byte_graph_v2(
            wire(graph),
            lift=replace(lift, functions={lift.main: function}),
            pass_record=parse_pass_record(wire(record)),
        )


@pytest.mark.parametrize("extra", [0, 1])
def test_pass_bytes_bound(extra: int) -> None:
    _, _, record = sample()
    raw = wire(record)
    raw += b" " * (65536 - len(raw) + extra)
    if extra:
        with pytest.raises(ByteGraphV2LimitError):
            parse_pass_record(raw)
    else:
        assert parse_pass_record(raw).record() == record


@pytest.mark.parametrize(
    "field", ["binary_sha256", "lift_sha256", "pass_id", "raw_c_sha256"]
)
@pytest.mark.parametrize("bad", ["0" * 63, "0" * 65, "A" * 64, "g" * 64, True, None, 0])
def test_digest_shape(field: str, bad: object) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    graph[field] = bad
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph), lift=lift, pass_record=parse_pass_record(wire(record))
        )


@pytest.mark.parametrize("flag_bits", range(64))
def test_all_value_flags_are_preserved(flag_bits: int) -> None:
    document, graph, record = sample()
    value = graph["values"][3]
    names = (
        "is_constant",
        "is_input",
        "is_free",
        "address_tied",
        "persistent",
        "unaffected",
    )
    for index, name in enumerate(names):
        value[name] = bool(flag_bits & (1 << index))
    if value["is_constant"]:
        value.update(storage=address(0x30, "const"), bits="0x30")
    parsed = read(document, graph, record)
    assert [getattr(parsed.values[3], name) for name in names] == [
        bool(flag_bits & (1 << index)) for index in range(6)
    ]


def test_opcode_and_sequence_exact_upper_bounds() -> None:
    document, graph, record = sample()
    key = graph["operations"][1]["id"]
    key["sequence"]["index"] = 1_000_000
    graph["operations"][1]["opcode"] = "A" * 64
    ordinary = document["functions"][0]["decompilation"]["analyzed_pcode"][1]
    ordinary.update(sequence=deepcopy(key["sequence"]), opcode="A" * 64)
    graph["gaps"] = [g for g in graph["gaps"] if g["code"] != "unowned_operation"]
    graph["gaps"].extend(
        [
            gap("unowned_operation", operation=key),
            gap("unsupported_opcode", operation=key),
        ]
    )
    parsed = read(document, graph, record)
    assert parsed.operations[1].id.sequence.index == 1_000_000
    assert parsed.operations[1].opcode == "A" * 64


def test_missing_entry_block_is_not_reconstructed() -> None:
    document, graph, record = sample()
    graph["blocks"] = []
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)


def test_unowned_phi_requires_both_gaps() -> None:
    document, graph, record = sample()
    graph["operations"][1]["opcode"] = "MULTIEQUAL"
    document["functions"][0]["decompilation"]["analyzed_pcode"][1]["opcode"] = (
        "MULTIEQUAL"
    )
    with pytest.raises(ByteGraphV2FormatError):
        read(document, graph, record)
    graph["gaps"].append(
        gap("phi_binding_unproved", operation=graph["operations"][1]["id"])
    )
    assert read(document, graph, record).operations[1].parent is None


def test_hashing_coding_error_is_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    import phoenix.lift.byte_graph_v2 as module

    document, graph, record = sample()
    lift = bind(document, graph)
    parsed_pass = parse_pass_record(wire(record))

    def broken(_: bytes) -> Any:
        raise RuntimeError("Hash implementation failed.")

    monkeypatch.setattr(module, "sha256", broken)
    with pytest.raises(RuntimeError, match="Hash implementation failed"):
        parse_byte_graph_v2(wire(graph), lift=lift, pass_record=parsed_pass)


@pytest.mark.parametrize("bad", [True, 1.0, -1, 2**64])
def test_constructed_pass_does_not_coerce_entry_type(bad: Any) -> None:
    document, graph, record = sample()
    parsed = parse_pass_record(wire(record))
    forged = replace(parsed, function=replace(parsed.function, ghidra_entry=bad))
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(wire(graph), lift=bind(document, graph), pass_record=forged)


@pytest.mark.parametrize("bad", [True, 1.0, -1, 2**64])
def test_supplied_lift_address_types_are_not_coerced(bad: Any) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    function = lift.functions[lift.main]
    operation = function.analyzed[0]
    location = replace(operation.sequence.address, offset=bad)
    operation = replace(
        operation, sequence=replace(operation.sequence, address=location)
    )
    function = replace(function, analyzed=(operation, *function.analyzed[1:]))
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph),
            lift=replace(lift, functions={lift.main: function}),
            pass_record=parse_pass_record(wire(record)),
        )


@pytest.mark.parametrize("source", [None, "\ud800"])
def test_missing_or_invalid_ordinary_source_refuses(source: Any) -> None:
    document, graph, record = sample()
    lift = bind(document, graph)
    function = replace(lift.functions[lift.main], raw_c=source)
    with pytest.raises(ByteGraphV2Error):
        parse_byte_graph_v2(
            wire(graph),
            lift=replace(lift, functions={lift.main: function}),
            pass_record=parse_pass_record(wire(record)),
        )
