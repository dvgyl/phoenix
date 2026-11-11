"""Rebuild source evidence before reducing exact saved capture bytes."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from phoenix.analyze import DevelopmentCase
from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import (
    MAX_BYTES,
    MappingError,
    digest,
    load_json,
    object_fields,
    parse_mapping,
    uint,
)
from phoenix.observe.capture import (
    CaptureReceipt,
    ReturnExit,
    RootAnchor,
    _CheckedCapture,
)
from phoenix.observe.frames import (
    AdmissionResult,
    RejectCode,
    Rejected,
    Rejection,
    admit_frames,
)
from phoenix.observe.mapping import (
    ExternalTarget,
    ObservationRejected,
    _target,
    map_observation,
)
from phoenix.observe.plan import build_trace_plan
from phoenix.observe.runtime import parse_runtime_manifest
from phoenix.observe.scope import (
    CaptureLimits,
    RequestedScope,
    ScopeSelection,
    select_scope,
)
from phoenix.observe.wire import TraceIdentity, TraceWireError
from phoenix.recover.addresses import ElfVA, prove_addresses
from phoenix_eval.outcome import Outcome
from phoenix_eval.wire import decode_result, encode_result


@dataclass(frozen=True, slots=True)
class CaptureArtifacts:
    wire: bytes
    receipt: bytes
    runtime_manifest: bytes
    observed_outcome: bytes


def parse_receipt(raw: bytes) -> CaptureReceipt:
    if not 0 < len(raw) <= CaptureLimits().receipt_bytes:
        raise MappingError("The capture receipt exceeds its byte limit.")
    record = object_fields(
        load_json(raw),
        "schema wire_identity raw_trace_sha256 scope_sha256 "
        "runtime_manifest_sha256 root root_exit guard_profile_sha256 "
        "guard_passed emitted_events execution_callbacks translated_instructions "
        "selected_instruction_callbacks outside_window_callbacks "
        "opaque_external_callbacks omitted_active_hits plugin_status",
    )
    if (
        record["schema"] != "phoenix-frame-capture-1"
        or record["plugin_status"] != "complete"
        or type(record["guard_passed"]) is not bool
    ):
        raise MappingError("The capture receipt profile is invalid or incomplete.")
    identity = object_fields(
        record["wire_identity"],
        "binary_sha256 plan_sha256 invocation_sha256 runtime_sha256",
    )
    root = object_fields(
        record["root"], "entry_sequence site predecessor_pc rsp stack_target"
    )
    exit_record = object_fields(
        record["root_exit"], "return_sequence transfer_sequence next_rsp"
    )
    return CaptureReceipt(
        TraceIdentity(
            digest(identity["binary_sha256"]),
            digest(identity["plan_sha256"]),
            digest(identity["invocation_sha256"]),
            digest(identity["runtime_sha256"]),
        ),
        digest(record["raw_trace_sha256"]),
        digest(record["scope_sha256"]),
        digest(record["runtime_manifest_sha256"]),
        RootAnchor(
            uint(root["entry_sequence"], 9999),
            ElfVA(uint(root["site"])),
            uint(root["predecessor_pc"]),
            uint(root["rsp"]),
            uint(root["stack_target"]),
        ),
        ReturnExit(
            uint(exit_record["return_sequence"], 9999),
            uint(exit_record["transfer_sequence"], 9999),
            uint(exit_record["next_rsp"]),
        ),
        digest(record["guard_profile_sha256"]),
        record["guard_passed"],
        uint(record["emitted_events"], 10000),
        uint(record["execution_callbacks"], 1000000),
        uint(record["translated_instructions"], 1000000),
        uint(record["selected_instruction_callbacks"], 1000000),
        uint(record["outside_window_callbacks"], 1000000),
        uint(record["opaque_external_callbacks"], 1000000),
        uint(record["omitted_active_hits"], 1000000),
        "complete",
    )


def _outcome(raw: bytes) -> Outcome:
    if not 0 < len(raw) <= 32 * 1024 * 1024:
        raise MappingError("The observed outcome exceeds its byte limit.")
    load_json(raw)
    try:
        observed = decode_result(raw.decode("ascii"))
        if (
            not isinstance(observed, Outcome)
            or observed.trace is not None
            or encode_result(observed).encode("ascii") != raw
        ):
            raise MappingError("The observed outcome is not canonical and complete.")
        return observed
    except (KeyError, ValueError, UnicodeError, RecursionError) as error:
        raise MappingError("The observed outcome protocol is invalid.") from error


def _reject(
    stage: Literal["selection", "mapping", "capture"],
    code: RejectCode,
    detail: str,
    full_plan_sha256: str,
    scope_sha256: str | None = None,
    identity: TraceIdentity | None = None,
    trace_sha256: str | None = None,
) -> Rejected:
    return Rejected(
        Rejection(
            stage,
            code,
            None,
            (),
            full_plan_sha256,
            scope_sha256,
            identity,
            trace_sha256,
            detail[:512],
        ),
        (),
    )


def admit_observation(
    binary: bytes,
    lift_raw: bytes,
    mapping_raw: bytes,
    full_plan_raw: bytes,
    scope_raw: bytes,
    requested: RequestedScope,
    artifacts: CaptureArtifacts,
    case: DevelopmentCase,
    expected_runtime_sha256: str,
    *,
    limits: CaptureLimits = CaptureLimits(),
) -> AdmissionResult:
    """Check saved bytes. The future runner owns their execution association."""
    plan_digest = ""
    try:
        ceiling = CaptureLimits()
        for raw, maximum in (
            (binary, MAX_BYTES),
            (lift_raw, MAX_BYTES),
            (mapping_raw, MAX_BYTES),
            (full_plan_raw, ceiling.full_plan_bytes),
            (scope_raw, ceiling.scope_bytes),
            (artifacts.wire, ceiling.wire_bytes),
            (artifacts.receipt, ceiling.receipt_bytes),
            (artifacts.runtime_manifest, ceiling.receipt_bytes),
            (artifacts.observed_outcome, 32 * 1024 * 1024),
        ):
            if not 0 < len(raw) <= maximum:
                raise MappingError("A capture input exceeds its byte limit.")
        plan_digest = sha256(full_plan_raw).hexdigest()
        lift = parse_lift(lift_raw, binary)
        mapping = parse_mapping(mapping_raw, binary, lift_raw)
        proof = prove_addresses(binary, lift, mapping)
        plan = build_trace_plan(binary, lift, proof)
        if plan.to_bytes() != full_plan_raw:
            raise MappingError("The full plan differs from its canonical source.")
        selection = select_scope(binary, lift, proof, plan, requested, limits=limits)
        if not isinstance(selection, ScopeSelection):
            return _reject("selection", selection.code, selection.detail, plan_digest)
        if selection.to_bytes() != scope_raw:
            return _reject(
                "selection",
                "scope_identity",
                "The scope differs from its canonical reconstruction.",
                plan_digest,
            )
    except (ValueError, RecursionError) as error:
        return _reject("selection", "scope_identity", str(error), plan_digest)
    scope_digest = sha256(scope_raw).hexdigest()
    try:
        runtime = parse_runtime_manifest(
            artifacts.runtime_manifest, expected_runtime_sha256
        )
        if (
            runtime.full_plan_sha256 != plan.sha256
            or runtime.scope_sha256 != scope_digest
            or runtime.policy_implementation_sha256
            != selection.policy_implementation_sha256
            or runtime.registers != selection.registers
        ):
            raise MappingError("The runtime manifest differs from the checked scope.")
        receipt = parse_receipt(artifacts.receipt)
        observed = _outcome(artifacts.observed_outcome)
        mapped = map_observation(
            artifacts.wire,
            binary,
            lift,
            proof,
            plan,
            case,
            observed,
            expected_runtime_sha256,
        )
        image_start = min(segment.va for segment in proof.image.segments) + mapped.bias
        image_end = (
            max(segment.va + segment.memory_size for segment in proof.image.segments)
            + mapped.bias
        )
        if image_end > 1 << 64:
            raise ObservationRejected("runtime_mapping")
        if any(
            isinstance(target, ExternalTarget)
            and image_start <= target.runtime_address < image_end
            for _, target in mapped.targets
        ):
            raise ObservationRejected("target_mapping")
        predecessor = _target(proof.image, receipt.root.predecessor_pc, mapped.bias)
        stack_target = _target(proof.image, receipt.root.stack_target, mapped.bias)
        if (
            not isinstance(predecessor, ExternalTarget)
            or not isinstance(stack_target, ExternalTarget)
            or any(
                image_start <= address < image_end
                for address in (
                    receipt.root.predecessor_pc,
                    receipt.root.stack_target,
                )
            )
        ):
            return _reject(
                "capture",
                "root_anchor",
                "The root predecessor and saved stack target must be external.",
                plan_digest,
                scope_digest,
                mapped.trace.identity,
                mapped.trace.sha256,
            )
        checked = _CheckedCapture(
            mapped,
            selection,
            receipt,
            sha256(artifacts.receipt).hexdigest(),
            runtime.guard_profile_sha256,
            predecessor,
            stack_target,
            len(artifacts.wire),
            len(artifacts.receipt),
            observed.termination,
            mapped.outcome_sha256,
        )
        return admit_frames(checked)
    except TraceWireError as error:
        return _reject("mapping", "wire_invalid", str(error), plan_digest, scope_digest)
    except ObservationRejected as error:
        code: RejectCode = (
            "outcome_mismatch"
            if error.reason == "outcome_mismatch"
            else "mapping_invalid"
        )
        return _reject("mapping", code, error.reason, plan_digest, scope_digest)
    except (ValueError, RecursionError) as error:
        return _reject(
            "capture", "receipt_identity", str(error), plan_digest, scope_digest
        )
