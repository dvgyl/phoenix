from dataclasses import replace
from hashlib import sha256
from struct import pack_into

import pytest
from test_recovery_u1 import evidence, fixture

from phoenix.analyze import DevelopmentCase
from phoenix.lift.mapping import MappingError
from phoenix.observe.mapping import (
    ExternalTarget,
    InternalTarget,
    ObservationRejected,
    map_observation,
)
from phoenix.observe.plan import build_trace_plan
from phoenix.observe.wire import TraceIdentity, TraceWireError
from phoenix.recover.addresses import ElfVA
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import EntryKind, Exited, Outcome, TreeEntry, TreeSnapshot
from phoenix_eval.wire import encode_invocation

_RUNTIME = "d" * 64
_REGS = "\t".join(f"{value:016x}" for value in (1, 2, 3, 4, 5, 0x8000))
_CASE = DevelopmentCase(
    Invocation(("sample",), b"input"),
    Outcome(
        b"output",
        b"",
        Exited(0),
        TreeSnapshot(entries=(TreeEntry("result", EntryKind.FILE, 0o644, b"bytes"),)),
    ),
)


def _wire(
    identity: TraceIdentity,
    bias: int,
    *,
    code_end: int = 0x400,
    link_base: int = 0,
    change: str = "",
) -> bytes:
    rows = [
        f"E\t0\t{link_base + 0x100:016x}\texternal\t{_REGS}",
        f"A\t1\t{link_base + 0x100:016x}\t{_REGS}",
        f"T\t2\t1\t{bias + link_base + 0x140:016x}",
        f"E\t3\t{link_base + 0x140:016x}\tcall\t{_REGS}",
        f"J\t4\t{link_base + 0x140:016x}",
        f"T\t5\t4\t{0x7FFF000000:016x}",
        f"C\t6\t1\t{link_base + 0x105:016x}\t{_REGS}",
        f"R\t7\t{link_base + 0x105:016x}\t{0x7FFF000080:016x}\t{0x8000:016x}\t{5:016x}",
        f"T\t8\t7\t{0x7FFF000080:016x}",
    ]
    if change == "direct-target":
        rows[2] = f"T\t2\t1\t{bias + link_base + 0x105:016x}"
    elif change == "return-target":
        rows[8] = f"T\t8\t7\t{0x7FFF000081:016x}"
    elif change == "continuation":
        rows[6] = f"C\t6\t1\t{link_base + 0x140:016x}\t{_REGS}"
    elif change == "unplanned":
        rows[0] = f"E\t0\t{link_base + 0x101:016x}\texternal\t{_REGS}"
    elif change == "role":
        rows[4] = f"J\t4\t{link_base + 0x105:016x}"
    elif change == "data-target":
        rows[5] = f"T\t5\t4\t{bias + link_base + 0x2000:016x}"
    elif change == "hole-target":
        rows[5] = f"T\t5\t4\t{bias + link_base + 0x1000:016x}"
    elif change == "gap":
        rows = ["G\t0\tmapping"]
    elif change == "empty":
        rows = []
    header = "\t".join(
        (
            "PXTRACE",
            "2",
            identity.binary_sha256,
            identity.plan_sha256,
            identity.invocation_sha256,
            identity.runtime_sha256,
            f"{bias + link_base:016x}",
            f"{bias + link_base + code_end:016x}",
        )
    )
    body = ("\n".join((header, *rows)) + "\n").encode("ascii")
    status = "gap" if change == "gap" else "complete"
    return body + f"END\t{len(rows)}\t{sha256(body).hexdigest()}\t{status}\n".encode()


def _identity(binary: bytes, plan_sha256: str) -> TraceIdentity:
    return TraceIdentity(
        sha256(binary).hexdigest(),
        plan_sha256,
        sha256(encode_invocation(_CASE.invocation).encode()).hexdigest(),
        _RUNTIME,
    )


def test_mapping_retains_internal_addresses_and_opaque_external_targets() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    raw = _wire(_identity(binary, plan.sha256), 0x400000)
    mapped = map_observation(
        raw, binary, lift, proof, plan, _CASE, _CASE.expected, _RUNTIME
    )
    assert mapped.bias == 0x400000
    assert mapped.targets == (
        (2, InternalTarget(ElfVA(0x140))),
        (5, ExternalTarget(0x7FFF000000)),
        (8, ExternalTarget(0x7FFF000080)),
    )
    assert mapped.trace.sha256 == sha256(raw).hexdigest()
    assert mapped.plan == plan


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("direct-target", "call_target"),
        ("return-target", "return_target"),
        ("continuation", "site_role"),
        ("unplanned", "unplanned_site"),
        ("role", "site_role"),
        ("data-target", "target_mapping"),
        ("gap", "capture_incomplete"),
        ("empty", "capture_empty"),
    ],
)
def test_mapping_rejects_false_roles_targets_and_incomplete_capture(
    change: str,
    reason: str,
) -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    raw = _wire(_identity(binary, plan.sha256), 0x400000, change=change)
    with pytest.raises(ObservationRejected, match=reason):
        map_observation(raw, binary, lift, proof, plan, _CASE, _CASE.expected, _RUNTIME)


@pytest.mark.parametrize("change", ["stdout", "mode", "exit"])
def test_mapping_requires_the_full_accepted_outcome(change: str) -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    observed = _CASE.expected
    if change == "stdout":
        observed = replace(observed, stdout=b"different")
    elif change == "mode":
        tree = replace(
            observed.tree, entries=(replace(observed.tree.entries[0], mode=0o600),)
        )
        observed = replace(observed, tree=tree)
    else:
        observed = replace(observed, termination=Exited(1))
    raw = _wire(_identity(binary, plan.sha256), 0)
    with pytest.raises(ObservationRejected, match="outcome_mismatch"):
        map_observation(raw, binary, lift, proof, plan, _CASE, observed, _RUNTIME)
    assert _CASE.expected.stdout == b"output" and _CASE.expected.termination == Exited(
        0
    )


def test_mapping_rejects_a_changed_plan_and_invocation() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    raw = _wire(_identity(binary, plan.sha256), 0)
    with pytest.raises(MappingError, match="checked source"):
        map_observation(
            raw,
            binary,
            lift,
            proof,
            replace(plan, scope=()),
            _CASE,
            _CASE.expected,
            _RUNTIME,
        )
    case = replace(_CASE, invocation=Invocation(("other",)))
    with pytest.raises(TraceWireError, match="input identities"):
        map_observation(raw, binary, lift, proof, plan, case, case.expected, _RUNTIME)


def test_mapping_keeps_a_gap_between_executable_segments() -> None:
    original, document = fixture()
    binary = bytearray(original)
    pack_into("<I", binary, 124, 5)
    lift, _, proof = evidence(bytes(binary), document)
    plan = build_trace_plan(bytes(binary), lift, proof)
    raw = _wire(
        _identity(bytes(binary), plan.sha256),
        0x400000,
        code_end=0x2600,
        change="hole-target",
    )
    with pytest.raises(ObservationRejected, match="target_mapping"):
        map_observation(
            raw, bytes(binary), lift, proof, plan, _CASE, _CASE.expected, _RUNTIME
        )


def test_mapping_rejects_a_false_runtime_envelope() -> None:
    binary, document = fixture()
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    raw = _wire(_identity(binary, plan.sha256), 0x400000, code_end=0x401)
    with pytest.raises(ObservationRejected, match="runtime_mapping"):
        map_observation(raw, binary, lift, proof, plan, _CASE, _CASE.expected, _RUNTIME)


@pytest.mark.parametrize("bias", [0, 0x100000])
def test_fixed_entry_image_requires_zero_runtime_bias(bias: int) -> None:
    binary, document = fixture(base=0x400000)
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    raw = _wire(_identity(binary, plan.sha256), bias, link_base=0x400000)
    if bias:
        with pytest.raises(ObservationRejected, match="runtime_mapping"):
            map_observation(
                raw, binary, lift, proof, plan, _CASE, _CASE.expected, _RUNTIME
            )
    else:
        mapped = map_observation(
            raw, binary, lift, proof, plan, _CASE, _CASE.expected, _RUNTIME
        )
        assert mapped.bias == 0
        assert mapped.targets[0] == (2, InternalTarget(ElfVA(0x400140)))
