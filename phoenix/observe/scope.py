"""Compile a bounded static certificate for one requested activation."""

import json
from bisect import bisect_right
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from phoenix.lift.index import Instruction, LiftIndex
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.observe.plan import Call, TracePlan, TraceSite, build_trace_plan
from phoenix.recover.addresses import AddressProof, ElfVA, InstructionWitness
from phoenix.recover.imports import (
    _ENDBR64,
    _NOPS,
    ImportBinding,
    ImportId,
    _bind_checked_imports,
    _thunk_terminal,
)
from phoenix.recover.transfers import CheckedTransfers, check_transfers

type ImportRequest = ImportId
type OmissionReason = Literal[
    "outside_requested_users", "runtime_lifecycle_outside_window"
]
type RejectCode = Literal[
    "scope_identity",
    "scope_root",
    "scope_partition",
    "scope_bound",
    "scope_route",
    "scope_guard",
    "nonreturn_contract",
]

_ORDINARY_INPUTS = {
    **dict.fromkeys(
        (
            "COPY INT_ZEXT INT_SEXT INT_2COMP INT_NEGATE BOOL_NEGATE "
            "FLOAT_NAN FLOAT_NEG FLOAT_ABS FLOAT_SQRT FLOAT_INT2FLOAT "
            "FLOAT_FLOAT2FLOAT FLOAT_TRUNC FLOAT_CEIL FLOAT_FLOOR FLOAT_ROUND "
            "POPCOUNT LZCOUNT"
        ).split(),
        1,
    ),
    **dict.fromkeys(
        (
            "LOAD PIECE SUBPIECE INT_EQUAL INT_NOTEQUAL INT_SLESS INT_SLESSEQUAL "
            "INT_LESS INT_LESSEQUAL INT_ADD INT_SUB INT_CARRY INT_SCARRY "
            "INT_SBORROW INT_XOR INT_AND INT_OR INT_LEFT INT_RIGHT INT_SRIGHT "
            "INT_MULT INT_DIV INT_SDIV INT_REM INT_SREM BOOL_XOR BOOL_AND "
            "BOOL_OR FLOAT_EQUAL FLOAT_NOTEQUAL FLOAT_LESS FLOAT_LESSEQUAL "
            "FLOAT_ADD FLOAT_SUB FLOAT_MULT FLOAT_DIV"
        ).split(),
        2,
    ),
    "STORE": 3,
}


def _canonical(record: object, limit: int) -> bytes:
    chunks = []
    length = 1
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    for chunk in encoder.iterencode(record):
        length += len(chunk)
        if length > limit:
            raise MappingError("The scope certificate exceeds its byte limit.")
        chunks.append(chunk)
    return ("".join(chunks) + "\n").encode("ascii")


@dataclass(frozen=True, slots=True)
class LiftMain:
    lift_sha256: str
    main_elf: ElfVA
    kind: Literal["lift_main"] = field(init=False, default="lift_main")


@dataclass(frozen=True, slots=True)
class ExplicitEntry:
    request_sha256: str
    kind: Literal["explicit_entry"] = field(init=False, default="explicit_entry")


@dataclass(frozen=True, slots=True)
class RequestedScope:
    root: ElfVA
    users: tuple[ElfVA, ...]
    root_evidence: LiftMain | ExplicitEntry
    policy: Literal["main-window-six-v1"] = "main-window-six-v1"

    @property
    def intent_sha256(self) -> str:
        return sha256(
            _canonical(
                {
                    "root": self.root,
                    "users": self.users,
                    "policy": self.policy,
                    "claim": "requested-entry",
                },
                512 * 1024,
            )
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class User:
    owner: ElfVA
    kind: Literal["user"] = field(init=False, default="user")


@dataclass(frozen=True, slots=True)
class Transit:
    route_ids: tuple[str, ...]
    kind: Literal["transit"] = field(init=False, default="transit")


@dataclass(frozen=True, slots=True)
class Omitted:
    reason: OmissionReason
    kind: Literal["omitted"] = field(init=False, default="omitted")


type SiteDisposition = User | Transit | Omitted


@dataclass(frozen=True, slots=True)
class OmittedSite:
    address: ElfVA
    owner: ElfVA
    witness_sha256: str
    full_roles: tuple[str, ...]
    reason: OmissionReason


@dataclass(frozen=True, slots=True)
class TransitRoute:
    call_site: ElfVA
    binding_sha256: str
    entries: tuple[ElfVA, ...]
    instruction_path: tuple[ElfVA, ...]
    terminal: ElfVA
    slot: ElfVA
    request: ImportRequest

    @property
    def sha256(self) -> str:
        return sha256(_canonical(asdict(self), 512 * 1024)).hexdigest()


@dataclass(frozen=True, slots=True)
class Ordinary:
    successor: ElfVA
    kind: Literal["ordinary"] = field(init=False, default="ordinary")


@dataclass(frozen=True, slots=True)
class LocalDirect:
    destination: ElfVA
    kind: Literal["local_direct"] = field(init=False, default="local_direct")


@dataclass(frozen=True, slots=True)
class LocalConditional:
    taken: ElfVA
    fallthrough: ElfVA
    kind: Literal["local_conditional"] = field(init=False, default="local_conditional")


@dataclass(frozen=True, slots=True)
class PlannedRoles:
    transfer_kind: Literal["direct_call", "indirect_call", "indirect_jump", "return"]
    destination: ElfVA | None
    continuation: ElfVA | None
    kind: Literal["planned_roles"] = field(init=False, default="planned_roles")


@dataclass(frozen=True, slots=True)
class TransitInstruction:
    positions: tuple[tuple[str, int], ...]
    kind: Literal["transit_instruction"] = field(
        init=False, default="transit_instruction"
    )


@dataclass(frozen=True, slots=True)
class Reject:
    reason: str
    kind: Literal["reject"] = field(init=False, default="reject")


type GuardRule = (
    Ordinary
    | LocalDirect
    | LocalConditional
    | PlannedRoles
    | TransitInstruction
    | Reject
)


@dataclass(frozen=True, slots=True)
class GuardInstruction:
    address: ElfVA
    owner: ElfVA
    witness_hex: str
    full_roles: tuple[str, ...]
    rule: GuardRule


@dataclass(frozen=True, slots=True)
class DormantOutsideWindow:
    reason: str
    kind: Literal["dormant_outside_window"] = field(
        init=False, default="dormant_outside_window"
    )


@dataclass(frozen=True, slots=True)
class GuardReject:
    reason: str
    kind: Literal["guard_reject"] = field(init=False, default="guard_reject")


@dataclass(frozen=True, slots=True)
class LocalBranchGuard:
    rule: Literal["local_direct", "local_conditional"]
    destination: ElfVA
    fallthrough: ElfVA | None
    kind: Literal["local_branch_guard"] = field(
        init=False, default="local_branch_guard"
    )


@dataclass(frozen=True, slots=True)
class MetadataOnly:
    reason: str
    kind: Literal["metadata_only"] = field(init=False, default="metadata_only")


type GapDisposition = (
    DormantOutsideWindow | GuardReject | LocalBranchGuard | MetadataOnly
)


@dataclass(frozen=True, slots=True)
class GapRecord:
    index: int
    address: GhidraVA
    elf: ElfVA | None
    reason: str
    disposition: GapDisposition
    domain: Literal["ghidra"] = field(init=False, default="ghidra")


@dataclass(frozen=True, slots=True)
class CaptureLimits:
    events: int = 10_000
    wire_bytes: int = 8 * 1024 * 1024
    frames: int = 64
    execution_callbacks: int = 1_000_000
    translated_instructions: int = 1_000_000
    snapshot_bytes: int = 8
    full_plan_sites: int = 4096
    full_plan_bytes: int = 512 * 1024
    guarded_instructions: int = 65536
    scope_bytes: int = 8 * 1024 * 1024
    receipt_bytes: int = 65536
    route_entries: int = 32
    thunk_neutral_instructions: int = 8
    thunk_neutral_bytes: int = 32


@dataclass(frozen=True, slots=True)
class ExitFromSupportedBits:
    register: str
    width: int
    transform: str


@dataclass(frozen=True, slots=True)
class ExactSignal:
    signal: int


@dataclass(frozen=True, slots=True)
class TerminationContract:
    rule_sha256: str
    binary_sha256: str
    full_plan_sha256: str
    call_site: ElfVA
    import_binding_sha256: str | None
    runtime_manifest_base_sha256: str
    provider_evidence_sha256: str
    permitted_physical_route_sha256: str
    termination_rule: ExitFromSupportedBits | ExactSignal
    schema: Literal[1] = field(init=False, default=1)
    behavior: Literal["process-termination"] = field(
        init=False, default="process-termination"
    )
    callbacks: Literal["forbidden"] = field(init=False, default="forbidden")
    cleanup: Literal["no-unobserved-main-reentry"] = field(
        init=False, default="no-unobserved-main-reentry"
    )


@dataclass(frozen=True, slots=True)
class Rejection:
    code: RejectCode
    detail: str
    full_plan_sha256: str
    stage: Literal["selection"] = field(init=False, default="selection")
    scope_sha256: None = field(init=False, default=None)


@dataclass(frozen=True, slots=True)
class ScopeSelection:
    policy: Literal["main-window-six-v1"]
    policy_implementation_sha256: str
    full_plan_sha256: str
    binary_sha256: str
    lift_sha256: str
    address_proof_sha256: str
    request: RequestedScope
    root: ElfVA
    users: tuple[ElfVA, ...]
    dispositions: tuple[tuple[ElfVA, SiteDisposition], ...]
    omitted: tuple[OmittedSite, ...]
    routes: tuple[TransitRoute, ...]
    guard_instructions: tuple[GuardInstruction, ...]
    gap_dispositions: tuple[GapRecord, ...]
    contracts: tuple[TerminationContract, ...]
    limits: CaptureLimits
    registers: tuple[tuple[str, int], ...]
    schema: Literal[1] = field(init=False, default=1)
    claim: Literal["requested-main-activation"] = field(
        init=False, default="requested-main-activation"
    )
    outside_window: Literal["all-sites-outside-frame-capture"] = field(
        init=False, default="all-sites-outside-frame-capture"
    )
    active_unlisted: Literal["reject"] = field(init=False, default="reject")
    transit_profile: Literal["eager-only"] = field(init=False, default="eager-only")
    lazy_resolver: Literal["unsupported"] = field(init=False, default="unsupported")

    def record(self) -> dict[str, object]:
        return asdict(self)

    def to_bytes(self) -> bytes:
        return _canonical(self.record(), self.limits.scope_bytes)

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()


def policy_implementation_sha256() -> str:
    """Bind the static policy source bytes with relative module names."""
    root = Path(__file__).resolve().parents[2]
    names = (
        "phoenix/observe/scope.py",
        "phoenix/observe/plan.py",
        "phoenix/recover/addresses.py",
        "phoenix/recover/imports.py",
        "phoenix/recover/plan.py",
        "phoenix/recover/transfers.py",
        "phoenix/lift/index.py",
        "phoenix/lift/mapping.py",
        "phoenix/lift/evidence.py",
    )
    sources = tuple(
        (name, sha256((root / name).read_bytes()).hexdigest()) for name in names
    )
    return sha256(_canonical(sources, 65536)).hexdigest()


class _Failure(Exception):
    def __init__(self, code: RejectCode, detail: str) -> None:
        self.code = code
        self.detail = detail


def _require(condition: bool, code: RejectCode, detail: str) -> None:
    if not condition:
        raise _Failure(code, detail)


def _exact_evidence(derived: object, supplied: object) -> bool:
    if type(derived) is not type(supplied):
        return False
    if is_dataclass(derived) and not isinstance(derived, type):
        return all(
            _exact_evidence(getattr(derived, item.name), getattr(supplied, item.name))
            for item in fields(derived)
        )
    if isinstance(derived, tuple) and isinstance(supplied, tuple):
        return len(derived) == len(supplied) and all(
            _exact_evidence(left, right)
            for left, right in zip(derived, supplied, strict=True)
        )
    return derived == supplied


def _roles(site: TraceSite | None) -> tuple[str, ...]:
    if site is None:
        return ()
    roles = []
    if site.entry:
        roles.append("entry")
    if site.continuation_of:
        roles.append("continuation")
    if site.transfer is not None:
        roles.append(site.transfer.kind)
    return tuple(sorted(roles))


def _request(
    requested: RequestedScope, lift: LiftIndex, proof: AddressProof, plan: TracePlan
) -> set[GhidraVA]:
    _require(requested.policy == "main-window-six-v1", "scope_root", "Unknown policy.")
    _require(
        type(requested.users) is tuple
        and 0 < len(requested.users) <= 4096
        and all(
            type(address) is int and 0 <= address < 1 << 64
            for address in requested.users
        )
        and type(requested.root) is int
        and 0 <= requested.root < 1 << 64,
        "scope_root",
        "The request needs bounded integer entries.",
    )
    _require(
        tuple(sorted(set(requested.users))) == requested.users
        and requested.root in requested.users,
        "scope_root",
        "Users must be sorted and distinct and include the root.",
    )
    entries = {site.address: site for site in plan.sites if site.entry}
    selected = set()
    for address in requested.users:
        site = entries.get(address)
        _require(
            site is not None and site.owner == address,
            "scope_root",
            "Each user needs one exact full-plan entry.",
        )
        ghidra = proof.to_ghidra(address)
        _require(
            ghidra in lift.functions
            and lift.functions[ghidra].thunk_target is None
            and lift.owners(ghidra) == (ghidra,),
            "scope_root",
            "A user must be a unique physical function and cannot be a thunk.",
        )
        proof.witness(ghidra, owner=ghidra)
        selected.add(ghidra)
    evidence = requested.root_evidence
    if isinstance(evidence, LiftMain):
        _require(
            type(evidence.main_elf) is int
            and evidence.lift_sha256 == lift.lift_sha256
            and evidence.main_elf == requested.root
            and proof.to_elf(lift.main) == requested.root,
            "scope_root",
            "The root differs from the checked lift main.",
        )
    elif isinstance(evidence, ExplicitEntry):
        _require(
            evidence.request_sha256 == requested.intent_sha256,
            "scope_root",
            "The explicit entry evidence differs from the request.",
        )
    else:
        raise _Failure("scope_root", "Unknown root evidence.")
    return selected


def _routes(
    lift: LiftIndex,
    checked: CheckedTransfers,
    plan: TracePlan,
    selected: set[GhidraVA],
    limits: CaptureLimits,
    binary: bytes,
) -> tuple[TransitRoute, ...]:
    bindings = _bind_checked_imports(binary, lift, checked)
    available = set(bindings)
    routes = []
    proof = checked.proof
    selected_elf = {proof.to_elf(entry) for entry in selected}
    for site in plan.sites:
        call = site.transfer
        if site.owner not in selected_elf:
            continue
        if not isinstance(call, Call) or call.imported is None:
            continue
        binding: ImportBinding = call.imported
        _require(
            binding in available
            and binding.identity is not None
            and binding.relocation_slot is not None
            and binding.gap is None,
            "scope_route",
            "The import binding cannot be reconstructed.",
        )
        assert binding.identity is not None and binding.relocation_slot is not None
        _require(
            len(binding.thunk_path) <= limits.route_entries,
            "scope_bound",
            "The import route exceeds its entry limit.",
        )
        entries = []
        path: list[ElfVA] = []
        for entry in binding.thunk_path:
            _require(
                entry not in selected,
                "scope_partition",
                "User and transit owners conflict.",
            )
            function = lift.functions[entry]
            terminal = _thunk_terminal(function, checked)
            _require(
                not isinstance(terminal, str),
                "scope_route",
                "The thunk path has no checked terminal.",
            )
            _require(
                len(function.instructions) - 1 <= limits.thunk_neutral_instructions,
                "scope_bound",
                "The thunk exceeds its instruction limit.",
            )
            neutral_bytes = sum(ins.size for ins in function.instructions[:-1])
            _require(
                neutral_bytes <= limits.thunk_neutral_bytes,
                "scope_bound",
                "The thunk exceeds its neutral byte limit.",
            )
            entries.append(proof.witness(entry, owner=entry).elf)
            path.extend(
                proof.witness(ins.address, owner=entry).elf
                for ins in function.instructions
            )
        terminal_address = path[-1] if path else site.address
        fact = checked.sites[proof.to_ghidra(terminal_address)]
        _require(
            fact.physical is not None
            and fact.gap is None
            and fact.physical.import_slot == binding.relocation_slot
            and fact.physical.kind == ("indirect_jump" if path else "indirect_call"),
            "scope_route",
            "The route needs its exact RIP-relative slot transfer.",
        )
        routes.append(
            TransitRoute(
                site.address,
                sha256(_canonical(asdict(binding), limits.full_plan_bytes)).hexdigest(),
                tuple(entries),
                tuple(path),
                terminal_address,
                binding.relocation_slot,
                binding.identity,
            )
        )
    return tuple(routes)


def _branch(
    witness: InstructionWitness,
    instruction: Instruction,
    witnesses: dict[ElfVA, InstructionWitness],
    proof: AddressProof,
) -> LocalDirect | LocalConditional | None:
    data = witness.data
    conditional = (len(data) == 2 and 0x70 <= data[0] <= 0x7F) or (
        len(data) == 6 and data[0] == 0x0F and 0x80 <= data[1] <= 0x8F
    )
    direct = (len(data) == 2 and data[0] == 0xEB) or (
        len(data) == 5 and data[0] == 0xE9
    )
    if not conditional and not direct:
        return None
    raw = [
        operation
        for operation in instruction.pcode
        if operation.opcode
        in ("CALL", "CALLIND", "BRANCH", "CBRANCH", "BRANCHIND", "RETURN", "CALLOTHER")
    ]
    if len(raw) != 1:
        return None
    operation = raw[0]
    if (
        operation.opcode != ("CBRANCH" if conditional else "BRANCH")
        or len(operation.inputs) != (2 if conditional else 1)
        or operation.output is not None
    ):
        return None
    operand = operation.inputs[0]
    if (
        operand.address.ram is None
        or operand.definition is not None
        or operand.size != 8
    ):
        return None
    end = witness.elf + len(data)
    displacement = int.from_bytes(
        data[2:] if len(data) == 6 else data[1:], "little", signed=True
    )
    destination = end + displacement
    if not 0 <= end < 1 << 64 or not 0 <= destination < 1 << 64:
        return None
    try:
        target = proof.to_elf(operand.address.ram)
    except MappingError:
        return None
    if target != destination:
        return None
    target_witness = witnesses.get(target)
    if target_witness is None or target_witness.owner != witness.owner:
        return None
    if not conditional:
        return LocalDirect(target)
    fallthrough = witnesses.get(ElfVA(end))
    if fallthrough is None or fallthrough.owner != witness.owner:
        return None
    return LocalConditional(target, fallthrough.elf)


def _user_rule(
    witness: InstructionWitness,
    lift: LiftIndex,
    checked: CheckedTransfers,
    sites: dict[ElfVA, TraceSite],
    witnesses: dict[ElfVA, InstructionWitness],
) -> GuardRule:
    instruction = lift.instructions[witness.ghidra]
    branch = _branch(witness, instruction, witnesses, checked.proof)
    if branch is not None:
        return branch
    fact = checked.sites.get(witness.ghidra)
    if fact is not None:
        if fact.gap is not None:
            return Reject(fact.gap)
        site = sites.get(witness.elf)
        if site is None or site.transfer is None or fact.physical is None:
            return Reject("unsupported_transfer_encoding")
        transfer = site.transfer
        if isinstance(transfer, Call):
            if fact.continuation is None:
                return Reject("unavailable_continuation")
            if fact.physical.kind == "direct_call":
                operation = fact.operation
                try:
                    raw_target = (
                        checked.proof.to_elf(operation.inputs[0].address.ram)
                        if operation is not None
                        and operation.inputs
                        and operation.inputs[0].address.ram is not None
                        else None
                    )
                except MappingError:
                    raw_target = None
                if (
                    operation is None
                    or len(operation.inputs) != 1
                    or operation.inputs[0].address.ram is None
                    or operation.inputs[0].definition is not None
                    or raw_target != fact.physical.destination
                ):
                    return Reject("conflicting_call_bytes")
            return PlannedRoles(
                transfer.kind, fact.physical.destination, transfer.continuation
            )
        return PlannedRoles(transfer.kind, None, None)
    if _control_bytes(witness.data):
        return Reject("unsupported_transfer_encoding")
    neutral = witness.data in _NOPS or (
        witness.data == _ENDBR64 and witness.ghidra == witness.owner
    )
    if not instruction.pcode and not neutral:
        return Reject("missing_ordinary_evidence")
    for operation in instruction.pcode:
        if _ORDINARY_INPUTS.get(operation.opcode) != len(operation.inputs) or (
            operation.output is None
        ) != (operation.opcode == "STORE"):
            return Reject("unsupported_ordinary_pcode")
        if neutral and (
            operation.opcode != "COPY"
            or operation.output is None
            or operation.output.address.space != "register"
            or operation.inputs != (operation.output,)
        ):
            return Reject("conflicting_neutral_pcode")
    adjacent = witnesses.get(ElfVA(witness.elf + len(witness.data)))
    if adjacent is None or adjacent.owner != witness.owner:
        return Reject("unavailable_same_owner_fallthrough")
    return Ordinary(adjacent.elf)


def _control_bytes(data: bytes) -> bool:
    # These vetoes do not prove that other bytes have ordinary flow.
    cursor = 0
    while cursor < len(data) and (
        data[cursor]
        in (0xF0, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65, 0x66, 0x67)
        or 0x40 <= data[cursor] <= 0x4F
    ):
        cursor += 1
    if cursor == len(data):
        return True
    opcode = data[cursor]
    if opcode in (0xC6, 0xC7) and data[cursor + 1 : cursor + 2] == b"\xf8":
        return True
    if opcode in (
        0x9A,
        0xEA,
        0xC2,
        0xC3,
        0xCA,
        0xCB,
        0xCC,
        0xCD,
        0xCE,
        0xCF,
        0xF1,
        0xF4,
    ):
        return True
    if 0x70 <= opcode <= 0x7F or 0xE0 <= opcode <= 0xEB:
        return True
    if opcode == 0xFF:
        return cursor + 1 == len(data) or (data[cursor + 1] >> 3) & 7 in (2, 3, 4, 5)
    if opcode == 0x0F and cursor + 1 < len(data):
        second = data[cursor + 1]
        return 0x80 <= second <= 0x8F or second in (0x05, 0x07, 0x0B, 0x34, 0x35)
    return False


def _compile(
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    full_plan: TracePlan,
    requested: RequestedScope,
    contracts: tuple[TerminationContract, ...],
    limits: CaptureLimits,
) -> ScopeSelection:
    maximum = CaptureLimits()
    for item in fields(limits):
        value = getattr(limits, item.name)
        _require(
            type(value) is int and 0 < value <= getattr(maximum, item.name),
            "scope_bound",
            "A capture limit is invalid or exceeds the policy limit.",
        )
    _require(
        limits.snapshot_bytes == 8,
        "scope_bound",
        "The stack word must have eight bytes.",
    )
    _require(
        not contracts, "nonreturn_contract", "Nonreturn contracts are unsupported."
    )
    _require(
        len(full_plan.sites) <= limits.full_plan_sites,
        "scope_bound",
        "Too many full-plan sites.",
    )
    _require(
        len(full_plan.to_bytes()) <= limits.full_plan_bytes,
        "scope_bound",
        "The full plan exceeds its byte limit.",
    )
    rebuilt = build_trace_plan(binary, lift, proof)
    _require(
        rebuilt.to_bytes() == full_plan.to_bytes(),
        "scope_identity",
        "The full plan differs from its exact reconstruction.",
    )
    checked = check_transfers(binary, lift, proof)
    _require(
        _exact_evidence(checked.proof, proof),
        "scope_identity",
        "The supplied proof fields differ in value or exact type.",
    )
    proof = checked.proof
    selected = _request(requested, lift, proof, full_plan)
    _require(
        len(proof.witnesses) <= limits.guarded_instructions,
        "scope_bound",
        "Too many guarded instruction starts.",
    )
    routes = _routes(lift, checked, full_plan, selected, limits, binary)
    selected_elf = set(requested.users)
    import_calls = {route.call_site for route in routes}
    active_owners = selected | {
        proof.to_ghidra(entry) for route in routes for entry in route.entries
    }
    for left, right in zip(proof.witnesses, proof.witnesses[1:]):
        _require(
            left.elf + len(left.data) <= right.elf
            or not active_owners.intersection((left.owner, right.owner)),
            "scope_guard",
            "Active instruction witnesses overlap.",
        )
    for fact_address, fact in checked.sites.items():
        if fact.physical is not None and fact.physical.kind == "direct_call":
            _require(
                fact.physical.destination != requested.root
                or proof.witness(fact_address).owner == proof.to_ghidra(requested.root),
                "scope_root",
                "The requested root has an internal caller.",
            )
    for edge in lift.edges:
        reported = checked.sites.get(edge.site)
        if (
            edge.kind == "call"
            and edge.target is not None
            and edge.target.ram == proof.to_ghidra(requested.root)
            and reported is not None
            and reported.physical is not None
            and reported.physical.kind in ("direct_call", "indirect_call")
        ):
            _require(
                proof.witness(edge.site).owner == proof.to_ghidra(requested.root),
                "scope_root",
                "The requested root has a reported internal caller.",
            )
    positions: dict[ElfVA, list[tuple[str, int]]] = {}
    successors: dict[ElfVA, ElfVA | None] = {}
    for route in routes:
        route_id = route.sha256
        for index, address in enumerate(route.instruction_path):
            successor = (
                route.instruction_path[index + 1]
                if index + 1 < len(route.instruction_path)
                else None
            )
            _require(
                address not in successors or successors[address] == successor,
                "scope_partition",
                "Shared transit paths have conflicting successors.",
            )
            successors[address] = successor
            positions.setdefault(address, []).append((route_id, index))
    sites = {site.address: site for site in full_plan.sites}
    witnesses = {w.elf: w for w in proof.witnesses}
    guards = {}
    for witness in proof.witnesses:
        try:
            owner = proof.to_elf(witness.owner)
        except MappingError:
            _require(
                witness.owner not in active_owners,
                "scope_guard",
                "An active owner lacks an ELF mapping.",
            )
            continue
        if witness.elf in positions:
            _require(
                witness.owner not in selected,
                "scope_partition",
                "User and transit ownership conflict.",
            )
            rule: GuardRule = TransitInstruction(tuple(sorted(positions[witness.elf])))
        elif witness.owner in selected:
            rule = _user_rule(witness, lift, checked, sites, witnesses)
            if (
                isinstance(rule, PlannedRoles)
                and rule.transfer_kind == "direct_call"
                and rule.destination not in selected_elf
                and witness.elf not in import_calls
            ):
                rule = Reject("outside_requested_users")
        else:
            rule = Reject("outside_requested_users")
        guards[witness.elf] = GuardInstruction(
            witness.elf, owner, witness.data.hex(), _roles(sites.get(witness.elf)), rule
        )
    gap_records = []
    starts = sorted(witnesses)
    for index, (gap_address, reason) in enumerate(full_plan.gaps):
        try:
            elf = proof.to_elf(gap_address)
        except MappingError:
            elf = None
        owners = lift.owners(gap_address)
        active = bool(active_owners.intersection(owners))
        _require(
            elf is not None or not active,
            "scope_guard",
            "An unmappable gap overlaps selected code.",
        )
        guard = guards.get(elf) if elf is not None else None
        if guard is None and elf is not None:
            previous = bisect_right(starts, elf) - 1
            if previous >= 0:
                witness = witnesses[starts[previous]]
                if elf < witness.elf + len(witness.data):
                    guard = guards.get(witness.elf)
        disposition: GapDisposition
        if not active:
            disposition = DormantOutsideWindow(reason)
        elif (
            reason == "unsupported_transfer_encoding"
            and guard is not None
            and isinstance(guard.rule, (LocalDirect, LocalConditional))
        ):
            branch = guard.rule
            disposition = LocalBranchGuard(
                branch.kind,
                branch.destination if isinstance(branch, LocalDirect) else branch.taken,
                None if isinstance(branch, LocalDirect) else branch.fallthrough,
            )
        elif (
            reason in ("unknown", "unresolved_static_target", "unresolved_target")
            and guard is not None
            and (
                isinstance(guard.rule, TransitInstruction)
                or (
                    isinstance(guard.rule, PlannedRoles)
                    and guard.rule.transfer_kind in ("indirect_call", "indirect_jump")
                )
            )
        ):
            disposition = MetadataOnly(reason)
        else:
            disposition = GuardReject(reason)
            if guard is not None:
                guards[guard.address] = GuardInstruction(
                    guard.address,
                    guard.owner,
                    guard.witness_hex,
                    guard.full_roles,
                    Reject(reason),
                )
        gap_records.append(GapRecord(index, gap_address, elf, reason, disposition))
    dispositions = []
    omitted = []
    for site in full_plan.sites:
        if site.owner in requested.users:
            site_disposition: SiteDisposition = User(site.owner)
        elif site.address in positions:
            site_disposition = Transit(
                tuple(sorted({route_id for route_id, _ in positions[site.address]}))
            )
        else:
            omission_reason: OmissionReason = (
                "runtime_lifecycle_outside_window"
                if proof.to_ghidra(site.owner) == lift.startup
                else "outside_requested_users"
            )
            site_disposition = Omitted(omission_reason)
            omitted.append(
                OmittedSite(
                    site.address,
                    site.owner,
                    sha256(bytes.fromhex(site.witness_hex)).hexdigest(),
                    _roles(site),
                    omission_reason,
                )
            )
        dispositions.append((site.address, site_disposition))
    selection = ScopeSelection(
        requested.policy,
        policy_implementation_sha256(),
        full_plan.sha256,
        proof.binary_sha256,
        proof.lift_sha256,
        proof.sha256,
        requested,
        requested.root,
        requested.users,
        tuple(dispositions),
        tuple(omitted),
        routes,
        tuple(guards[address] for address in sorted(guards)),
        tuple(gap_records),
        (),
        limits,
        full_plan.registers,
    )
    selection.to_bytes()
    return selection


def select_scope(
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    full_plan: TracePlan,
    requested: RequestedScope,
    contracts: tuple[TerminationContract, ...] = (),
    *,
    limits: CaptureLimits = CaptureLimits(),
) -> ScopeSelection | Rejection:
    """Reconstruct static evidence and return a certificate or a rejection."""
    plan_sha256 = ""
    try:
        _require(
            len(full_plan.sites) <= 4096
            and len(full_plan.gaps) <= 65536
            and len(proof.witnesses) <= 65536,
            "scope_bound",
            "The static input exceeds a record limit.",
        )
        plan_sha256 = full_plan.sha256
        return _compile(binary, lift, proof, full_plan, requested, contracts, limits)
    except _Failure as error:
        return Rejection(error.code, error.detail[:512], plan_sha256)
    except MappingError as error:
        code: RejectCode = (
            "scope_bound" if "byte limit" in str(error) else "scope_identity"
        )
        return Rejection(code, str(error)[:512], plan_sha256)
