"""Build a static plan candidate. This module cannot execute a target."""

import json
from dataclasses import asdict, dataclass

from phoenix.lift.index import LiftIndex
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.recover.addresses import AddressProof, ElfVA, synthetic_external_target
from phoenix.recover.imports import ImportBinding, _bind_checked_imports
from phoenix.recover.transfers import check_transfers


@dataclass(frozen=True, slots=True)
class StaticTarget:
    kind: str
    elf: ElfVA | None
    ghidra: GhidraVA | None


@dataclass(frozen=True, slots=True)
class CandidateSite:
    ghidra: GhidraVA
    elf: ElfVA
    function_entry: ElfVA
    witness_hex: str
    roles: tuple[str, ...]
    static_targets: tuple[StaticTarget, ...]
    continuation: ElfVA | None


@dataclass(frozen=True, slots=True)
class PlanCandidate:
    binary_sha256: str
    lift_sha256: str
    address_proof_sha256: str
    sites: tuple[CandidateSite, ...]
    imports: tuple[ImportBinding, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]
    status: str = "static_candidate_requires_live_gates"


def make_candidate(
    binary: bytes, lift: LiftIndex, proof: AddressProof
) -> PlanCandidate:
    checked = check_transfers(binary, lift, proof)
    proof = checked.proof
    imports = _bind_checked_imports(binary, lift, checked)
    roles: dict[GhidraVA, set[str]] = {}
    continuations: dict[GhidraVA, ElfVA] = {}
    gaps = [*lift.gaps, *proof.gaps]
    witnesses = {witness.ghidra: witness for witness in proof.witnesses}
    external = {
        item.address for item in lift.imports if item.address.space == "EXTERNAL"
    }
    synthetic = {
        entry
        for entry in lift.functions
        if synthetic_external_target(lift, proof, entry) in external
    }
    for function in lift.functions.values():
        entry_witness = witnesses.get(function.entry)
        if entry_witness is not None and entry_witness.owner == function.entry:
            roles.setdefault(function.entry, set()).add("entry")
        elif function.entry not in synthetic:
            gaps.append((function.entry, "unavailable_function_entry"))
    for address, transfer_fact in checked.sites.items():
        if transfer_fact.gap is not None:
            gaps.append((address, transfer_fact.gap))
            continue
        physical = transfer_fact.physical
        if physical is None or physical.kind == "direct_jump":
            continue
        roles.setdefault(address, set()).add(physical.kind)
        if transfer_fact.continuation is not None:
            continuations[address] = transfer_fact.continuation.elf
            roles.setdefault(transfer_fact.continuation.ghidra, set()).add(
                "continuation"
            )
        elif physical.kind in ("direct_call", "indirect_call"):
            gaps.append((address, "unavailable_continuation"))
    edges: dict[GhidraVA, set[StaticTarget]] = {}
    for edge in lift.edges:
        if edge.site not in witnesses or edge.caller != witnesses[edge.site].owner:
            gaps.append((edge.site, "unavailable_or_conflicting_edge_owner"))
            continue
        if edge.kind == "call":
            fact = checked.sites.get(edge.site)
            if fact is None:
                gaps.append((edge.site, "conflicting_call_target"))
                continue
            if fact.gap is not None:
                continue
            physical, operation = fact.physical, fact.operation
            if physical is None or operation is None:
                continue
            if physical.kind == "direct_call":
                if (
                    len(operation.inputs) != 1
                    or operation.inputs[0].address != edge.target
                ):
                    gaps.append((edge.site, "conflicting_call_target"))
                    continue
                if (
                    edge.target is None
                    or edge.target.ram is None
                    or physical.destination != edge.target.ram - proof.ghidra_delta
                ):
                    continue
            elif physical.kind not in ("indirect_call", "indirect_jump"):
                gaps.append((edge.site, "conflicting_call_target"))
                continue
        target = edge.target
        if target is None:
            resolved = StaticTarget("unknown", None, None)
        elif target in external or target.ram in synthetic:
            resolved = StaticTarget("external", None, target.ram)
        elif target.ram is None:
            resolved = StaticTarget("unresolved_target", None, None)
        else:
            address = target.ram
            kind = lift.target_kind(address)
            elf = None
            if kind in ("function_entry", "instruction"):
                target_witness = witnesses.get(address)
                if target_witness is not None and (
                    kind == "instruction" or target_witness.owner == address
                ):
                    elf = target_witness.elf
                else:
                    kind = "unavailable_target"
            resolved = StaticTarget(kind, elf, address)
        edges.setdefault(edge.site, set()).add(resolved)
        if resolved.kind in (
            "unknown",
            "interior",
            "ambiguous_owner",
            "unresolved_target",
            "unavailable_target",
            "unavailable_function_entry",
        ):
            gaps.append((edge.site, resolved.kind))
    for address, site_roles in roles.items():
        if site_roles & {
            "direct_call",
            "indirect_call",
            "indirect_jump",
        } and not edges.get(address):
            gaps.append((address, "unresolved_static_target"))
    if len(roles) > 4096:
        raise MappingError("The candidate exceeds 4096 sites.")
    sites = []
    for address, site_roles in sorted(roles.items()):
        witness = witnesses[address]
        try:
            entry = proof.witness(witness.owner, owner=witness.owner).elf
        except MappingError:
            gaps.append((address, "unavailable_owner_entry"))
            continue
        sites.append(
            CandidateSite(
                address,
                witness.elf,
                entry,
                witness.data.hex(),
                tuple(sorted(site_roles)),
                tuple(
                    sorted(
                        edges.get(address, ()),
                        key=lambda target: (
                            target.kind,
                            -1 if target.ghidra is None else target.ghidra,
                        ),
                    )
                ),
                continuations.get(address),
            )
        )
    candidate = PlanCandidate(
        lift.binary_sha256,
        lift.lift_sha256,
        proof.sha256,
        tuple(sites),
        imports,
        tuple(sorted(set(gaps))),
    )
    if len(json.dumps(asdict(candidate), sort_keys=True).encode()) > 512 * 1024:
        raise MappingError("The candidate exceeds 512 KiB.")
    return candidate
