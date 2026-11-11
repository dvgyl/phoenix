"""Static controls do not execute target instructions."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_recovery_u1 import evidence, fixture, loc, op, operand

from phoenix.lift.index import LiftIndex
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.observe.plan import Call, TracePlan, build_trace_plan
from phoenix.observe.scope import (
    CaptureLimits,
    ExactSignal,
    ExplicitEntry,
    LiftMain,
    LocalBranchGuard,
    LocalConditional,
    LocalDirect,
    Omitted,
    Ordinary,
    Reject,
    Rejection,
    RequestedScope,
    ScopeSelection,
    TerminationContract,
    Transit,
    TransitInstruction,
    User,
    policy_implementation_sha256,
    select_scope,
)
from phoenix.recover.addresses import AddressProof, ElfVA


def inputs(
    binary: bytes, document: dict[str, Any], delta: int = 0x100000
) -> tuple[LiftIndex, AddressProof, TracePlan, RequestedScope]:
    lift, _, proof = evidence(binary, document, delta)
    plan = build_trace_plan(binary, lift, proof)
    main = proof.to_elf(lift.main)
    request = RequestedScope(main, (main,), LiftMain(lift.lift_sha256, main))
    return lift, proof, plan, request


def compile_scope(
    binary: bytes, document: dict[str, Any], delta: int = 0x100000
) -> ScopeSelection:
    lift, proof, plan, request = inputs(binary, document, delta)
    result = select_scope(binary, lift, proof, plan, request)
    assert isinstance(result, ScopeSelection), result
    return result


def control(
    data: bytes,
    opcode: str | None,
    target: int = 0x10010A,
    *,
    space: str = "ram",
    width: int = 8,
) -> tuple[bytes, dict[str, Any]]:
    binary, document = fixture()
    image = bytearray(binary)
    image[0x105 : 0x105 + len(data)] = data
    last = max(0x10A, 0x105 + len(data))
    image[last] = 0xC3
    function = document["functions"][0]
    function["ranges"][0]["end"] = loc(0x100000 + last)
    template = deepcopy(function["instructions"][1])
    branch = deepcopy(template)
    branch["size"] = len(data)
    arguments = [dict(operand(target, space), size=width)]
    if opcode == "CBRANCH":
        arguments.append(dict(operand(0, "register"), size=1))
    branch["pcode"] = [] if opcode is None else [op(0x100105, opcode, arguments)]
    instructions = [function["instructions"][0], branch]
    for address in range(0x105 + len(data), last):
        image[address] = 0x90
        ordinary = deepcopy(template)
        ordinary.update(address=loc(0x100000 + address), size=1, pcode=[])
        instructions.append(ordinary)
    template["address"] = loc(0x100000 + last)
    template["pcode"] = [op(0x100000 + last, "RETURN", [operand(0, "register")])]
    instructions.append(template)
    function["instructions"] = instructions
    return bytes(image), document


def guard(scope: ScopeSelection, address: int = 0x105) -> Any:
    return next(g.rule for g in scope.guard_instructions if g.address == address)


@pytest.mark.parametrize("name", ("elf", "file_offset", "ghidra", "owner"))
def test_proof_address_fields_require_exact_integer_types(name: str) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    first = proof.witnesses[0]
    changes: dict[str, Any] = {name: float(getattr(first, name))}
    alias = replace(first, **changes)
    supplied = replace(proof, witnesses=(alias, *proof.witnesses[1:]))
    assert isinstance(select_scope(binary, lift, supplied, plan, request), Rejection)


def test_lift_main_evidence_rejects_a_float_address_alias() -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    alias: Any = float(request.root)
    supplied = replace(request, root_evidence=LiftMain(lift.lift_sha256, alias))
    result = select_scope(binary, lift, proof, plan, supplied)
    assert isinstance(result, Rejection) and result.code == "scope_root"


@pytest.mark.parametrize("data", (b"\xc7\xf8\xf5\xff\xff\xff", b"\x66\xc7\xf8\xfa\xff"))
def test_transaction_abort_branch_never_gets_an_ordinary_guard(data: bytes) -> None:
    binary, document = control(data, None)
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize("indirect", (False, True))
def test_reported_external_owner_call_to_root_rejects_selection(indirect: bool) -> None:
    binary, document = fixture()
    image = bytearray(binary)
    function = deepcopy(document["functions"][0])
    start = 0x100180
    target = 0x100100
    data = (
        b"\xff\xd0"
        if indirect
        else b"\xe8" + (target - start - 5).to_bytes(4, "little", signed=True)
    )
    end = start + len(data)
    function.update(entry=loc(start), ranges=[{"start": loc(start), "end": loc(end)}])
    function["instructions"][0].update(
        address=loc(start),
        size=len(data),
        pcode=[
            op(
                start,
                "CALLIND" if indirect else "CALL",
                [operand(0, "register") if indirect else operand(target)],
            )
        ],
    )
    function["instructions"][1].update(
        address=loc(end), pcode=[op(end, "RETURN", [operand(0, "register")])]
    )
    image[0x180 : 0x181 + len(data)] = data + b"\xc3"
    document["functions"].append(function)
    document["call_edges"].append(
        {
            "caller": loc(start),
            "site": loc(start),
            "target": loc(target),
            "kind": "COMPUTED_CALL" if indirect else "UNCONDITIONAL_CALL",
            "indirect": indirect,
        }
    )
    lift, proof, plan, request = inputs(bytes(image), document)
    result = select_scope(bytes(image), lift, proof, plan, request)
    assert isinstance(result, Rejection) and result.code == "scope_root"


@pytest.mark.parametrize("base", [0, 0x400000])
@pytest.mark.parametrize("delta", [0x100000, 0x200000])
def test_exact_partition_routes_roles_and_serialization(base: int, delta: int) -> None:
    binary, document = fixture(base=base, delta=delta)
    lift, proof, plan, request = inputs(binary, document, delta)
    original = plan.to_bytes()
    result = select_scope(binary, lift, proof, plan, request)
    assert isinstance(result, ScopeSelection), result
    assert plan.to_bytes() == original
    assert result.full_plan_sha256 == plan.sha256
    assert result.root == base + 0x100 and result.users == (base + 0x100,)
    partition = dict(result.dispositions)
    assert isinstance(partition[ElfVA(base + 0x100)], User)
    assert isinstance(partition[ElfVA(base + 0x105)], User)
    assert isinstance(partition[ElfVA(base + 0x140)], Transit)
    assert len(partition) == len(plan.sites) and not result.omitted
    assert result.routes[0].entries == (base + 0x140,)
    assert result.routes[0].instruction_path == (base + 0x140,)
    assert result.routes[0].terminal == base + 0x140
    assert result.routes[0].slot == base + 0x2500
    assert result.routes[0].request.symbol == "fwrite"
    assert result.routes[0].request.needed_library is None
    assert guard(result, base + 0x140) == TransitInstruction(
        ((result.routes[0].sha256, 0),)
    )
    guards = {g.address: g for g in result.guard_instructions}
    assert guards[ElfVA(base + 0x100)].full_roles == ("direct_call", "entry")
    assert guards[ElfVA(base + 0x105)].full_roles == ("continuation", "return")
    assert guards[ElfVA(base + 0x140)].full_roles == ("entry", "indirect_jump")
    assert all(
        g.witness_hex == proof.witness(proof.to_ghidra(g.address)).data.hex()
        for g in guards.values()
    )
    encoded = result.to_bytes()
    assert encoded.endswith(b"\n") and not encoded.endswith(b"\n\n")
    assert (
        encoded
        == (
            json.dumps(
                result.record(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            + "\n"
        ).encode()
    )
    assert result.sha256 == sha256(encoded).hexdigest()
    repeated = select_scope(binary, lift, proof, plan, request)
    assert isinstance(repeated, ScopeSelection)
    assert result.to_bytes() == repeated.to_bytes()
    with pytest.raises(FrozenInstanceError):
        result.root = ElfVA(1)  # type: ignore[misc]
    record = result.record()
    record["root"] = 9
    assert result.root == base + 0x100


@pytest.mark.parametrize(
    "fault", ["binary", "proof", "plan", "binding", "roles", "gaps"]
)
def test_exact_input_reconstruction(fault: str) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    if fault == "binary":
        binary += b"x"
    elif fault == "proof":
        proof = replace(
            proof,
            witnesses=(replace(proof.witnesses[0], data=b"x"), *proof.witnesses[1:]),
        )
    elif fault == "plan":
        plan = replace(plan, scope=())
    elif fault == "roles":
        plan = replace(
            plan, sites=(replace(plan.sites[0], entry=False), *plan.sites[1:])
        )
    elif fault == "gaps":
        plan = replace(plan, gaps=((*plan.gaps, (GhidraVA(0x100100), "invented"))))
    else:
        transfer = plan.sites[0].transfer
        assert isinstance(transfer, Call) and transfer.imported is not None
        changed = replace(transfer, imported=replace(transfer.imported, thunk_path=()))
        plan = replace(
            plan, sites=(replace(plan.sites[0], transfer=changed), *plan.sites[1:])
        )
    result = select_scope(binary, lift, proof, plan, request)
    assert isinstance(result, Rejection) and result.code == "scope_identity"


@pytest.mark.parametrize(
    "fault",
    [
        "missing-root",
        "duplicate",
        "unsorted",
        "interior",
        "thunk",
        "main-evidence",
        "lift-evidence",
        "explicit-evidence",
        "policy",
        "boolean",
    ],
)
def test_request_validation(fault: str) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    requests = {
        "missing-root": replace(request, users=()),
        "duplicate": replace(request, users=(request.root, request.root)),
        "unsorted": replace(request, users=(ElfVA(0x140), request.root)),
        "interior": replace(request, root=ElfVA(0x101), users=(ElfVA(0x101),)),
        "thunk": replace(request, users=(request.root, ElfVA(0x140))),
        "main-evidence": replace(
            request, root_evidence=LiftMain(lift.lift_sha256, ElfVA(1))
        ),
        "lift-evidence": replace(
            request, root_evidence=LiftMain("0" * 64, request.root)
        ),
        "explicit-evidence": replace(request, root_evidence=ExplicitEntry("0" * 64)),
        "policy": replace(request, policy="other"),  # type: ignore[arg-type]
        "boolean": replace(request, root=True),  # type: ignore[arg-type]
    }
    result = select_scope(binary, lift, proof, plan, requests[fault])
    assert isinstance(result, Rejection) and result.code == "scope_root"


def test_explicit_entry_label_and_digest() -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    explicit = replace(request, root_evidence=ExplicitEntry(request.intent_sha256))
    selected = select_scope(binary, lift, proof, plan, explicit)
    assert isinstance(selected, ScopeSelection)
    assert isinstance(selected.request.root_evidence, ExplicitEntry)
    assert selected.sha256 != compile_scope(binary, document).sha256


@pytest.mark.parametrize(
    ("data", "opcode", "expected"),
    [
        (b"\x75\x03", "CBRANCH", LocalConditional(ElfVA(0x10A), ElfVA(0x107))),
        (
            b"\x0f\x84\xff\xff\xff\xff",
            "CBRANCH",
            LocalConditional(ElfVA(0x10A), ElfVA(0x10B)),
        ),
        (b"\xeb\x03", "BRANCH", LocalDirect(ElfVA(0x10A))),
        (b"\xe9\x00\x00\x00\x00", "BRANCH", LocalDirect(ElfVA(0x10A))),
    ],
)
def test_exact_local_branch_discharge(
    data: bytes, opcode: str, expected: object
) -> None:
    if len(data) == 6:
        data = b"\x0f\x84\xf5\xff\xff\xff"
        binary, document = control(data, opcode, 0x100100)
        function = document["functions"][0]
        function["ranges"][0]["end"] = loc(0x10010B)
        function["instructions"][-1]["address"] = loc(0x10010B)
        function["instructions"][-1]["pcode"][0]["sequence"]["address"] = loc(0x10010B)
        image = bytearray(binary)
        image[0x10B] = 0xC3
        binary = bytes(image)
        expected = LocalConditional(ElfVA(0x100), ElfVA(0x10B))
    else:
        binary, document = control(data, opcode)
    selected = compile_scope(binary, document)
    assert guard(selected) == expected
    if opcode == "CBRANCH":
        gap = next(g for g in selected.gap_dispositions if g.address == 0x100105)
        assert gap.reason == "unsupported_transfer_encoding"
        assert isinstance(gap.disposition, LocalBranchGuard)
        assert gap.domain == "ghidra" and gap.elf == 0x105


@pytest.mark.parametrize(
    ("data", "opcode", "target", "space", "width"),
    [
        (b"\x75\x03", "CBRANCH", 0x100109, "ram", 8),
        (b"\x75\x03", "CBRANCH", 3, "const", 8),
        (b"\x75\x03", "CBRANCH", 0x10010A, "ram", 4),
        (b"\x75\x03", "BRANCH", 0x10010A, "ram", 8),
        (b"\x75\x03", None, 0x10010A, "ram", 8),
        (b"\x66\x75\x02", "CBRANCH", 0x10010A, "ram", 8),
        (b"\x75\x03\x90", "CBRANCH", 0x10010A, "ram", 8),
        (b"\xeb\x39", "BRANCH", 0x100140, "ram", 8),
        (b"\xc2\x00\x00", None, 0, "ram", 8),
        (b"\xf4", "BRANCH", 0x100105, "ram", 8),
        (b"\x0f\x05", None, 0, "ram", 8),
        (b"\xe2\x03", "CBRANCH", 0x10010A, "ram", 8),
        (b"\x90", "CBRANCH", 0, "const", 8),
    ],
)
def test_unsupported_executed_instruction_has_reject_guard(
    data: bytes,
    opcode: str | None,
    target: int,
    space: str,
    width: int,
) -> None:
    binary, document = control(data, opcode, target, space=space, width=width)
    selected = compile_scope(binary, document)
    assert isinstance(guard(selected), Reject)
    assert any(g.address == 0x105 for g in selected.guard_instructions)
    assert selected.active_unlisted == "reject"


def test_ordinary_successor_and_cross_owner_rejection() -> None:
    binary, document = control(b"\x90", None)
    assert guard(compile_scope(binary, document)) == Ordinary(ElfVA(0x106))
    root = document["functions"][0]
    instructions = root["instructions"]
    extra = deepcopy(root)
    extra["entry"] = loc(0x100106)
    extra["ranges"] = [{"start": loc(0x100106), "end": loc(0x10010A)}]
    extra["instructions"] = instructions[2:]
    root["ranges"][0]["end"] = loc(0x100105)
    root["instructions"] = instructions[:2]
    document["functions"].append(extra)
    selected = compile_scope(binary, document)
    assert isinstance(guard(selected), Reject)
    omission = next(o for o in selected.omitted if o.address == 0x106)
    assert omission.reason == "outside_requested_users"
    assert omission.full_roles == ("entry",)
    assert isinstance(guard(selected, 0x106), Reject)
    assert isinstance(dict(selected.dispositions)[ElfVA(0x106)], Omitted)


def test_gaps_keep_domain_index_and_reject_active_uncertainty() -> None:
    binary, document = control(b"\x75\x03", "CBRANCH")
    document["functions"][0]["decompilation"]["analyzed_pcode"] = [
        op(0x100108, "COPY", [operand(0, "register")])
    ]
    selected = compile_scope(binary, document)
    lift, proof, plan, _ = inputs(binary, document)
    assert [(g.index, g.address, g.reason) for g in selected.gap_dispositions] == [
        (i, address, reason) for i, (address, reason) in enumerate(plan.gaps)
    ]
    assert all(g.domain == "ghidra" for g in selected.gap_dispositions)
    assert selected.address_proof_sha256 == proof.sha256
    assert selected.lift_sha256 == lift.lift_sha256


@pytest.mark.parametrize(
    "name",
    [
        "events",
        "wire_bytes",
        "frames",
        "execution_callbacks",
        "translated_instructions",
        "full_plan_sites",
        "full_plan_bytes",
        "guarded_instructions",
        "scope_bytes",
        "receipt_bytes",
        "route_entries",
        "thunk_neutral_instructions",
        "thunk_neutral_bytes",
    ],
)
@pytest.mark.parametrize("fault", ["zero", "excess"])
def test_limit_validation(name: str, fault: str) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    limits = CaptureLimits()
    value = 0 if fault == "zero" else getattr(limits, name) + 1
    result = select_scope(
        binary, lift, proof, plan, request, limits=replace(limits, **{name: value})
    )
    assert isinstance(result, Rejection) and result.code == "scope_bound"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("guarded_instructions", 2),
        ("full_plan_sites", 2),
        ("full_plan_bytes", 32),
        ("scope_bytes", 100),
        ("snapshot_bytes", 4),
    ],
)
def test_actual_capacity_excess(name: str, value: int) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    result = select_scope(
        binary,
        lift,
        proof,
        plan,
        request,
        limits=replace(CaptureLimits(), **{name: value}),
    )
    assert isinstance(result, Rejection) and result.code == "scope_bound"


def test_nonreturn_contracts_are_never_admitted() -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    contract = TerminationContract(
        "0" * 64,
        proof.binary_sha256,
        plan.sha256,
        request.root,
        None,
        "0" * 64,
        "0" * 64,
        "0" * 64,
        ExactSignal(9),
    )
    result = select_scope(binary, lift, proof, plan, request, (contract,))
    assert isinstance(result, Rejection) and result.code == "nonreturn_contract"
    selected = compile_scope(binary, document)
    assert selected.contracts == ()
    assert (
        selected.transit_profile == "eager-only"
        and selected.lazy_resolver == "unsupported"
    )


def test_policy_digest_binds_source_bytes_without_absolute_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = policy_implementation_sha256()
    read_bytes = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = read_bytes(path)
        return raw + b"\n# Policy change.\n" if path.name == "scope.py" else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert policy_implementation_sha256() != original


@given(st.integers(min_value=1, max_value=10000))
@settings(max_examples=12)
def test_limits_and_request_evidence_bind_scope_digest(events: int) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    original = compile_scope(binary, document)
    changed = select_scope(
        binary,
        lift,
        proof,
        plan,
        request,
        limits=replace(CaptureLimits(), events=events),
    )
    assert isinstance(changed, ScopeSelection)
    assert (changed.sha256 == original.sha256) == (events == 10000)


def test_direct_got_route_has_no_fabricated_thunk_entry() -> None:
    from test_transfer_evidence import change_call, relative

    binary, document = change_call(
        relative(b"\xff\x15", 0x100100, 0x102500),
        "CALLIND",
        operand(0x102500),
        external=True,
    )
    selected = compile_scope(bytes(binary), document)
    (route,) = selected.routes
    assert route.entries == route.instruction_path == ()
    assert route.call_site == route.terminal == 0x100
    assert route.slot == 0x2500 and route.request.symbol == "fwrite"
    assert isinstance(guard(selected, 0x140), Reject)
    assert selected.omitted[0].address == 0x140


@pytest.mark.parametrize(
    "prefixes",
    [
        ("90",),
        ("f30f1efa", "90"),
        ("90",) * 8,
        ("0f1f840000000000",) * 4,
    ],
)
def test_exact_neutral_route_instructions(prefixes: tuple[str, ...]) -> None:
    from test_transfer_evidence import thunk_case

    binary, document = thunk_case(prefixes)
    selected = compile_scope(bytes(binary), document)
    (route,) = selected.routes
    assert len(route.instruction_path) == len(prefixes) + 1
    assert route.entries == (0x140,)
    assert route.terminal == 0x140 + sum(len(bytes.fromhex(p)) for p in prefixes)
    for position, address in enumerate(route.instruction_path):
        assert guard(selected, address) == TransitInstruction(
            ((route.sha256, position),)
        )


@pytest.mark.parametrize(
    ("name", "limit", "prefixes"),
    [
        ("thunk_neutral_instructions", 1, ("90", "90")),
        ("thunk_neutral_bytes", 1, ("6690",)),
    ],
)
def test_lower_thunk_limits_reject_without_truncation(
    name: str,
    limit: int,
    prefixes: tuple[str, ...],
) -> None:
    from test_transfer_evidence import thunk_case

    binary, document = thunk_case(prefixes)
    lift, proof, plan, request = inputs(bytes(binary), document)
    result = select_scope(
        bytes(binary),
        lift,
        proof,
        plan,
        request,
        limits=replace(CaptureLimits(), **{name: limit}),
    )
    assert isinstance(result, Rejection) and result.code == "scope_bound"


@pytest.mark.parametrize("count", [2, 32, 33])
def test_route_hop_limit_and_exact_direct_hops(count: int) -> None:
    from test_transfer_evidence import relative, write_thunk

    original, document = fixture()
    binary = bytearray(original)
    template = document["functions"].pop()
    for index in range(count):
        thunk = deepcopy(template)
        address = 0x100140 + 8 * index
        if index + 1 < count:
            target = address + 8
            thunk["thunk_target"] = loc(target)
            raw = relative(b"\xeb", address, target, 1)
            operation = op(address, "BRANCH", [operand(target)])
        else:
            raw = relative(b"\xff\x25", address, 0x102500)
            operation = op(address, "BRANCHIND", [operand(0x102500)])
        write_thunk(binary, thunk, address, (), raw, operation)
        document["functions"].append(thunk)
    selected = compile_scope(bytes(binary), document)
    if count == 33:
        assert selected.routes == ()
        assert isinstance(guard(selected, 0x100), Reject)
    else:
        (route,) = selected.routes
        assert route.entries == tuple(0x140 + 8 * i for i in range(count))
        assert route.instruction_path == route.entries
        assert route.terminal == route.entries[-1]
        lift, proof, plan, request = inputs(bytes(binary), document)
        result = select_scope(
            bytes(binary),
            lift,
            proof,
            plan,
            request,
            limits=replace(CaptureLimits(), route_entries=1),
        )
        assert isinstance(result, Rejection) and result.code == "scope_bound"


def test_shared_route_has_one_guard_with_all_call_bound_positions() -> None:
    from test_transfer_evidence import relative

    original, document = fixture()
    binary = bytearray(original)
    binary[0x105:0x10B] = relative(b"\xe8", 0x100105, 0x100140) + b"\xc3"
    root = document["functions"][0]
    call = deepcopy(root["instructions"][0])
    call.update(
        address=loc(0x100105), pcode=[op(0x100105, "CALL", [operand(0x100140)])]
    )
    resume = root["instructions"][1]
    resume.update(
        address=loc(0x10010A), pcode=[op(0x10010A, "RETURN", [operand(0, "register")])]
    )
    root["instructions"].insert(1, call)
    root["ranges"][0]["end"] = loc(0x10010A)
    edge = deepcopy(document["call_edges"][0])
    edge["site"] = loc(0x100105)
    document["call_edges"].append(edge)
    selected = compile_scope(bytes(binary), document)
    assert len(selected.routes) == 2
    assert len({r.sha256 for r in selected.routes}) == 2
    rule = guard(selected, 0x140)
    assert isinstance(rule, TransitInstruction) and len(rule.positions) == 2
    assert {route for route, _ in rule.positions} == {r.sha256 for r in selected.routes}
    site = next(g for g in selected.guard_instructions if g.address == 0x105)
    assert site.full_roles == ("continuation", "direct_call")
    assert len([g for g in selected.guard_instructions if g.address == 0x140]) == 1


def test_gap_dispositions_preserve_metadata_and_active_rejection() -> None:
    from phoenix.observe.scope import GuardReject, MetadataOnly

    binary, document = control(b"\x90", None)
    document["functions"][0]["decompilation"]["analyzed_pcode"] = [
        op(0x100106, "COPY", [operand(0, "register")])
    ]
    selected = compile_scope(binary, document)
    # The analyzed site exists. Only the thunk's unresolved target is metadata.
    assert any(
        isinstance(g.disposition, MetadataOnly) for g in selected.gap_dispositions
    )
    document["functions"][0]["decompilation"]["analyzed_pcode"][0]["sequence"][
        "address"
    ] = loc(0x100109 + 0x20)
    selected = compile_scope(binary, document)
    gap = next(
        g
        for g in selected.gap_dispositions
        if g.reason == "analyzed_site_has_no_instruction"
    )
    assert isinstance(gap.disposition, GuardReject)
    assert isinstance(guard(selected, 0x100), Reject)


def test_unmappable_selected_gap_blocks_selection() -> None:
    from phoenix.lift.mapping import FileOffset, LiftSpan
    from phoenix.recover.addresses import prove_addresses

    binary, document = control(b"\x90", None)
    lift, mapping, _ = evidence(binary, document)
    spans = []
    for start, end in ((0, 0x108), (0x109, 0x400)):
        digest = sha256(binary[start:end]).hexdigest()
        spans.append(
            LiftSpan(
                GhidraVA(0x100000 + start),
                FileOffset(start),
                end - start,
                digest,
                digest,
            )
        )
    mapping = replace(mapping, spans=(*spans, mapping.spans[1]))
    proof = prove_addresses(binary, lift, mapping)
    plan = build_trace_plan(binary, lift, proof)
    request = RequestedScope(
        ElfVA(0x100), (ElfVA(0x100),), LiftMain(lift.lift_sha256, ElfVA(0x100))
    )
    result = select_scope(binary, lift, proof, plan, request)
    assert isinstance(result, Rejection) and result.code == "scope_guard"


def test_overlapping_instruction_starts_cannot_discharge_an_interior_branch() -> None:
    binary, document = control(b"\x75\xff", "CBRANCH", 0x100106)
    extra = deepcopy(document["functions"][0]["instructions"][2])
    extra["address"] = loc(0x100106)
    document["functions"][0]["instructions"].insert(2, extra)
    with pytest.raises(MappingError, match="Different instructions overlap"):
        inputs(binary, document)


def test_known_internal_caller_cannot_supply_the_requested_root() -> None:
    from test_transfer_evidence import relative

    original, document = fixture()
    binary = bytearray(original)
    extra = deepcopy(document["functions"][0])
    extra["entry"] = loc(0x100180)
    extra["ranges"] = [{"start": loc(0x100180), "end": loc(0x100185)}]
    extra["instructions"][0].update(
        address=loc(0x100180), pcode=[op(0x100180, "CALL", [operand(0x100100)])]
    )
    extra["instructions"][1].update(
        address=loc(0x100185), pcode=[op(0x100185, "RETURN", [operand(0, "register")])]
    )
    binary[0x180:0x186] = relative(b"\xe8", 0x100180, 0x100100) + b"\xc3"
    document["functions"].append(extra)
    lift, proof, plan, request = inputs(bytes(binary), document)
    result = select_scope(bytes(binary), lift, proof, plan, request)
    assert isinstance(result, Rejection) and result.code == "scope_root"


def test_unsupported_thunk_stays_visible_with_rejecting_call_guard() -> None:
    from test_transfer_evidence import thunk_case

    binary, document = thunk_case(("50",))
    selected = compile_scope(bytes(binary), document)
    assert selected.routes == ()
    assert isinstance(guard(selected, 0x100), Reject)
    assert any(o.address == 0x140 for o in selected.omitted)
    assert any(g.address == 0x140 for g in selected.guard_instructions)


def test_omissions_roles_guards_and_limits_change_the_scope_digest() -> None:
    binary, document = fixture()
    selected = compile_scope(binary, document)
    variants = [
        replace(selected, guard_instructions=()),
        replace(selected, dispositions=selected.dispositions[:-1]),
        replace(selected, gap_dispositions=()),
        replace(selected, routes=()),
        replace(selected, registers=()),
        replace(selected, limits=replace(selected.limits, frames=63)),
    ]
    assert all(v.sha256 != selected.sha256 for v in variants)


@pytest.mark.parametrize("condition", range(16))
@pytest.mark.parametrize("near", [False, True])
def test_all_conditional_forms_only_certify_destinations(
    condition: int, near: bool
) -> None:
    if near:
        raw = bytes((0x0F, 0x80 + condition)) + (-11).to_bytes(4, "little", signed=True)
        target = 0x100100
        expected = LocalConditional(ElfVA(0x100), ElfVA(0x10B))
    else:
        raw = bytes((0x70 + condition, 3))
        target = 0x10010A
        expected = LocalConditional(ElfVA(0x10A), ElfVA(0x107))
    binary, document = control(raw, "CBRANCH", target)
    assert guard(compile_scope(binary, document)) == expected


@pytest.mark.parametrize(
    ("raw", "target", "space"),
    [
        (b"\x75\x03", 0x10010A, "const"),
        (b"\x75\x03", 0x10A, "const"),
        (b"\x75\x03", 0x10A, "ram"),
        (b"\x75\x39", 0x100140, "ram"),
        (b"\x0f\x85\x00\x00\x00\x80", 0, "ram"),
    ],
)
def test_branch_domain_cross_owner_and_arithmetic_failures(
    raw: bytes,
    target: int,
    space: str,
) -> None:
    binary, document = control(raw, "CBRANCH", target, space=space)
    assert isinstance(guard(compile_scope(binary, document)), Reject)


def test_local_branch_needs_both_same_owner_successors() -> None:
    binary, document = control(b"\x75\x03", "CBRANCH")
    root = document["functions"][0]
    root["instructions"] = [
        instruction
        for instruction in root["instructions"]
        if instruction["address"] != loc(0x100107)
    ]
    selected = compile_scope(binary, document)
    assert isinstance(guard(selected), Reject)
    assert any(
        g.reason == "unsupported_transfer_encoding" for g in selected.gap_dispositions
    )


def test_dormant_gap_and_complete_omission_change_digest() -> None:
    from phoenix.observe.scope import DormantOutsideWindow

    binary, document = fixture()
    extra = deepcopy(document["functions"][0])
    extra.update(
        entry=loc(0x100180), ranges=[{"start": loc(0x100180), "end": loc(0x100180)}]
    )
    extra["instructions"] = [
        {
            "address": loc(0x100180),
            "size": 1,
            "text": "return proof is absent",
            "pcode": [op(0x100180, "BRANCH", [operand(0x100180)])],
        }
    ]
    document["functions"].append(extra)
    image = bytearray(binary)
    image[0x180] = 0xF4
    selected = compile_scope(bytes(image), document)
    (omission,) = selected.omitted
    assert omission.address == 0x180 and omission.owner == 0x180
    assert omission.full_roles == ("entry",)
    assert omission.witness_sha256 == sha256(b"\xf4").hexdigest()
    gap = next(g for g in selected.gap_dispositions if g.address == 0x100180)
    assert isinstance(gap.disposition, DormantOutsideWindow)
    assert isinstance(guard(selected, 0x180), Reject)
    assert replace(selected, omitted=()).sha256 != selected.sha256
    assert (
        replace(
            selected, omitted=(replace(omission, full_roles=("entry", "return")),)
        ).sha256
        != selected.sha256
    )


@pytest.mark.parametrize(
    "name", ["scope_bytes", "full_plan_sites", "guarded_instructions"]
)
def test_exact_selected_capacity_is_accepted(name: str) -> None:
    binary, document = fixture()
    lift, proof, plan, request = inputs(binary, document)
    selected = compile_scope(binary, document)
    value = {
        "scope_bytes": len(selected.to_bytes()),
        "full_plan_sites": len(plan.sites),
        "guarded_instructions": len(proof.witnesses),
    }[name]
    limits = replace(CaptureLimits(), **{name: value})
    # A smaller byte-limit field also changes the encoded certificate length.
    result = select_scope(binary, lift, proof, plan, request, limits=limits)
    assert isinstance(result, ScopeSelection), result
    if name == "scope_bytes":
        exact = len(result.to_bytes())
        result = select_scope(
            binary,
            lift,
            proof,
            plan,
            request,
            limits=replace(limits, scope_bytes=exact),
        )
        assert isinstance(result, ScopeSelection), result
        rejected = select_scope(
            binary,
            lift,
            proof,
            plan,
            request,
            limits=replace(limits, scope_bytes=exact - 1),
        )
        assert isinstance(rejected, Rejection) and rejected.code == "scope_bound"


def test_unmapped_omitted_owner_keeps_its_gaps_dormant() -> None:
    from phoenix.lift.mapping import FileOffset, LiftSpan
    from phoenix.observe.scope import DormantOutsideWindow
    from phoenix.recover.addresses import prove_addresses

    binary, document = fixture()
    extra = deepcopy(document["functions"][0])
    extra.update(
        entry=loc(0x100170), ranges=[{"start": loc(0x100170), "end": loc(0x100180)}]
    )
    extra["instructions"] = [
        {
            "address": loc(0x100180),
            "size": 1,
            "text": "",
            "pcode": [op(0x100180, "BRANCH", [operand(0x100180)])],
        }
    ]
    document["functions"].append(extra)
    image = bytearray(binary)
    image[0x180] = 0xF4
    binary = bytes(image)
    lift, mapping, _ = evidence(binary, document)
    spans = []
    for start, end in ((0, 0x170), (0x171, 0x400)):
        digest = sha256(binary[start:end]).hexdigest()
        spans.append(
            LiftSpan(
                GhidraVA(0x100000 + start),
                FileOffset(start),
                end - start,
                digest,
                digest,
            )
        )
    mapping = replace(mapping, spans=(*spans, mapping.spans[1]))
    proof = prove_addresses(binary, lift, mapping)
    plan = build_trace_plan(binary, lift, proof)
    request = RequestedScope(
        ElfVA(0x100), (ElfVA(0x100),), LiftMain(lift.lift_sha256, ElfVA(0x100))
    )
    selected = select_scope(binary, lift, proof, plan, request)
    assert isinstance(selected, ScopeSelection), selected
    gaps = [g for g in selected.gap_dispositions if g.address in (0x100170, 0x100180)]
    assert gaps and all(isinstance(g.disposition, DormantOutsideWindow) for g in gaps)
    assert selected.active_unlisted == "reject"


@pytest.mark.parametrize("immediate", range(256))
def test_xabort_requires_rejection_without_a_transaction_entry_precondition(
    immediate: int,
) -> None:
    binary, document = control(bytes((0xC6, 0xF8, immediate)), None)
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize(
    "prefix",
    (
        "",
        "66",
        "67",
        "f0",
        "f2",
        "f3",
        "2e",
        "36",
        "3e",
        "26",
        "64",
        "65",
        "40",
        "48",
        "4f",
        "666748",
        "f26648",
    ),
)
@pytest.mark.parametrize("data", ("c6f800", "c7f800000000", "c7f80000"))
@pytest.mark.parametrize("raw_evidence", ("empty", "copy", "callother"))
def test_transaction_bytes_reject_with_missing_or_conflicting_raw_evidence(
    prefix: str,
    data: str,
    raw_evidence: str,
) -> None:
    binary, document = control(bytes.fromhex(prefix + data), None)
    register = operand(0, "register")
    if raw_evidence != "empty":
        document["functions"][0]["instructions"][1]["pcode"] = [
            op(
                0x100105,
                "COPY" if raw_evidence == "copy" else "CALLOTHER",
                [register],
                register if raw_evidence == "copy" else None,
            )
        ]
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize(
    "data",
    (
        "4889c0",
        "31c0",
        "c6c000",
        "c7c000000000",
        "c6f000",
        "c6f900",
        "c7f900000000",
        "0f01d5",
        "0f01d6",
        "f390",
        "4190",
        "6691",
        "0f1e00",
        "0f1f08",
        "f00f1f00",
        "9090",
        "c6",
        "c6f8",
        "c7",
        "0f",
        "f3",
        "66",
        "48",
        "0f1f",
        "0f1f40",
        "0f1f400000",
    ),
)
def test_empty_raw_contract_rejects_every_unproved_form(data: str) -> None:
    """Empty MOV and XOR evidence is an explicit capability restriction."""
    binary, document = control(bytes.fromhex(data), None)
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize(
    "data",
    (
        "90",
        "6690",
        "0f1f00",
        "0f1f4000",
        "0f1f440000",
        "660f1f440000",
        "0f1f8000000000",
        "0f1f840000000000",
        "660f1f840000000000",
    ),
)
@pytest.mark.parametrize("with_identity_copy", (False, True))
def test_exact_neutral_bytes_supply_bounded_ordinary_evidence(
    data: str,
    with_identity_copy: bool,
) -> None:
    binary, document = control(bytes.fromhex(data), None)
    if with_identity_copy:
        register = operand(0, "register")
        document["functions"][0]["instructions"][1]["pcode"] = [
            op(0x100105, "COPY", [register], register)
        ]
    assert guard(compile_scope(binary, document)) == Ordinary(
        ElfVA(0x105 + len(bytes.fromhex(data)))
    )


@pytest.mark.parametrize("data", ("90", "6690", "0f1f00"))
@pytest.mark.parametrize("opcode", ("COPY", "INT_ADD", "STORE", "CALLOTHER", "CBRANCH"))
def test_neutral_bytes_do_not_hide_conflicting_raw_operations(
    data: str,
    opcode: str,
) -> None:
    binary, document = control(bytes.fromhex(data), None)
    register = operand(0, "register")
    arguments = [operand(1, "const")]
    if opcode == "INT_ADD":
        arguments.append(register)
    if opcode == "STORE":
        arguments = [operand(0, "const"), register, register]
    document["functions"][0]["instructions"][1]["pcode"] = [
        op(0x100105, opcode, arguments, None if opcode == "STORE" else register)
    ]
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize("at_entry", (False, True))
def test_empty_endbr64_needs_the_proved_owner_entry(at_entry: bool) -> None:
    binary, document = control(bytes.fromhex("f30f1efa"), None)
    address = 0x105
    if at_entry:
        image = bytearray(binary)
        image[0x100:0x105] = bytes.fromhex("f30f1efac3")
        function = document["functions"][0]
        instruction = deepcopy(function["instructions"][1])
        instruction["address"] = loc(0x100100)
        terminal = deepcopy(function["instructions"][-1])
        terminal.update(
            address=loc(0x100104),
            pcode=[op(0x100104, "RETURN", [operand(0, "register")])],
        )
        function["instructions"] = [instruction, terminal]
        function["ranges"][0]["end"] = loc(0x100104)
        document["call_edges"] = []
        binary = bytes(image)
        address = 0x100
    result = guard(compile_scope(binary, document), address)
    if at_entry:
        assert result == Ordinary(ElfVA(0x104))
    else:
        assert result == Reject("missing_ordinary_evidence")


def ordinary_data_control(data: str) -> tuple[bytes, dict[str, Any]]:
    """Supply explicit raw operations for the revised ordinary controls."""
    binary, document = control(bytes.fromhex(data), None)
    register = operand(0, "register")
    byte_register = dict(register, size=1)
    zero = dict(operand(0, "const"), size=1)
    if data == "4889c0":
        operations = [op(0x100105, "COPY", [register], register)]
    elif data == "c6c000":
        operations = [op(0x100105, "COPY", [zero], byte_register)]
    elif data == "31c0":
        low = dict(register, size=4)
        operations = [
            op(0x100105, "INT_XOR", [low, low], low),
            op(0x100105, "INT_ZEXT", [low], register, 1),
        ]
        for index, (flag, value) in enumerate(
            ((0x200, 0), (0x20B, 0), (0x207, 0), (0x206, 1), (0x202, 1)), 2
        ):
            operations.append(
                op(
                    0x100105,
                    "COPY",
                    [dict(zero, address=loc(value, "const"))],
                    dict(byte_register, address=loc(flag, "register")),
                    index,
                )
            )
    elif data == "488b03":
        operations = [
            op(
                0x100105,
                "LOAD",
                [operand(0, "const"), operand(0x18, "register")],
                register,
            )
        ]
    else:
        assert data == "488903"
        operations = [
            op(
                0x100105,
                "STORE",
                [operand(0, "const"), operand(0x18, "register"), register],
            )
        ]
    document["functions"][0]["instructions"][1]["pcode"] = operations
    return binary, document


@pytest.mark.parametrize("data", ("4889c0", "31c0", "c6c000", "488b03", "488903"))
def test_revised_ordinary_positive_has_explicit_raw_data_evidence(data: str) -> None:
    binary, document = ordinary_data_control(data)
    assert guard(compile_scope(binary, document)) == Ordinary(
        ElfVA(0x105 + len(bytes.fromhex(data)))
    )


@pytest.mark.parametrize(
    "opcode",
    (
        "UNKNOWN",
        "UNIMPLEMENTED",
        "MULTIEQUAL",
        "INDIRECT",
        "CALLOTHER",
        "CPOOLREF",
        "NEW",
    ),
)
def test_nonempty_unknown_or_pseudo_pcode_cannot_prove_ordinary_flow(
    opcode: str,
) -> None:
    binary, document = ordinary_data_control("c6c000")
    document["functions"][0]["instructions"][1]["pcode"][0]["opcode"] = opcode
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize(
    "fault", ("no_output", "no_inputs", "extra_input", "raw_transfer")
)
def test_incomplete_or_conflicting_ordinary_raw_evidence_rejects(fault: str) -> None:
    binary, document = ordinary_data_control("c6c000")
    operations = document["functions"][0]["instructions"][1]["pcode"]
    if fault == "no_output":
        operations[0]["output"] = None
    elif fault == "no_inputs":
        operations[0]["inputs"] = []
    elif fault == "extra_input":
        operations[0]["inputs"].append(operand(0, "register"))
    else:
        operations.append(op(0x100105, "CALLOTHER", [operand(0, "const")], index=1))
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@pytest.mark.parametrize("data", ("e83b000000", "ffd0", "c3", "7503", "eb03"))
def test_valid_data_operation_cannot_hide_physical_control(data: str) -> None:
    binary, document = control(bytes.fromhex(data), None)
    register = operand(0, "register")
    document["functions"][0]["instructions"][1]["pcode"] = [
        op(0x100105, "COPY", [register], register)
    ]
    assert isinstance(guard(compile_scope(binary, document)), Reject)


@given(st.binary(min_size=1, max_size=15))
@settings(max_examples=150, deadline=None)
def test_empty_raw_pcode_never_proves_an_unlisted_ordinary_form(data: bytes) -> None:
    binary, document = control(data, None)
    result = guard(compile_scope(binary, document))
    if isinstance(result, Ordinary):
        assert data.hex() in {
            "90",
            "6690",
            "0f1f00",
            "0f1f4000",
            "0f1f440000",
            "660f1f440000",
            "0f1f8000000000",
            "0f1f840000000000",
            "660f1f840000000000",
        }
        assert result.successor == 0x105 + len(data)
    else:
        assert isinstance(result, Reject)
