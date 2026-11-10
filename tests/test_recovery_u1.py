"""Host controls use synthetic ELF records. Live gates are separate."""

import json
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from struct import pack_into
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    parse_mapping,
    publish_companion,
    read_companion,
)
from phoenix.recover.addresses import (
    ElfVA,
    checked_end,
    prove_addresses,
    read_elf,
    signed_difference,
)
from phoenix.recover.imports import bind_imports, read_dynamic_imports
from phoenix.recover.plan import make_candidate


def loc(address: int, space: str = "ram") -> dict[str, str]:
    return {"space": space, "offset": hex(address)}


def op(
    site: int,
    opcode: str,
    inputs: list[dict[str, Any]],
    output: dict[str, Any] | None = None,
    index: int = 0,
) -> dict[str, Any]:
    return {
        "sequence": {"address": loc(site), "index": index},
        "opcode": opcode,
        "output": output,
        "inputs": inputs,
    }


def operand(address: int, space: str = "ram") -> dict[str, Any]:
    return {"address": loc(address, space), "size": 8, "definition": None}


def fixture(delta: int = 0x100000, base: int = 0) -> tuple[bytes, dict[str, Any]]:
    """Construct bounded headers and one versioned external relocation."""
    data = bytearray(0xE00)
    ident = b"\x7fELF\x02\x01\x01" + bytes(9)
    pack_into(
        "<16sHHIQQQIHHHHHH",
        data,
        0,
        ident,
        3 if not base else 2,
        62,
        1,
        base + 0x100,
        64,
        0,
        0,
        64,
        56,
        3,
        0,
        0,
        0,
    )
    pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, base, base, 0x400, 0x400, 1)
    pack_into("<IIQQQQQQ", data, 120, 1, 6, 0x800, base + 0x2000, 0, 0x600, 0x700, 1)
    strings = b"\0fwrite\0libc.so.6\0GLIBC_2.2.5\0"
    tags = [
        (5, base + 0x2300),
        (10, len(strings)),
        (6, base + 0x2200),
        (11, 24),
        (4, base + 0x2280),
        (7, base + 0x2400),
        (8, 24),
        (9, 24),
        (1, 8),
        (0x6FFFFFF0, base + 0x22C0),
        (0x6FFFFFFE, base + 0x2480),
        (0x6FFFFFFF, 1),
        (0, 0),
    ]
    pack_into(
        "<IIQQQQQQ",
        data,
        176,
        2,
        6,
        0x800,
        base + 0x2000,
        0,
        len(tags) * 16,
        len(tags) * 16,
        1,
    )
    for index, (tag, value) in enumerate(tags):
        pack_into("<qQ", data, 0x800 + index * 16, tag, value)
    data[0x100:0x106] = b"\xe8\x3b\x00\x00\x00\xc3"
    data[0x140:0x146] = b"\xff\x25\xba\x23\x00\x00"
    data[0xB00 : 0xB00 + len(strings)] = strings
    pack_into("<IBBHQQ", data, 0xA18, 1, 0x12, 0, 0, 0, 0)
    pack_into("<IIIII", data, 0xA80, 1, 2, 1, 0, 0)
    pack_into("<HH", data, 0xAC0, 0, 2)
    pack_into("<QQq", data, 0xC00, base + 0x2500, (1 << 32) | 7, 0)
    pack_into("<HHIII", data, 0xC80, 1, 1, 8, 16, 0)
    pack_into("<IHHII", data, 0xC90, 0x09691A75, 0, 2, 18, 0)
    g = base + delta
    call, ret, thunk = g + 0x100, g + 0x105, g + 0x140

    def instruction(
        site: int, size: int, operations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "address": loc(site),
            "size": size,
            "text": "ignored label",
            "pcode": operations,
        }

    def function(
        entry: int,
        end: int,
        instructions: list[dict[str, Any]],
        target: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "entry": loc(entry),
            "name": "poisoned_public_label",
            "signature": {"return_type": "int", "parameters": [], "variadic": False},
            "thunk_target": target,
            "ranges": [{"start": loc(entry), "end": loc(end)}],
            "decompilation": {
                "status": "ok",
                "raw_c": "int f(void){return 0;}",
                "analyzed_pcode": [],
                "statements": [],
                "diagnostic": None,
            },
            "instructions": instructions,
            "blocks": [],
            "flow_edges": [],
        }

    document = {
        "schema_version": 1,
        "image_base": loc(g),
        "main": {
            "entry": loc(call),
            "startup": loc(call),
            "setup": loc(call),
            "call": loc(call),
        },
        "functions": [
            function(
                call,
                ret,
                [
                    instruction(call, 5, [op(call, "CALL", [operand(thunk)])]),
                    instruction(ret, 1, [op(ret, "RETURN", [operand(0, "register")])]),
                ],
            ),
            function(
                thunk,
                thunk + 5,
                [
                    instruction(
                        thunk, 6, [op(thunk, "BRANCHIND", [operand(g + 0x2500)])]
                    )
                ],
                loc(1, "EXTERNAL"),
            ),
        ],
        "imports": [
            {
                "address": loc(1, "EXTERNAL"),
                "name": "fwrite",
                "library": "untrusted.so",
                "library_address": None,
            }
        ],
        "strings": [],
        "data_references": [],
        "call_edges": [
            {
                "caller": loc(call),
                "site": loc(call),
                "target": loc(thunk),
                "kind": "UNCONDITIONAL_CALL",
                "indirect": False,
            }
        ],
    }
    return bytes(data), document


def raw_json(document: object) -> bytes:
    return json.dumps(document, sort_keys=True).encode()


def mapping_wire(binary: bytes, raw: bytes, delta: int = 0x100000) -> dict[str, Any]:
    image = read_elf(binary)
    spans = []
    for segment in image.segments:
        start = segment.file_offset
        end = start + segment.file_size
        digest = sha256(binary[start:end]).hexdigest()
        spans.append(
            {
                "ghidra_start": hex(segment.va + delta),
                "length": segment.file_size,
                "source_file_offset": 0,
                "source_size": len(binary),
                "source_sha256": sha256(binary).hexdigest(),
                "source_start": start,
                "source_end": end - 1,
                "memory_sha256": digest,
                "original_sha256": digest,
            }
        )
    return {
        "schema_version": 1,
        "binary_sha256": sha256(binary).hexdigest(),
        "lift_sha256": sha256(raw).hexdigest(),
        "image_base": hex(image.segments[0].va + delta),
        "startup": hex(image.entry + delta),
        "spans": spans,
    }


def evidence(
    binary: bytes, document: dict[str, Any], delta: int = 0x100000
) -> tuple[Any, Any, Any]:
    raw = raw_json(document)
    mapping = parse_mapping(raw_json(mapping_wire(binary, raw, delta)), binary, raw)
    lift = parse_lift(raw, binary)
    return lift, mapping, prove_addresses(binary, lift, mapping)


@given(st.integers(0, 2**31), st.integers(0, 0x3FF))
def test_checked_address_round_trip(delta: int, offset: int) -> None:
    binary, document = fixture(delta=delta)
    _, _, proof = evidence(binary, document, delta)
    assert proof.to_elf(GhidraVA(delta + offset)) == offset
    assert proof.to_ghidra(ElfVA(offset)) == delta + offset


@given(st.integers(0, 2**64 - 1), st.integers(0, 2**64 - 1))
def test_unsigned_range_and_signed_difference(left: int, right: int) -> None:
    if left + right <= 2**64:
        assert checked_end(left, right) == left + right
    else:
        with pytest.raises(MappingError):
            checked_end(left, right)
    if -(2**63) <= left - right < 2**63:
        assert signed_difference(left, right) == left - right
    else:
        with pytest.raises(MappingError):
            signed_difference(left, right)


@pytest.mark.parametrize("base", [0, 0x400000])
def test_actual_bytes_import_identity_and_candidate(base: int) -> None:
    binary, document = fixture(base=base)
    lift, _, proof = evidence(binary, document)
    bindings = bind_imports(binary, lift, proof)
    assert bindings[0].gap is None
    assert bindings[0].identity is not None
    assert bindings[0].identity.symbol == "fwrite"
    assert bindings[0].identity.version == "GLIBC_2.2.5"
    assert bindings[0].identity.needed_library is None
    candidate = make_candidate(lift, proof, bindings)
    assert candidate.status == "static_candidate_requires_live_gates"
    call = next(site for site in candidate.sites if "direct_call" in site.roles)
    assert call.elf == base + 0x100
    assert call.continuation == base + 0x105
    for witness in proof.witnesses:
        assert (
            witness.data
            == binary[witness.file_offset : witness.file_offset + len(witness.data)]
        )
    assert len(proof.witness(GhidraVA(base + 0x100100)).data) == 5


def test_labels_do_not_select_semantics() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    first = make_candidate(lift, proof, bind_imports(binary, lift, proof))
    document["functions"][0]["name"] = "fwrite"
    document["functions"][0]["instructions"][0]["text"] = "not a call"
    other, _, other_proof = evidence(binary, document)
    second = make_candidate(
        other, other_proof, bind_imports(binary, other, other_proof)
    )
    assert first.sites == second.sites
    assert [(i.site, i.identity, i.relocation_slot, i.gap) for i in first.imports] == [
        (i.site, i.identity, i.relocation_slot, i.gap) for i in second.imports
    ]


@pytest.mark.parametrize("field", ["startup", "image_base"])
def test_metadata_anchor_changes_reject(field: str) -> None:
    binary, document = fixture()
    if field == "startup":
        document["main"][field] = loc(0x100101)
    else:
        document[field] = loc(0x100001)
    raw = raw_json(document)
    wire = mapping_wire(binary, raw)
    wire[field] = "0x100101" if field == "startup" else "0x100001"
    lift = parse_lift(raw, binary)
    with pytest.raises(MappingError):
        prove_addresses(binary, lift, parse_mapping(raw_json(wire), binary, raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_start", 1),
        ("source_end", 0),
        ("source_file_offset", 1),
        ("source_size", 1),
        ("source_sha256", "0" * 64),
        ("original_sha256", "0" * 64),
        ("length", 2**64),
        ("ghidra_start", "0x100001"),
    ],
)
def test_poisoned_mapping(field: str, value: object) -> None:
    binary, document = fixture()
    raw = raw_json(document)
    wire = mapping_wire(binary, raw)
    wire["spans"][0][field] = value
    with pytest.raises(MappingError):
        mapping = parse_mapping(raw_json(wire), binary, raw)
        prove_addresses(binary, parse_lift(raw, binary), mapping)


def test_changed_data_is_unavailable_and_changed_code_cannot_witness() -> None:
    binary, document = fixture()
    raw = raw_json(document)
    wire = mapping_wire(binary, raw)
    wire["spans"][1]["memory_sha256"] = "0" * 64
    lift = parse_lift(raw, binary)
    proof = prove_addresses(binary, lift, parse_mapping(raw_json(wire), binary, raw))
    assert (GhidraVA(0x102000), "changed_memory_bytes") in proof.gaps
    assert len(proof.witnesses) == 3
    wire["spans"][0]["memory_sha256"] = "0" * 64
    with pytest.raises(MappingError, match="startup and main"):
        prove_addresses(binary, lift, parse_mapping(raw_json(wire), binary, raw))


def test_instruction_interiors_gaps_and_bss_are_not_witnesses() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    assert lift.target_kind(GhidraVA(0x100101)) == "interior"
    with pytest.raises(MappingError, match="exact admitted"):
        proof.witness(GhidraVA(0x100101))
    for address in (0x100400, 0x101000, 0x102600):
        with pytest.raises(MappingError):
            proof.to_elf(GhidraVA(address))
    with pytest.raises(MappingError):
        proof.to_elf(GhidraVA(0x1003FF), 2)


def test_overlapping_function_ownership_stays_explicit() -> None:
    binary, document = fixture()
    overlap = deepcopy(document["functions"][1])
    overlap["entry"] = loc(0x100141)
    document["functions"].append(overlap)
    lift, _, proof = evidence(binary, document)
    assert lift.owners(GhidraVA(0x100140), 6) == (0x100140, 0x100141)
    with pytest.raises(MappingError):
        proof.witness(GhidraVA(0x100140))


@pytest.mark.parametrize(
    "offset,layout,value",
    [
        (0xC08, "<Q", (1 << 32) | 37),
        (0xA1C, "<B", 0x1A),
    ],
)
def test_unsupported_relocation_and_ifunc_are_gaps(
    offset: int, layout: str, value: int
) -> None:
    original, document = fixture()
    binary = bytearray(original)
    pack_into(layout, binary, offset, value)
    lift, _, proof = evidence(bytes(binary), document)
    binding = bind_imports(bytes(binary), lift, proof)[0]
    assert binding.identity is None
    assert binding.gap in ("unsupported_relocation", "unsupported_symbol_or_ifunc")


@pytest.mark.parametrize(
    "offset,layout,value",
    [
        (0xC08, "<Q", (3 << 32) | 7),
        (0xC10, "<q", 1),
        (0xA18, "<I", 0xFFFF),
        (0xAC2, "<H", 3),
        (0xC90, "<I", 0),
        (0xC8C, "<I", 16),
        (0xC84, "<I", 1),
        (0xA84, "<I", 0xFFFFFFFF),
        (0xC00, "<Q", 0x1000),
        (0xC9C, "<I", 16),
    ],
)
def test_malformed_dynamic_records_reject(offset: int, layout: str, value: int) -> None:
    original, _ = fixture()
    binary = bytearray(original)
    pack_into(layout, binary, offset, value)
    with pytest.raises(MappingError):
        read_dynamic_imports(bytes(binary), read_elf(bytes(binary)))


def test_unknown_or_conflicting_import_stays_unnamed() -> None:
    binary, document = fixture()
    document["imports"][0]["name"] = "memcpy"
    lift, _, proof = evidence(binary, document)
    binding = bind_imports(binary, lift, proof)[0]
    assert binding.identity is None
    assert binding.gap == "conflicting_import_identity"
    document["call_edges"][0]["target"] = None
    document["functions"][0]["instructions"][0]["pcode"] = [
        op(0x100100, "CALLIND", [operand(0x20, "register")])
    ]
    lift, _, proof = evidence(binary, document)
    assert bind_imports(binary, lift, proof)[0].gap == "unknown_import"


def test_complete_publication_is_required(tmp_path: Path) -> None:
    binary, document = fixture()
    raw = raw_json(document)
    lift = tmp_path / "lift.json"
    mapping = tmp_path / "mapping.json"
    lift.write_bytes(raw)
    mapping.write_bytes(raw_json(mapping_wire(binary, raw)))
    with pytest.raises(MappingError, match="incomplete"):
        read_companion(tmp_path, binary)
    publish_companion(lift, mapping, binary)
    saved, parsed = read_companion(tmp_path, binary)
    assert saved == raw and parsed.binary_sha256 == sha256(binary).hexdigest()
    mapping.write_bytes(mapping.read_bytes() + b" ")
    with pytest.raises(MappingError, match="commit"):
        read_companion(tmp_path, binary)
    mapping.unlink()
    with pytest.raises(MappingError, match="incomplete"):
        read_companion(tmp_path, binary)


def test_duplicate_keys_and_noncanonical_addresses_reject() -> None:
    binary, document = fixture()
    raw = raw_json(document)
    with pytest.raises(MappingError):
        parse_lift(b'{"schema_version":1,"schema_version":1}', binary)
    wire = mapping_wire(binary, raw)
    wire["image_base"] = "0x0100000"
    with pytest.raises(MappingError):
        parse_mapping(raw_json(wire), binary, raw)


def test_instruction_bytes_and_binary_identity_are_bound() -> None:
    binary, document = fixture()
    lift, mapping, _ = evidence(binary, document)
    changed = bytearray(binary)
    changed[0x100] ^= 1
    with pytest.raises(MappingError):
        prove_addresses(bytes(changed), lift, mapping)
    with pytest.raises(MappingError):
        prove_addresses(binary, lift, replace(mapping, lift_sha256="0" * 64))


@given(st.integers(-0x200000, 0x200000), st.integers(0, 0x3FF))
def test_signed_rebase_round_trip(delta: int, offset: int) -> None:
    binary, document = fixture(delta=delta, base=0x400000)
    _, _, proof = evidence(binary, document, delta)
    assert proof.to_elf(GhidraVA(0x400000 + delta + offset)) == 0x400000 + offset
    assert proof.to_ghidra(ElfVA(0x400000 + offset)) == 0x400000 + delta + offset


def test_inconsistent_rebase_and_overlapping_segments_reject() -> None:
    binary, document = fixture()
    raw = raw_json(document)
    wire = mapping_wire(binary, raw)
    wire["spans"][1]["ghidra_start"] = "0x102001"
    with pytest.raises(MappingError, match="uniform rebase"):
        prove_addresses(
            binary, parse_lift(raw, binary), parse_mapping(raw_json(wire), binary, raw)
        )
    for offset, value in ((120 + 16, 0x100), (120 + 8, 0x100), (64 + 40, 2**64 - 1)):
        changed = bytearray(binary)
        pack_into("<Q", changed, offset, value)
        with pytest.raises(MappingError):
            read_elf(bytes(changed))


def test_raw_copy_chain_establishes_got_call() -> None:
    binary, document = fixture()
    call = document["functions"][0]["instructions"][0]
    call["pcode"] = [
        op(0x100100, "COPY", [operand(0x102500)], operand(0x99, "unique")),
        op(0x100100, "CALLIND", [operand(0x99, "unique")], index=1),
    ]
    document["call_edges"][0]["target"] = loc(1, "EXTERNAL")
    document["call_edges"][0]["indirect"] = True
    lift, _, proof = evidence(binary, document)
    assert bind_imports(binary, lift, proof)[0].identity is not None
    call["pcode"][0]["opcode"] = "INT_ADD"
    lift, _, proof = evidence(binary, document)
    assert bind_imports(binary, lift, proof)[0].identity is None


def test_call_edge_cannot_override_the_raw_target() -> None:
    binary, document = fixture()
    document["call_edges"][0]["target"] = loc(1, "EXTERNAL")
    lift, _, proof = evidence(binary, document)
    assert bind_imports(binary, lift, proof)[0].gap == "conflicting_call_target"


def test_unrelated_reference_is_not_an_import_witness() -> None:
    binary, document = fixture()
    document["functions"][1]["instructions"][0]["pcode"][0]["inputs"] = [
        operand(0x20, "register")
    ]
    document["data_references"] = [
        {"from": loc(0x100140), "to": loc(0x102500), "kind": "READ", "operand_index": 0}
    ]
    lift, _, proof = evidence(binary, document)
    binding = bind_imports(binary, lift, proof)[0]
    assert binding.identity is None and binding.gap == "missing_or_ambiguous_got_slot"


def test_version_identity_and_binding_inputs_stay_distinct() -> None:
    original, document = fixture()
    binary = bytearray(original)
    pack_into("<H", binary, 0xAC2, 0x8002)
    lift, _, proof = evidence(bytes(binary), document)
    bindings = bind_imports(bytes(binary), lift, proof)
    assert bindings[0].identity is not None and bindings[0].identity.version_hidden
    with pytest.raises(MappingError, match="different evidence"):
        make_candidate(lift, proof, (replace(bindings[0], binary_sha256="0" * 64),))


def test_gnu_hash_bounds_and_malformed_chain() -> None:
    original, document = fixture()
    binary = bytearray(original)
    # Replace DT_HASH with DT_GNU_HASH. There is one hashed symbol.
    pack_into("<qQ", binary, 0x800 + 4 * 16, 0x6FFFFEF5, 0x2280)
    pack_into("<IIIIQII", binary, 0xA80, 1, 1, 1, 0, 0, 1, 1)
    records = read_dynamic_imports(bytes(binary), read_elf(bytes(binary)))
    assert records[0].identity is not None
    pack_into("<I", binary, 0xA80 + 16 + 8, 0xFFFFFFFF)
    with pytest.raises(MappingError):
        read_dynamic_imports(bytes(binary), read_elf(bytes(binary)))


def test_import_count_and_symbol_size_bounds_reject() -> None:
    original, _ = fixture()
    for tag_index, value in ((1, 1024 * 1024 + 1), (3, 16), (6, 25), (11, 65537)):
        binary = bytearray(original)
        pack_into("<Q", binary, 0x800 + tag_index * 16 + 8, value)
        with pytest.raises(MappingError):
            read_dynamic_imports(bytes(binary), read_elf(bytes(binary)))


def test_jump_arrays_are_preserved_separately() -> None:
    from phoenix.lift.evidence import Address, JumpEvidence

    binary, document = fixture()
    jump = JumpEvidence(
        Address("ram", "0x100140"),
        tuple(Address("ram", hex(0x100100 + index)) for index in range(13)),
        tuple(range(12)),
    )
    from phoenix.lift.evidence import (
        PrototypeEvidence,
        Slot,
        StaticEvidence,
        StorageEvidence,
    )

    slot = Slot(None, None, StorageEvidence("void", 0, False, None, ()))
    listing = PrototypeEvidence("listing", "unknown", False, False, False, (), slot)
    decompiler = replace(listing, source="decompiler", custom_storage=None)
    static = StaticEvidence(1, "proposal", listing, decompiler, (), (), (jump,))
    document["functions"][1]["static_evidence"] = asdict(static)
    lift, _, _ = evidence(binary, document)
    saved = lift.functions[GhidraVA(0x100140)].static_evidence
    assert saved is not None
    assert saved.jump_tables[0].targets == jump.targets
    assert saved.jump_tables[0].labels == jump.labels


def fake_install(tmp_path: Path, script: str) -> tuple[Path, Path, Path]:
    installation = tmp_path / "ghidra"
    launcher = installation / "support" / "analyzeHeadless"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\nset -eu\n" + script, encoding="utf-8")
    launcher.chmod(0o755)
    java = tmp_path / "java"
    (java / "bin").mkdir(parents=True)
    (java / "bin" / "java").touch()
    binary = tmp_path / "public.elf"
    return binary, installation, java


def test_launcher_opt_in_publishes_pair_and_default_stays_legacy(
    tmp_path: Path,
) -> None:
    from shlex import quote

    from phoenix.lift import lift_binary

    binary_bytes, document = fixture()
    raw = raw_json(document)
    template = tmp_path / "template.json"
    template.write_bytes(raw)
    mapped = tmp_path / "template-mapping.json"
    mapped.write_bytes(raw_json(mapping_wire(binary_bytes, raw)))
    script = f"""
    while [ "$1" != "-postScript" ]; do shift; done
    cp {quote(str(template))} "$3"
    if [ "$#" -gt 3 ]; then
        test "$4" = "-postScript"
        test "$5" = "ExportMapping.java"
        cp {quote(str(mapped))} "$6"
    fi
    """
    binary, installation, java = fake_install(tmp_path, script)
    binary.write_bytes(binary_bytes)
    old = tmp_path / "legacy" / "lift.json"
    lift_binary(binary, old, installation, java)
    assert old.read_bytes() == raw
    assert not (old.parent / "mapping.json").exists()
    assert not (old.parent / "evidence-commit.json").exists()
    new = tmp_path / "companion" / "lift.json"
    lift_binary(binary, new, installation, java, mapping_companion=True)
    assert read_companion(new.parent, binary_bytes)[0] == raw


def test_launcher_rejects_partial_companion(tmp_path: Path) -> None:
    from shlex import quote

    from phoenix.lift import LiftError, lift_binary

    binary_bytes, document = fixture()
    template = tmp_path / "template.json"
    template.write_bytes(raw_json(document))
    script = f"""
    while [ "$1" != "-postScript" ]; do shift; done
    cp {quote(str(template))} "$3"
    """
    binary, installation, java = fake_install(tmp_path, script)
    binary.write_bytes(binary_bytes)
    output = tmp_path / "partial" / "lift.json"
    with pytest.raises(LiftError, match="mapping companion"):
        lift_binary(binary, output, installation, java, mapping_companion=True)
    assert not output.exists()
    assert not (output.parent / "evidence-commit.json").exists()


def test_unmapped_analyzed_proposal_has_explicit_gap() -> None:
    binary, document = fixture()
    document["functions"][0]["decompilation"]["analyzed_pcode"] = [
        op(0x100102, "COPY", [operand(1, "const")], operand(3, "unique"))
    ]
    lift, _, proof = evidence(binary, document)
    assert (0x100100, "analyzed_site_has_no_instruction") in lift.gaps
    assert (0x100100, "analyzed_site_has_no_instruction") in make_candidate(
        lift, proof, ()
    ).gaps


def test_analyzed_dangling_definition_rejects() -> None:
    binary, document = fixture()
    source = operand(1, "unique")
    source["definition"] = {"address": loc(0x100100), "index": 999}
    document["functions"][0]["decompilation"]["analyzed_pcode"] = [
        op(0x100100, "COPY", [source], operand(3, "unique"))
    ]
    with pytest.raises(MappingError, match="definition reference"):
        parse_lift(raw_json(document), binary)


@pytest.mark.parametrize("address", [0x102000, 0x102600, 0x101000])
def test_nonexecuting_bss_and_gap_instructions_are_unavailable(address: int) -> None:
    binary, document = fixture()
    function = deepcopy(document["functions"][1])
    function["entry"] = loc(address)
    function["ranges"] = [{"start": loc(address), "end": loc(address)}]
    function["thunk_target"] = None
    function["instructions"] = [
        {"address": loc(address), "size": 1, "text": "untrusted", "pcode": []}
    ]
    document["functions"].append(function)
    lift, _, proof = evidence(binary, document)
    with pytest.raises(MappingError):
        proof.witness(GhidraVA(address))
    assert any(site == address for site, _ in proof.gaps)
    assert (address, "unavailable_function_entry") in make_candidate(
        lift, proof, ()
    ).gaps


def test_conflicting_edge_owner_does_not_supply_a_static_target() -> None:
    binary, document = fixture()
    document["call_edges"][0]["caller"] = loc(0x100140)
    lift, _, proof = evidence(binary, document)
    candidate = make_candidate(lift, proof, ())
    call = next(site for site in candidate.sites if "direct_call" in site.roles)
    assert not call.static_targets
    assert (0x100100, "unavailable_or_conflicting_edge_owner") in candidate.gaps


def test_multiple_executable_segments_are_checked_by_full_range() -> None:
    original, document = fixture()
    binary = bytearray(original)
    pack_into("<I", binary, 120 + 4, 5)
    lift, _, proof = evidence(bytes(binary), document)
    assert proof.to_elf(GhidraVA(0x102000), 1) == 0x2000
    assert proof.image.segment(ElfVA(0x2000), 1, executable=True).index == 1
    with pytest.raises(MappingError):
        proof.to_elf(GhidraVA(0x1003FF), 0x1C02)
    assert lift.target_kind(GhidraVA(0x100140)) == "function_entry"
