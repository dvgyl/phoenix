import json
import os
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix.lift import evidence as boundary
from phoenix.lift import lift_binary
from phoenix.lift.evidence import (
    Address,
    EvidenceError,
    JumpEvidence,
    PrototypeEvidence,
    RegisterEvidence,
    Slot,
    StaticEvidence,
    StorageEvidence,
    StoragePiece,
    TypeEvidence,
    parse_static_evidence,
    read_static_evidence,
)
from phoenix.recover import recover
from phoenix_eval.integrity import original_shapes


def proposal() -> StaticEvidence:
    storage = StorageEvidence(
        "assigned",
        4,
        False,
        None,
        (StoragePiece(Address("register", "0x0"), 4, "EAX", None),),
    )
    result = Slot(None, "t0", storage)
    listing = PrototypeEvidence(
        "listing", "custom-example", True, False, False, (), result
    )
    return StaticEvidence(
        1,
        "proposal",
        listing,
        replace(listing, source="decompiler", custom_storage=None),
        (TypeEvidence("t0", "/int", "int", "opaque", 4, None, None),),
        (RegisterEvidence("EAX", Address("register", "0x0"), 32, "EAX", 0),),
        (),
    )


def wire(value: StaticEvidence | None = None) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(asdict(value or proposal()))))


def change(document: dict[str, object], path: str, value: object) -> None:
    parts = path.split(".")
    parent: object = document
    for part in parts[:-1]:
        parent = (
            cast(list[object], parent)[int(part)]
            if isinstance(parent, list)
            else cast(dict[str, object], parent)[part]
        )
    if isinstance(parent, list):
        parent[int(parts[-1])] = value
    else:
        cast(dict[str, object], parent)[parts[-1]] = value


def test_distinct_proposals_round_trip() -> None:
    value = parse_static_evidence(wire())
    assert value == proposal()
    assert value.listing.source == "listing"
    assert value.listing.custom_storage is True
    assert value.decompiler is not None
    assert value.decompiler.source == "decompiler"
    assert value.decompiler.custom_storage is None
    assert value.status == "proposal"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("status", "verified"),
        ("listing.source", "decompiler"),
        ("listing.custom_storage", None),
        ("decompiler.custom_storage", False),
        ("listing.variadic", 1),
        ("types.0.id", "t00"),
        ("types.0.target", "absent"),
        ("types.0.count", 2),
        ("types.0.size", -2),
        ("types.0.path", "x" * 1025),
        ("listing.result.type", "absent"),
        ("registers.0.base", "absent"),
        ("registers.0.least_bit", 1),
        ("registers.0.bits", 8),
        ("registers.0.bits", 0),
        ("registers.0.bits", 65537),
        ("listing.result.storage.size", 5),
        ("listing.result.storage.state", "unknown"),
        ("listing.result.storage.pieces.0.register", "absent"),
        ("listing.result.storage.pieces.0.address.offset", "0x00"),
        ("listing.result.storage.pieces.0.address.offset", "0x10000000000000000"),
        ("listing.result.storage.pieces.0.stack_offset", 0),
        ("listing.result.storage.pieces.0.size", True),
        ("listing.result.storage.pieces.0.size", 0),
        ("listing.result.storage.pieces.0.size", 8193),
    ],
)
def test_rejects_malformed_metadata(path: str, value: object) -> None:
    document = wire()
    change(document, path, value)
    with pytest.raises(EvidenceError):
        parse_static_evidence(document)


@given(st.one_of(st.integers(max_value=0), st.integers(min_value=65537), st.booleans()))
def test_rejects_invalid_register_widths(width: object) -> None:
    document = wire()
    change(document, "registers.0.bits", width)
    with pytest.raises(EvidenceError):
        parse_static_evidence(document)


@given(st.data(), st.integers(1, 8192))
def test_stack_offsets_and_widths_round_trip(data: st.DataObject, size: int) -> None:
    offset = data.draw(
        st.one_of(
            st.integers(min_value=-(2**63) + 1, max_value=-size),
            st.integers(min_value=0, max_value=2**63 - size),
        ),
        label="stack offset",
    )
    value = proposal()
    piece = StoragePiece(Address("stack", hex(offset % 2**64)), size, None, offset)
    storage = StorageEvidence("assigned", size, True, "RETURN_STORAGE_PTR", (piece,))
    value = replace(
        value, listing=replace(value.listing, result=Slot(None, None, storage))
    )
    assert parse_static_evidence(wire(value)) == value
    document = wire(value)
    change(document, "listing.result.storage.pieces.0.stack_offset", offset ^ 1)
    with pytest.raises(EvidenceError, match="stack offset"):
        parse_static_evidence(document)


@pytest.mark.parametrize("state", ["unknown", "bad", "unassigned", "void"])
def test_preserves_unresolved_and_void_storage(state: str) -> None:
    document = wire()
    change(document, "listing.result.storage.state", state)
    change(document, "listing.result.storage.size", 0)
    change(document, "listing.result.storage.pieces", [])
    result = parse_static_evidence(document)
    assert result.listing.result.storage.state == state
    assert result.listing.result.storage.pieces == ()


@pytest.mark.parametrize("field", ["types", "registers"])
def test_rejects_duplicate_identities(field: str) -> None:
    document = wire()
    document[field] = cast(list[object], document[field]) * 2
    with pytest.raises(EvidenceError, match="duplicate"):
        parse_static_evidence(document)


@pytest.mark.parametrize(("field", "count"), [("types", 257), ("registers", 513)])
def test_rejects_oversized_tables(field: str, count: int) -> None:
    document = wire()
    document[field] = cast(list[object], document[field]) * count
    with pytest.raises(EvidenceError, match="limit"):
        parse_static_evidence(document)


def test_preserves_explicit_recursive_pointer_references() -> None:
    value = replace(
        proposal(),
        types=(
            TypeEvidence("t0", "/recursive", "recursive", "pointer", 8, "t0", None),
        ),
    )
    assert parse_static_evidence(wire(value)) == value
    document = wire(value)
    change(document, "types.0.kind", "typedef")
    with pytest.raises(EvidenceError, match="recursive"):
        parse_static_evidence(document)
    change(document, "types.0.target", {"target": "t0"})
    with pytest.raises(EvidenceError):
        parse_static_evidence(document)


def test_rejects_deep_and_dangling_type_chains() -> None:
    chain = tuple(
        TypeEvidence(f"t{i}", f"/p{i}", f"p{i}", "pointer", 8, f"t{i + 1}", None)
        for i in range(33)
    )
    value = replace(
        proposal(), types=(*chain, replace(chain[0], id="t33", target=None))
    )
    with pytest.raises(EvidenceError, match="depth"):
        parse_static_evidence(wire(value))
    with pytest.raises(EvidenceError, match="reference"):
        parse_static_evidence(wire(replace(value, types=chain)))


def test_jump_tables_keep_api_order_repeated_targets_and_missing_labels() -> None:
    jump = JumpEvidence(
        Address("ram", "0x100"),
        (Address("ram", "0x200"), Address("ram", "0x200"), None),
        (-1,),
    )
    value = replace(proposal(), jump_tables=(jump,))
    assert parse_static_evidence(wire(value)) == value
    with pytest.raises(EvidenceError, match="duplicate"):
        parse_static_evidence(wire(replace(value, jump_tables=(jump, jump))))
    with pytest.raises(EvidenceError, match="decompiler"):
        parse_static_evidence(wire(replace(value, decompiler=None)))
    with pytest.raises(EvidenceError, match="limit"):
        parse_static_evidence(
            wire(replace(value, jump_tables=(replace(jump, labels=(0,) * 4097),)))
        )


def test_rejects_recursive_objects_and_unknown_fields() -> None:
    document = wire()
    document["listing"] = document
    with pytest.raises(EvidenceError):
        parse_static_evidence(document)
    document = wire()
    document["verified"] = True
    with pytest.raises(EvidenceError):
        parse_static_evidence(document)


def legacy_export() -> dict[str, object]:
    entry = {"space": "ram", "offset": "0x100"}
    return {
        "schema_version": 1,
        "main": {"entry": entry, "startup": entry, "setup": entry, "call": entry},
        "functions": [
            {
                "entry": entry,
                "name": "FUN_100",
                "signature": {
                    "return_type": "int",
                    "parameters": [],
                    "variadic": False,
                },
                "thunk_target": None,
                "ranges": [{"start": entry, "end": entry}],
                "instructions": [{"address": entry}],
                "decompilation": {
                    "status": "ok",
                    "raw_c": "int FUN_100(void) { return 0; }",
                },
                "flow_edges": [],
            }
        ],
        "call_edges": [],
        "data_references": [],
        "imports": [],
        "strings": [],
    }


def test_optional_evidence_preserves_recovery_and_integrity_readers(
    tmp_path: Path,
) -> None:
    document = legacy_export()
    path = tmp_path / "lift.json"
    path.write_text(json.dumps(document))
    legacy = recover(path)
    shapes = original_shapes(json.dumps(asdict(legacy)).encode(), raw=True)
    assert read_static_evidence(path)[0].evidence is None
    change(document, "functions.0.static_evidence", wire())
    path.write_text(json.dumps(document))
    assert recover(path) == legacy
    assert (
        original_shapes(json.dumps(asdict(recover(path))).encode(), raw=True) == shapes
    )
    assert read_static_evidence(path)[0].evidence == proposal()
    assert read_static_evidence(path)[0].decompilation_status == "ok"
    change(document, "functions.0.decompilation.status", "timeout")
    path.write_text(json.dumps(document))
    assert read_static_evidence(path)[0].decompilation_status == "timeout"
    assert read_static_evidence(path)[0].evidence == proposal()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":1,"functions":[]}',
        b'{"schema_version":true,"functions":[]}',
        b'{"schema_version":2,"functions":[]}',
        b'{"schema_version":1,"functions":[{"entry":{"space":"ram","offset":"0x00"}}]}',
        b"[" * 2000 + b"]" * 2000,
        b"\xff",
    ],
)
def test_reader_rejects_malformed_json(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "lift.json"
    path.write_bytes(raw)
    with pytest.raises(EvidenceError):
        read_static_evidence(path)


def test_reader_bounds_bytes_and_function_and_site_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "lift.json"
    document = legacy_export()
    functions = cast(list[object], document["functions"])
    document["functions"] = functions * 2
    path.write_text(json.dumps(document))
    with pytest.raises(EvidenceError, match="duplicate function"):
        read_static_evidence(path)
    document["functions"] = functions
    value = replace(
        proposal(), jump_tables=(JumpEvidence(Address("ram", "0x999"), (), ()),)
    )
    change(document, "functions.0.static_evidence", wire(value))
    path.write_text(json.dumps(document))
    with pytest.raises(EvidenceError, match="site"):
        read_static_evidence(path)
    monkeypatch.setattr(boundary, "MAX_EXPORT_BYTES", 32)
    with pytest.raises(EvidenceError, match="limit"):
        read_static_evidence(path)


def test_public_phase_grid_storage(tmp_path: Path) -> None:
    fixture = os.environ.get("PHOENIX_LIFT_EVIDENCE_FIXTURE")
    if fixture is None:
        pytest.skip(
            "Set PHOENIX_LIFT_EVIDENCE_FIXTURE to the fixed public phase-grid GCC ELF."
        )
    binary = Path(fixture)
    assert sha256(binary.read_bytes()).hexdigest() == (
        "771e830a15ff273d0c57ef75f6e75710a5e0550148342a119cb3b4b54f753688"
    )
    path = lift_binary(
        binary,
        tmp_path / "lift.json",
        Path(os.environ["PHOENIX_LIFT_GHIDRA"]),
        Path(os.environ["PHOENIX_LIFT_JAVA"]),
        max_heap_mib=384,
    ).export_path
    records = {
        record.entry.offset: record.evidence for record in read_static_evidence(path)
    }
    scan, next_state = records["0x1011e1"], records["0x1011a9"]
    assert scan is not None and next_state is not None
    assert scan.decompiler is not None and next_state.decompiler is not None
    assert scan.listing.parameters == next_state.listing.parameters == ()
    assert next_state.listing.result.storage.state == "unassigned"
    assert scan.decompiler.parameters[0].storage.pieces[0].register == "EDI"
    assert [
        slot.storage.pieces[0].register for slot in next_state.decompiler.parameters
    ] == ["EDI", "ESI", "EDX"]
    assert next_state.decompiler.result.storage.pieces[0].register == "EAX"
    assert next_state.decompiler.result.storage.size == 4
    document = json.loads(path.read_text())
    assert any(
        call["caller"]["offset"] == "0x1011e1"
        and call["site"]["offset"] == "0x101249"
        and call["target"]["offset"] == "0x1011a9"
        for call in document["call_edges"]
        if call["caller"] is not None and call["target"] is not None
    )
    caller = next(
        fn for fn in document["functions"] if fn["entry"]["offset"] == "0x1011e1"
    )
    assert any(
        op["opcode"] == "CALL" and op["sequence"]["address"]["offset"] == "0x101249"
        for ins in caller["instructions"]
        for op in ins["pcode"]
    )
    assert any(
        op["opcode"] == "CALL" and op["sequence"]["address"]["offset"] == "0x101249"
        for op in caller["decompilation"]["analyzed_pcode"]
    )
    assert all(not item.jump_tables for item in records.values() if item is not None)


def test_subregister_and_compound_storage_keep_piece_order() -> None:
    value = proposal()
    registers = (
        RegisterEvidence("RAX", Address("register", "0x0"), 64, "RAX", 0),
        RegisterEvidence("AH", Address("register", "0x1"), 8, "RAX", 8),
    )
    pieces = (
        StoragePiece(Address("stack", "0x8"), 4, None, 8),
        StoragePiece(Address("register", "0x1"), 1, "AH", None),
    )
    slot = Slot("value", None, StorageEvidence("assigned", 5, False, None, pieces))
    value = replace(
        value,
        registers=registers,
        listing=replace(value.listing, parameters=(slot,), result=slot),
        decompiler=None,
    )
    assert parse_static_evidence(wire(value)) == value
    document = wire(value)
    change(document, "listing.result.storage.pieces.0", asdict(pieces[1]))
    change(document, "listing.result.storage.size", 2)
    with pytest.raises(EvidenceError, match="pieces"):
        parse_static_evidence(document)


def storage_proposal(*pieces: StoragePiece) -> StaticEvidence:
    value = proposal()
    slot = Slot(
        None,
        None,
        StorageEvidence(
            "assigned", sum(piece.size for piece in pieces), False, None, pieces
        ),
    )
    return replace(
        value,
        listing=replace(value.listing, result=slot),
        decompiler=None,
        registers=(
            RegisterEvidence("RAX", Address("register", "0x0"), 64, "RAX", 0),
            RegisterEvidence("EAX", Address("register", "0x0"), 32, "RAX", 0),
            RegisterEvidence("AX", Address("register", "0x0"), 16, "RAX", 0),
            RegisterEvidence("AL", Address("register", "0x0"), 8, "RAX", 0),
            RegisterEvidence("AH", Address("register", "0x1"), 8, "RAX", 8),
            RegisterEvidence("RDX", Address("register", "0x10"), 64, "RDX", 0),
        ),
    )


@pytest.mark.parametrize("first_size", [2, 4, 8])
@pytest.mark.parametrize("first_name", [None, "RAX"])
def test_rejects_overlapping_subregister_pieces(
    first_size: int, first_name: str | None
) -> None:
    value = storage_proposal(
        StoragePiece(Address("register", "0x0"), first_size, first_name, None),
        StoragePiece(Address("register", "0x1"), 1, "AH", None),
    )
    with pytest.raises(EvidenceError, match="overlap"):
        parse_static_evidence(wire(value))


@pytest.mark.parametrize(
    ("space", "offset", "size"),
    [
        ("stack", -1, 2),
        ("stack", -7, 8),
        ("stack", 2**63 - 1, 2),
        ("stack", 2**63 - 7, 8),
        ("register", 2**64 - 1, 2),
        ("ram", 2**64 - 7, 8),
        ("unique", 2**64 - 1, 2),
    ],
)
def test_rejects_storage_spans_across_address_boundaries(
    space: str, offset: int, size: int
) -> None:
    piece = StoragePiece(
        Address(space, hex(offset % 2**64)),
        size,
        None,
        offset if space == "stack" else None,
    )
    with pytest.raises(EvidenceError, match="span"):
        parse_static_evidence(wire(storage_proposal(piece)))


@pytest.mark.parametrize(
    "piece",
    [
        StoragePiece(Address("stack", "0x8"), 4, None, 8),
        StoragePiece(Address("ram", "0x100"), 4, None, None),
        StoragePiece(Address("register", "0x4"), 4, None, None),
    ],
)
def test_rejects_unresolved_pieces_after_first_compound_piece(
    piece: StoragePiece,
) -> None:
    value = storage_proposal(
        StoragePiece(Address("register", "0x1"), 1, "AH", None), piece
    )
    with pytest.raises(EvidenceError, match="order"):
        parse_static_evidence(wire(value))


@pytest.mark.parametrize(
    "pieces",
    [
        (StoragePiece(Address("register", "0x0"), 3, "EAX", None),),
        (StoragePiece(Address("register", "0x4"), 4, None, None),),
        (
            StoragePiece(Address("register", "0x0"), 1, "AL", None),
            StoragePiece(Address("register", "0x1"), 1, "AH", None),
        ),
        (
            StoragePiece(Address("register", "0x10"), 8, "RDX", None),
            StoragePiece(Address("register", "0x0"), 8, "RAX", None),
        ),
        (
            StoragePiece(Address("ram", "0x0"), 8, None, None),
            StoragePiece(Address("register", "0x0"), 8, "RAX", None),
        ),
        (
            StoragePiece(Address("register", "0x4"), 4, None, None),
            StoragePiece(Address("register", "0x10"), 8, "RDX", None),
        ),
        (StoragePiece(Address("stack", "0xffffffffffffffff"), 1, None, -1),),
        (StoragePiece(Address("stack", "0xfffffffffffffff8"), 8, None, -8),),
        (StoragePiece(Address("stack", "0x0"), 8, None, 0),),
        (StoragePiece(Address("stack", "0x7fffffffffffffff"), 1, None, 2**63 - 1),),
        (StoragePiece(Address("ram", "0xffffffffffffffff"), 1, None, None),),
    ],
)
def test_preserves_valid_aliases_partial_pieces_and_storage_order(
    pieces: tuple[StoragePiece, ...],
) -> None:
    value = storage_proposal(*pieces)
    assert parse_static_evidence(wire(value)) == value


@pytest.mark.parametrize(
    ("offset", "bits", "least_bit"),
    [(0x100, 8, 8), (0, 8, 8), (1, 8, 0), (1, 8, 16), (7, 16, 56)],
)
def test_rejects_register_address_and_base_bit_conflicts(
    offset: int, bits: int, least_bit: int
) -> None:
    value = storage_proposal(
        StoragePiece(Address("register", hex(offset)), 1, "AH", None)
    )
    registers = list(value.registers)
    registers[4] = replace(
        registers[4],
        address=Address("register", hex(offset)),
        bits=bits,
        least_bit=least_bit,
    )
    with pytest.raises(EvidenceError, match="register"):
        parse_static_evidence(wire(replace(value, registers=tuple(registers))))


def test_rejects_register_before_its_base() -> None:
    value = storage_proposal(StoragePiece(Address("register", "0x1"), 1, "AH", None))
    registers = tuple(
        replace(register, address=Address("register", "0x8"))
        if register.name == "RAX"
        else register
        for register in value.registers
    )
    with pytest.raises(EvidenceError, match="register"):
        parse_static_evidence(wire(replace(value, registers=registers)))


def test_rejects_base_register_span_wrap() -> None:
    value = storage_proposal(StoragePiece(Address("ram", "0x0"), 1, None, None))
    register = RegisterEvidence(
        "base", Address("register", "0xffffffffffffffff"), 16, "base", 0
    )
    with pytest.raises(EvidenceError, match="register"):
        parse_static_evidence(wire(replace(value, registers=(register,))))


def test_preserves_register_bit_fields_within_the_base() -> None:
    value = storage_proposal(StoragePiece(Address("register", "0x0"), 3, "EAX", None))
    field = RegisterEvidence("bits", Address("register", "0x0"), 5, "RAX", 7)
    value = replace(value, registers=(*value.registers, field))
    assert parse_static_evidence(wire(value)) == value


def test_unknown_type_and_storage_address_stay_unresolved() -> None:
    value = proposal()
    piece = StoragePiece(Address("unique", "0x100"), 8, None, None)
    slot = Slot(None, None, StorageEvidence("assigned", 8, True, None, (piece,)))
    value = replace(value, listing=replace(value.listing, result=slot))
    assert parse_static_evidence(wire(value)) == value


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("listing.parameters", [None] * 129),
        ("listing.result.storage.pieces", [None] * 33),
        ("jump_tables", [None] * 257),
    ],
)
def test_rejects_oversized_evidence_before_reading_items(
    path: str, value: object
) -> None:
    document = wire()
    change(document, path, value)
    with pytest.raises(EvidenceError, match="limit"):
        parse_static_evidence(document)


def test_rejects_total_jump_budget_and_out_of_range_labels() -> None:
    jumps = tuple(
        JumpEvidence(Address("ram", hex(i)), (None,) * 4096, (0,) * 4096)
        for i in range(3)
    )
    with pytest.raises(EvidenceError, match="total limit"):
        parse_static_evidence(wire(replace(proposal(), jump_tables=jumps)))
    with pytest.raises(EvidenceError, match="bounds"):
        parse_static_evidence(
            wire(replace(proposal(), jump_tables=(JumpEvidence(None, (), (2**31,)),)))
        )
