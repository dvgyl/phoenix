from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from phoenix.generate.checked_switch import emit_checked_switch
from phoenix.generate.protected_switch import (
    ProtectedDefinition,
    protect_switch,
    protected_prefix,
)
from phoenix.generate.switch_binding import (
    SourceConflict,
    SourceGap,
    admit_switch_source,
)
from phoenix.generate.switch_source import SwitchSourceError
from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import GhidraVA, LiftGeneration, MappingError
from phoenix.recover import Program
from phoenix.recover.addresses import prove_addresses


@dataclass(frozen=True, slots=True)
class SwitchDisposition:
    function: GhidraVA
    status: Literal["gap", "conflict"]
    reason: str
    detail: str


@dataclass(frozen=True, slots=True)
class SwitchPlan:
    binary_sha256: str
    lift_sha256: str
    protected: tuple[ProtectedDefinition, ...]
    dispositions: tuple[SwitchDisposition, ...]

    def record(self) -> dict[str, object]:
        return {
            "schema": 1,
            "rule": "checked-switch-c11-v1",
            "binary_sha256": self.binary_sha256,
            "lift_sha256": self.lift_sha256,
            "protected": [
                {
                    "function": hex(item.entry),
                    "graph_sha256": item.emission.graph_sha256,
                    "address_proof_sha256": item.emission.address_proof_sha256,
                    "ordinary_source_sha256": item.emission.input_source_sha256,
                    "checked_source_sha256": item.emission.output_source_sha256,
                    "written_source_sha256": item.source_sha256,
                    "selectors": item.emission.cases,
                    "typed_globals": [
                        {
                            "name": global_.name,
                            "elf_address": hex(global_.address),
                            "bytes": 4,
                            "initial": global_.value,
                        }
                        for global_ in item.globals
                    ],
                }
                for item in self.protected
            ],
            "dispositions": [
                {
                    "function": hex(item.function),
                    "status": item.status,
                    "reason": item.reason,
                    "detail": item.detail,
                }
                for item in self.dispositions
            ],
        }


def plan_switches(
    binary: bytes, generation: LiftGeneration, program: Program
) -> SwitchPlan:
    if generation.switches is None or generation.ordinary_switches is None:
        raise MappingError("Checked generation needs both switch companions.")
    lift = parse_lift(generation.lift, binary)
    if (
        program.main != lift.main
        or program.startup != lift.startup
        or any(
            function.entry not in lift.functions
            or function.raw_c != lift.functions[GhidraVA(function.entry)].raw_c
            for function in program.functions
        )
    ):
        raise MappingError("The recovered program differs from the bound lift.")
    proof = prove_addresses(binary, lift, generation.mapping)
    graphs = {item.function: item for item in generation.switches.graphs}
    bodies = {item.function: item for item in generation.ordinary_switches.bodies}
    wire_gaps = dict(generation.switches.gaps)
    for entry, reason in generation.ordinary_switches.gaps:
        wire_gaps.setdefault(entry, reason)
    protected = []
    dispositions = []
    for function in program.functions:
        entry = GhidraVA(function.entry)
        candidate = entry in graphs.keys() | bodies.keys() | wire_gaps.keys()
        candidate = candidate or any(
            operation.opcode == "BRANCHIND"
            for instruction in lift.functions[entry].instructions
            for operation in instruction.pcode
        )
        if entry == lift.main or not candidate:
            continue
        if entry in wire_gaps:
            dispositions.append(SwitchDisposition(entry, "gap", wire_gaps[entry], ""))
            continue
        if entry not in graphs or entry not in bodies:
            dispositions.append(
                SwitchDisposition(entry, "gap", "switch_companion_unavailable", "")
            )
            continue
        admitted = admit_switch_source(bodies[entry])
        if isinstance(admitted, SourceGap):
            dispositions.append(
                SwitchDisposition(entry, "gap", admitted.reason, admitted.detail)
            )
            continue
        if isinstance(admitted, SourceConflict):
            dispositions.append(
                SwitchDisposition(entry, "conflict", admitted.reason, admitted.detail)
            )
            continue
        try:
            emitted = emit_checked_switch(
                binary, lift, proof, graphs[entry], bodies[entry]
            )
        except (MappingError, SwitchSourceError) as error:
            dispositions.append(
                SwitchDisposition(entry, "gap", "machine_dispatch_unproved", str(error))
            )
            continue
        try:
            protected.append(protect_switch(emitted, function, binary, lift, proof))
        except (MappingError, SwitchSourceError) as error:
            dispositions.append(
                SwitchDisposition(
                    entry, "gap", "switch_dependencies_unproved", str(error)
                )
            )
    definitions = tuple(protected)
    if definitions:
        try:
            protected_prefix(definitions)
        except MappingError as error:
            dispositions.extend(
                SwitchDisposition(
                    GhidraVA(item.entry),
                    "conflict",
                    "global_declaration_conflict",
                    str(error),
                )
                for item in definitions
            )
            definitions = ()
    return SwitchPlan(
        sha256(binary).hexdigest(),
        lift.lift_sha256,
        definitions,
        tuple(sorted(dispositions, key=lambda item: (item.function, item.reason))),
    )
