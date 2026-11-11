import json
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from typing import Any

import pytest
from test_recovery_u1 import evidence, fixture, loc, op, operand

from phoenix.lift.mapping import MappingError
from phoenix.observe.plan import Call, Jump, Return, build_trace_plan
from phoenix.recover.addresses import ElfVA


@pytest.mark.parametrize("base", [0, 0x400000])
def test_plan_keeps_shared_roles_and_binds_original_bytes(base: int) -> None:
    binary, document = fixture(base=base)
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    by_address = {site.address: site for site in plan.sites}
    entry = by_address[ElfVA(base + 0x100)]
    resume = by_address[ElfVA(base + 0x105)]
    thunk = by_address[ElfVA(base + 0x140)]
    assert entry.entry and entry.address in plan.scope
    assert entry.witness_hex == binary[0x100:0x105].hex()
    assert isinstance(entry.transfer, Call)
    assert entry.transfer.kind == "direct_call"
    assert entry.transfer.continuation == resume.address
    assert entry.transfer.imported is not None
    assert entry.transfer.imported.identity is not None
    assert entry.transfer.imported.identity.symbol == "fwrite"
    assert resume.continuation_of == (entry.address,)
    assert isinstance(resume.transfer, Return)
    assert thunk.entry and isinstance(thunk.transfer, Jump)
    assert len(plan.sites) == len(by_address)
    wire = plan.to_bytes()
    assert plan.sha256 == sha256(wire).hexdigest()
    record = json.loads(wire)
    assert record["schema"] == 2
    assert record["registers"] == [
        [name, 64] for name in ("rdi", "rsi", "rdx", "rcx", "rax", "rsp")
    ]
    assert record["address_proof_sha256"] == proof.sha256
    with pytest.raises(MappingError, match="identities disagree"):
        build_trace_plan(binary + b" ", lift, proof)


@pytest.mark.parametrize(
    "conflict", ["missing-continuation", "multiple-transfers", "duplicate-call"]
)
def test_unproved_transfer_stays_a_gap(conflict: str) -> None:
    binary, document = fixture()
    function: dict[str, Any] = document["functions"][0]
    if conflict == "missing-continuation":
        function["instructions"].pop()
        gap = "unavailable_continuation"
    else:
        opcode = "CALL" if conflict == "duplicate-call" else "BRANCHIND"
        function["instructions"][0]["pcode"].append(
            op(0x100100, opcode, [operand(0, "register")], index=1)
        )
        gap = "conflicting_transfer_roles"
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    entry = next(site for site in plan.sites if site.address == 0x100)
    assert entry.entry and entry.transfer is None
    assert (0x100100, gap) in plan.gaps
    assert not any(site.continuation_of for site in plan.sites)
    assert plan.to_bytes() == build_trace_plan(binary, lift, proof).to_bytes()


def test_plan_refuses_a_lift_with_another_identity() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    document["functions"][0]["instructions"][0]["text"] = "changed"
    other, _, _ = evidence(binary, document)
    assert lift.lift_sha256 != other.lift_sha256
    with pytest.raises(MappingError, match="identities disagree"):
        build_trace_plan(binary, other, proof)


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        ("call-target", "conflicting_call_bytes"),
        ("import-slot", "conflicting_import_slot_bytes"),
        ("symbol", "conflicting_import_identity"),
    ],
)
def test_unconfirmed_import_stays_distinct_from_the_call(
    fault: str, reason: str
) -> None:
    original, document = fixture()
    binary = bytearray(original)
    if fault == "call-target":
        binary[0x101] = 0
    elif fault == "import-slot":
        binary[0x142] ^= 8
    else:
        document["imports"][0]["name"] = "fread"
    lift, _, proof = evidence(bytes(binary), document)
    plan = build_trace_plan(bytes(binary), lift, proof)
    call = next(site for site in plan.sites if site.address == 0x100)
    assert isinstance(call.transfer, Call)
    assert call.transfer.imported is None
    assert call.transfer.import_gaps == (reason,)


def test_plan_does_not_admit_a_continuation_under_another_owner() -> None:
    binary, document = fixture()
    function = document["functions"][0]
    resume = function["instructions"].pop()
    function["ranges"][0]["end"] = loc(0x100104)
    second = deepcopy(function)
    second["entry"] = resume["address"]
    second["ranges"] = [{"start": resume["address"], "end": resume["address"]}]
    second["instructions"] = [resume]
    document["functions"].append(second)
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    assert (0x100100, "unavailable_continuation") in plan.gaps
    call = next(site for site in plan.sites if site.address == 0x100)
    after = next(site for site in plan.sites if site.address == 0x105)
    assert call.transfer is None and not after.continuation_of
    assert after.entry and isinstance(after.transfer, Return)


def test_plan_refuses_a_replaced_instruction_witness() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    witnesses = tuple(
        replace(witness, data=b"\x90") if witness.elf == 0x105 else witness
        for witness in proof.witnesses
    )
    with pytest.raises(MappingError, match="address proof differs"):
        build_trace_plan(binary, lift, replace(proof, witnesses=witnesses))
