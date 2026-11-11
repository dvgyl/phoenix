"""Synthetic checked records and schema 2 wire, never live collector evidence."""

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from typing import Any, cast

import pytest

from phoenix.lift.mapping import MappingError
from phoenix.observe.capture import (
    CaptureReceipt,
    ProcessExit,
    ReturnExit,
    RootAnchor,
    _CheckedCapture,
)
from phoenix.observe.frames import (
    Admitted,
    ExternalExcursion,
    ExternalResumed,
    Rejected,
    Returned,
    RootReturned,
    UserFunction,
    admit_frames,
    local_registers,
)
from phoenix.observe.mapping import ExternalTarget, InternalTarget, MappedObservation
from phoenix.observe.plan import Call, Jump, Return, TracePlan, TraceSite
from phoenix.observe.scope import (
    CaptureLimits,
    ExplicitEntry,
    GuardInstruction,
    GuardRule,
    LocalDirect,
    Ordinary,
    PlannedRoles,
    RequestedScope,
    ScopeSelection,
    SiteDisposition,
    Transit,
    TransitInstruction,
    TransitRoute,
    User,
)
from phoenix.observe.wire import (
    CallAttempt,
    Continuation,
    Entry,
    Event,
    JumpAttempt,
    Registers,
    ReturnAttempt,
    TraceIdentity,
    TraceWireError,
    Transfer,
    parse_trace_wire,
)
from phoenix.recover.addresses import ElfVA
from phoenix.recover.imports import ImportId
from phoenix_eval.outcome import Exited

_D = "d" * 64
_EXT = 0xF000
_REG = Registers(11, 22, 33, 44, 55, 0x1000)


def changed[T](value: T, **changes: object) -> T:
    """Mutate synthetic evidence, including deliberately invalid field values."""
    return cast(T, replace(cast(Any, value), **changes))


class Stream:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def add(self, event: Event) -> int:
        sequence = len(self.events)
        self.events.append(changed(event, sequence=sequence))
        return sequence

    def entry(
        self,
        site: int,
        rsp: int,
        *,
        external: bool = False,
        registers: Registers = _REG,
    ) -> int:
        return self.add(
            Entry(
                0, site, "external" if external else "call", changed(registers, rsp=rsp)
            )
        )

    def call(
        self, site: int, target: int, rsp: int, registers: Registers = _REG
    ) -> int:
        sequence = self.add(CallAttempt(0, site, changed(registers, rsp=rsp)))
        self.add(Transfer(0, sequence, target))
        return sequence

    def ret(self, site: int, target: int, rsp: int, rax: int = 42) -> int:
        sequence = self.add(ReturnAttempt(0, site, target, rsp, rax))
        self.add(Transfer(0, sequence, target))
        return sequence

    def resume(self, call: int, site: int, rsp: int, rax: int = 42) -> int:
        return self.add(Continuation(0, call, site, changed(_REG, rsp=rsp, rax=rax)))

    def jump(self, site: int, target: int) -> int:
        sequence = self.add(JumpAttempt(0, site))
        self.add(Transfer(0, sequence, target))
        return sequence


def site(
    address: int,
    owner: int,
    transfer: Call | Jump | Return | None = None,
    *,
    entry: bool = False,
    calls: tuple[int, ...] = (),
) -> TraceSite:
    witness = (
        "ffd0"
        if isinstance(transfer, Call)
        else "ffe0"
        if isinstance(transfer, Jump)
        else "c3"
        if isinstance(transfer, Return)
        else "90"
    )
    return TraceSite(
        ElfVA(address),
        ElfVA(owner),
        witness,
        entry,
        tuple(ElfVA(c) for c in calls),
        transfer,
    )


def call(continuation: int) -> Call:
    return Call("indirect_call", ElfVA(continuation), None, ("unknown_import",))


def standard_sites() -> tuple[TraceSite, ...]:
    return (
        site(0x100, 0x100, entry=True),
        site(0x110, 0x100, call(0x112)),
        site(0x112, 0x100, calls=(0x110,)),
        site(0x120, 0x100, Return()),
        site(0x200, 0x200, entry=True),
        site(0x210, 0x200, Return()),
    )


def standard_stream() -> Stream:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, 0x200, 0x800)
    s.entry(0x200, 0x7F8)
    s.ret(0x210, 0x112, 0x7F8)
    s.resume(c, 0x112, 0x800)
    s.ret(0x120, _EXT, 0x1000, 3)
    return s


def wire(events: tuple[Event, ...], identity: TraceIdentity) -> bytes:
    rows = [
        "\t".join(
            (
                "PXTRACE",
                "2",
                identity.binary_sha256,
                identity.plan_sha256,
                identity.invocation_sha256,
                identity.runtime_sha256,
                f"{0x100:016x}",
                f"{0x1000:016x}",
            )
        )
    ]
    for event in events:

        def regs(value: Registers) -> list[str]:
            return [
                f"{getattr(value, name):016x}"
                for name in ("rdi", "rsi", "rdx", "rcx", "rax", "rsp")
            ]

        seq = str(event.sequence)
        if isinstance(event, Entry):
            row = ["E", seq, f"{event.site:016x}", event.origin, *regs(event.registers)]
        elif isinstance(event, CallAttempt):
            row = ["A", seq, f"{event.site:016x}", *regs(event.registers)]
        elif isinstance(event, JumpAttempt):
            row = ["J", seq, f"{event.site:016x}"]
        elif isinstance(event, ReturnAttempt):
            row = [
                "R",
                seq,
                *(
                    f"{n:016x}"
                    for n in (event.site, event.stack_target, event.rsp, event.rax)
                ),
            ]
        elif isinstance(event, Continuation):
            row = [
                "C",
                seq,
                str(event.call),
                f"{event.site:016x}",
                *regs(event.registers),
            ]
        elif isinstance(event, Transfer):
            row = ["T", seq, str(event.attempt), f"{event.next_pc:016x}"]
        else:
            row = ["G", seq, event.reason]
        rows.append("\t".join(row))
    body = ("\n".join(rows) + "\n").encode("ascii")
    return body + f"END\t{len(events)}\t{sha256(body).hexdigest()}\tcomplete\n".encode()


def checked(
    s: Stream | None = None,
    sites: tuple[TraceSite, ...] | None = None,
    *,
    routes: tuple[TransitRoute, ...] = (),
    extra_guards: tuple[GuardInstruction, ...] = (),
    limits: CaptureLimits = CaptureLimits(),
) -> _CheckedCapture:
    s = s or standard_stream()
    sites = sites or standard_sites()
    plan = TracePlan(_D, _D, _D, tuple(x.address for x in sites if x.entry), sites, ())
    transit_entries = {entry for route in routes for entry in route.entries}
    users = tuple(sorted({x.owner for x in sites if x.owner not in transit_entries}))
    request = RequestedScope(ElfVA(0x100), users, ExplicitEntry(_D))
    instructions = []
    dispositions = []
    rule: GuardRule
    disposition: SiteDisposition
    for x in sites:
        route_positions = tuple(
            (r.sha256, r.instruction_path.index(x.address))
            for r in routes
            if x.address in r.instruction_path
        )
        if route_positions:
            rule = TransitInstruction(route_positions)
            disposition = Transit(tuple(r for r, _ in route_positions))
        else:
            rule = (
                PlannedRoles(
                    x.transfer.kind,
                    None,
                    x.transfer.continuation if isinstance(x.transfer, Call) else None,
                )
                if x.transfer
                else Ordinary(x.address)
            )
            disposition = User(x.owner)
        instructions.append(
            GuardInstruction(x.address, x.owner, x.witness_hex, (), rule)
        )
        dispositions.append((x.address, disposition))
    scope = ScopeSelection(
        "main-window-six-v1",
        _D,
        plan.sha256,
        _D,
        _D,
        _D,
        request,
        ElfVA(0x100),
        users,
        tuple(dispositions),
        (),
        routes,
        (*instructions, *extra_guards),
        (),
        (),
        limits,
        plan.registers,
    )
    identity = TraceIdentity(_D, plan.sha256, _D, _D)
    raw = wire(tuple(s.events), identity)
    trace = parse_trace_wire(raw, identity)
    targets = tuple(
        (
            e.sequence,
            InternalTarget(ElfVA(e.next_pc))
            if 0x100 <= e.next_pc < 0x1000
            else ExternalTarget(e.next_pc),
        )
        for e in trace.events
        if isinstance(e, Transfer)
    )
    mapped = MappedObservation(trace, plan, 0, _D, targets)
    root = s.events[0]
    root_rsp = root.registers.rsp if isinstance(root, Entry) else 0x1000
    last = next((e for e in reversed(s.events) if isinstance(e, ReturnAttempt)), None)
    root_exit = ReturnExit(
        last.sequence if last else 0, last.sequence + 1 if last else 1, root_rsp + 8
    )
    receipt = CaptureReceipt(
        identity,
        trace.sha256,
        scope.sha256,
        _D,
        RootAnchor(0, ElfVA(0x100), _EXT + 1, root_rsp, _EXT),
        root_exit,
        _D,
        True,
        len(trace.events),
        100,
        100,
        70,
        20,
        10,
        0,
        "complete",
    )
    return _CheckedCapture(
        mapped,
        scope,
        receipt,
        _D,
        _D,
        ExternalTarget(_EXT + 1),
        ExternalTarget(_EXT),
        len(raw),
        1000,
        Exited(0),
        _D,
    )


def rejected(value: _CheckedCapture, code: str | None = None) -> Rejected:
    result = admit_frames(value)
    assert isinstance(result, Rejected), result
    if code:
        assert result.rejection.code == code
    assert len(result.rejection.detail) <= 512
    return result


def admitted(value: _CheckedCapture) -> Admitted:
    result = admit_frames(value)
    assert isinstance(result, Admitted), result
    return result


def test_call_stack_changes_and_exact_evidence() -> None:
    value = checked()
    before = repr(value)
    result = admitted(value)
    assert repr(value) == before
    root, child = result.tree.frames
    assert root.id == 0 and child.id == 1 and root.children == (1,)
    assert child.parent == 0 and child.pre_call_rsp == 0x800
    assert child.entry_rsp == 0x7F8 and root.entry_rsp == 0x1000
    assert isinstance(child.end, Returned) and child.end.result_bits == 42
    assert child.end.return_attempt.sequence == 4
    assert child.end.transfer.sequence == 5 and child.end.continuation.sequence == 6
    assert isinstance(root.end, RootReturned)
    assert result.tree.claim == "requested-main-activation"
    assert result.tree.provider_identity == "unknown"
    assert result.tree.receipt_sha256 == _D
    assert admit_frames(value) == result
    assert {r.register for r in local_registers(value)} == {
        "rdi",
        "rsi",
        "rdx",
        "rcx",
        "rax",
        "rsp",
    }
    assert all(
        r.meaning == "raw-pre-instruction-bits" and r.width == 64
        for r in local_registers(value)
    )
    with pytest.raises(FrozenInstanceError):
        setattr(value.receipt, "guard_passed", False)


@pytest.mark.parametrize("register", ["rdi", "rsi", "rdx", "rcx", "rax", "rsp"])
def test_near_call_snapshot_mismatch(register: str) -> None:
    s = standard_stream()
    entry = s.events[3]
    assert isinstance(entry, Entry)
    s.events[3] = changed(
        entry, registers=changed(entry.registers, **{register: 0x800})
    )
    rejected(checked(s), "entry_rsp" if register == "rsp" else "entry_registers")


@pytest.mark.parametrize(
    "index,field,value,code",
    [
        (4, "rsp", 0x1000, "return_rsp"),
        (4, "stack_target", 0x120, "nonlocal_return"),
        (7, "rsp", 0x800, "return_rsp"),
        (7, "stack_target", _EXT + 8, "root_anchor"),
    ],
)
def test_return_anchors(index: int, field: str, value: int, code: str) -> None:
    s = standard_stream()
    s.events[index] = changed(s.events[index], **{field: value})
    if field == "stack_target":
        s.events[index + 1] = changed(s.events[index + 1], next_pc=value)
    rejected(checked(s), code)


@pytest.mark.parametrize(
    "register,value,code",
    [
        ("rsp", 0x7F8, "continuation"),
        ("rax", 43, "return_value"),
    ],
)
def test_continuation_checks(register: str, value: int, code: str) -> None:
    s = standard_stream()
    event = s.events[6]
    assert isinstance(event, Continuation)
    s.events[6] = changed(
        event, registers=changed(event.registers, **{register: value})
    )
    rejected(checked(s), code)


def recursive(depth: int) -> _CheckedCapture:
    sites = (
        *standard_sites()[:4],
        site(0x200, 0x200, entry=True),
        site(0x210, 0x200, call(0x212)),
        site(0x212, 0x200, calls=(0x210,)),
        site(0x220, 0x200, Return()),
    )
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    calls = []
    for level in range(depth):
        rsp = 0x800 - level * 32
        calls.append(s.call(0x110 if level == 0 else 0x210, 0x200, rsp))
        s.entry(0x200, rsp - 8)
    for level in reversed(range(depth)):
        rsp = 0x800 - level * 32
        continuation = 0x112 if level == 0 else 0x212
        s.ret(0x220, continuation, rsp - 8)
        s.resume(calls[level], continuation, rsp)
    s.ret(0x120, _EXT, 0x1000)
    return checked(s, sites)


def test_recursion_same_continuation_addresses() -> None:
    value = recursive(4)
    frames = admitted(value).tree.frames
    assert [f.id for f in frames] == list(range(5))
    assert [f.parent for f in frames] == [None, 0, 1, 2, 3]
    assert [f.kind for f in frames[1:]] == [UserFunction(ElfVA(0x200))] * 4
    events = list(value.mapped.trace.events)
    continuations = [
        e for e in events if isinstance(e, Continuation) and e.site == 0x212
    ]
    first, second = continuations[:2]
    events[first.sequence] = changed(first, call=second.call)
    events[second.sequence] = changed(second, call=first.call)
    trace = changed(value.mapped.trace, events=tuple(events))
    rejected(changed(value, mapped=changed(value.mapped, trace=trace)), "continuation")


@pytest.mark.parametrize("depth,passes", [(63, True), (64, False)])
def test_total_frame_bound(depth: int, passes: bool) -> None:
    value = recursive(depth)
    if passes:
        assert len(admitted(value).tree.frames) == 64
    else:
        assert not rejected(value, "limit").local


@pytest.mark.parametrize(
    "shared", ["entry-call", "entry-return", "continuation-call", "continuation-return"]
)
def test_shared_site_roles(shared: str) -> None:
    sites: tuple[TraceSite, ...]
    s = Stream()
    if shared == "entry-return":
        sites = (site(0x100, 0x100, Return(), entry=True),)
        s.entry(0x100, 0x1000, external=True)
        s.ret(0x100, _EXT, 0x1000, _REG.rax)
    else:
        call_site = 0x100 if shared == "entry-call" else 0x110
        continuation_transfer = (
            call(0x114)
            if shared == "continuation-call"
            else Return()
            if shared == "continuation-return"
            else None
        )
        sites = tuple(
            x for x in standard_sites() if x.address not in (0x100, 0x110, 0x112)
        )
        sites = (
            site(0x100, 0x100, call(0x112) if call_site == 0x100 else None, entry=True),
            *(() if call_site == 0x100 else (site(0x110, 0x100, call(0x112)),)),
            site(0x112, 0x100, continuation_transfer, calls=(call_site,)),
            *sites,
        )
        s.entry(0x100, 0x1000, external=True)
        rsp = 0x1000 if shared in ("entry-call", "continuation-return") else 0x800
        c = s.call(call_site, 0x200, rsp)
        s.entry(0x200, rsp - 8)
        s.ret(0x210, 0x112, rsp - 8)
        s.resume(c, 0x112, rsp)
        if shared == "continuation-call":
            sites += (site(0x114, 0x100, calls=(0x112,)),)
            regs = changed(_REG, rax=42)
            c = s.call(0x112, 0x200, rsp, regs)
            s.entry(0x200, rsp - 8, registers=regs)
            s.ret(0x210, 0x114, rsp - 8)
            s.resume(c, 0x114, rsp)
        s.ret(0x112 if shared == "continuation-return" else 0x120, _EXT, 0x1000)
    value = checked(s, sites)
    admitted(value)
    if shared == "entry-call":
        index = 1
    elif shared == "entry-return":
        index = 1
    else:
        index = 7
    event = s.events[index]
    if isinstance(event, CallAttempt):
        s.events[index] = changed(event, registers=changed(event.registers, rax=999))
    else:
        assert isinstance(event, ReturnAttempt)
        s.events[index] = changed(event, rax=999)
    failure = rejected(checked(s, sites), "entry_registers")
    prior = 0 if shared.startswith("entry") else 6
    assert all(x.event.sequence not in (prior, index) for x in failure.local)


def test_continuation_entry_call_uses_one_snapshot() -> None:
    sites = (
        site(0x100, 0x100, call(0x102), entry=True, calls=(0x110,)),
        site(0x102, 0x100, calls=(0x100,)),
        site(0x110, 0x100, call(0x100)),
        site(0x120, 0x100, Return()),
        site(0x200, 0x200, entry=True),
        site(0x210, 0x200, Return()),
    )
    s = Stream()
    s.entry(0x100, 0x1000, external=True)

    def leaf(at: int, continuation: int, regs: Registers) -> None:
        c = s.call(at, 0x200, 0x1000, regs)
        s.entry(0x200, 0xFF8, registers=regs)
        s.ret(0x210, continuation, 0xFF8)
        s.resume(c, continuation, 0x1000)

    leaf(0x100, 0x102, _REG)
    leaf(0x110, 0x100, _REG)
    shared_entry = s.add(Entry(0, 0x100, "unknown", changed(_REG, rax=42)))
    leaf(0x100, 0x102, changed(_REG, rax=42))
    s.ret(0x120, _EXT, 0x1000)
    assert len(admitted(checked(s, sites)).tree.frames) == 4
    entry = s.events[shared_entry]
    assert isinstance(entry, Entry)
    s.events[shared_entry] = changed(entry, registers=changed(entry.registers, rdi=999))
    result = rejected(checked(s, sites), "entry_registers")
    assert all(
        o.event.sequence not in (shared_entry - 1, shared_entry, shared_entry + 1)
        for o in result.local
    )


def external_stream(target: int = _EXT + 100) -> Stream:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, target, 0x800)
    s.resume(c, 0x112, 0x800)
    s.ret(0x120, _EXT, 0x1000)
    return s


def test_external_leaf_has_no_invented_entry_or_provider() -> None:
    frames = admitted(checked(external_stream())).tree.frames
    leaf = frames[1]
    assert leaf.entry is None and leaf.entry_rsp is None
    assert isinstance(leaf.kind, ExternalExcursion)
    assert leaf.kind.request is None and leaf.kind.first_external_pc == _EXT + 100
    assert isinstance(leaf.end, ExternalResumed)


@pytest.mark.parametrize("kind", ["callback", "wrong-continuation", "user-return"])
def test_external_reentry(kind: str) -> None:
    s = external_stream()
    if kind == "callback":
        s.events[3] = Entry(3, 0x200, "unknown", _REG)
    elif kind == "wrong-continuation":
        s.events[3] = changed(s.events[3], site=0x120)
    else:
        s.events[3] = ReturnAttempt(3, 0x210, 0x112, 0x7F8, 42)
        s.events.insert(4, Transfer(4, 3, 0x112))
        s.events = [changed(e, sequence=i) for i, e in enumerate(s.events)]
        s.events[-1] = changed(s.events[-1], attempt=5)
    rejected(checked(s))


def route_fixture() -> tuple[Stream, tuple[TraceSite, ...], TransitRoute]:
    route = TransitRoute(
        ElfVA(0x110),
        _D,
        (ElfVA(0x300), ElfVA(0x310)),
        (ElfVA(0x300), ElfVA(0x302), ElfVA(0x310), ElfVA(0x314)),
        ElfVA(0x314),
        ElfVA(0x900),
        ImportId("fwrite", None, False),
    )
    sites = (
        *standard_sites(),
        site(0x300, 0x300, entry=True),
        site(0x310, 0x310, entry=True),
        site(0x314, 0x310, Jump()),
    )
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, 0x300, 0x800)
    s.entry(0x300, 0x7F8)
    s.add(Entry(0, 0x310, "unknown", changed(_REG, rsp=0x7F8)))
    s.jump(0x314, _EXT + 100)
    s.resume(c, 0x112, 0x800)
    s.ret(0x120, _EXT, 0x1000)
    return s, sites, route


def test_transit_route_is_one_external_leaf() -> None:
    s, sites, route = route_fixture()
    tree = admitted(checked(s, sites, routes=(route,))).tree
    assert len(tree.frames) == 2
    kind = tree.frames[1].kind
    assert isinstance(kind, ExternalExcursion)
    assert kind.request == route.request
    assert [r.sequence for r in kind.transit] == [3, 4, 5, 6]
    assert tree.frames[1].entry is None


@pytest.mark.parametrize(
    "mutation",
    ["skip-hop", "wrong-hop", "origin", "register", "resolver", "terminal", "bypass"],
)
def test_bad_transit(mutation: str) -> None:
    s, sites, route = route_fixture()
    if mutation == "skip-hop":
        s.events[4] = JumpAttempt(4, 0x314)
        # A structurally complete skipped hop uses the remaining terminal J/T.
        del s.events[4]
        s.events = [changed(e, sequence=i) for i, e in enumerate(s.events)]
        s.events[5] = changed(s.events[5], attempt=4)
        s.events[-1] = changed(s.events[-1], attempt=len(s.events) - 2)
    elif mutation == "wrong-hop":
        s.events[4] = changed(s.events[4], site=0x312)
    elif mutation == "origin":
        s.events[4] = changed(s.events[4], origin="call")
    elif mutation == "register":
        s.events[4] = changed(s.events[4], registers=changed(_REG, rsp=0x7F8, rdi=99))
    elif mutation == "resolver":
        s.events[6] = changed(s.events[6], next_pc=0x318)
    elif mutation == "terminal":
        s.events[5] = changed(s.events[5], site=0x312)
    else:
        s = external_stream()
    rejected(checked(s, sites, routes=(route,)))


def test_direct_got_route_retains_only_request() -> None:
    route = TransitRoute(
        ElfVA(0x110),
        _D,
        (),
        (),
        ElfVA(0x110),
        ElfVA(0x900),
        ImportId("fwrite", "GLIBC_2.2.5", False),
    )
    leaf = admitted(checked(external_stream(), routes=(route,))).tree.frames[1]
    assert isinstance(leaf.kind, ExternalExcursion)
    assert leaf.kind.request == route.request and leaf.kind.transit == ()


@pytest.mark.parametrize(
    "target,passes",
    [(0x118, True), (0x200, False), (0x119, False), (_EXT + 100, False)],
)
def test_indirect_jump_exact_owner_instruction(target: int, passes: bool) -> None:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    s.jump(0x110, target)
    s.ret(0x120, _EXT, 0x1000)
    sites = (
        site(0x100, 0x100, entry=True),
        site(0x110, 0x100, Jump()),
        site(0x120, 0x100, Return()),
        site(0x200, 0x200, entry=True),
    )
    guard = GuardInstruction(
        ElfVA(0x118), ElfVA(0x100), "90", (), Ordinary(ElfVA(0x120))
    )
    value = checked(s, sites, extra_guards=(guard,))
    if passes:
        assert len(admitted(value).tree.frames) == 1
    else:
        rejected(value, "tail_candidate")


def test_jump_to_entry_is_checkpoint_not_recursion() -> None:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    s.jump(0x110, 0x100)
    s.add(Entry(0, 0x100, "unknown", _REG))
    s.ret(0x120, _EXT, 0x1000)
    sites = (
        site(0x100, 0x100, entry=True),
        site(0x110, 0x100, Jump()),
        site(0x120, 0x100, Return()),
    )
    assert len(admitted(checked(s, sites)).tree.frames) == 1
    s.events[3] = changed(s.events[3], origin="call")
    rejected(checked(s, sites), "origin")


def test_guarded_local_branch_to_entry_is_checkpoint() -> None:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    s.add(Entry(0, 0x100, "unknown", _REG))
    s.ret(0x120, _EXT, 0x1000)
    guard = GuardInstruction(
        ElfVA(0x118), ElfVA(0x100), "ebe6", (), LocalDirect(ElfVA(0x100))
    )
    assert len(admitted(checked(s, extra_guards=(guard,))).tree.frames) == 1
    rejected(checked(s), "duplicate_event")


@pytest.mark.parametrize("target", [0x201, 0x300, 0x800])
def test_call_to_interior_or_omitted_target(target: int) -> None:
    s = standard_stream()
    s.events[2] = changed(s.events[2], next_pc=target)
    rejected(checked(s), "call_target")


@pytest.mark.parametrize(
    "change",
    [
        "saved-target",
        "predecessor",
        "entry-sequence",
        "site",
        "next-rsp",
        "return-sequence",
        "transfer-sequence",
    ],
)
def test_root_receipt_is_independent(change: str) -> None:
    value = checked()
    anchor = value.receipt.root
    exit_record = value.receipt.root_exit
    assert isinstance(exit_record, ReturnExit)
    if change == "saved-target":
        anchor = changed(anchor, stack_target=_EXT + 2)
        value = changed(value, root_stack_target=ExternalTarget(_EXT + 2))
    elif change == "predecessor":
        anchor = changed(anchor, predecessor_pc=0x100)
    elif change == "entry-sequence":
        anchor = changed(anchor, entry_sequence=1)
    elif change == "site":
        anchor = changed(anchor, site=ElfVA(0x200))
    elif change == "next-rsp":
        exit_record = changed(exit_record, next_rsp=anchor.rsp)
    elif change == "return-sequence":
        exit_record = changed(exit_record, return_sequence=4)
    else:
        exit_record = changed(exit_record, transfer_sequence=5)
    rejected(
        changed(
            value, receipt=changed(value.receipt, root=anchor, root_exit=exit_record)
        ),
        "root_anchor",
    )


@pytest.mark.parametrize(
    "field",
    [
        "raw_trace_sha256",
        "scope_sha256",
        "runtime_manifest_sha256",
        "guard_profile_sha256",
    ],
)
def test_receipt_identities_do_not_salvage(field: str) -> None:
    value = checked()
    value = changed(value, receipt=changed(value.receipt, **{field: "e" * 64}))
    assert not rejected(value, "receipt_identity").local
    assert not local_registers(value)


@pytest.mark.parametrize(
    "field,value",
    [("guard_passed", False), ("omitted_active_hits", 1), ("emitted_events", 2)],
)
def test_incomplete_capture_has_no_local_facts(field: str, value: object) -> None:
    capture = checked()
    capture = changed(capture, receipt=changed(capture.receipt, **{field: value}))
    assert not rejected(capture, "capture_incomplete").local


@pytest.mark.parametrize(
    "field,value",
    [
        ("execution_callbacks", 1_000_001),
        ("translated_instructions", 1_000_001),
        ("selected_instruction_callbacks", -1),
        ("outside_window_callbacks", 21),
        ("opaque_external_callbacks", -1),
    ],
)
def test_counter_bounds(field: str, value: int) -> None:
    capture = checked()
    capture = changed(capture, receipt=changed(capture.receipt, **{field: value}))
    assert not rejected(capture, "limit").local


@pytest.mark.parametrize(
    "field,value", [("raw_trace_bytes", 8 * 1024 * 1024 + 1), ("receipt_bytes", 65537)]
)
def test_saved_byte_bounds(field: str, value: int) -> None:
    assert not rejected(changed(checked(), **{field: value}), "limit").local


@pytest.mark.parametrize(
    "field",
    [
        "events",
        "frames",
        "execution_callbacks",
        "translated_instructions",
        "snapshot_bytes",
    ],
)
def test_caller_cannot_raise_limits(field: str) -> None:
    defaults = CaptureLimits()
    limits = changed(defaults, **{field: getattr(defaults, field) + 1})
    assert not rejected(checked(limits=limits), "limit").local


def test_lower_event_bound() -> None:
    assert not rejected(
        checked(limits=changed(CaptureLimits(), events=8)), "limit"
    ).local


def test_nonreturn_is_always_unsupported() -> None:
    value = checked(external_stream())
    value = changed(
        value, receipt=changed(value.receipt, root_exit=ProcessExit(_D, 1, _D))
    )
    assert not rejected(value, "nonreturn_contract").local


@pytest.mark.parametrize("end", [1, 3, 4, 7])
def test_complete_footer_does_not_close_open_frames(end: int) -> None:
    s = standard_stream()
    s.events = s.events[:end]
    assert rejected(checked(s)).rejection.code in ("open_frame", "missing_event")


def test_wrong_root_and_origin() -> None:
    s = standard_stream()
    s.events[0] = changed(s.events[0], site=0x200)
    rejected(checked(s), "root_missing")
    s.events[0] = changed(s.events[0], site=0x100, origin="unknown")
    rejected(checked(s), "origin")


def test_second_root_is_rejected() -> None:
    s = standard_stream()
    s.entry(0x100, 0x1000, external=True)
    rejected(checked(s), "root_reentry")


def test_targets_use_transfer_sequence_not_attempt_index() -> None:
    value = checked()
    assert [seq for seq, _ in value.mapped.targets] == [2, 5, 8]
    bad = tuple((seq - 1, target) for seq, target in value.mapped.targets)
    assert not rejected(
        changed(value, mapped=changed(value.mapped, targets=bad)), "mapping_invalid"
    ).local


def test_frame_failure_preserves_only_local_raw_values() -> None:
    s = standard_stream()
    s.events[4] = changed(s.events[4], rsp=0x1000)
    value = checked(s)
    failure = rejected(value, "return_rsp")
    assert failure.local == local_registers(value)
    assert {x.event.sequence for x in failure.local} == {0, 1, 3, 6}
    assert not hasattr(failure, "tree")
    assert all(
        not hasattr(x, "parent") and not hasattr(x, "argument") for x in failure.local
    )


def test_missing_return_cannot_be_repaired_by_continuation() -> None:
    s = standard_stream()
    del s.events[4:6]
    s.events = [changed(e, sequence=i) for i, e in enumerate(s.events)]
    s.events[-1] = changed(s.events[-1], attempt=5)
    rejected(checked(s), "event_order")


def test_structural_wire_rejects_missing_transfer() -> None:
    s = standard_stream()
    del s.events[2]
    s.events = [changed(e, sequence=i) for i, e in enumerate(s.events)]
    with pytest.raises(TraceWireError):
        checked(s)


def test_scope_serialization_bound_remains_enforced() -> None:
    with pytest.raises(MappingError):
        checked(limits=changed(CaptureLimits(), scope_bytes=1))


def test_continuation_entry_return_shared_snapshot() -> None:
    """Check a synthetic role bundle, without a static reachability claim."""
    sites = tuple(x for x in standard_sites() if x.address != 0x112)
    sites += (site(0x112, 0x100, Return(), entry=True, calls=(0x110,)),)
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, 0x200, 0x1000)
    s.entry(0x200, 0xFF8)
    s.ret(0x210, 0x112, 0xFF8)
    s.resume(c, 0x112, 0x1000)
    s.add(Entry(0, 0x112, "unknown", changed(_REG, rax=42)))
    s.ret(0x112, _EXT, 0x1000)
    assert len(admitted(checked(s, sites)).tree.frames) == 2
    s.events[8] = changed(s.events[8], rax=999)
    failure = rejected(checked(s, sites), "entry_registers")
    assert all(o.event.sequence not in (6, 7) for o in failure.local)


def reindexed(events: list[Event]) -> Stream:
    result = Stream()
    positions = {e.sequence: i for i, e in enumerate(events)}
    for event in events:
        if isinstance(event, Transfer):
            event = changed(event, attempt=positions.get(event.attempt, 9999))
        elif isinstance(event, Continuation):
            event = changed(event, call=positions.get(event.call, 9999))
        result.add(event)
    return result


@pytest.mark.parametrize("removed", range(9))
def test_each_missing_event_rejects_without_alignment(removed: int) -> None:
    s = standard_stream()
    admitted(checked(s))
    del s.events[removed]
    s = reindexed(s.events)
    try:
        value = checked(s)
    except TraceWireError:
        return
    assert not rejected(value).local


@pytest.mark.parametrize("index", range(9))
def test_each_duplicate_event_rejects(index: int) -> None:
    s = standard_stream()
    admitted(checked(s))
    duplicate = changed(s.events[index], sequence=9000)
    s.events.insert(index + 1, duplicate)
    s = reindexed(s.events)
    try:
        value = checked(s)
    except TraceWireError:
        return
    rejected(value)


def test_return_before_continuation_rejects() -> None:
    sites = tuple(x for x in standard_sites() if x.address != 0x112)
    sites += (site(0x112, 0x100, Return(), calls=(0x110,)),)
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, 0x200, 0x1000)
    s.entry(0x200, 0xFF8)
    s.ret(0x210, 0x112, 0xFF8)
    s.resume(c, 0x112, 0x1000)
    s.ret(0x112, _EXT, 0x1000)
    admitted(checked(s, sites))
    events = s.events[:6] + s.events[7:] + [s.events[6]]
    rejected(checked(reindexed(events), sites), "missing_event")


def test_call_before_continuation_rejects() -> None:
    sites = tuple(x for x in standard_sites() if x.address != 0x112)
    sites += (
        site(0x112, 0x100, call(0x114), calls=(0x110,)),
        site(0x114, 0x100, calls=(0x112,)),
    )
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x110, _EXT + 100, 0x800)
    s.resume(c, 0x112, 0x800)
    c2 = s.call(0x112, _EXT + 100, 0x800, changed(_REG, rax=42))
    s.resume(c2, 0x114, 0x800)
    s.ret(0x120, _EXT, 0x1000)
    admitted(checked(s, sites))
    events = s.events[:3] + s.events[4:6] + [s.events[3]] + s.events[6:]
    rejected(checked(reindexed(events), sites), "external_reentry")


def test_monotonic_ids_and_bound_apply_to_closed_frames() -> None:
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    for _ in range(63):
        c = s.call(0x110, _EXT + 100, 0x800)
        s.resume(c, 0x112, 0x800)
    s.ret(0x120, _EXT, 0x1000)
    frames = admitted(checked(s)).tree.frames
    assert [f.id for f in frames] == list(range(64))
    assert frames[0].children == tuple(range(1, 64))
    del s.events[-2:]
    c = s.call(0x110, _EXT + 100, 0x800)
    s.resume(c, 0x112, 0x800)
    s.ret(0x120, _EXT, 0x1000)
    assert not rejected(checked(s), "limit").local


@pytest.mark.parametrize("bias", [0x10000, 0x100000000])
def test_runtime_bias_keeps_elf_sites_and_runtime_continuations_separate(
    bias: int,
) -> None:
    value = checked()
    events: list[Event] = []
    for event in value.mapped.trace.events:
        if isinstance(event, Transfer) and 0x100 <= event.next_pc < 0x1000:
            event = changed(event, next_pc=event.next_pc + bias)
        elif isinstance(event, ReturnAttempt) and 0x100 <= event.stack_target < 0x1000:
            event = changed(event, stack_target=event.stack_target + bias)
        events.append(event)
    trace = changed(
        value.mapped.trace,
        events=tuple(events),
        code_start=0x100 + bias,
        code_end=0x1000 + bias,
    )
    mapped = changed(value.mapped, trace=trace, bias=bias)
    admitted(changed(value, mapped=mapped))
    events[4] = changed(events[4], stack_target=0x112)
    trace = changed(trace, events=tuple(events))
    rejected(changed(value, mapped=changed(mapped, trace=trace)), "nonlocal_return")


def test_near_call_underflow_and_root_return_overflow() -> None:
    s = standard_stream()
    s.events[1] = changed(s.events[1], registers=changed(_REG, rsp=7))
    rejected(checked(s), "entry_rsp")
    s = Stream()
    rsp = (1 << 64) - 1
    s.entry(0x100, rsp, external=True)
    s.ret(0x120, _EXT, rsp)
    rejected(checked(s), "root_anchor")


@pytest.mark.parametrize(
    "field",
    [
        "full_plan_sha256",
        "binary_sha256",
        "lift_sha256",
        "address_proof_sha256",
        "registers",
    ],
)
def test_scope_identity_failure_has_no_local_values(field: str) -> None:
    value = checked()
    replacement: object = (("r8", 64),) if field == "registers" else "e" * 64
    selection = changed(value.selection, **{field: replacement})
    receipt = changed(value.receipt, scope_sha256=selection.sha256)
    assert not rejected(
        changed(value, selection=selection, receipt=receipt), "scope_identity"
    ).local


def test_changed_outcome_does_not_salvage_values() -> None:
    assert not rejected(
        changed(checked(), full_outcome_sha256="e" * 64), "outcome_mismatch"
    ).local


def test_scope_bound_failure_returns_typed_rejection() -> None:
    value = checked()
    scope = changed(value.selection, limits=changed(CaptureLimits(), scope_bytes=1))
    assert not rejected(changed(value, selection=scope), "limit").local


def test_root_external_classification_is_separate_from_anchor_words() -> None:
    value = checked()
    assert not rejected(
        changed(value, root_predecessor=InternalTarget(ElfVA(0x100))), "root_anchor"
    ).local
    assert not rejected(
        changed(value, root_stack_target=InternalTarget(ElfVA(0x100))), "root_anchor"
    ).local


def test_plan_gap_is_preserved_without_a_typed_claim() -> None:
    value = checked()
    assert value.mapped.plan.sites[1].transfer == call(0x112)
    frame = admitted(value).tree.frames[1]
    assert frame.kind == UserFunction(ElfVA(0x200))
    assert not hasattr(frame, "prototype")
    assert not hasattr(frame, "provider")


def test_nonempty_contract_table_rejects_before_reduction() -> None:
    value = checked()
    scope = changed(value.selection, contracts=("untrusted-contract",))
    receipt = changed(value.receipt, scope_sha256=scope.sha256)
    assert not rejected(
        changed(value, selection=scope, receipt=receipt), "nonreturn_contract"
    ).local


def test_exact_lower_limits_accept_at_boundary() -> None:
    value = checked(
        limits=changed(
            CaptureLimits(),
            frames=2,
            events=9,
            execution_callbacks=100,
            translated_instructions=100,
        )
    )
    assert len(admitted(value).tree.frames) == 2
    limits = changed(value.selection.limits, frames=1)
    scope = changed(value.selection, limits=limits)
    receipt = changed(value.receipt, scope_sha256=scope.sha256)
    assert not rejected(changed(value, selection=scope, receipt=receipt), "limit").local


def test_wrong_active_owner_rejects() -> None:
    s = standard_stream()
    s.events[4] = changed(s.events[4], site=0x120)
    failure = rejected(checked(s), "owner")
    assert failure.local


def test_gap_and_noncomplete_footer_disable_local_values() -> None:
    value = checked()
    trace = changed(value.mapped.trace, status="gap")
    assert not rejected(
        changed(value, mapped=changed(value.mapped, trace=trace)), "capture_incomplete"
    ).local


@pytest.mark.parametrize("missing", [0, 1, 3, 4])
def test_entry_call_shared_roles_cannot_be_omitted(missing: int) -> None:
    sites = tuple(x for x in standard_sites() if x.address not in (0x100, 0x110, 0x112))
    sites += (
        site(0x100, 0x100, call(0x112), entry=True),
        site(0x112, 0x100, calls=(0x100,)),
    )
    s = Stream()
    s.entry(0x100, 0x1000, external=True)
    c = s.call(0x100, 0x200, 0x1000)
    s.entry(0x200, 0xFF8)
    s.ret(0x210, 0x112, 0xFF8)
    s.resume(c, 0x112, 0x1000)
    s.ret(0x120, _EXT, 0x1000)
    admitted(checked(s, sites))
    del s.events[missing]
    try:
        value = checked(reindexed(s.events), sites)
    except TraceWireError:
        return
    rejected(value)
