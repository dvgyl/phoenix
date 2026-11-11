import json
from hashlib import sha256
from typing import Any

import pytest
from test_recovery_u1 import evidence, fixture, op, operand

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
    with pytest.raises(MappingError, match="does not bind the original binary"):
        build_trace_plan(binary + b" ", lift, proof)


@pytest.mark.parametrize("conflict", ["missing-continuation", "multiple-transfers"])
def test_unproved_transfer_stays_a_gap(conflict: str) -> None:
    binary, document = fixture()
    function: dict[str, Any] = document["functions"][0]
    if conflict == "missing-continuation":
        function["instructions"].pop()
        gap = "unavailable_continuation"
    else:
        function["instructions"][0]["pcode"].append(
            op(0x100100, "BRANCHIND", [operand(0, "register")], index=1)
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
