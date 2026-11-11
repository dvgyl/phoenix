"""Keep bounded static lift facts separate from legacy Program addresses."""

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from phoenix.lift.evidence import StaticEvidence, parse_static_evidence
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    array,
    bounded_read,
    hex_address,
    load_json,
    object_fields,
    text,
    uint,
)


@dataclass(frozen=True, slots=True)
class Location:
    space: str
    offset: int

    @property
    def ram(self) -> GhidraVA | None:
        return GhidraVA(self.offset) if self.space == "ram" else None


@dataclass(frozen=True, slots=True)
class Sequence:
    address: Location
    index: int


@dataclass(frozen=True, slots=True)
class Operand:
    address: Location
    size: int
    definition: Sequence | None


@dataclass(frozen=True, slots=True)
class Operation:
    sequence: Sequence
    opcode: str
    output: Operand | None
    inputs: tuple[Operand, ...]


@dataclass(frozen=True, slots=True)
class Instruction:
    address: GhidraVA
    size: int
    pcode: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class Block:
    entry: GhidraVA
    ranges: tuple[tuple[GhidraVA, GhidraVA], ...]


@dataclass(frozen=True, slots=True)
class Function:
    entry: GhidraVA
    ranges: tuple[tuple[GhidraVA, GhidraVA], ...]
    thunk_target: Location | None
    instructions: tuple[Instruction, ...]
    analyzed: tuple[Operation, ...]
    static_evidence: StaticEvidence | None
    blocks: tuple[Block, ...] = ()
    raw_c: str | None = None


@dataclass(frozen=True, slots=True)
class StaticEdge:
    caller: GhidraVA | None
    site: GhidraVA
    target: Location | None
    kind: str
    flow_type: str = ""
    indirect: bool | None = None
    from_block: GhidraVA | None = None
    to_block: GhidraVA | None = None


def call_transfer_kind(
    instruction: Instruction, target: Location | None
) -> Literal["direct", "indirect"] | None:
    direct = [op for op in instruction.pcode if op.opcode == "CALL"]
    indirect = any(op.opcode in ("CALLIND", "BRANCHIND") for op in instruction.pcode)
    if direct:
        if (
            len(direct) == 1
            and not indirect
            and len(direct[0].inputs) == 1
            and direct[0].inputs[0].address == target
        ):
            return "direct"
        return None
    return "indirect" if indirect else None


@dataclass(frozen=True, slots=True)
class ExternalImport:
    address: Location
    name: str | None


@dataclass(frozen=True, slots=True)
class Reference:
    source: Location
    target: Location


@dataclass(frozen=True, slots=True)
class Ownership:
    start: int
    end: int
    entries: tuple[GhidraVA, ...]


@dataclass(frozen=True, slots=True)
class LiftIndex:
    binary_sha256: str
    lift_sha256: str
    image_base: GhidraVA
    startup: GhidraVA
    main: GhidraVA
    functions: Mapping[GhidraVA, Function]
    instructions: Mapping[GhidraVA, Instruction]
    edges: tuple[StaticEdge, ...]
    references: tuple[Reference, ...]
    imports: tuple[ExternalImport, ...]
    ownership: tuple[Ownership, ...]
    ownership_starts: tuple[int, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]

    def owners(self, address: GhidraVA, size: int = 1) -> tuple[GhidraVA, ...]:
        index = bisect_right(self.ownership_starts, address) - 1
        if index < 0:
            return ()
        span = self.ownership[index]
        if span.start <= address and address + size <= span.end:
            return span.entries
        return ()

    def target_kind(self, address: GhidraVA) -> str:
        owners = self.owners(address)
        if len(owners) > 1:
            return "ambiguous_owner"
        if address in self.functions:
            if owners == (address,) and address in self.instructions:
                return "function_entry"
            return "unavailable_function_entry"
        if address in self.instructions:
            return "instruction"
        if owners:
            return "interior"
        return "unresolved_target"


def location(value: object) -> Location:
    item = object_fields(value, "space offset")
    space = text(item["space"])
    if not space:
        raise MappingError("The address space name is empty.")
    return Location(space, hex_address(item["offset"]))


def ram(value: object) -> GhidraVA:
    result = location(value).ram
    if result is None:
        raise MappingError("Expected a Ghidra RAM address.")
    return result


def _optional_location(value: object) -> None:
    if value is not None:
        location(value)


def _string(value: object, *, optional: bool = False) -> None:
    if not isinstance(value, str) and not (optional and value is None):
        raise MappingError("Expected lift text.")


def _signature(value: object) -> None:
    signature = object_fields(
        value, "calling_convention return_type parameters variadic"
    )
    _string(signature["calling_convention"], optional=True)
    _string(signature["return_type"])
    if type(signature["variadic"]) is not bool:
        raise MappingError("Invalid variadic flag.")
    for value_parameter in array(signature["parameters"]):
        parameter = object_fields(value_parameter, "name type")
        _string(parameter["name"])
        _string(parameter["type"])


def _sequence(value: object) -> Sequence:
    item = object_fields(value, "address index")
    return Sequence(location(item["address"]), uint(item["index"], 1_000_000))


def _operand(value: object) -> Operand | None:
    if value is None:
        return None
    item = object_fields(value, "address size definition")
    return Operand(
        location(item["address"]),
        uint(item["size"], 65536),
        None if item["definition"] is None else _sequence(item["definition"]),
    )


def _operations(value: object) -> tuple[Operation, ...]:
    result = []
    identities: set[Sequence] = set()
    for raw in array(value):
        item = object_fields(raw, "sequence opcode output inputs")
        sequence = _sequence(item["sequence"])
        if sequence in identities:
            raise MappingError("Duplicate operation identity within one domain.")
        identities.add(sequence)
        inputs = tuple(_operand(operand) for operand in array(item["inputs"], 256))
        if any(operand is None for operand in inputs):
            raise MappingError("An operation input cannot be null.")
        result.append(
            Operation(
                sequence,
                text(item["opcode"]),
                _operand(item["output"]),
                tuple(operand for operand in inputs if operand is not None),
            )
        )
    return tuple(result)


def _ownership(functions: Mapping[GhidraVA, Function]) -> tuple[Ownership, ...]:
    events: dict[int, list[tuple[GhidraVA, int]]] = defaultdict(list)
    for function in functions.values():
        for start, end in function.ranges:
            events[start].append((function.entry, 1))
            events[end + 1].append((function.entry, -1))
    active: dict[GhidraVA, int] = {}
    result = []
    previous = 0
    total = 0
    for position, changes in sorted(events.items()):
        if active and position > previous:
            total += len(active)
            if total > 1_000_000:
                raise MappingError("Function ownership exceeds the bound.")
            result.append(Ownership(previous, position, tuple(sorted(active))))
        for entry, change in changes:
            active[entry] = active.get(entry, 0) + change
            if active[entry] == 0:
                del active[entry]
        previous = position
    return tuple(result)


def parse_lift(raw: bytes, binary: bytes) -> LiftIndex:
    """Parse the existing export. No symbol label selects instruction semantics."""
    item = object_fields(
        load_json(raw),
        "schema_version image_base main functions imports strings "
        "data_references call_edges",
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise MappingError("Unsupported lift schema.")
    main = object_fields(item["main"], "entry startup setup call")
    ram(main["setup"])
    ram(main["call"])
    functions: dict[GhidraVA, Function] = {}
    instructions: dict[GhidraVA, Instruction] = {}
    edges = []
    total = 0
    gaps = []
    for value in array(item["functions"], 65536):
        function = object_fields(value)
        allowed = set(
            (
                "entry name signature thunk_target ranges decompilation instructions "
                "blocks flow_edges static_evidence"
            ).split()
        )
        if function.keys() - allowed or allowed - {"static_evidence"} - function.keys():
            raise MappingError("Invalid function fields.")
        _string(function["name"])
        _signature(function["signature"])
        entry = ram(function["entry"])
        ranges = []
        for value_range in array(function["ranges"], 65536):
            region = object_fields(value_range, "start end")
            start, end = ram(region["start"]), ram(region["end"])
            if start > end:
                raise MappingError("Invalid function range.")
            ranges.append((start, end))
        ranges.sort()
        if any(left[1] >= right[0] for left, right in zip(ranges, ranges[1:])):
            raise MappingError("One function has overlapping ranges.")
        range_starts = [start for start, _ in ranges]
        decoded = []
        decoded_addresses: set[GhidraVA] = set()
        for value_instruction in array(function["instructions"]):
            ins = object_fields(value_instruction, "address size text pcode")
            _string(ins["text"])
            address, size = ram(ins["address"]), uint(ins["size"], 15)
            owner_index = bisect_right(range_starts, address) - 1
            if (
                not size
                or owner_index < 0
                or address + size - 1 > ranges[owner_index][1]
            ):
                raise MappingError("An instruction is outside its function ranges.")
            operations = _operations(ins["pcode"])
            if any(op.sequence.address.ram != address for op in operations):
                raise MappingError("A raw operation has the wrong instruction site.")
            instruction = Instruction(address, size, operations)
            previous = instructions.setdefault(address, instruction)
            if previous != instruction or address in decoded_addresses:
                raise MappingError("Conflicting or duplicate instruction records.")
            decoded.append(instruction)
            decoded_addresses.add(address)
            total += 1 + len(operations)
        decompilation = object_fields(
            function["decompilation"],
            "raw_c status diagnostic analyzed_pcode statements",
        )
        source = decompilation["raw_c"]
        if source is not None and not isinstance(source, str):
            raise MappingError("Expected lift text.")
        _string(decompilation["diagnostic"], optional=True)
        if decompilation["status"] not in ("ok", "timeout", "incomplete"):
            raise MappingError("Invalid decompilation status.")
        for value_statement in array(decompilation["statements"]):
            statement = object_fields(value_statement, "text start end operation")
            _string(statement["text"])
            _optional_location(statement["start"])
            _optional_location(statement["end"])
            if statement["operation"] is not None:
                _sequence(statement["operation"])
        analyzed = _operations(decompilation["analyzed_pcode"])
        definitions = {operation.sequence: operation for operation in analyzed}
        for operation in analyzed:
            if operation.sequence.address.ram not in decoded_addresses:
                gaps.append((entry, "analyzed_site_has_no_instruction"))
            operands = (
                *operation.inputs,
                *((operation.output,) if operation.output else ()),
            )
            for operand in operands:
                if operand.definition is not None:
                    defining = definitions.get(operand.definition)
                    if (
                        defining is None
                        or defining.output is None
                        or defining.output.address != operand.address
                        or defining.output.size != operand.size
                    ):
                        raise MappingError(
                            "An analyzed definition reference is invalid."
                        )
        total += len(analyzed) + len(ranges)
        if total > 1_000_000:
            raise MappingError("The lift index exceeds the record bound.")
        blocks = []
        for value_block in array(function["blocks"], 65536):
            block = object_fields(value_block, "entry ranges")
            block_ranges = []
            for value_region in array(block["ranges"], 65536):
                region = object_fields(value_region, "start end")
                start, end = ram(region["start"]), ram(region["end"])
                owner_index = bisect_right(range_starts, start) - 1
                if start > end or owner_index < 0 or end > ranges[owner_index][1]:
                    raise MappingError("A block range is outside its function.")
                block_ranges.append((start, end))
            blocks.append(Block(ram(block["entry"]), tuple(block_ranges)))
            total += 1 + len(block_ranges)
        if len({block.entry for block in blocks}) != len(blocks):
            raise MappingError("Duplicate block entry.")
        for value_edge in array(function["flow_edges"]):
            edge = object_fields(value_edge, "from_block to_block site target kind")
            edges.append(
                StaticEdge(
                    entry,
                    ram(edge["site"]),
                    location(edge["target"]),
                    "flow",
                    text(edge["kind"]),
                    None,
                    ram(edge["from_block"]),
                    ram(edge["to_block"]),
                )
            )
        if entry in functions:
            raise MappingError("Duplicate function entry.")
        functions[entry] = Function(
            entry,
            tuple(ranges),
            None
            if function["thunk_target"] is None
            else location(function["thunk_target"]),
            tuple(sorted(decoded, key=lambda ins: ins.address)),
            analyzed,
            parse_static_evidence(function["static_evidence"])
            if "static_evidence" in function
            else None,
            tuple(blocks),
            source if decompilation["status"] == "ok" else None,
        )
    for value in array(item["call_edges"]):
        edge = object_fields(value, "caller site target kind indirect")
        if type(edge["indirect"]) is not bool:
            raise MappingError("Invalid indirect-call flag.")
        edges.append(
            StaticEdge(
                None if edge["caller"] is None else ram(edge["caller"]),
                ram(edge["site"]),
                None if edge["target"] is None else location(edge["target"]),
                "call",
                text(edge["kind"]),
                bool(edge["indirect"]),
            )
        )
    references = []
    for value in array(item["data_references"]):
        ref = object_fields(value, "from to kind operand_index")
        _string(ref["kind"])
        if type(ref["operand_index"]) is not int:
            raise MappingError("Invalid reference operand index.")
        references.append(Reference(location(ref["from"]), location(ref["to"])))
    imports = []
    for value in array(item["imports"], 65536):
        imported = object_fields(value, "address library name library_address")
        _string(imported["library"])
        _optional_location(imported["library_address"])
        imports.append(
            ExternalImport(
                location(imported["address"]),
                None if imported["name"] is None else text(imported["name"]),
            )
        )
    if len({imported.address for imported in imports}) != len(imports):
        raise MappingError("Duplicate import address.")
    for value in array(item["strings"]):
        string = object_fields(value, "address value type size")
        location(string["address"])
        _string(string["value"])
        _string(string["type"])
        if not uint(string["size"]):
            raise MappingError("Invalid string size.")
    if len(edges) + len(references) + total > 1_000_000:
        raise MappingError("The lift index exceeds the total bound.")
    ordered = sorted(instructions.values(), key=lambda ins: ins.address)
    if any(
        left.address + left.size > right.address
        for left, right in zip(ordered, ordered[1:])
    ):
        raise MappingError("Different instructions overlap.")
    ownership = _ownership(functions)
    return LiftIndex(
        sha256(binary).hexdigest(),
        sha256(raw).hexdigest(),
        ram(item["image_base"]),
        ram(main["startup"]),
        ram(main["entry"]),
        MappingProxyType(functions),
        MappingProxyType(instructions),
        tuple(edges),
        tuple(references),
        tuple(imports),
        ownership,
        tuple(span.start for span in ownership),
        tuple(sorted(set(gaps))),
    )


def read_lift(path: Path, binary: bytes) -> LiftIndex:
    return parse_lift(bounded_read(path), binary)
