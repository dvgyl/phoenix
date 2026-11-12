"""Reduce checked capture evidence without execution or typed inference."""

from dataclasses import dataclass, field, replace
from typing import Literal

from phoenix.lift.mapping import MappingError
from phoenix.observe.capture import ProcessExit, ReturnExit, _CheckedCapture
from phoenix.observe.mapping import ExternalTarget, InternalTarget, Target
from phoenix.observe.plan import Call, Jump, TraceSite
from phoenix.observe.scope import (
    CaptureLimits,
    ImportRequest,
    LocalConditional,
    LocalDirect,
    OmittedSite,
    Reject,
    TransitRoute,
    User,
)
from phoenix.observe.wire import (
    CallAttempt,
    Continuation,
    Entry,
    Event,
    Gap,
    JumpAttempt,
    Registers,
    ReturnAttempt,
    TraceIdentity,
    Transfer,
)
from phoenix.recover.addresses import ElfVA

type RejectCode = Literal[
    "scope_identity",
    "scope_root",
    "scope_partition",
    "scope_bound",
    "scope_route",
    "scope_guard",
    "wire_invalid",
    "mapping_invalid",
    "outcome_mismatch",
    "capture_incomplete",
    "receipt_identity",
    "root_anchor",
    "root_missing",
    "root_reentry",
    "origin",
    "owner",
    "event_order",
    "missing_event",
    "duplicate_event",
    "call_target",
    "entry_rsp",
    "entry_registers",
    "return_rsp",
    "return_target",
    "return_value",
    "continuation",
    "open_frame",
    "external_reentry",
    "unknown_callback",
    "tail_candidate",
    "nonlocal_return",
    "unresolved_target",
    "transit",
    "nonreturn_contract",
    "limit",
]


@dataclass(frozen=True, slots=True)
class EventRef:
    trace_sha256: str
    sequence: int


@dataclass(frozen=True, slots=True)
class UserFunction:
    entry: ElfVA


@dataclass(frozen=True, slots=True)
class ExternalExcursion:
    request: ImportRequest | None
    first_external_pc: int
    transit: tuple[EventRef, ...]


type FrameKind = UserFunction | ExternalExcursion


@dataclass(frozen=True, slots=True)
class Returned:
    return_attempt: EventRef
    transfer: EventRef
    continuation: EventRef
    result_bits: int


@dataclass(frozen=True, slots=True)
class ExternalResumed:
    continuation: EventRef
    result_bits: int


@dataclass(frozen=True, slots=True)
class RootReturned:
    return_attempt: EventRef
    transfer: EventRef


type FrameEnd = Returned | ExternalResumed | RootReturned


@dataclass(frozen=True, slots=True)
class AdmittedFrame:
    id: int
    parent: int | None
    kind: FrameKind
    call: EventRef | None
    entry: EventRef | None
    pre_call_rsp: int | None
    entry_rsp: int | None
    continuation: ElfVA | None
    end: FrameEnd
    children: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LocalRegisterObservation:
    trace_sha256: str
    identity: TraceIdentity
    scope_sha256: str
    event: EventRef
    site: ElfVA
    register: str
    bits: int
    width: Literal[64] = field(init=False, default=64)
    meaning: Literal["raw-pre-instruction-bits"] = field(
        init=False, default="raw-pre-instruction-bits"
    )


@dataclass(frozen=True, slots=True)
class AdmittedCallTree:
    identity: TraceIdentity
    trace_sha256: str
    scope_sha256: str
    receipt_sha256: str
    policy_sha256: str
    outcome_sha256: str
    root: int
    frames: tuple[AdmittedFrame, ...]
    omitted: tuple[OmittedSite, ...]
    unexercised: tuple[str, ...]
    schema: Literal[1] = field(init=False, default=1)
    claim: Literal["requested-main-activation"] = field(
        init=False, default="requested-main-activation"
    )
    provider_identity: Literal["unknown"] = field(init=False, default="unknown")


@dataclass(frozen=True, slots=True)
class Rejection:
    stage: Literal["selection", "mapping", "capture", "frames"]
    code: RejectCode
    event: EventRef | None
    related: tuple[EventRef, ...]
    full_plan_sha256: str
    scope_sha256: str | None
    wire_identity: TraceIdentity | None
    raw_trace_sha256: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class Admitted:
    tree: AdmittedCallTree


@dataclass(frozen=True, slots=True)
class Rejected:
    rejection: Rejection
    local: tuple[()]


type AdmissionResult = Admitted | Rejected


class _Failure(Exception):
    def __init__(
        self,
        code: RejectCode,
        event: Event | None = None,
        related: tuple[Event, ...] = (),
        *,
        capture: bool = False,
    ) -> None:
        self.code = code
        self.event = event
        self.related = related
        self.capture = capture


def _require(
    condition: bool,
    code: RejectCode,
    event: Event | None = None,
    related: tuple[Event, ...] = (),
    *,
    capture: bool = False,
) -> None:
    if not condition:
        raise _Failure(code, event, related, capture=capture)


def _word(value: int) -> bool:
    return type(value) is int and 0 <= value < 1 << 64


def _digest(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _preflight(checked: _CheckedCapture) -> str:
    mapped, scope, receipt = checked.mapped, checked.selection, checked.receipt
    trace, plan, limits = mapped.trace, mapped.plan, scope.limits
    ceiling = CaptureLimits()
    for name in CaptureLimits.__dataclass_fields__:
        value = getattr(limits, name)
        _require(
            type(value) is int and 0 < value <= getattr(ceiling, name),
            "limit",
            capture=True,
        )
    _require(limits.snapshot_bytes == 8, "limit", capture=True)
    _require(
        len(trace.events) <= limits.events
        and len(plan.sites) <= limits.full_plan_sites
        and len(scope.guard_instructions) <= limits.guarded_instructions
        and 0 < checked.raw_trace_bytes <= limits.wire_bytes
        and 0 < checked.receipt_bytes <= limits.receipt_bytes,
        "limit",
        capture=True,
    )
    try:
        _require(len(plan.to_bytes()) <= limits.full_plan_bytes, "limit", capture=True)
        scope_digest = scope.sha256
    except MappingError as error:
        raise _Failure("limit", capture=True) from error
    _require(
        scope.policy == "main-window-six-v1"
        and scope.full_plan_sha256 == plan.sha256 == trace.identity.plan_sha256
        and scope.binary_sha256 == plan.binary_sha256 == trace.identity.binary_sha256
        and scope.lift_sha256 == plan.lift_sha256
        and scope.address_proof_sha256 == plan.address_proof_sha256
        and scope.registers == plan.registers,
        "scope_identity",
        capture=True,
    )
    _require(
        receipt.wire_identity == trace.identity
        and receipt.raw_trace_sha256 == trace.sha256
        and receipt.scope_sha256 == scope_digest
        and receipt.runtime_manifest_sha256 == trace.identity.runtime_sha256
        and receipt.guard_profile_sha256 == checked.guard_profile_sha256,
        "receipt_identity",
        capture=True,
    )
    _require(
        all(
            _digest(value)
            for value in (
                checked.receipt_sha256,
                checked.guard_profile_sha256,
                trace.sha256,
                checked.full_outcome_sha256,
                trace.identity.invocation_sha256,
                trace.identity.runtime_sha256,
            )
        ),
        "receipt_identity",
        capture=True,
    )
    _require(
        checked.full_outcome_sha256 == mapped.outcome_sha256,
        "outcome_mismatch",
        capture=True,
    )
    _require(
        not scope.contracts and not isinstance(receipt.root_exit, ProcessExit),
        "nonreturn_contract",
        capture=True,
    )
    _require(
        trace.status == "complete"
        and receipt.plugin_status == "complete"
        and receipt.guard_passed is True
        and receipt.omitted_active_hits == 0
        and receipt.emitted_events == len(trace.events),
        "capture_incomplete",
        capture=True,
    )
    counts = (
        receipt.execution_callbacks,
        receipt.translated_instructions,
        receipt.selected_instruction_callbacks,
        receipt.outside_window_callbacks,
        receipt.opaque_external_callbacks,
    )
    _require(
        all(type(n) is int and n >= 0 for n in counts)
        and 0 < receipt.execution_callbacks <= limits.execution_callbacks
        and 0 < receipt.translated_instructions <= limits.translated_instructions
        and receipt.selected_instruction_callbacks > 0
        and sum(counts[2:]) == receipt.execution_callbacks,
        "limit",
        capture=True,
    )
    anchor = receipt.root
    _require(
        anchor.entry_sequence == 0
        and anchor.site == scope.root
        and all(
            _word(n) for n in (anchor.rsp, anchor.stack_target, anchor.predecessor_pc)
        )
        and isinstance(checked.root_predecessor, ExternalTarget)
        and checked.root_predecessor.runtime_address == anchor.predecessor_pc
        and isinstance(checked.root_stack_target, ExternalTarget)
        and checked.root_stack_target.runtime_address == anchor.stack_target,
        "root_anchor",
        capture=True,
    )
    # The boundary owns authenticity. These checks detect inconsistent inputs.
    confirmed: set[int] = set()
    continued: set[int] = set()
    targets = dict(mapped.targets)
    _require(len(targets) == len(mapped.targets), "mapping_invalid", capture=True)
    transfers = 0
    for sequence, event in enumerate(trace.events):
        _require(
            event.sequence == sequence and not isinstance(event, Gap),
            "wire_invalid",
            event,
            capture=True,
        )
        if isinstance(event, Transfer):
            _require(
                event.attempt == sequence - 1
                and sequence > 0
                and isinstance(
                    trace.events[sequence - 1],
                    (CallAttempt, JumpAttempt, ReturnAttempt),
                ),
                "wire_invalid",
                event,
                capture=True,
            )
            target = targets.get(sequence)
            _require(target is not None, "mapping_invalid", event, capture=True)
            assert target is not None
            runtime = (
                target.address + mapped.bias
                if isinstance(target, InternalTarget)
                else target.runtime_address
            )
            _require(
                _word(runtime) and runtime == event.next_pc,
                "mapping_invalid",
                event,
                capture=True,
            )
            confirmed.add(event.attempt)
            transfers += 1
        elif isinstance(event, Continuation):
            _require(
                event.call in confirmed
                and event.call not in continued
                and isinstance(trace.events[event.call], CallAttempt),
                "wire_invalid",
                event,
                capture=True,
            )
            continued.add(event.call)
        if isinstance(event, (CallAttempt, JumpAttempt, ReturnAttempt)):
            _require(
                sequence + 1 < len(trace.events)
                and isinstance(trace.events[sequence + 1], Transfer),
                "wire_invalid",
                event,
                capture=True,
            )
    _require(transfers == len(targets), "mapping_invalid", capture=True)
    return scope_digest


@dataclass(slots=True)
class _Node:
    id: int
    parent: int | None
    kind: FrameKind
    call: CallAttempt | None
    entry: Entry | None
    continuation: ElfVA | None
    children: list[int] = field(default_factory=list)
    end: FrameEnd | None = None


@dataclass(frozen=True, slots=True)
class _Visit:
    address: ElfVA
    origin: Literal["call", "unknown"]
    call: CallAttempt | None = None
    snapshot: Entry | Continuation | None = None


@dataclass(frozen=True, slots=True)
class _Resume:
    attempt: ReturnAttempt | None
    transfer: Transfer | None


@dataclass(slots=True)
class _Transit:
    route: TransitRoute
    index: int = 0
    snapshot: Registers | None = None
    evidence: list[EventRef] = field(default_factory=list)


class _Reducer:
    def __init__(self, checked: _CheckedCapture, scope_digest: str) -> None:
        self.checked = checked
        self.scope_digest = scope_digest
        self.events = checked.mapped.trace.events
        self.sites = {s.address: s for s in checked.mapped.plan.sites}
        self.guards = {g.address: g for g in checked.selection.guard_instructions}
        self.users = frozenset(checked.selection.users)
        self.dispositions = dict(checked.selection.dispositions)
        self.routes = {r.call_site: r for r in checked.selection.routes}
        self.targets = dict(checked.mapped.targets)
        self.branch_entries: set[ElfVA] = set()
        for guard in self.guards.values():
            rule = guard.rule
            destinations: tuple[ElfVA, ...] = ()
            if isinstance(rule, LocalDirect):
                destinations = (rule.destination,)
            elif isinstance(rule, LocalConditional):
                destinations = (rule.taken, rule.fallthrough)
            for destination in destinations:
                if destination == guard.owner:
                    self.branch_entries.add(destination)
        self.position = 0
        self.nodes: list[_Node] = []
        self.stack: list[_Node] = []
        self.wait: _Visit | _Resume | _Transit | None = None

    def ref(self, event: Event) -> EventRef:
        return EventRef(self.checked.mapped.trace.sha256, event.sequence)

    def take(self) -> Event:
        _require(self.position < len(self.events), "missing_event")
        event = self.events[self.position]
        self.position += 1
        return event

    def add(
        self, kind: FrameKind, call: CallAttempt | None, continuation: ElfVA | None
    ) -> _Node:
        _require(
            len(self.nodes)
            < min(self.checked.selection.limits.frames, len(self.events)),
            "limit",
            call,
            capture=True,
        )
        parent = self.stack[-1] if self.stack else None
        node = _Node(
            len(self.nodes),
            parent.id if parent else None,
            kind,
            call,
            None,
            continuation,
        )
        self.nodes.append(node)
        if parent:
            parent.children.append(node.id)
        self.stack.append(node)
        return node

    def user_site(self, address: ElfVA, event: Event) -> TraceSite:
        site = self.sites.get(address)
        guard = self.guards.get(address)
        disposition = self.dispositions.get(address)
        _require(
            site is not None
            and isinstance(disposition, User)
            and guard is not None
            and not isinstance(guard.rule, Reject),
            "owner",
            event,
        )
        assert site is not None
        top = self.stack[-1]
        _require(
            isinstance(top.kind, UserFunction) and top.kind.entry == site.owner,
            "owner",
            event,
        )
        return site

    def snapshots(
        self,
        events: tuple[Entry | Continuation | CallAttempt, ...],
        ret: ReturnAttempt | None = None,
    ) -> None:
        if not events:
            return
        registers = events[0].registers
        valid = all(e.registers == registers for e in events[1:])
        valid = valid and (
            ret is None or (ret.rsp, ret.rax) == (registers.rsp, registers.rax)
        )
        if not valid:
            raise _Failure("entry_registers", ret or events[-1], tuple(events))

    def bundle(
        self, site: TraceSite, snapshots: tuple[Entry | Continuation | CallAttempt, ...]
    ) -> None:
        transfer = site.transfer
        if transfer is None:
            self.wait = None
            return
        event = self.take()
        expected = (
            CallAttempt
            if isinstance(transfer, Call)
            else JumpAttempt
            if isinstance(transfer, Jump)
            else ReturnAttempt
        )
        _require(
            isinstance(event, expected)
            and getattr(event, "site", None) == site.address,
            "missing_event",
            event,
            tuple(snapshots),
        )
        if isinstance(event, CallAttempt):
            self.snapshots((*snapshots, event))
        elif isinstance(event, ReturnAttempt):
            self.snapshots(snapshots, event)
        self.attempt(event, site)

    def visit(self, visit: _Visit) -> None:
        event = self.events[self.position] if self.position < len(self.events) else None
        _require(event is not None, "missing_event")
        assert event is not None
        site = self.user_site(visit.address, event)
        snapshots: tuple[Entry | Continuation | CallAttempt, ...] = (
            (visit.snapshot,) if visit.snapshot else ()
        )
        if site.entry:
            entry = self.take()
            _require(
                isinstance(entry, Entry) and entry.site == site.address,
                "missing_event",
                entry,
            )
            assert isinstance(entry, Entry)
            _require(entry.origin == visit.origin, "origin", entry)
            if visit.call:
                call = visit.call
                _require(
                    entry.registers.rsp == call.registers.rsp - 8,
                    "entry_rsp",
                    entry,
                    (call,),
                )
                _require(
                    replace(entry.registers, rsp=call.registers.rsp) == call.registers,
                    "entry_registers",
                    entry,
                    (call,),
                )
                self.stack[-1].entry = entry
            snapshots = (*snapshots, entry)
            self.snapshots(snapshots)
        else:
            _require(visit.call is None, "call_target", event)
        self.bundle(site, snapshots)

    def attempt(self, event: Event, site: TraceSite) -> None:
        top = self.stack[-1]
        _require(
            isinstance(event, (CallAttempt, JumpAttempt, ReturnAttempt)),
            "event_order",
            event,
        )
        assert isinstance(event, (CallAttempt, JumpAttempt, ReturnAttempt))
        if isinstance(event, CallAttempt):
            _require(event.registers.rsp >= 8, "entry_rsp", event)
        elif isinstance(event, ReturnAttempt):
            assert top.entry is not None
            _require(event.rsp == top.entry.registers.rsp, "return_rsp", event)
            if top.parent is None:
                destination = self.checked.receipt.root.stack_target
                _require(event.stack_target == destination, "root_anchor", event)
            else:
                assert top.continuation is not None
                destination = top.continuation + self.checked.mapped.bias
                _require(
                    _word(destination) and event.stack_target == destination,
                    "nonlocal_return",
                    event,
                )
        confirmed = self.take()
        _require(
            isinstance(confirmed, Transfer) and confirmed.attempt == event.sequence,
            "event_order",
            confirmed,
        )
        assert isinstance(confirmed, Transfer)
        target = self.targets[confirmed.sequence]
        if isinstance(event, CallAttempt):
            self.call(event, site, target)
        elif isinstance(event, JumpAttempt):
            self.jump(event, target)
        else:
            _require(
                confirmed.next_pc == event.stack_target, "return_target", confirmed
            )
            if top.parent is not None:
                self.wait = _Resume(event, confirmed)
            else:
                exit_record = self.checked.receipt.root_exit
                assert isinstance(exit_record, ReturnExit)
                _require(
                    isinstance(target, ExternalTarget)
                    and exit_record.return_sequence == event.sequence
                    and exit_record.transfer_sequence == confirmed.sequence
                    and _word(event.rsp + 8)
                    and exit_record.next_rsp == event.rsp + 8,
                    "root_anchor",
                    confirmed,
                )
                top.end = RootReturned(self.ref(event), self.ref(confirmed))
                self.stack.pop()
                self.wait = None

    def call(self, event: CallAttempt, site: TraceSite, target: Target) -> None:
        transfer = site.transfer
        assert isinstance(transfer, Call)
        _require(
            _word(transfer.continuation + self.checked.mapped.bias),
            "continuation",
            event,
        )
        if isinstance(target, InternalTarget) and target.address in self.users:
            self.add(UserFunction(target.address), event, transfer.continuation)
            self.wait = _Visit(target.address, "call", call=event)
            return
        route = self.routes.get(site.address)
        request = route.request if route is not None else None
        if isinstance(target, ExternalTarget):
            _require(route is None or not route.entries, "transit", event)
            self.add(
                ExternalExcursion(request, target.runtime_address, ()),
                event,
                transfer.continuation,
            )
            self.wait = _Resume(None, None)
            return
        _require(
            route is not None
            and bool(route.entries)
            and target.address == route.entries[0],
            "call_target",
            event,
        )
        assert route is not None
        self.add(ExternalExcursion(request, 0, ()), event, transfer.continuation)
        self.wait = _Transit(route)

    def jump(self, event: JumpAttempt, target: Target) -> None:
        top = self.stack[-1]
        assert isinstance(top.kind, UserFunction)
        _require(isinstance(target, InternalTarget), "tail_candidate", event)
        assert isinstance(target, InternalTarget)
        guard = self.guards.get(target.address)
        _require(
            guard is not None and guard.owner == top.kind.entry, "tail_candidate", event
        )
        assert guard is not None
        _require(not isinstance(guard.rule, Reject), "scope_guard", event)
        self.wait = (
            _Visit(target.address, "unknown") if target.address in self.sites else None
        )

    def resume(self, wait: _Resume) -> None:
        top = self.stack[-1]
        assert top.call is not None and top.continuation is not None
        event = self.take()
        external = isinstance(top.kind, ExternalExcursion)
        if external and isinstance(event, Entry):
            raise _Failure("unknown_callback", event)
        _require(
            isinstance(event, Continuation),
            "external_reentry" if external else "missing_event",
            event,
        )
        assert isinstance(event, Continuation)
        _require(
            event.call == top.call.sequence
            and event.site == top.continuation
            and event.registers.rsp == top.call.registers.rsp,
            "continuation",
            event,
            (top.call,),
        )
        if external:
            top.end = ExternalResumed(self.ref(event), event.registers.rax)
        else:
            assert wait.attempt is not None and wait.transfer is not None
            _require(
                event.registers.rax == wait.attempt.rax,
                "return_value",
                event,
                (wait.attempt,),
            )
            top.end = Returned(
                self.ref(wait.attempt),
                self.ref(wait.transfer),
                self.ref(event),
                event.registers.rax,
            )
        self.stack.pop()
        self.visit(_Visit(ElfVA(event.site), "unknown", snapshot=event))

    def transit(self, wait: _Transit) -> None:
        top = self.stack[-1]
        assert top.call is not None
        if wait.index < len(wait.route.entries):
            entry = self.take()
            _require(
                isinstance(entry, Entry)
                and entry.site == wait.route.entries[wait.index],
                "transit",
                entry,
            )
            assert isinstance(entry, Entry)
            _require(
                entry.origin == ("call" if wait.index == 0 else "unknown"),
                "origin",
                entry,
            )
            if wait.index == 0:
                expected = replace(top.call.registers, rsp=top.call.registers.rsp - 8)
            else:
                assert wait.snapshot is not None
                expected = wait.snapshot
            _require(entry.registers == expected, "entry_registers", entry)
            wait.snapshot = entry.registers
            wait.evidence.append(self.ref(entry))
            wait.index += 1
            return
        jump = self.take()
        _require(
            isinstance(jump, JumpAttempt) and jump.site == wait.route.terminal,
            "transit",
            jump,
        )
        transfer = self.take()
        _require(
            isinstance(transfer, Transfer) and transfer.attempt == jump.sequence,
            "transit",
            transfer,
        )
        assert isinstance(transfer, Transfer)
        target = self.targets[transfer.sequence]
        _require(isinstance(target, ExternalTarget), "transit", transfer)
        assert isinstance(target, ExternalTarget)
        wait.evidence.extend((self.ref(jump), self.ref(transfer)))
        top.kind = ExternalExcursion(
            wait.route.request, target.runtime_address, tuple(wait.evidence)
        )
        self.wait = _Resume(None, None)

    def run(self) -> AdmittedCallTree:
        root = self.take()
        anchor = self.checked.receipt.root
        _require(
            isinstance(root, Entry) and root.site == anchor.site, "root_missing", root
        )
        assert isinstance(root, Entry)
        _require(root.origin == "external", "origin", root)
        _require(root.registers.rsp == anchor.rsp, "root_anchor", root)
        node = self.add(UserFunction(anchor.site), None, None)
        node.entry = root
        site = self.user_site(anchor.site, root)
        _require(site.entry, "root_missing", root)
        self.bundle(site, (root,))
        while self.position < len(self.events):
            event = self.events[self.position]
            _require(bool(self.stack), "root_reentry", event)
            if isinstance(self.wait, _Visit):
                self.visit(self.wait)
            elif isinstance(self.wait, _Resume):
                self.resume(self.wait)
            elif isinstance(self.wait, _Transit):
                self.transit(self.wait)
            else:
                _require(
                    not isinstance(event, (Transfer, Continuation)),
                    "event_order",
                    event,
                )
                _require(
                    not isinstance(event, Gap),
                    "capture_incomplete",
                    event,
                    capture=True,
                )
                assert isinstance(
                    event, (Entry, CallAttempt, JumpAttempt, ReturnAttempt)
                )
                site = self.user_site(ElfVA(event.site), event)
                if isinstance(event, Entry):
                    _require(
                        site.address in self.branch_entries, "duplicate_event", event
                    )
                    self.visit(_Visit(site.address, "unknown"))
                else:
                    _require(not site.entry, "missing_event", event)
                    _require(site.transfer is not None, "event_order", event)
                    self.bundle(site, ())
        _require(not self.stack and self.wait is None, "open_frame")
        frames: list[AdmittedFrame] = []
        for n in self.nodes:
            assert n.end is not None
            frames.append(
                AdmittedFrame(
                    n.id,
                    n.parent,
                    n.kind,
                    self.ref(n.call) if n.call else None,
                    self.ref(n.entry) if n.entry else None,
                    n.call.registers.rsp if n.call else None,
                    n.entry.registers.rsp if n.entry else None,
                    n.continuation,
                    n.end,
                    tuple(n.children),
                )
            )
        checked = self.checked
        return AdmittedCallTree(
            checked.mapped.trace.identity,
            checked.mapped.trace.sha256,
            self.scope_digest,
            checked.receipt_sha256,
            checked.selection.policy_implementation_sha256,
            checked.full_outcome_sha256,
            0,
            tuple(frames),
            checked.selection.omitted,
            (
                "live-collector",
                "root-read-calibration",
                "scope-guard-calibration",
                "collector-mutation-controls",
                "provider-identity",
                "abi-types",
                "nonreturn-contracts",
                "lazy-resolver-transit",
            ),
        )


def _local(
    checked: _CheckedCapture, scope_digest: str
) -> tuple[LocalRegisterObservation, ...]:
    observations: list[LocalRegisterObservation] = []
    for event in checked.mapped.trace.events:
        if isinstance(event, (Entry, CallAttempt, Continuation)):
            for register, _ in checked.mapped.plan.registers:
                observations.append(
                    LocalRegisterObservation(
                        checked.mapped.trace.sha256,
                        checked.mapped.trace.identity,
                        scope_digest,
                        EventRef(checked.mapped.trace.sha256, event.sequence),
                        ElfVA(event.site),
                        register,
                        getattr(event.registers, register),
                    )
                )
    return tuple(observations)


def _reduce(
    checked: _CheckedCapture,
) -> tuple[AdmissionResult, tuple[LocalRegisterObservation, ...]]:
    scope_digest: str | None = None
    try:
        scope_digest = _preflight(checked)
        reducer = _Reducer(checked, scope_digest)
        tree = reducer.run()
    except _Failure as failure:
        trace = checked.mapped.trace
        rejection = Rejection(
            "capture" if failure.capture else "frames",
            failure.code,
            EventRef(trace.sha256, failure.event.sequence) if failure.event else None,
            tuple(EventRef(trace.sha256, e.sequence) for e in failure.related),
            trace.identity.plan_sha256,
            scope_digest,
            trace.identity,
            trace.sha256,
            f"The capture failed the {failure.code} check.",
        )
        return Rejected(rejection, ()), ()
    local = _local(checked, scope_digest)
    return Admitted(tree), local


def admit_frames(checked: _CheckedCapture) -> AdmissionResult:
    """Admit only a complete requested activation from private checked input."""
    return _reduce(checked)[0]


def local_registers(checked: _CheckedCapture) -> tuple[LocalRegisterObservation, ...]:
    """Return raw snapshots only after complete frame admission."""
    return _reduce(checked)[1]
