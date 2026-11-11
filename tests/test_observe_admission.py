"""Exact-byte controls use synthetic evidence. They do not prove a collector."""

import json
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_observe_mapping import _CASE, _wire
from test_recovery_u1 import evidence, fixture, mapping_wire, raw_json

from phoenix.analyze import DevelopmentCase
from phoenix.lift.mapping import MappingError
from phoenix.observe.admission import CaptureArtifacts, admit_observation, parse_receipt
from phoenix.observe.capture import CaptureReceipt, ReturnExit, RootAnchor
from phoenix.observe.frames import AdmissionResult, Admitted, Rejected
from phoenix.observe.plan import build_trace_plan
from phoenix.observe.runtime import (
    RuntimeManifest,
    admission_implementation_sha256,
    canonical,
    guard_profile_sha256,
    parse_runtime_manifest,
)
from phoenix.observe.scope import (
    LiftMain,
    RequestedScope,
    ScopeSelection,
    select_scope,
)
from phoenix.observe.wire import TraceIdentity
from phoenix_eval.outcome import Exited, Outcome
from phoenix_eval.wire import encode_invocation, encode_result

_D = "d" * 64


@dataclass(frozen=True)
class Sample:
    binary: bytes
    lift: bytes
    mapping: bytes
    plan: bytes
    scope: bytes
    request: RequestedScope
    artifacts: CaptureArtifacts
    runtime_sha256: str

    def admit(
        self,
        artifacts: CaptureArtifacts | None = None,
        case: DevelopmentCase = _CASE,
    ) -> AdmissionResult:
        return admit_observation(
            self.binary,
            self.lift,
            self.mapping,
            self.plan,
            self.scope,
            self.request,
            artifacts or self.artifacts,
            case,
            self.runtime_sha256,
        )


def sample() -> Sample:
    binary, document = fixture()
    lift_raw = raw_json(document)
    mapping_raw = raw_json(mapping_wire(binary, lift_raw))
    lift, _, proof = evidence(binary, document)
    plan = build_trace_plan(binary, lift, proof)
    root = proof.to_elf(lift.main)
    request = RequestedScope(root, (root,), LiftMain(lift.lift_sha256, root))
    scope = select_scope(binary, lift, proof, plan, request)
    assert isinstance(scope, ScopeSelection)
    runtime = RuntimeManifest(
        "phoenix-frame-runtime-1",
        "phoenix-frame-capture-1",
        plan.sha256,
        scope.sha256,
        scope.policy_implementation_sha256,
        admission_implementation_sha256(),
        guard_profile_sha256(_D, _D),
        scope.registers,
        _D,
        _D,
        _D,
        "9.2.0",
        "ae35f033b874c627d81d51070187fbf55f0bf1a7",
        "sha256:" + _D,
        "sha256:" + _D,
        _D,
    )
    runtime_raw = runtime.to_bytes()
    pin = sha256(runtime_raw).hexdigest()
    identity = TraceIdentity(
        sha256(binary).hexdigest(),
        plan.sha256,
        sha256(encode_invocation(_CASE.invocation).encode("ascii")).hexdigest(),
        pin,
    )
    wire = _wire(identity, 0x400000)
    before, _ = wire.rsplit(b"END\t", 1)
    lines = before.splitlines(keepends=True)
    lines[4] = lines[4].replace(b"0000000000008000", b"0000000000007ff8")
    before = b"".join(lines)
    wire = before + f"END\t9\t{sha256(before).hexdigest()}\tcomplete\n".encode()
    receipt = CaptureReceipt(
        identity,
        sha256(wire).hexdigest(),
        scope.sha256,
        pin,
        RootAnchor(0, root, 0x7FFF000040, 0x8000, 0x7FFF000080),
        ReturnExit(7, 8, 0x8008),
        runtime.guard_profile_sha256,
        True,
        9,
        100,
        100,
        3,
        10,
        87,
        0,
        "complete",
    )
    return Sample(
        binary,
        lift_raw,
        mapping_raw,
        plan.to_bytes(),
        scope.to_bytes(),
        request,
        CaptureArtifacts(
            wire,
            canonical(asdict(receipt)),
            runtime_raw,
            encode_result(_CASE.expected).encode("ascii"),
        ),
        pin,
    )


def reject(result: AdmissionResult) -> Rejected:
    assert isinstance(result, Rejected), result
    assert not result.local
    return result


def receipt_record(run: Sample) -> dict[str, Any]:
    return dict(json.loads(run.artifacts.receipt))


def test_exact_saved_bytes_rebuild_source_and_admit_one_bounded_tree() -> None:
    run = sample()
    admitted = run.admit()
    assert isinstance(admitted, Admitted), admitted
    assert len(admitted.tree.frames) == 2
    assert admitted.tree.frames[0].children == (1,)
    assert admitted.tree.receipt_sha256 == sha256(run.artifacts.receipt).hexdigest()
    assert admitted.tree.trace_sha256 == sha256(run.artifacts.wire).hexdigest()
    assert admitted.tree.provider_identity == "unknown"
    assert "live-collector" in admitted.tree.unexercised
    assert run.admit() == admitted


@pytest.mark.parametrize("field", ("binary", "lift", "mapping", "plan", "scope"))
def test_changed_source_artifacts_cannot_reuse_capture(field: str) -> None:
    run = sample()
    value = getattr(run, field) + b" "
    if field == "mapping":
        record = json.loads(run.mapping)
        record["spans"][0]["original_sha256"] = "e" * 64
        value = raw_json(record)
    changed = replace(run, **{field: value})
    rejected = reject(changed.admit())
    assert rejected.rejection.stage == "selection"


def test_equivalent_mapping_formatting_rebuilds_the_same_proof() -> None:
    run = sample()
    assert replace(run, mapping=run.mapping + b" ").admit() == run.admit()


def test_changed_request_cannot_reuse_scope_or_capture() -> None:
    run = sample()
    changed = replace(run, request=replace(run.request, users=()))
    assert reject(changed.admit()).rejection.code == "scope_root"


@pytest.mark.parametrize(
    "field", ("wire", "receipt", "runtime_manifest", "observed_outcome")
)
def test_changed_raw_artifacts_never_reuse_admitted_tree(field: str) -> None:
    run = sample()
    changed = replace(run.artifacts, **{field: getattr(run.artifacts, field) + b"x"})
    reject(run.admit(changed))


@pytest.mark.parametrize(
    "field", ("wire", "receipt", "runtime_manifest", "observed_outcome")
)
def test_empty_artifact_is_rejected_without_local_salvage(field: str) -> None:
    run = sample()
    reject(run.admit(replace(run.artifacts, **{field: b""})))


@pytest.mark.parametrize(
    "field", ("stdout", "stderr", "termination", "tree", "invocation")
)
def test_accepted_full_outcome_and_invocation_are_required(field: str) -> None:
    run = sample()
    case = _CASE
    if field == "stdout":
        case = replace(case, expected=replace(case.expected, stdout=b"changed"))
    elif field == "stderr":
        case = replace(case, expected=replace(case.expected, stderr=b"changed"))
    elif field == "termination":
        case = replace(case, expected=replace(case.expected, termination=Exited(1)))
    elif field == "tree":
        tree = case.expected.tree
        tree = replace(tree, entries=(replace(tree.entries[0], mode=0o600),))
        case = replace(case, expected=replace(case.expected, tree=tree))
    else:
        case = replace(case, invocation=replace(case.invocation, stdin=b"changed"))
    reject(run.admit(case=case))


@pytest.mark.parametrize("field", ("predecessor_pc", "stack_target"))
@pytest.mark.parametrize("address", (0x400100, 0x402000, 0x400800))
def test_root_addresses_are_independently_classified(field: str, address: int) -> None:
    run = sample()
    record = receipt_record(run)
    record["root"][field] = address
    reject(run.admit(replace(run.artifacts, receipt=canonical(record))))


@pytest.mark.parametrize(
    "field",
    (
        "raw_trace_sha256",
        "scope_sha256",
        "runtime_manifest_sha256",
        "guard_profile_sha256",
    ),
)
def test_receipt_cross_artifact_identities_are_required(field: str) -> None:
    run = sample()
    record = receipt_record(run)
    record[field] = "e" * 64
    assert (
        reject(
            run.admit(replace(run.artifacts, receipt=canonical(record)))
        ).rejection.code
        == "receipt_identity"
    )


@pytest.mark.parametrize(
    "field", ("emitted_events", "execution_callbacks", "omitted_active_hits")
)
def test_receipt_counters_cannot_disguise_incomplete_capture(field: str) -> None:
    run = sample()
    record = receipt_record(run)
    record[field] = 1
    reject(run.admit(replace(run.artifacts, receipt=canonical(record))))


@pytest.mark.parametrize(
    "mutation", ("extra", "duplicate", "nonreturn", "bool", "status")
)
def test_receipt_parser_rejects_unsupported_or_ambiguous_records(mutation: str) -> None:
    run = sample()
    record = receipt_record(run)
    if mutation == "extra":
        record["extra"] = 0
    elif mutation == "nonreturn":
        record["root_exit"] = {
            "contract_sha256": _D,
            "call_sequence": 1,
            "outcome_sha256": _D,
        }
    elif mutation == "bool":
        record["root"]["rsp"] = True
    elif mutation == "status":
        record["plugin_status"] = "gap"
    raw = canonical(record)
    if mutation == "duplicate":
        raw = b'{"guard_passed":true,' + raw[1:]
    with pytest.raises(MappingError):
        parse_receipt(raw)
    reject(run.admit(replace(run.artifacts, receipt=raw)))


@pytest.mark.parametrize(
    "mutation", ("pin", "scope", "guard", "qemu", "registers", "canonical", "extra")
)
def test_runtime_manifest_requires_runner_pin_and_exact_profile(mutation: str) -> None:
    run = sample()
    record = dict(json.loads(run.artifacts.runtime_manifest))
    pin = run.runtime_sha256
    if mutation == "scope":
        record["scope_sha256"] = "e" * 64
    elif mutation == "guard":
        record["guard_profile_sha256"] = "e" * 64
    elif mutation == "qemu":
        record["qemu_version"] = "8.2.2"
    elif mutation == "registers":
        record["registers"][-1] = ["r8", 64]
    elif mutation == "extra":
        record["extra"] = 0
    raw = canonical(record)
    if mutation == "canonical":
        raw += b" "
    if mutation != "pin":
        pin = sha256(raw).hexdigest()
    else:
        pin = "e" * 64
    artifacts = replace(run.artifacts, runtime_manifest=raw)
    reject(replace(run, runtime_sha256=pin).admit(artifacts))


@given(st.binary(min_size=32, max_size=32), st.binary(min_size=32, max_size=32))
def test_runtime_schema_round_trip_binds_collector_and_plugin(
    collector: bytes, plugin: bytes
) -> None:
    run = sample()
    original = parse_runtime_manifest(
        run.artifacts.runtime_manifest, run.runtime_sha256
    )
    changed = replace(
        original,
        collector_source_sha256=collector.hex(),
        plugin_sha256=plugin.hex(),
        guard_profile_sha256=guard_profile_sha256(collector.hex(), plugin.hex()),
    )
    raw = changed.to_bytes()
    assert parse_runtime_manifest(raw, sha256(raw).hexdigest()) == changed


@pytest.mark.parametrize("raw", (b"{", b"[]", b'{"exit":0,"exit":1}', b"\xff"))
def test_malformed_outcome_has_no_local_salvage(raw: bytes) -> None:
    run = sample()
    reject(run.admit(replace(run.artifacts, observed_outcome=raw)))


def test_outcome_failure_or_analysis_trace_is_not_a_capture_outcome() -> None:
    run = sample()
    for raw in (
        b'{"failure":"trace","detail":"incomplete"}',
        run.artifacts.observed_outcome.replace(
            b'"trace": null', b'"trace": {"start": 0, "end": 1, "hits": [0]}'
        ),
    ):
        reject(run.admit(replace(run.artifacts, observed_outcome=raw)))


def test_complete_outcome_digest_excludes_analysis_metadata() -> None:
    run = sample()
    result = run.admit()
    assert isinstance(result, Admitted)
    observed = _CASE.expected
    assert isinstance(observed, Outcome)
    assert (
        result.tree.outcome_sha256
        == sha256(encode_result(observed).encode("ascii")).hexdigest()
    )


def test_opaque_transfer_cannot_enter_a_gap_in_the_original_image() -> None:
    run = sample()
    body, _ = run.artifacts.wire.rsplit(b"END\t", 1)
    body = body.replace(b"T\t5\t4\t0000007fff000000", b"T\t5\t4\t0000000000400800")
    wire = body + f"END\t9\t{sha256(body).hexdigest()}\tcomplete\n".encode()
    record = receipt_record(run)
    record["raw_trace_sha256"] = sha256(wire).hexdigest()
    result = reject(
        run.admit(replace(run.artifacts, wire=wire, receipt=canonical(record)))
    )
    assert result.rejection.code == "mapping_invalid"
    assert result.rejection.detail == "target_mapping"


@pytest.mark.parametrize(
    ("field", "size"),
    (("receipt", 65537), ("runtime_manifest", 65537), ("wire", 8 * 1024 * 1024 + 1)),
)
def test_raw_artifact_caps_reject_before_reconstruction(field: str, size: int) -> None:
    run = sample()
    result = reject(run.admit(replace(run.artifacts, **{field: b"x" * size})))
    assert result.rejection.detail == "A capture input exceeds its byte limit."
    assert result.rejection.full_plan_sha256 == ""


@given(st.integers(min_value=0, max_value=(1 << 64) - 1))
def test_receipt_schema_round_trip_preserves_full_stack_word(value: int) -> None:
    record = receipt_record(sample())
    record["root"]["stack_target"] = value
    raw = canonical(record)
    parsed = parse_receipt(raw)
    assert parsed.root.stack_target == value
    assert canonical(asdict(parsed)) == raw


def test_capture_cannot_reuse_a_different_admission_implementation() -> None:
    run = sample()
    record = json.loads(run.artifacts.runtime_manifest)
    record["admission_implementation_sha256"] = "e" * 64
    raw = canonical(record)
    changed = replace(run, runtime_sha256=sha256(raw).hexdigest())
    result = reject(changed.admit(replace(run.artifacts, runtime_manifest=raw)))
    assert result.rejection.detail == (
        "The runtime manifest has a different admission implementation."
    )


@pytest.mark.parametrize(
    "name",
    (
        "phoenix/observe/admission.py",
        "phoenix/observe/runtime.py",
        "phoenix/observe/capture.py",
        "phoenix/observe/frames.py",
        "phoenix/observe/mapping.py",
        "phoenix/observe/wire.py",
        "phoenix_eval/case.py",
        "phoenix_eval/outcome.py",
        "phoenix_eval/trace.py",
        "phoenix_eval/wire.py",
    ),
)
def test_each_admission_dependency_changes_implementation_identity(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = admission_implementation_sha256()
    read = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = read(path)
        return raw + b" " if str(path).endswith("/" + name) else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert admission_implementation_sha256() != original
