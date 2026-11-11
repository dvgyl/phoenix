from dataclasses import dataclass
from hashlib import sha256

from phoenix.analyze import DevelopmentCase
from phoenix.lift.index import LiftIndex
from phoenix.lift.mapping import MappingError, digest
from phoenix.observe.plan import Call, Jump, Return, TracePlan, build_trace_plan
from phoenix.observe.wire import (
    CallAttempt,
    Continuation,
    Entry,
    Gap,
    JumpAttempt,
    ReturnAttempt,
    TraceIdentity,
    Transfer,
    WireTrace,
    parse_trace_wire,
)
from phoenix.recover.addresses import AddressProof, ElfImage, ElfVA, checked_end
from phoenix.recover.transfers import decode_transfer
from phoenix_eval.outcome import Outcome, compare
from phoenix_eval.wire import encode_invocation, encode_result


class ObservationRejected(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class InternalTarget:
    address: ElfVA


@dataclass(frozen=True, slots=True)
class ExternalTarget:
    runtime_address: int


type Target = InternalTarget | ExternalTarget


@dataclass(frozen=True, slots=True)
class MappedObservation:
    trace: WireTrace
    plan: TracePlan
    bias: int
    outcome_sha256: str
    targets: tuple[tuple[int, Target], ...]


def _bias(image: ElfImage, trace: WireTrace) -> int:
    executable = tuple(segment for segment in image.segments if segment.flags & 1)
    if not executable:
        raise MappingError("The observation image has no executable segment.")
    start = min(segment.va for segment in executable)
    end = max(checked_end(segment.va, segment.file_size) for segment in executable)
    if (
        trace.code_start < start
        or trace.code_end - trace.code_start != end - start
        or image.kind == 2
        and trace.code_start != start
    ):
        raise ObservationRejected("runtime_mapping")
    result = trace.code_start - start
    if end + result != trace.code_end or trace.code_end >= 1 << 64:
        raise ObservationRejected("runtime_mapping")
    return result


def _target(image: ElfImage, runtime: int, bias: int) -> Target:
    address = runtime - bias
    if 0 <= address < 1 << 64:
        owners = [
            segment
            for segment in image.segments
            if segment.va <= address < segment.va + segment.memory_size
        ]
        if owners:
            executable = [
                segment
                for segment in owners
                if segment.flags & 1 and address < segment.va + segment.file_size
            ]
            if len(owners) != 1 or len(executable) != 1:
                raise ObservationRejected("target_mapping")
            return InternalTarget(ElfVA(address))
        executable = [segment for segment in image.segments if segment.flags & 1]
        if (
            min(segment.va for segment in executable)
            <= address
            < max(segment.va + segment.file_size for segment in executable)
        ):
            raise ObservationRejected("target_mapping")
    return ExternalTarget(runtime)


def map_observation(
    raw: bytes,
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    plan: TracePlan,
    case: DevelopmentCase,
    observed: Outcome,
    runtime_sha256: str,
) -> MappedObservation:
    canonical = build_trace_plan(binary, lift, proof)
    if plan.to_bytes() != canonical.to_bytes():
        raise MappingError("The observation plan differs from the checked source.")
    identity = TraceIdentity(
        sha256(binary).hexdigest(),
        canonical.sha256,
        sha256(encode_invocation(case.invocation).encode("ascii")).hexdigest(),
        digest(runtime_sha256),
    )
    trace = parse_trace_wire(raw, identity)
    if compare(case.expected, observed):
        raise ObservationRejected("outcome_mismatch")
    if trace.status != "complete":
        raise ObservationRejected("capture_incomplete")
    bias = _bias(proof.image, trace)
    sites = {site.address: site for site in canonical.sites}
    targets: list[tuple[int, Target]] = []
    for event in trace.events:
        if isinstance(event, Transfer):
            attempt = trace.events[event.attempt]
            target = _target(proof.image, event.next_pc, bias)
            if isinstance(attempt, CallAttempt):
                caller_site = sites[ElfVA(attempt.site)]
                physical = decode_transfer(
                    bytes.fromhex(caller_site.witness_hex), caller_site.address
                )
                assert physical is not None
                if physical.kind == "direct_call" and (
                    not isinstance(target, InternalTarget)
                    or target.address != physical.destination
                ):
                    raise ObservationRejected("call_target")
            elif isinstance(attempt, ReturnAttempt):
                if event.next_pc != attempt.stack_target:
                    raise ObservationRejected("return_target")
            targets.append((event.sequence, target))
            continue
        if isinstance(event, Gap):
            raise ObservationRejected("capture_incomplete")
        site = sites.get(ElfVA(event.site))
        if site is None:
            raise ObservationRejected("unplanned_site")
        if isinstance(event, Entry):
            valid = site.entry
        elif isinstance(event, CallAttempt):
            valid = isinstance(site.transfer, Call)
        elif isinstance(event, JumpAttempt):
            valid = isinstance(site.transfer, Jump)
        elif isinstance(event, ReturnAttempt):
            valid = isinstance(site.transfer, Return)
        elif isinstance(event, Continuation):
            attempt = trace.events[event.call]
            assert isinstance(attempt, CallAttempt)
            caller = sites.get(ElfVA(attempt.site))
            valid = (
                caller is not None
                and isinstance(caller.transfer, Call)
                and caller.transfer.continuation == site.address
                and caller.address in site.continuation_of
            )
        else:
            raise ObservationRejected("capture_incomplete")
        if not valid:
            raise ObservationRejected("site_role")
    if not any(isinstance(event, Entry) for event in trace.events):
        raise ObservationRejected("capture_empty")
    outcome = Outcome(
        observed.stdout, observed.stderr, observed.termination, observed.tree
    )
    return MappedObservation(
        trace,
        canonical,
        bias,
        sha256(encode_result(outcome).encode("ascii")).hexdigest(),
        tuple(targets),
    )
