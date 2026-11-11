import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Literal

from phoenix.lift.index import Instruction, LiftIndex
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.recover.addresses import AddressProof, ElfVA
from phoenix.recover.imports import ImportBinding, bind_imports
from phoenix.recover.plan import CandidateSite, make_candidate

_MAX_PLAN_BYTES = 512 * 1024
_REGISTERS = ("rdi", "rsi", "rdx", "rcx", "rax", "rsp")
type TransferKind = Literal["direct_call", "indirect_call", "indirect_jump", "return"]
_TRANSFER_ROLES: tuple[TransferKind, ...] = (
    "direct_call",
    "indirect_call",
    "indirect_jump",
    "return",
)
_TRANSFER_OPCODES = frozenset(("CALL", "CALLIND", "BRANCHIND", "RETURN"))


@dataclass(frozen=True, slots=True)
class Call:
    kind: Literal["direct_call", "indirect_call"]
    continuation: ElfVA
    imported: ImportBinding | None
    import_gaps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Jump:
    kind: Literal["indirect_jump"] = field(init=False, default="indirect_jump")


@dataclass(frozen=True, slots=True)
class Return:
    kind: Literal["return"] = field(init=False, default="return")


type Transfer = Call | Jump | Return


@dataclass(frozen=True, slots=True)
class TraceSite:
    address: ElfVA
    owner: ElfVA
    witness_hex: str
    entry: bool
    continuation_of: tuple[ElfVA, ...]
    transfer: Transfer | None


@dataclass(frozen=True, slots=True)
class TraceLimits:
    events: int = 10_000
    wire_bytes: int = 8 * 1024 * 1024
    frames: int = 64
    execution_callbacks: int = 1_000_000
    translated_instructions: int = 1_000_000
    snapshot_bytes: int = 8


@dataclass(frozen=True, slots=True)
class TracePlan:
    binary_sha256: str
    lift_sha256: str
    address_proof_sha256: str
    scope: tuple[ElfVA, ...]
    sites: tuple[TraceSite, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]
    schema: Literal[2] = field(init=False, default=2)
    registers: tuple[tuple[str, int], ...] = field(
        init=False, default=tuple((name, 64) for name in _REGISTERS)
    )
    limits: TraceLimits = field(init=False, default=TraceLimits())

    def to_bytes(self) -> bytes:
        raw = (
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("ascii")
        if len(raw) > _MAX_PLAN_BYTES:
            raise MappingError("The observation plan exceeds 512 KiB.")
        return raw

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()


def _transfer(
    site: CandidateSite,
    instruction: Instruction,
    sites: dict[ElfVA, CandidateSite],
    bindings: list[ImportBinding],
    gaps: set[tuple[GhidraVA, str]],
) -> Transfer | None:
    roles = tuple(role for role in _TRANSFER_ROLES if role in site.roles)
    count = sum(
        operation.opcode in _TRANSFER_OPCODES for operation in instruction.pcode
    )
    if len(roles) > 1 or count > 1:
        gaps.add((site.ghidra, "conflicting_transfer_roles"))
        return None
    if not roles:
        return None
    (kind,) = roles
    if kind == "indirect_jump":
        return Jump()
    if kind == "return":
        return Return()
    continuation = (
        sites.get(site.continuation) if site.continuation is not None else None
    )
    if (
        continuation is None
        or continuation.function_entry != site.function_entry
        or "continuation" not in continuation.roles
        or continuation.elf != site.elf + len(site.witness_hex) // 2
    ):
        gaps.add((site.ghidra, "unavailable_continuation"))
        return None
    imports = {
        binding
        for binding in bindings
        if binding.identity is not None and binding.gap is None
    }
    import_gaps = {binding.gap for binding in bindings if binding.gap is not None}
    if len(imports) > 1:
        import_gaps.add("conflicting_import_paths")
    imported = next(iter(imports)) if len(imports) == 1 and not import_gaps else None
    return Call(kind, continuation.elf, imported, tuple(sorted(import_gaps)))


def build_trace_plan(binary: bytes, lift: LiftIndex, proof: AddressProof) -> TracePlan:
    if sha256(binary).hexdigest() != proof.binary_sha256:
        raise MappingError("The observation plan does not bind the original binary.")
    for witness in proof.witnesses:
        size = len(witness.data)
        if (
            proof.to_elf(witness.ghidra, size) != witness.elf
            or proof.image.offset(witness.elf, size) != witness.file_offset
            or binary[witness.file_offset : witness.file_offset + size] != witness.data
        ):
            raise MappingError(
                "An observation instruction witness differs from the binary."
            )
    imports = bind_imports(binary, lift, proof)
    candidate = make_candidate(lift, proof, imports)
    sites = {site.elf: site for site in candidate.sites}
    if not sites or len(sites) != len(candidate.sites):
        raise MappingError("The observation plan needs unique witnessed sites.")
    bindings: dict[GhidraVA, list[ImportBinding]] = {}
    for binding in imports:
        bindings.setdefault(binding.site, []).append(binding)
    gaps = set(candidate.gaps)
    transfers = {
        address: _transfer(
            site,
            lift.instructions[site.ghidra],
            sites,
            bindings.get(site.ghidra, []),
            gaps,
        )
        for address, site in sites.items()
    }
    continuations: dict[ElfVA, list[ElfVA]] = {}
    for address, transfer in sorted(transfers.items()):
        if isinstance(transfer, Call):
            continuations.setdefault(transfer.continuation, []).append(address)
    selected = tuple(
        TraceSite(
            address,
            site.function_entry,
            site.witness_hex,
            "entry" in site.roles,
            tuple(continuations.get(address, ())),
            transfers[address],
        )
        for address, site in sorted(sites.items())
        if "entry" in site.roles
        or address in continuations
        or transfers[address] is not None
    )
    scope = tuple(site.address for site in selected if site.entry)
    if not scope:
        raise MappingError("The observation plan has no checked function entry.")
    plan = TracePlan(
        proof.binary_sha256,
        proof.lift_sha256,
        proof.sha256,
        scope,
        selected,
        tuple(sorted(gaps)),
    )
    plan.to_bytes()
    return plan
