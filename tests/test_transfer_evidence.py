import json
from copy import deepcopy
from dataclasses import replace
from itertools import product
from struct import pack_into
from typing import Any

import pytest
from test_recovery_u1 import evidence, fixture, loc, op, operand

from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.observe.plan import Return, build_trace_plan
from phoenix.recover import transfers
from phoenix.recover.addresses import ElfVA, prove_addresses
from phoenix.recover.imports import bind_imports
from phoenix.recover.plan import make_candidate
from phoenix.recover.transfers import decode_transfer

_CALL = 0x100100
_THUNK = 0x100140
_SLOT = 0x102500
_EXT = loc(1, "EXTERNAL")
_NOPS = (
    "90",
    "6690",
    "0f1f00",
    "0f1f4000",
    "0f1f440000",
    "660f1f440000",
    "0f1f8000000000",
    "0f1f840000000000",
    "660f1f840000000000",
)


def relative(prefix: bytes, start: int, target: int, width: int = 4) -> bytes:
    return prefix + (target - start - len(prefix) - width).to_bytes(
        width, "little", signed=True
    )


def change_call(
    raw: bytes, opcode: str, target: dict[str, Any], *, external: bool = False
) -> tuple[bytearray, dict[str, Any]]:
    original, document = fixture()
    binary = bytearray(original)
    binary[0x100 : 0x101 + len(raw)] = raw + b"\xc3"
    function = document["functions"][0]
    call, after = function["instructions"]
    after_address = _CALL + len(raw)
    call.update(size=len(raw), pcode=[op(_CALL, opcode, [target])])
    after.update(
        address=loc(after_address),
        pcode=[op(after_address, "RETURN", [operand(0, "register")])],
    )
    function["ranges"][0]["end"] = loc(after_address)
    if external:
        document["call_edges"][0].update(target=_EXT, indirect=True)
        pack_into("<Q", binary, 0xC08, (1 << 32) | 6)
    return binary, document


def write_thunk(
    binary: bytearray,
    function: dict[str, Any],
    start: int,
    prefixes: tuple[bytes, ...],
    terminal: bytes,
    operation: dict[str, Any],
) -> None:
    address = start
    instructions = []
    for raw in (*prefixes, terminal):
        offset = address - 0x100000
        binary[offset : offset + len(raw)] = raw
        instructions.append(
            {"address": loc(address), "size": len(raw), "text": "", "pcode": []}
        )
        address += len(raw)
    instructions[-1]["pcode"] = [operation]
    function.update(
        entry=loc(start),
        ranges=[{"start": loc(start), "end": loc(address - 1)}],
        instructions=instructions,
    )


def thunk_case(
    prefixes: tuple[str, ...], *, prefix: bytes = b"", slot: int = _SLOT
) -> tuple[bytearray, dict[str, Any]]:
    original, document = fixture()
    binary = bytearray(original)
    raw = tuple(bytes.fromhex(item) for item in prefixes)
    terminal = _THUNK + sum(map(len, raw))
    write_thunk(
        binary,
        document["functions"][1],
        _THUNK,
        raw,
        relative(prefix + b"\xff\x25", terminal, slot),
        op(terminal, "BRANCHIND", [operand(_SLOT)]),
    )
    return binary, document


def check_call(
    binary: bytes | bytearray,
    document: dict[str, Any],
    *,
    physical_gap: str | None = None,
    import_gap: str | None = None,
) -> None:
    original = bytes(binary)
    lift, _, proof = evidence(original, document)
    binding = next(
        item for item in bind_imports(original, lift, proof) if item.site == _CALL
    )
    plan = build_trace_plan(original, lift, proof)
    serialized = json.loads(plan.to_bytes())
    call = next(site for site in serialized["sites"] if site["address"] == 0x100)
    assert call["entry"]
    if physical_gap is not None:
        if physical_gap == "unavailable_continuation":
            assert binding.identity is not None and binding.gap is None
        else:
            assert binding.identity is None and binding.gap == physical_gap
        assert call["transfer"] is None
        assert [_CALL, physical_gap] in serialized["gaps"]
        assert all(0x100 not in site["continuation_of"] for site in serialized["sites"])
        return
    after = call["address"] + len(bytes.fromhex(call["witness_hex"]))
    assert call["transfer"]["continuation"] == after
    assert next(site for site in serialized["sites"] if site["address"] == after)[
        "continuation_of"
    ] == [0x100]
    if import_gap is not None:
        assert binding.identity is None and binding.gap == import_gap
        assert call["transfer"]["imported"] is None
        assert call["transfer"]["import_gaps"] == [import_gap]
        assert [_CALL, import_gap] not in serialized["gaps"]
    else:
        assert binding.identity is not None and binding.identity.symbol == "fwrite"
        assert binding.relocation_slot == 0x2500
        assert call["transfer"]["imported"]["identity"]["symbol"] == "fwrite"
        assert call["transfer"]["import_gaps"] == []


@pytest.mark.parametrize(
    "extra", ["CALL", "RETURN", "BRANCH", "BRANCHIND", "CALLOTHER"]
)
def test_raw_role_conflicts_apply_to_both_consumers(extra: str) -> None:
    binary, document = fixture()
    document["functions"][0]["instructions"][0]["pcode"].append(
        op(_CALL, extra, [operand(_THUNK)], index=1)
    )
    check_call(binary, document, physical_gap="conflicting_transfer_roles")


@pytest.mark.parametrize(
    ("raw", "opcode", "gap"),
    [
        ("e93b000000", "CALL", "conflicting_transfer_bytes"),
        ("e83b000000", "COPY", "conflicting_transfer_bytes"),
        ("c3", "COPY", "conflicting_transfer_bytes"),
        ("ffd0", "COPY", "conflicting_transfer_bytes"),
        ("ff25fa230000", "CALLIND", "conflicting_transfer_bytes"),
        ("ff15fa230000", "BRANCHIND", "conflicting_transfer_bytes"),
        ("ff1425", "CALLIND", "unsupported_transfer_encoding"),
        ("e83b00", "CALL", "unsupported_transfer_encoding"),
        ("ffd090", "CALLIND", "unsupported_transfer_encoding"),
        ("48", "CALLIND", "unsupported_transfer_encoding"),
        ("67ff15f9230000", "CALLIND", "unsupported_transfer_encoding"),
        ("64ff15f9230000", "CALLIND", "unsupported_transfer_encoding"),
        ("66ffd0", "CALLIND", "unsupported_transfer_encoding"),
        ("413effd0", "CALLIND", "unsupported_transfer_encoding"),
        ("3e3effd0", "CALLIND", "unsupported_transfer_encoding"),
        ("f0ffd0", "CALLIND", "unsupported_transfer_encoding"),
    ],
)
def test_lift_roles_need_an_exact_compatible_encoding(
    raw: str, opcode: str, gap: str
) -> None:
    binary, document = change_call(bytes.fromhex(raw), opcode, operand(_THUNK))
    check_call(binary, document, physical_gap=gap)


@pytest.mark.parametrize("raw", ["90", "f3c3", "c21000", "cb", "cf", "c390"])
def test_return_needs_exact_c3_and_keeps_incoming_continuation(raw: str) -> None:
    original, document = fixture()
    binary = bytearray(original)
    data = bytes.fromhex(raw)
    binary[0x105 : 0x105 + len(data)] = data
    main = document["functions"][0]
    main["instructions"][1]["size"] = len(data)
    main["ranges"][0]["end"] = loc(_CALL + 4 + len(data))
    lift, _, proof = evidence(bytes(binary), document)
    plan = build_trace_plan(bytes(binary), lift, proof)
    after = next(site for site in plan.sites if site.address == 0x105)
    assert after.continuation_of == (0x100,) and after.transfer is None
    assert (_CALL + 5, "unsupported_transfer_encoding") in plan.gaps


@pytest.mark.parametrize(
    "raw", ["ffd0", "41ffd0", "ff1424", "ff544824", "ff944878563412", "ff142578563412"]
)
def test_general_indirect_calls_do_not_prove_import_slots(raw: str) -> None:
    binary, document = change_call(
        bytes.fromhex(raw), "CALLIND", operand(_SLOT), external=True
    )
    check_call(binary, document, import_gap="unsupported_import_operand")


def test_physical_call_without_call_edge_keeps_an_import_gap() -> None:
    original, document = fixture()
    document["call_edges"].clear()
    check_call(original, document, import_gap="unknown_import")


@pytest.mark.parametrize("prefix", ["", "f2", "3e"])
@pytest.mark.parametrize("wrong_slot", [False, True])
def test_rip_relative_call_and_thunk_prefix_forms(
    prefix: str, wrong_slot: bool
) -> None:
    start = bytes.fromhex(prefix)
    slot = _SLOT + 8 * wrong_slot
    gap = "conflicting_import_slot_bytes" if wrong_slot else None
    raw = relative(start + b"\xff\x15", _CALL, slot)
    binary, document = change_call(raw, "CALLIND", operand(_SLOT), external=True)
    check_call(binary, document, import_gap=gap)
    binary, document = thunk_case((), prefix=start, slot=slot)
    check_call(binary, document, import_gap=gap)


@pytest.mark.parametrize("prefix", (*_NOPS, "f30f1efa"))
def test_exact_neutral_prefixes_prove_a_path(prefix: str) -> None:
    binary, document = thunk_case((prefix,))
    if prefix != "f30f1efa":
        register = operand(0, "register")
        document["functions"][1]["instructions"][0]["pcode"] = [
            op(_THUNK, "COPY", [register], register)
        ]
    check_call(binary, document)


@pytest.mark.parametrize(
    "prefixes",
    [
        ("eb1e",),
        ("eb00",),
        ("f30f1efb",),
        ("90", "f30f1efa"),
        ("f30f1efa", "f30f1efa"),
        ("f390",),
        ("89c0",),
        ("488d00",),
        ("8900",),
        ("e800000000",),
        ("cc",),
        ("0f0b",),
        ("0f1f01",),
        ("90",) * 9,
        ("660f1f840000000000",) * 4,
        ("660f1f840000000000",) * 3 + ("660f1f440000",),
        ("f30f1efa",) + ("90",) * 8,
    ],
)
def test_unproved_thunk_prefix_cannot_be_skipped(prefixes: tuple[str, ...]) -> None:
    binary, document = thunk_case(prefixes)
    check_call(binary, document, import_gap="unsupported_thunk_prefix")


@pytest.mark.parametrize("opcode", ["STORE", "CALLOTHER", "BRANCH", "COPY"])
def test_neutral_bytes_cannot_override_conflicting_prefix_pcode(opcode: str) -> None:
    binary, document = thunk_case(("90",))
    document["functions"][1]["instructions"][0]["pcode"] = [
        op(_THUNK, opcode, [operand(4, "register")], operand(0, "register"))
    ]
    check_call(binary, document, import_gap="unsupported_thunk_prefix")


@pytest.mark.parametrize("prefixes", [("90",) * 8, ("0f1f840000000000",) * 4])
def test_thunk_neutral_limits_are_inclusive(prefixes: tuple[str, ...]) -> None:
    binary, document = thunk_case(prefixes)
    check_call(binary, document)


def test_terminal_jump_must_be_last() -> None:
    binary, document = thunk_case(())
    after = _THUNK + 6
    thunk = document["functions"][1]
    thunk["ranges"][0]["end"] = loc(after)
    thunk["instructions"].append(
        {"address": loc(after), "size": 1, "text": "", "pcode": []}
    )
    binary[0x146] = 0x90
    check_call(binary, document, import_gap="unsupported_thunk_prefix")


@pytest.mark.parametrize(("count", "cycle"), [(32, False), (33, False), (2, True)])
def test_thunk_hop_limit_and_cycle(count: int, cycle: bool) -> None:
    original, document = fixture()
    binary = bytearray(original)
    template = document["functions"].pop()
    for index in range(count):
        thunk = deepcopy(template)
        address = _THUNK + 8 * index
        if index < count - 1 or cycle:
            target = _THUNK if index == count - 1 else address + 8
            thunk["thunk_target"] = loc(target)
            raw = relative(b"\xeb", address, target, 1)
            operation = op(address, "BRANCH", [operand(target)])
        else:
            raw = relative(b"\xff\x25", address, _SLOT)
            operation = op(address, "BRANCHIND", [operand(_SLOT)])
        write_thunk(binary, thunk, address, (), raw, operation)
        document["functions"].append(thunk)
    check_call(
        binary,
        document,
        import_gap="thunk_cycle_or_bound" if count > 32 or cycle else None,
    )


@pytest.mark.parametrize("initial", [False, True])
def test_a_direct_transfer_cannot_reach_a_synthetic_external_entry(
    initial: bool,
) -> None:
    original, document = fixture()
    binary = bytearray(original)
    address = 0x105000
    thunk = document["functions"][1]
    synthetic = deepcopy(thunk)
    synthetic.update(
        entry=loc(address),
        ranges=[{"start": loc(address), "end": loc(address)}],
        instructions=[],
    )
    document["functions"].append(synthetic)
    if initial:
        binary[0x100:0x105] = relative(b"\xe8", _CALL, address)
        document["call_edges"][0]["target"] = loc(address)
        document["functions"][0]["instructions"][0]["pcode"][0]["inputs"] = [
            operand(address)
        ]
    else:
        thunk["thunk_target"] = loc(address)
        write_thunk(
            binary,
            thunk,
            _THUNK,
            (),
            relative(b"\xe9", _THUNK, address),
            op(_THUNK, "BRANCH", [operand(address)]),
        )
    check_call(binary, document, import_gap="unavailable_thunk_target")


def test_ambiguous_continuation_is_unavailable() -> None:
    binary, document = fixture()
    second = deepcopy(document["functions"][0])
    second.update(
        entry=loc(_CALL + 5),
        ranges=[{"start": loc(_CALL + 5), "end": loc(_CALL + 5)}],
        instructions=[],
    )
    document["functions"].append(second)
    check_call(binary, document, physical_gap="unavailable_continuation")


def test_wrong_return_length_cannot_shift_a_call_continuation() -> None:
    binary, document = fixture()
    main = document["functions"][0]
    main["instructions"][0]["size"] = 6
    with pytest.raises(MappingError, match="overlap"):
        evidence(binary, document)


def test_compatible_tail_jump_keeps_jump_and_cannot_supply_a_call_import() -> None:
    raw = relative(b"\xff\x25", _CALL, _SLOT)
    binary, document = change_call(raw, "BRANCHIND", operand(_SLOT), external=True)
    lift, _, proof = evidence(bytes(binary), document)
    (binding,) = bind_imports(bytes(binary), lift, proof)
    assert binding.identity is None and binding.gap == "conflicting_call_target"
    plan = build_trace_plan(bytes(binary), lift, proof)
    site = next(site for site in plan.sites if site.address == 0x100)
    after = next(site for site in plan.sites if site.address == 0x106)
    assert site.transfer is not None and site.transfer.kind == "indirect_jump"
    assert isinstance(after.transfer, Return) and not after.continuation_of


def test_public_operations_reject_tampered_address_proof() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    witness = proof.witnesses[0]
    segment = proof.image.segments[0]
    span = proof.spans[0]
    variants = [
        *(
            replace(proof, witnesses=(replace(witness, **fields), *proof.witnesses[1:]))
            for fields in (
                {"data": b"\xe8\x00\x00\x00\x00"},
                {"file_offset": witness.file_offset + 1},
                {"owner": _THUNK},
                {"elf": witness.elf + 1},
            )
        ),
        replace(
            proof,
            image=replace(
                proof.image,
                segments=(
                    replace(segment, flags=segment.flags ^ 1),
                    *proof.image.segments[1:],
                ),
            ),
        ),
        replace(proof, image=replace(proof.image, dynamic=proof.image.dynamic[:-1])),
        replace(proof, ghidra_delta=proof.ghidra_delta + 1),
        replace(
            proof, spans=(replace(span, original_sha256="0" * 64), *proof.spans[1:])
        ),
        replace(proof, spans=proof.spans[:-1]),
        replace(proof, sha256="0" * 64),
        replace(proof, binary_sha256="0" * 64),
        replace(proof, lift_sha256="0" * 64),
        replace(proof, witnesses=tuple(reversed(proof.witnesses))),
        replace(proof, witnesses=proof.witnesses[1:]),
        replace(proof, witnesses=(*proof.witnesses, witness)),
        replace(proof, gaps=((GhidraVA(_CALL), "extra_gap"),)),
    ]
    for field in ("witness_starts", "span_starts"):
        altered = replace(proof)
        object.__setattr__(altered, field, ())
        variants.append(altered)
    for operation in (bind_imports, build_trace_plan, make_candidate):
        assert operation(binary, lift, replace(proof)) == operation(binary, lift, proof)
        for altered in variants:
            with pytest.raises(MappingError):
                operation(binary, lift, altered)


@pytest.mark.parametrize("operation", [bind_imports, build_trace_plan, make_candidate])
def test_each_operation_rederives_proof_once(
    monkeypatch: pytest.MonkeyPatch, operation: Any
) -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    original = prove_addresses
    calls: list[int] = []

    def count(*args: Any) -> Any:
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(transfers, "prove_addresses", count)
    operation(binary, lift, proof)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "prefix", [b""] + [bytes([x]) for x in (64, 65, 66, 67, 72, 73, 74, 75)]
)
@pytest.mark.parametrize("group", [2, 4])
def test_all_indirect_modrm_and_sib_bytes_are_exact(prefix: bytes, group: int) -> None:
    address = ElfVA(0x100000000)
    kind = "indirect_call" if group == 2 else "indirect_jump"
    widths = (
        (0, 0, 0, 0, -1, 4, 0, 0),
        (1, 1, 1, 1, -1, 1, 1, 1),
        (4, 4, 4, 4, -1, 4, 4, 4),
        (0, 0, 0, 0, 0, 0, 0, 0),
    )
    for mod, rm in product(range(4), range(8)):
        modrm = (mod << 6) | (group << 3) | rm
        width = widths[mod][rm]
        base = prefix + bytes([0xFF, modrm])
        variants = (
            ((base, width, None),)
            if width >= 0
            else (
                (
                    base + bytes([sib]),
                    (4 if sib % 8 == 5 else 0) if mod == 0 else (1, 4)[mod - 1],
                    sib,
                )
                for sib in range(256)
            )
        )
        for head, size, sib in variants:
            displacements = (
                {0, -(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1} if size else {0}
            )
            for displacement in displacements:
                raw = head + displacement.to_bytes(size, "little", signed=True)
                result = decode_transfer(raw, address)
                assert result is not None and result.operand is not None, raw.hex()
                assert (result.kind, result.length, result.prefix) == (
                    kind,
                    len(raw),
                    prefix[0] if prefix else None,
                )
                assert (
                    result.operand.mod,
                    result.operand.rm,
                    result.operand.sib,
                    result.operand.displacement,
                ) == (mod, rm, sib, displacement)
                expected_slot = (
                    address + len(raw) + displacement if modrm in (0x15, 0x25) else None
                )
                rex = prefix[0] if prefix else 0
                assert (
                    result.operand.rex_w,
                    result.operand.rex_x,
                    result.operand.rex_b,
                ) == (bool(rex & 8), bool(rex & 2), bool(rex & 1))
                assert result.operand.rip_slot == expected_slot
                assert result.import_slot == (None if prefix else expected_slot)
                assert all(
                    decode_transfer(raw[:n], address) is None for n in range(len(raw))
                )
                assert decode_transfer(raw + b"\x90", address) is None


@pytest.mark.parametrize(
    ("hex_bytes", "address", "destination", "kind"),
    [
        ("e800000080", 0x80000000, 5, "direct_call"),
        ("e8ffffff7f", 0, 0x80000004, "direct_call"),
        ("eb80", 0x100, 0x82, "direct_jump"),
        ("eb7f", 0x100, 0x181, "direct_jump"),
        ("e9fbffffff", 0x100, 0x100, "direct_jump"),
        ("e8faffffff", 0, None, "direct_call"),
        ("e901000000", (1 << 64) - 6, None, "direct_jump"),
        ("eb00", (1 << 64) - 2, None, "direct_jump"),
        ("ff15f9ffffff", 0, None, "indirect_call"),
        ("ff2501000000", (1 << 64) - 7, None, "indirect_jump"),
    ],
)
def test_signed_relative_address_bounds(
    hex_bytes: str, address: int, destination: int | None, kind: str
) -> None:
    raw = bytes.fromhex(hex_bytes)
    transfer = decode_transfer(raw, ElfVA(address))
    if destination is None:
        assert transfer is None
    else:
        assert transfer is not None
        assert (transfer.kind, transfer.length, transfer.destination) == (
            kind,
            len(raw),
            destination,
        )
        assert all(
            decode_transfer(raw[:n], ElfVA(address)) is None for n in range(len(raw))
        )
        assert decode_transfer(raw + b"\x90", ElfVA(address)) is None


def test_excluded_group_selectors_and_prefixes_remain_gaps() -> None:
    for selector in range(8):
        if selector in (2, 4):
            continue
        for mod, rm in product(range(4), range(8)):
            raw = bytes([0xFF, mod * 64 + selector * 8 + rm])
            for count in range(7):
                assert decode_transfer(raw + bytes(count), ElfVA(0x1000)) is None
    accepted = {0x40, 0x41, 0x42, 0x43, 0x48, 0x49, 0x4A, 0x4B}
    for prefix in range(256):
        if prefix not in accepted:
            assert decode_transfer(bytes([prefix, 0xFF, 0xD0]), ElfVA(0x1000)) is None
    for hex_bytes in (
        "f2ffd0",
        "3effd0",
        "f3ff15f9230000",
        "2eff15f9230000",
        "4841ffd0",
        "40f2ffd0",
        "f240ffd0",
        "c3" + "90" * 15,
    ):
        assert decode_transfer(bytes.fromhex(hex_bytes), ElfVA(0x1000)) is None


@pytest.mark.parametrize("opcode", ["e8", "e9", "eb"])
@pytest.mark.parametrize("displacement", [-128, -1, 0, 127])
def test_direct_signed_forms_are_exact(opcode: str, displacement: int) -> None:
    width = 1 if opcode == "eb" else 4
    raw = bytes.fromhex(opcode) + displacement.to_bytes(width, "little", signed=True)
    result = decode_transfer(raw, ElfVA(0x1000))
    assert result is not None
    assert result.destination == 0x1000 + len(raw) + displacement
    assert result.kind == ("direct_call" if opcode == "e8" else "direct_jump")
    assert all(decode_transfer(raw[:n], ElfVA(0x1000)) is None for n in range(len(raw)))
    assert decode_transfer(raw + b"\x90", ElfVA(0x1000)) is None


def test_missing_relocation_keeps_the_physical_call() -> None:
    original, document = fixture()
    binary = bytearray(original)
    pack_into("<Q", binary, 0xC00, 0x2508)
    check_call(binary, document, import_gap="missing_or_ambiguous_got_slot")


def test_wrong_thunk_hop_keeps_the_physical_call() -> None:
    original, document = fixture()
    binary = bytearray(original)
    thunk = document["functions"][1]
    thunk["thunk_target"] = loc(0x100120)
    write_thunk(
        binary,
        thunk,
        _THUNK,
        (),
        relative(b"\xe9", _THUNK, 0x100128),
        op(_THUNK, "BRANCH", [operand(0x100120)]),
    )
    check_call(binary, document, import_gap="conflicting_thunk_bytes")


def test_rex_flags_and_sib_fields_are_retained() -> None:
    raw = bytes.fromhex("4bff544824")
    result = decode_transfer(raw, ElfVA(0x100))
    assert result is not None and result.prefix == 0x4B
    assert result.operand is not None
    assert (result.operand.mod, result.operand.rm, result.operand.sib) == (1, 4, 0x48)
    assert result.operand.displacement == 0x24 and result.import_slot is None


def test_direct_jump_call_edge_keeps_a_static_target_conflict() -> None:
    binary, document = change_call(
        relative(b"\xe9", _CALL, _THUNK), "BRANCH", operand(_THUNK)
    )
    lift, _, proof = evidence(bytes(binary), document)
    candidate = make_candidate(bytes(binary), lift, proof)
    assert candidate.imports[0].gap == "conflicting_call_target"
    assert (_CALL, "conflicting_call_target") in candidate.gaps
    call = next(site for site in candidate.sites if site.ghidra == _CALL)
    assert call.roles == ("entry",) and call.continuation is None
    assert not call.static_targets


def test_unsupported_raw_branch_remains_an_explicit_gap() -> None:
    binary, document = change_call(b"\x75\x00", "CBRANCH", operand(_CALL + 2))
    lift, _, proof = evidence(bytes(binary), document)
    plan = build_trace_plan(bytes(binary), lift, proof)
    assert (_CALL, "unsupported_transfer_encoding") in plan.gaps
    assert not any(site.continuation_of for site in plan.sites)


def test_recovery_retains_a_proved_import_without_an_observation_continuation() -> None:
    binary, document = fixture()
    document["functions"][0]["instructions"].pop()
    lift, _, proof = evidence(binary, document)
    (binding,) = bind_imports(binary, lift, proof)
    candidate = make_candidate(binary, lift, proof)
    assert candidate.imports == (binding,)
    assert binding.identity is not None and binding.identity.symbol == "fwrite"
    call = next(site for site in candidate.sites if site.ghidra == _CALL)
    assert call.roles == ("direct_call", "entry") and call.continuation is None
    assert (_CALL, "unavailable_continuation") in candidate.gaps
    plan = build_trace_plan(binary, lift, proof)
    entry = next(site for site in plan.sites if site.address == 0x100)
    assert entry.transfer is None
    assert not any(site.continuation_of for site in plan.sites)


def test_transfer_bytes_cannot_cross_the_address_limit() -> None:
    assert decode_transfer(bytes.fromhex("ffd0"), ElfVA((1 << 64) - 1)) is None
    assert decode_transfer(bytes.fromhex("c3"), ElfVA(-1)) is None


def test_neutral_self_copy_requires_the_same_width() -> None:
    binary, document = thunk_case(("90",))
    register = operand(0, "register")
    document["functions"][1]["instructions"][0]["pcode"] = [
        op(_THUNK, "COPY", [register | {"size": 4}], register)
    ]
    check_call(binary, document, import_gap="unsupported_thunk_prefix")


def test_entry_endbr64_counts_toward_the_neutral_instruction_bound() -> None:
    binary, document = thunk_case(("f30f1efa",) + ("90",) * 7)
    check_call(binary, document)


@pytest.mark.parametrize("terminal", [False, True])
def test_each_thunk_instruction_requires_unique_ownership(terminal: bool) -> None:
    binary, document = thunk_case(("90",))
    start = _THUNK + int(terminal)
    end = start + (5 if terminal else 0)
    document["functions"][0]["ranges"].append({"start": loc(start), "end": loc(end)})
    check_call(binary, document, import_gap="unavailable_instruction")


def test_missing_thunk_entry_witness_cannot_use_a_later_jump() -> None:
    binary, document = thunk_case(("90",))
    document["functions"][1]["instructions"].pop(0)
    check_call(binary, document, import_gap="unavailable_instruction")


def test_call_bytes_with_no_call_edge_and_no_raw_call_keep_a_conflict() -> None:
    binary, document = fixture()
    document["call_edges"].clear()
    document["functions"][0]["instructions"][0]["pcode"] = []
    check_call(binary, document, physical_gap="conflicting_transfer_bytes")


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_alternative_edges_cannot_select_an_import(reverse: bool) -> None:
    binary, document = fixture()
    alternate = deepcopy(document["call_edges"][0])
    alternate["target"] = _EXT
    document["call_edges"].append(alternate)
    if reverse:
        document["call_edges"].reverse()
    lift, _, proof = evidence(binary, document)
    bindings = bind_imports(binary, lift, proof)
    assert len(bindings) == 2 and all(binding.identity is None for binding in bindings)
    plan = build_trace_plan(binary, lift, proof)
    call = next(
        site
        for site in json.loads(plan.to_bytes())["sites"]
        if site["address"] == 0x100
    )
    assert call["transfer"]["imported"] is None
    assert call["transfer"]["import_gaps"] == [
        "conflicting_call_target",
        "conflicting_import_paths",
    ]


@pytest.mark.parametrize("prefix", [b"\xf2", b"\x3e"])
@pytest.mark.parametrize("modrm", [0x15, 0x25])
@pytest.mark.parametrize("displacement", [-(1 << 31), 0, (1 << 31) - 1])
def test_explicit_legacy_rip_forms_are_exact(
    prefix: bytes, modrm: int, displacement: int
) -> None:
    address = ElfVA(1 << 32)
    raw = (
        prefix + bytes([0xFF, modrm]) + displacement.to_bytes(4, "little", signed=True)
    )
    result = decode_transfer(raw, address)
    assert result is not None and result.operand is not None
    assert result.length == 7 and result.prefix == prefix[0]
    assert result.kind == ("indirect_call" if modrm == 0x15 else "indirect_jump")
    assert result.import_slot == address + 7 + displacement
    assert not any((result.operand.rex_w, result.operand.rex_x, result.operand.rex_b))
    assert all(decode_transfer(raw[:n], address) is None for n in range(7))
    assert decode_transfer(raw + b"\x90", address) is None
