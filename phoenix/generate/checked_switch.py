from dataclasses import dataclass
from hashlib import sha256

from phoenix.generate.switch_binding import bind_switch_source
from phoenix.generate.switch_source import (
    FlatSwitch,
    Span,
    SwitchSourceError,
    parse_flat_switch,
)
from phoenix.lift.index import Function, LiftIndex, Operand
from phoenix.lift.mapping import GhidraVA
from phoenix.lift.switch_graph import SwitchGraph
from phoenix.lift.switch_source import (
    Block,
    OrdinarySourceObservation,
    SourceMarkerObservation,
)
from phoenix.recover.addresses import AddressProof
from phoenix.recover.switches import SwitchDispatch, recover_switch


@dataclass(frozen=True, slots=True)
class SwitchEmission:
    function: GhidraVA
    graph_sha256: str
    address_proof_sha256: str
    input_source_sha256: str
    output_source_sha256: str
    cases: tuple[int, ...]
    source: bytes


def _raw_block(
    marker: SourceMarkerObservation, function: Function, proof: AddressProof
) -> Block:
    block = marker.block
    site = marker.operation.sequence.address.ram
    if block is None or site is None:
        raise SwitchSourceError("An ordinary marker has no owned operation or block.")
    proof.witness(block.entry, owner=function.entry)
    proof.witness(site, owner=function.entry)
    if not any(
        raw.entry == block.entry
        and any(start <= site <= end for start, end in raw.ranges)
        for raw in function.blocks
    ):
        raise SwitchSourceError("An ordinary marker disagrees with its raw block.")
    return block


def _normalized_operand(graph: SwitchGraph, checked: SwitchDispatch) -> Operand:
    matches = [
        operation.output
        for block in graph.blocks
        for operation in block.operations
        if operation.sequence == checked.selector
    ]
    if len(matches) != 1 or matches[0] is None:
        raise SwitchSourceError("The checked selector operand is unavailable.")
    return matches[0]


def _selector(
    marker: SourceMarkerObservation,
    ordinal: int,
    graph: SwitchGraph,
    checked: SwitchDispatch,
) -> None:
    parameter = marker.parameter
    operation = marker.operation
    operand = _normalized_operand(graph, checked)
    if (
        parameter is None
        or parameter.ordinal != ordinal
        or parameter.definition is not None
        or parameter.storage != (parameter.operand,)
        or parameter.operand.address != operand.address
        or parameter.operand.size != operand.size
        or operand.size != 4
        or operand.address.space != "register"
        or operation.opcode != "INT_AND"
        or operation.sequence.address != checked.selector.address
        or len(operation.inputs) != 2
    ):
        raise SwitchSourceError(
            "The ordinary parameter does not match the original selector."
        )
    value, mask = operation.inputs
    if (
        value.address != operand.address
        or value.size != 4
        or value.definition is not None
        or mask.address.space != "const"
        or mask.address.offset != checked.mask
        or mask.size != 4
        or mask.definition is not None
    ):
        raise SwitchSourceError(
            "The ordinary mask does not match the original selector."
        )


def _edit(source: bytes, changes: list[tuple[Span, bytes]]) -> bytes:
    updated = bytearray()
    end = 0
    for span, replacement in sorted(changes, key=lambda change: change[0].start):
        updated.extend(source[end : span.start])
        updated.extend(replacement)
        end = span.end
    updated.extend(source[end:])
    return bytes(updated)


def _arm_bytes(
    parsed: FlatSwitch, source: bytes
) -> tuple[tuple[tuple[int | None, ...], bytes, bytes | None], ...]:
    return tuple(
        (
            tuple(label.value for label in arm.labels),
            source[arm.body.start : arm.body.end],
            None
            if arm.break_statement is None
            else source[arm.break_statement.start : arm.break_statement.end],
        )
        for arm in parsed.arms
    )


def emit_checked_switch(
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    graph: SwitchGraph,
    body: OrdinarySourceObservation,
) -> SwitchEmission:
    if graph.function != body.function:
        raise SwitchSourceError(
            "The switch graph and ordinary source name different functions."
        )
    checked = recover_switch(graph, binary, lift, proof)
    function = lift.functions.get(body.function)
    if function is None or function.raw_c is None:
        raise SwitchSourceError("The original lift has no ordinary switch source.")
    try:
        source = function.raw_c.encode("utf-8")
    except UnicodeEncodeError as error:
        raise SwitchSourceError("The original switch source is not UTF-8.") from error
    bound = bind_switch_source(body)
    parsed = bound.parsed
    if source != bound.source:
        raise SwitchSourceError(
            "The ordinary source observation differs from the exact lift."
        )
    if (
        parsed.source_sha256 != body.source_sha256
        or len(source) != body.source_bytes
        or parsed.mask != checked.mask
    ):
        raise SwitchSourceError(
            "The ordinary switch identity or selector mask differs."
        )
    labels = [label for arm in parsed.arms for label in arm.labels]
    operations = {operation.sequence: operation for operation in function.analyzed}
    if any(
        operations.get(marker.operation.sequence) != marker.operation
        for marker in body.markers
    ):
        raise SwitchSourceError(
            "An ordinary marker operation differs from the exact lift."
        )
    switch, parameter, *middle = body.markers
    *markers, finish = middle
    if (
        switch.operation.opcode != "BRANCHIND"
        or switch.operation.sequence.address.ram != checked.site_ghidra
        or finish.operation.opcode != "RETURN"
    ):
        raise SwitchSourceError("The ordinary switch or return operation differs.")
    _selector(parameter, parsed.parameter_index, graph, checked)
    join = _raw_block(finish, function, proof)
    if join.successors:
        raise SwitchSourceError("The ordinary continuation has another exit.")

    targets: dict[int | None, GhidraVA] = {
        case.selector: case.target_ghidra for case in checked.cases
    }
    targets[None] = checked.default_ghidra
    if set(targets) != {label.value for label in labels}:
        raise SwitchSourceError("The ordinary labels do not cover the proved switch.")
    changes = [
        (
            parsed.expression,
            f"((uint32_t)({parsed.parameter}) & {checked.mask}u)".encode("ascii"),
        )
    ]
    seen: set[GhidraVA] = set()
    marker_stream = iter(markers)
    for arm in parsed.arms:
        group: set[GhidraVA] = set()
        for label in arm.labels:
            marker = next(marker_stream)
            block = _raw_block(marker, function, proof)
            if (
                marker.value != label.value
                or block.entry != targets[label.value]
                or block.indirect_entries != (switch.operation,)
                or block.successors != (join.index,)
            ):
                raise SwitchSourceError(
                    "An ordinary arm disagrees with the checked dispatch."
                )
            group.add(block.entry)
            if label.value is not None:
                changes.append((label.marker, f"{label.value}u".encode("ascii")))
        if len(group) != 1 or seen & group or join.entry in group:
            raise SwitchSourceError("The ordinary arm entry is ambiguous.")
        seen.update(group)

    emitted = _edit(source, changes)
    result = parse_flat_switch(emitted)
    if (
        (result.parameter_index, result.parameter, result.mask)
        != (parsed.parameter_index, parsed.parameter, parsed.mask)
        or _arm_bytes(result, emitted) != _arm_bytes(parsed, source)
        or emitted[result.continuation.start : result.continuation.end]
        != source[parsed.continuation.start : parsed.continuation.end]
    ):
        raise SwitchSourceError("Emission changed the checked switch structure.")
    return SwitchEmission(
        body.function,
        graph.sha256,
        proof.sha256,
        body.source_sha256,
        sha256(emitted).hexdigest(),
        tuple(case.selector for case in checked.cases),
        emitted,
    )
