from dataclasses import dataclass
from hashlib import sha256
from struct import unpack

from phoenix.lift.index import LiftIndex, Operand, Operation, Sequence
from phoenix.lift.mapping import GhidraVA, MappingError, hex_address
from phoenix.lift.switch_graph import SwitchGraph
from phoenix.recover.addresses import AddressProof, ElfVA, InstructionWitness
from phoenix.recover.imports import read_dynamic_imports

MAX_SELECTORS = 4096
_GPR_OFFSETS = (0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38)
_LEGACY_PREFIXES = frozenset(
    (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67, 0xF0, 0xF2, 0xF3)
)
_DT_TEXTREL = 22
_DT_FLAGS = 30
_DF_TEXTREL = 4


@dataclass(frozen=True, slots=True)
class SwitchCase:
    selector: int
    target: ElfVA
    target_ghidra: GhidraVA


@dataclass(frozen=True, slots=True)
class SwitchDispatch:
    graph_sha256: str
    address_proof_sha256: str
    site: ElfVA
    site_ghidra: GhidraVA
    guard: Sequence
    selector: Sequence
    mask: int
    table: ElfVA
    table_sha256: str
    cases: tuple[SwitchCase, ...]
    default: ElfVA
    default_ghidra: GhidraVA


@dataclass(frozen=True, slots=True)
class _TableTransfer:
    base: GhidraVA
    load: GhidraVA
    add: GhidraVA
    jump: GhidraVA
    end: GhidraVA
    target_register: int


def _constant(operand: Operand, width: int) -> int:
    if (
        operand.address.space != "const"
        or operand.definition is not None
        or operand.size != width
        or operand.address.offset >= 1 << (width * 8)
    ):
        raise MappingError("The switch operand is not a constant of the required size.")
    return operand.address.offset


def _register_immediate(data: bytes, operation: int) -> tuple[int, int]:
    if (
        len(data) in (3, 6)
        and data[0] == (0x83 if len(data) == 3 else 0x81)
        and data[1] & 0xF8 == 0xC0 | (operation << 3)
    ):
        return data[1] & 7, int.from_bytes(data[2:], "little", signed=True)
    raise MappingError("The switch uses an unsupported raw register operation.")


def _above_displacement(data: bytes) -> int:
    if len(data) == 2 and data[0] == 0x77:
        return int.from_bytes(data[1:], "little", signed=True)
    if len(data) == 6 and data[:2] == b"\x0f\x87":
        return int.from_bytes(data[2:], "little", signed=True)
    raise MappingError("The raw range guard is not an unsigned branch above.")


def _decode_table_transfer(
    proof: AddressProof, entry: GhidraVA, start: GhidraVA, selector: int
) -> _TableTransfer:
    lea = proof.witness(start, owner=entry).data
    if len(lea) != 7 or lea[:2] != b"\x48\x8d" or lea[2] & 0xC7 != 0x05:
        raise MappingError("The switch has no supported RIP-relative table address.")
    base_register = (lea[2] >> 3) & 7
    load = GhidraVA(start + len(lea))
    base = GhidraVA(load + int.from_bytes(lea[3:], "little", signed=True))
    mov = proof.witness(load, owner=entry).data
    if (
        selector == 4
        or base_register in (4, 5, selector)
        or len(mov) != 4
        or mov[:2] != b"\x48\x63"
        or mov[2] & 0xC7 != 0x04
        or mov[3] != 0x80 | (selector << 3) | base_register
    ):
        raise MappingError("The raw signed table load uses an unsupported address.")
    target = (mov[2] >> 3) & 7
    add = GhidraVA(load + len(mov))
    addition = proof.witness(add, owner=entry).data
    if target in (4, base_register) or addition != bytes(
        (0x48, 0x01, 0xC0 | (base_register << 3) | target)
    ):
        raise MappingError("The raw table addition does not preserve its base.")
    jump = GhidraVA(add + len(addition))
    transfer = proof.witness(jump, owner=entry).data
    expected = bytes((0xFF, 0xE0 | target))
    if transfer not in (expected, b"\x3e" + expected):
        raise MappingError("The raw jump does not use the computed table target.")
    return _TableTransfer(base, load, add, jump, GhidraVA(jump + len(transfer)), target)


def _relative_target(witness: InstructionWitness) -> GhidraVA | None:
    data = witness.data
    index = 0
    while index < len(data) and (
        data[index] in _LEGACY_PREFIXES or 0x40 <= data[index] <= 0x4F
    ):
        index += 1
    data = data[index:]
    if not data:
        return None
    opcode = data[0]
    if len(data) == 2 and (
        opcode == 0xEB or 0x70 <= opcode <= 0x7F or 0xE0 <= opcode <= 0xE3
    ):
        displacement = data[1:]
    elif len(data) == 5 and opcode in (0xE8, 0xE9):
        displacement = data[1:]
    elif len(data) == 6 and opcode == 0x0F and 0x80 <= data[1] <= 0x8F:
        displacement = data[2:]
    else:
        return None
    return GhidraVA(
        witness.ghidra
        + len(witness.data)
        + int.from_bytes(displacement, "little", signed=True)
    )


def _check_dispatch_entries(
    lift: LiftIndex,
    proof: AddressProof,
    entry: GhidraVA,
    end: GhidraVA,
    instruction_sites: tuple[GhidraVA, ...],
) -> None:
    fallthrough = set(zip(instruction_sites[:-1], instruction_sites[1:], strict=True))
    for edge in lift.edges:
        target = edge.target.ram if edge.target is not None else None
        if (
            target is not None
            and entry < target < end
            and (
                edge.caller != entry
                or edge.kind != "flow"
                or edge.flow_type != "FALL_THROUGH"
                or (edge.site, target) not in fallthrough
            )
        ):
            raise MappingError("A listing edge can bypass part of the switch guard.")
    if any(
        entry < op.inputs[0].address.offset < end
        for instruction in lift.instructions.values()
        for op in instruction.pcode
        if op.opcode in ("BRANCH", "CBRANCH", "CALL")
        and op.inputs
        and op.inputs[0].address.space == "ram"
    ):
        raise MappingError("A raw transfer can bypass part of the switch guard.")
    if any(
        entry < target < end
        for witness in proof.witnesses
        if (target := _relative_target(witness)) is not None
    ):
        raise MappingError("An original relative transfer can bypass the switch guard.")
    if any(
        entry < hex_address(target.offset) < end
        for function in lift.functions.values()
        if function.static_evidence is not None
        for table in function.static_evidence.jump_tables
        for target in table.targets
        if target is not None and target.space == "ram"
    ):
        raise MappingError("A proposed indirect transfer can bypass the switch guard.")


def recover_switch(
    graph: SwitchGraph, binary: bytes, lift: LiftIndex, proof: AddressProof
) -> SwitchDispatch:
    if not (
        graph.binary_sha256
        == lift.binary_sha256
        == proof.binary_sha256
        == sha256(binary).hexdigest()
        and graph.lift_sha256 == lift.lift_sha256 == proof.lift_sha256
    ):
        raise MappingError("The switch and address evidence have different identities.")
    entry = graph.function
    function = lift.functions.get(entry)
    if function is None or function.static_evidence is None:
        raise MappingError("The switch has no matching function evidence.")
    proof.witness(entry, owner=entry)
    blocks = {block.index: block for block in graph.blocks}
    positions = {
        operation.sequence: (block.index, position, operation)
        for block in graph.blocks
        for position, operation in enumerate(block.operations)
    }
    branches = [
        (block, operation)
        for block in graph.blocks
        for operation in block.operations
        if operation.opcode == "BRANCHIND"
    ]
    if len(branches) != 1:
        raise MappingError("Expected exactly one normalized indirect branch.")
    dispatch, branch = branches[0]
    site = branch.sequence.address.ram
    if site is None or branch != dispatch.operations[-1] or len(branch.inputs) != 1:
        raise MappingError("The normalized indirect branch has an unsupported form.")
    witness = proof.witness(site, owner=entry)
    raw = lift.instructions.get(site)
    if raw is None or tuple(op.opcode for op in raw.pcode) != ("BRANCHIND",):
        raise MappingError("The indirect branch has no agreeing raw operation.")

    predecessors = [b for b in graph.blocks if dispatch.index in b.successors]
    if len(predecessors) != 1:
        raise MappingError("The normalized dispatch has an unproved predecessor.")
    guard = predecessors[0]
    if (
        guard.start != entry
        or any(guard.index in b.successors for b in graph.blocks)
        or guard.true_out != dispatch.index
        or guard.false_out is None
        or guard.false_out == dispatch.index
        or len(guard.successors) != 2
        or set(guard.successors) != {guard.true_out, guard.false_out}
        or not guard.operations
    ):
        raise MappingError("The normalized range guard does not control the dispatch.")
    condition = guard.operations[-1]
    guard_site = condition.sequence.address.ram
    if (
        guard_site is None
        or condition.opcode != "CBRANCH"
        or len(condition.inputs) != 2
    ):
        raise MappingError("The normalized guard has no supported conditional branch.")
    guard_witness = proof.witness(guard_site, owner=entry)
    raw_guard = lift.instructions.get(guard_site)
    default = blocks[guard.false_out].start
    default_witness = proof.witness(default, owner=entry)
    listing_edges = {
        (edge.flow_type, edge.target.ram)
        for edge in lift.edges
        if edge.kind == "flow"
        and edge.caller == entry
        and edge.site == guard_site
        and edge.target is not None
    }
    if (
        raw_guard is None
        or sum(op.opcode == "CBRANCH" for op in raw_guard.pcode) != 1
        or listing_edges
        != {("FALL_THROUGH", dispatch.start), ("CONDITIONAL_JUMP", default)}
    ):
        raise MappingError("The raw range guard and normalized edges disagree.")
    if any(
        op.opcode in {"STORE", "CALL", "CALLIND", "CALLOTHER"}
        for block in (guard, dispatch)
        for op in block.operations
    ):
        raise MappingError("The dispatch has an unproved side effect.")

    def definition(
        consumer: Operation, operand: Operand, opcode: str, width: int, count: int
    ) -> Operation:
        producer_record = (
            positions.get(operand.definition) if operand.definition else None
        )
        if producer_record is None or operand.size != width:
            raise MappingError("A switch operand has no supported definition.")
        source_block, source_position, producer = producer_record
        consumer_block, consumer_position, _ = positions[consumer.sequence]
        if (
            producer.opcode != opcode
            or producer.output != operand
            or len(producer.inputs) != count
            or not (
                source_block == consumer_block
                and source_position < consumer_position
                or source_block == guard.index
                and consumer_block == dispatch.index
            )
        ):
            raise MappingError("The definition does not prove the switch operand.")
        address = producer.sequence.address.ram
        if address is None:
            raise MappingError("The switch operation has no raw instruction address.")
        proof.witness(address, owner=entry)
        return producer

    less = definition(condition, condition.inputs[1], "INT_LESS", 1, 2)
    selector, bound = less.inputs
    mask_op = definition(less, selector, "INT_AND", 4, 2)
    mask = _constant(mask_op.inputs[1], 4)
    limit = _constant(bound, 4)
    if (
        not 0 < limit <= MAX_SELECTORS
        or limit > mask
        or mask & (mask + 1)
        or mask_op.inputs[0].address != selector.address
        or selector.address.space != "register"
        or mask_op.inputs[0].size != 4
        or mask_op.inputs[0].definition is not None
    ):
        raise MappingError("The checked selector range or mask is unsupported.")
    mask_site = mask_op.sequence.address.ram
    if mask_site is None:
        raise MappingError("The switch mask has no raw instruction address.")
    mask_witness = proof.witness(mask_site, owner=entry)
    compare_site = GhidraVA(mask_site + len(mask_witness.data))
    compare_witness = proof.witness(compare_site, owner=entry)
    raw_register, raw_mask = _register_immediate(mask_witness.data, 4)
    guard_register, raw_limit = _register_immediate(compare_witness.data, 7)
    next_site = guard_site + len(guard_witness.data)
    if (
        mask_site != entry
        or less.sequence.address.ram != guard_site
        or compare_site + len(compare_witness.data) != guard_site
        or raw_register != guard_register
        or raw_mask & 0xFFFF_FFFF != mask
        or raw_limit != limit - 1
        or next_site != dispatch.start
        or next_site + _above_displacement(guard_witness.data) != default
    ):
        raise MappingError("The selector mask or range disagrees with the raw bytes.")
    if selector.address.offset != _GPR_OFFSETS[raw_register]:
        raise MappingError("The normalized selector does not name the raw register.")
    transfer = _decode_table_transfer(proof, entry, dispatch.start, raw_register)
    if transfer.jump != site or entry <= default < transfer.end:
        raise MappingError("The dispatch or default disagrees with the raw sequence.")
    final_add = definition(branch, branch.inputs[0], "INT_ADD", 8, 2)
    sign = definition(final_add, final_add.inputs[0], "INT_SEXT", 8, 1)
    load = definition(sign, sign.inputs[0], "LOAD", 4, 2)
    address_add = definition(load, load.inputs[1], "INT_ADD", 8, 2)
    scale = definition(address_add, address_add.inputs[0], "INT_MULT", 8, 2)
    extend = definition(scale, scale.inputs[0], "INT_ZEXT", 8, 1)
    base = GhidraVA(_constant(final_add.inputs[1], 8))
    if (
        _constant(load.inputs[0], 4) != graph.memory_space_id
        or positions[load.sequence][0] != dispatch.index
        or _constant(address_add.inputs[1], 8) != base
        or base != transfer.base
        or _constant(scale.inputs[1], 8) != 4
        or extend.inputs != (selector,)
        or extend.sequence.address.ram != mask_site
        or any(
            op.sequence.address.ram != transfer.load
            for op in (scale, address_add, load, sign)
        )
        or final_add.sequence.address.ram != transfer.add
        or branch.inputs[0].address.space != "register"
        or branch.inputs[0].address.offset != _GPR_OFFSETS[transfer.target_register]
    ):
        raise MappingError(
            "The table expression does not use the checked selector and base."
        )

    table_size = 4 * limit
    table = proof.to_elf(base, table_size)
    if proof.image.segment(table, table_size).flags != 4:
        raise MappingError(
            "The switch table is not in a read-only file-backed segment."
        )
    dispatch_size = transfer.end - entry
    dispatch_start = proof.to_elf(entry, dispatch_size)
    dispatch_segment = proof.image.segment(
        dispatch_start, dispatch_size, executable=True
    )
    if dispatch_segment.flags & 2:
        raise MappingError("The original switch dispatch is in writable memory.")
    dispatch_end = dispatch_start + dispatch_size
    if any(
        tag == _DT_TEXTREL or tag == _DT_FLAGS and value & _DF_TEXTREL
        for tag, value in proof.image.dynamic
    ) or any(
        relocation.kind != 0
        and (
            relocation.slot < table + table_size
            or relocation.slot < dispatch_end
            and (
                relocation.write_size is None
                or relocation.slot + relocation.write_size > dispatch_start
            )
        )
        for relocation in read_dynamic_imports(binary, proof.image)
    ):
        raise MappingError("A relocation could change the switch table or dispatch.")
    offset = proof.image.offset(table, table_size)
    contents = binary[offset : offset + table_size]
    cases = tuple(
        SwitchCase(
            label,
            proof.witness(target := GhidraVA(base + relative), owner=entry).elf,
            target,
        )
        for label, relative in enumerate(unpack(f"<{limit}i", contents))
    )
    decoded = {case.target_ghidra for case in cases}
    proposed = tuple(
        table
        for table in function.static_evidence.jump_tables
        if table.site is not None
        and table.site.space == "ram"
        and hex_address(table.site.offset) == site
    )
    if (
        any(entry <= target < transfer.end for target in decoded)
        or decoded != {blocks[index].start for index in dispatch.successors}
        or len(proposed) != 1
        or any(
            target is None or target.space != "ram" for target in proposed[0].targets
        )
        or decoded | {default}
        != {
            GhidraVA(hex_address(t.offset))
            for t in proposed[0].targets
            if t is not None
        }
    ):
        raise MappingError(
            "The decoded switch destinations disagree with lift evidence."
        )
    _check_dispatch_entries(
        lift,
        proof,
        entry,
        transfer.end,
        (
            entry,
            compare_site,
            guard_site,
            dispatch.start,
            transfer.load,
            transfer.add,
            site,
        ),
    )
    return SwitchDispatch(
        graph.sha256,
        proof.sha256,
        witness.elf,
        site,
        condition.sequence,
        mask_op.sequence,
        mask,
        table,
        sha256(contents).hexdigest(),
        cases,
        default_witness.elf,
        default,
    )
