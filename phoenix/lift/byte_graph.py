"""Read structural byte-graph proposals. These records do not authorize C output."""

import json
from dataclasses import dataclass, fields
from hashlib import sha256
from typing import Literal, cast

from phoenix.lift.index import (
    Function,
    LiftIndex,
    Location,
    Operand,
    Sequence,
    location,
)
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    digest,
    hex_address,
    load_json,
    object_fields,
    text,
    uint,
)

type Domain = Literal["raw", "analyzed"]
type ValueKind = Literal["constant", "input", "defined", "free", "unexplained"]
type GapCode = Literal[
    "ssa_unbound",
    "cfg_unclosed",
    "unsupported_opcode",
    "volatile_or_unknown_memory",
    "source_unbound",
    "interface_unproved",
]


class ByteGraphError(ValueError):
    """The graph cannot be read under this structural contract."""


class ByteGraphFormatError(ByteGraphError):
    """The graph has invalid data or contradictory references."""


class ByteGraphLimitError(ByteGraphError):
    """A reader limit is invalid or an artifact exceeds a limit."""


@dataclass(frozen=True, slots=True)
class ByteGraphLimits:
    max_bytes: int = 16 * 1024 * 1024
    max_blocks: int = 32
    max_operations: int = 256
    max_raw_operations: int = 256
    max_raw_instructions: int = 256
    max_inputs: int = 256
    max_values: int = 256 * 257
    max_references: int = 256 * 257
    max_gaps: int = 256

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            maximum = field.default
            assert isinstance(maximum, int)
            if type(value) is not int or not 0 < value <= maximum:
                raise ByteGraphLimitError(f"Invalid limit: {field.name}.")


@dataclass(frozen=True, slots=True)
class FunctionKey:
    binary_sha256: str
    ghidra_entry: GhidraVA


@dataclass(frozen=True, slots=True)
class OpKey:
    function: FunctionKey
    domain: Domain
    pass_id: str
    sequence: Sequence


@dataclass(frozen=True, slots=True)
class ValueKey:
    function: FunctionKey
    pass_id: str
    local_id: int


@dataclass(frozen=True, slots=True)
class BlockKey:
    function: FunctionKey
    pass_id: str
    index: int


@dataclass(frozen=True, slots=True)
class EdgeSlot:
    other: BlockKey
    reciprocal_slot: int


@dataclass(frozen=True, slots=True)
class ValueRecord:
    id: ValueKey
    storage: Location
    size_bytes: int
    definition: OpKey | None
    kind: ValueKind
    bits: str | None
    address_tied: bool
    persistent: bool
    unaffected: bool


@dataclass(frozen=True, slots=True)
class AnalyzedOperation:
    id: OpKey
    opcode: str
    output: ValueKey | None
    inputs: tuple[ValueKey, ...]


@dataclass(frozen=True, slots=True)
class AnalyzedBlock:
    id: BlockKey
    start: GhidraVA
    incoming: tuple[EdgeSlot, ...]
    outgoing: tuple[EdgeSlot, ...]
    true_slot: int | None
    false_slot: int | None
    operations: tuple[AnalyzedOperation, ...]


@dataclass(frozen=True, slots=True)
class ByteGap:
    code: GapCode
    block: BlockKey | None
    operation: OpKey | None
    value: ValueKey | None


@dataclass(frozen=True, slots=True)
class ByteGraph:
    schema: Literal[1]
    binary_sha256: str
    lift_sha256: str
    function: FunctionKey
    pass_id: str
    raw_c_sha256: str
    ram_space_id: int
    ram_word_bytes: Literal[1]
    address_bits: Literal[64]
    byte_bits: Literal[8]
    endian: Literal["little"]
    entry: BlockKey
    blocks: tuple[AnalyzedBlock, ...]
    values: tuple[ValueRecord, ...]
    excluded_dead: tuple[OpKey, ...]
    raw_instruction_sites: tuple[GhidraVA, ...]
    explicit_volatile_sites: tuple[OpKey, ...]
    export_gaps: tuple[ByteGap, ...]

    def record(self) -> dict[str, object]:
        """Return a new wire object. No mutable child belongs to this graph."""
        return {field.name: _wire_field(self, field.name) for field in fields(self)}

    def to_bytes(self) -> bytes:
        return _canonical(self.record())

    @property
    def sha256(self) -> str:
        """Hash the complete canonical bytes outside the wire object."""
        return sha256(self.to_bytes()).hexdigest()


def _wire_field(record: object, name: str) -> object:
    value: object = getattr(record, name)
    if (
        (isinstance(record, FunctionKey) and name == "ghidra_entry")
        or (isinstance(record, AnalyzedBlock) and name == "start")
        or (isinstance(record, Location) and name == "offset")
    ):
        assert isinstance(value, int)
        return hex(value)
    if isinstance(record, ByteGraph) and name == "raw_instruction_sites":
        return [hex(site) for site in record.raw_instruction_sites]
    return _wire(value)


def _wire(value: object) -> object:
    if isinstance(value, tuple):
        return [_wire(child) for child in value]
    if isinstance(
        value,
        (
            FunctionKey,
            OpKey,
            ValueKey,
            BlockKey,
            EdgeSlot,
            ValueRecord,
            AnalyzedOperation,
            AnalyzedBlock,
            ByteGap,
            Location,
            Sequence,
        ),
    ):
        return {field.name: _wire_field(value, field.name) for field in fields(value)}
    return value


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _array(value: object, limit: int, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ByteGraphFormatError(f"Expected an array: {label}.")
    if len(value) > limit:
        raise ByteGraphLimitError(f"The {label} count exceeds its limit.")
    return cast(list[object], value)


def _choice[T: str](value: object, choices: tuple[T, ...]) -> T:
    for choice in choices:
        if type(value) is str and value == choice:
            return choice
    raise ByteGraphFormatError("Unknown graph discriminator.")


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ByteGraphFormatError("Expected a Boolean flag.")
    return value


def _constant(value: object, expected: int | str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ByteGraphFormatError("Unsupported graph profile constant.")


@dataclass(frozen=True, slots=True)
class _Reader:
    function: FunctionKey
    pass_id: str
    limits: ByteGraphLimits

    def function_key(self, value: object) -> FunctionKey:
        result = _function_key(value)
        if result != self.function:
            raise ByteGraphFormatError("A key names a different function or binary.")
        return result

    def scope(self, item: dict[str, object]) -> FunctionKey:
        function = self.function_key(item["function"])
        if digest(item["pass_id"]) != self.pass_id:
            raise ByteGraphFormatError("A key names a different pass.")
        return function

    def op_key(self, value: object, *, analyzed: bool = False) -> OpKey:
        item = object_fields(value, "function domain pass_id sequence")
        function = self.scope(item)
        domains: tuple[Domain, ...] = ("raw", "analyzed")
        domain = _choice(item["domain"], domains)
        if analyzed and domain != "analyzed":
            raise ByteGraphFormatError("Expected an analyzed operation key.")
        sequence = object_fields(item["sequence"], "address index")
        return OpKey(
            function,
            domain,
            self.pass_id,
            Sequence(
                _location(sequence["address"]), uint(sequence["index"], 1_000_000)
            ),
        )

    def value_key(self, value: object) -> ValueKey:
        item = object_fields(value, "function pass_id local_id")
        return ValueKey(
            self.scope(item), self.pass_id, uint(item["local_id"], 2**32 - 1)
        )

    def block_key(self, value: object) -> BlockKey:
        item = object_fields(value, "function pass_id index")
        return BlockKey(self.scope(item), self.pass_id, uint(item["index"], 2**31 - 1))

    def value(self, value: object) -> ValueRecord:
        item = object_fields(
            value,
            "id storage size_bytes definition kind bits "
            "address_tied persistent unaffected",
        )
        size = uint(item["size_bytes"], 65536)
        if not size:
            raise ByteGraphFormatError("A value must have a positive byte width.")
        result = ValueRecord(
            self.value_key(item["id"]),
            _location(item["storage"]),
            size,
            None
            if item["definition"] is None
            else self.op_key(item["definition"], analyzed=True),
            _choice(
                item["kind"], ("constant", "input", "defined", "free", "unexplained")
            ),
            None if item["bits"] is None else text(item["bits"]),
            _boolean(item["address_tied"]),
            _boolean(item["persistent"]),
            _boolean(item["unaffected"]),
        )
        if (result.kind == "defined") != (result.definition is not None):
            raise ByteGraphFormatError("The value kind and definition disagree.")
        if (result.kind == "constant") != (result.storage.space == "const"):
            raise ByteGraphFormatError("The constant kind and storage disagree.")
        if result.kind == "constant":
            bits = hex_address(result.bits)
            if bits != result.storage.offset or bits.bit_length() > size * 8:
                raise ByteGraphFormatError(
                    "The constant bits, width, and storage disagree."
                )
        elif result.bits is not None:
            raise ByteGraphFormatError("Only constants can have literal bits.")
        return result

    def operation(self, value: object) -> AnalyzedOperation:
        item = object_fields(value, "id opcode output inputs")
        opcode = text(item["opcode"])
        opcode.encode("utf-8")
        if not opcode:
            raise ByteGraphFormatError("The opcode is empty.")
        return AnalyzedOperation(
            self.op_key(item["id"], analyzed=True),
            opcode,
            None if item["output"] is None else self.value_key(item["output"]),
            tuple(
                self.value_key(v)
                for v in _array(item["inputs"], self.limits.max_inputs, "inputs")
            ),
        )

    def edges(self, value: object) -> tuple[EdgeSlot, ...]:
        result = []
        for edge in _array(value, self.limits.max_blocks, "edge slots"):
            item = object_fields(edge, "other reciprocal_slot")
            result.append(
                EdgeSlot(
                    self.block_key(item["other"]),
                    uint(item["reciprocal_slot"], self.limits.max_blocks - 1),
                )
            )
        return tuple(result)

    def block(self, value: object) -> AnalyzedBlock:
        item = object_fields(
            value, "id start incoming outgoing true_slot false_slot operations"
        )
        return AnalyzedBlock(
            self.block_key(item["id"]),
            GhidraVA(hex_address(item["start"])),
            self.edges(item["incoming"]),
            self.edges(item["outgoing"]),
            None
            if item["true_slot"] is None
            else uint(item["true_slot"], self.limits.max_blocks - 1),
            None
            if item["false_slot"] is None
            else uint(item["false_slot"], self.limits.max_blocks - 1),
            tuple(
                self.operation(v)
                for v in _array(
                    item["operations"], self.limits.max_operations, "operations"
                )
            ),
        )

    def gap(self, value: object) -> ByteGap:
        item = object_fields(value, "code block operation value")
        return ByteGap(
            _choice(
                item["code"],
                (
                    "ssa_unbound",
                    "cfg_unclosed",
                    "unsupported_opcode",
                    "volatile_or_unknown_memory",
                    "source_unbound",
                    "interface_unproved",
                ),
            ),
            None if item["block"] is None else self.block_key(item["block"]),
            None if item["operation"] is None else self.op_key(item["operation"]),
            None if item["value"] is None else self.value_key(item["value"]),
        )


def _location(value: object) -> Location:
    result = location(value)
    result.space.encode("utf-8")
    return result


def _function_key(value: object) -> FunctionKey:
    item = object_fields(value, "binary_sha256 ghidra_entry")
    return FunctionKey(
        digest(item["binary_sha256"]), GhidraVA(hex_address(item["ghidra_entry"]))
    )


def _preflight(
    item: dict[str, object], function: Function, limits: ByteGraphLimits
) -> None:
    blocks = _array(item["blocks"], limits.max_blocks, "blocks")
    dead = _array(item["excluded_dead"], limits.max_operations, "excluded operations")
    _array(
        item["values"],
        min(limits.max_values, limits.max_operations * (limits.max_inputs + 1)),
        "values",
    )
    _array(
        item["raw_instruction_sites"], limits.max_raw_instructions, "raw instructions"
    )
    _array(
        item["explicit_volatile_sites"],
        limits.max_operations + limits.max_raw_operations,
        "volatile sites",
    )
    _array(item["export_gaps"], limits.max_gaps, "export gaps")
    operations, references = len(dead), 0
    for raw_block in blocks:
        block = object_fields(
            raw_block, "id start incoming outgoing true_slot false_slot operations"
        )
        block_ops = _array(block["operations"], limits.max_operations, "operations")
        operations += len(block_ops)
        if operations > limits.max_operations:
            raise ByteGraphLimitError(
                "The complete analyzed operation count exceeds its limit."
            )
        for raw_op in block_ops:
            op = object_fields(raw_op, "id opcode output inputs")
            references += len(_array(op["inputs"], limits.max_inputs, "inputs")) + (
                op["output"] is not None
            )
            if references > limits.max_references:
                raise ByteGraphLimitError(
                    "The value reference count exceeds its limit."
                )
    if len(function.analyzed) > limits.max_operations:
        raise ByteGraphLimitError("The ordinary analyzed bank exceeds its limit.")
    if len(function.blocks) > limits.max_blocks:
        raise ByteGraphLimitError("The ordinary raw block count exceeds its limit.")
    if len(function.instructions) > limits.max_raw_instructions:
        raise ByteGraphLimitError(
            "The ordinary raw instruction count exceeds its limit."
        )
    raw_count = 0
    for instruction in function.instructions:
        raw_count += len(instruction.pcode)
        if raw_count > limits.max_raw_operations:
            raise ByteGraphLimitError(
                "The complete raw operation count exceeds its limit."
            )
        if any(len(op.inputs) > limits.max_inputs for op in instruction.pcode):
            raise ByteGraphLimitError("A raw input count exceeds its limit.")
    if any(len(op.inputs) > limits.max_inputs for op in function.analyzed):
        raise ByteGraphLimitError("An ordinary analyzed input count exceeds its limit.")


def _check_operand(value: ValueRecord, operand: Operand) -> None:
    definition = None if value.definition is None else value.definition.sequence
    if (value.storage, value.size_bytes, definition) != (
        operand.address,
        operand.size,
        operand.definition,
    ):
        raise ByteGraphFormatError("A value contradicts the ordinary operand.")


def _check_graph(graph: ByteGraph, function: Function) -> None:
    blocks = {block.id: block for block in graph.blocks}
    values = {value.id: value for value in graph.values}
    active = {op.id: op for block in graph.blocks for op in block.operations}
    active_count = sum(len(block.operations) for block in graph.blocks)
    if len(blocks) != len(graph.blocks) or graph.entry not in blocks:
        raise ByteGraphFormatError("The blocks or entry are missing or duplicated.")
    if len(values) != len(graph.values) or len(active) != active_count:
        raise ByteGraphFormatError(
            "A value or active operation has duplicate ownership."
        )
    if blocks[graph.entry].start != graph.function.ghidra_entry:
        raise ByteGraphFormatError(
            "The entry block does not start at the function entry."
        )
    bank = {
        OpKey(graph.function, "analyzed", graph.pass_id, op.sequence): op
        for op in function.analyzed
    }
    raw_bank = {
        OpKey(graph.function, "raw", graph.pass_id, op.sequence)
        for instruction in function.instructions
        for op in instruction.pcode
    }
    if len(bank) != len(function.analyzed) or len(raw_bank) != sum(
        len(ins.pcode) for ins in function.instructions
    ):
        raise ByteGraphFormatError(
            "The ordinary operation inventory has duplicate identities."
        )
    dead = set(graph.excluded_dead)
    if (
        len(dead) != len(graph.excluded_dead)
        or dead & active.keys()
        or dead | active.keys() != bank.keys()
    ):
        raise ByteGraphFormatError(
            "Active and excluded operations do not partition the ordinary bank."
        )
    if graph.raw_instruction_sites != tuple(
        ins.address for ins in function.instructions
    ):
        raise ByteGraphFormatError(
            "The raw instruction inventory differs from the ordinary lift."
        )
    used: set[ValueKey] = set()
    for operation in active.values():
        ordinary = bank[operation.id]
        if operation.opcode != ordinary.opcode or len(operation.inputs) != len(
            ordinary.inputs
        ):
            raise ByteGraphFormatError(
                "The analyzed opcode or input count contradicts the ordinary bank."
            )
        if (operation.output is None) != (ordinary.output is None):
            raise ByteGraphFormatError(
                "The analyzed output contradicts the ordinary bank."
            )
        for key, operand in zip(operation.inputs, ordinary.inputs, strict=True):
            if key not in values:
                raise ByteGraphFormatError("An input value is absent.")
            _check_operand(values[key], operand)
            used.add(key)
        if operation.output is not None:
            output = values.get(operation.output)
            if output is None or output.definition != operation.id:
                raise ByteGraphFormatError(
                    "An output does not name its exact definition."
                )
            assert ordinary.output is not None
            _check_operand(output, ordinary.output)
            used.add(output.id)
    if used != values.keys():
        raise ByteGraphFormatError("The value inventory has unused records.")
    for value in graph.values:
        if value.definition is not None:
            defining = active.get(value.definition)
            if defining is None or defining.output != value.id:
                raise ByteGraphFormatError(
                    "A value has an excluded, absent, or different definition output."
                )
    for block in graph.blocks:
        if not any(start <= block.start <= end for start, end in function.ranges):
            raise ByteGraphFormatError("A block start is outside the function.")
        for edges, incoming in ((block.incoming, True), (block.outgoing, False)):
            if len({edge.other for edge in edges}) != len(edges):
                raise ByteGraphFormatError(
                    "Parallel edges are outside this graph profile."
                )
            for slot, edge in enumerate(edges):
                other = blocks.get(edge.other)
                if other is None:
                    raise ByteGraphFormatError("An edge target is absent.")
                reverse = other.outgoing if incoming else other.incoming
                if edge.reciprocal_slot >= len(reverse) or reverse[
                    edge.reciprocal_slot
                ] != EdgeSlot(block.id, slot):
                    raise ByteGraphFormatError("Edge slots are not reciprocal.")
        conditional = [op for op in block.operations if op.opcode == "CBRANCH"]
        if conditional:
            if (
                len(conditional) != 1
                or conditional[0] != block.operations[-1]
                or len(block.outgoing) != 2
                or (block.false_slot, block.true_slot) != (0, 1)
            ):
                raise ByteGraphFormatError("The conditional block shape is invalid.")
            if len(conditional[0].inputs) != 2 or conditional[0].output is not None:
                raise ByteGraphFormatError(
                    "The conditional operation shape is invalid."
                )
        elif block.true_slot is not None or block.false_slot is not None:
            raise ByteGraphFormatError("Conditional slots require a terminal CBRANCH.")
        past_phi = False
        for op in block.operations:
            if op.opcode == "MULTIEQUAL":
                if (
                    past_phi
                    or not block.incoming
                    or len(op.inputs) != len(block.incoming)
                    or op.output is None
                ):
                    raise ByteGraphFormatError(
                        "The phi prefix or ordered operand count is invalid."
                    )
            else:
                past_phi = True
    all_ops = bank.keys() | raw_bank
    if len(set(graph.explicit_volatile_sites)) != len(
        graph.explicit_volatile_sites
    ) or any(op not in all_ops for op in graph.explicit_volatile_sites):
        raise ByteGraphFormatError("A volatile site is absent or duplicated.")
    if len(set(graph.export_gaps)) != len(graph.export_gaps):
        raise ByteGraphFormatError("An export gap is duplicated.")
    for gap in graph.export_gaps:
        if (
            (gap.block is not None and gap.block not in blocks)
            or (gap.operation is not None and gap.operation not in all_ops)
            or (gap.value is not None and gap.value not in values)
        ):
            raise ByteGraphFormatError("An export gap has an absent reference.")
        if (
            gap.block is not None
            and gap.operation is not None
            and gap.operation not in {op.id for op in blocks[gap.block].operations}
        ):
            raise ByteGraphFormatError(
                "The export gap block does not own its operation."
            )


def parse_byte_graph(
    raw: bytes, lift: LiftIndex, *, limits: ByteGraphLimits = ByteGraphLimits()
) -> ByteGraph:
    """Check structure against the ordinary lift. Producer flags remain proposals."""
    if type(limits) is not ByteGraphLimits:
        raise ByteGraphLimitError("Expected ByteGraphLimits.")
    limits.__post_init__()
    if type(raw) is not bytes:
        raise ByteGraphFormatError("Expected graph bytes.")
    if len(raw) > limits.max_bytes:
        raise ByteGraphLimitError("The graph byte count exceeds its limit.")
    try:
        item = object_fields(
            load_json(raw),
            "schema binary_sha256 lift_sha256 function pass_id raw_c_sha256 "
            "ram_space_id ram_word_bytes address_bits byte_bits endian entry "
            "blocks values excluded_dead raw_instruction_sites "
            "explicit_volatile_sites export_gaps",
        )
        if _canonical(item) != raw:
            raise ByteGraphFormatError(
                "Expected canonical ASCII JSON and one final LF."
            )
        for name, expected in (
            ("schema", 1),
            ("ram_word_bytes", 1),
            ("address_bits", 64),
            ("byte_bits", 8),
            ("endian", "little"),
        ):
            _constant(item[name], expected)
        function_key = _function_key(item["function"])
        binary_hash, lift_hash = (
            digest(item["binary_sha256"]),
            digest(item["lift_sha256"]),
        )
        function = lift.functions.get(function_key.ghidra_entry)
        if (
            binary_hash != lift.binary_sha256
            or function_key.binary_sha256 != binary_hash
            or lift_hash != lift.lift_sha256
            or function is None
            or function.entry != function_key.ghidra_entry
        ):
            raise ByteGraphFormatError(
                "The graph does not bind the supplied lift function."
            )
        source_hash = digest(item["raw_c_sha256"])
        if (
            function.raw_c is None
            or sha256(function.raw_c.encode("utf-8")).hexdigest() != source_hash
        ):
            raise ByteGraphFormatError(
                "The graph does not bind exact ordinary raw C bytes."
            )
        _preflight(item, function, limits)
        reader = _Reader(function_key, digest(item["pass_id"]), limits)
        result = ByteGraph(
            1,
            binary_hash,
            lift_hash,
            function_key,
            reader.pass_id,
            source_hash,
            uint(item["ram_space_id"], 2**32 - 1),
            1,
            64,
            8,
            "little",
            reader.block_key(item["entry"]),
            tuple(
                reader.block(v)
                for v in _array(item["blocks"], limits.max_blocks, "blocks")
            ),
            tuple(
                reader.value(v)
                for v in _array(item["values"], limits.max_values, "values")
            ),
            tuple(
                reader.op_key(v, analyzed=True)
                for v in _array(
                    item["excluded_dead"], limits.max_operations, "excluded operations"
                )
            ),
            tuple(
                GhidraVA(hex_address(v))
                for v in _array(
                    item["raw_instruction_sites"],
                    limits.max_raw_instructions,
                    "raw instructions",
                )
            ),
            tuple(
                reader.op_key(v)
                for v in _array(
                    item["explicit_volatile_sites"],
                    limits.max_operations + limits.max_raw_operations,
                    "volatile sites",
                )
            ),
            tuple(
                reader.gap(v)
                for v in _array(item["export_gaps"], limits.max_gaps, "export gaps")
            ),
        )
        _check_graph(result, function)
        return result
    except MappingError as error:
        raise ByteGraphFormatError(str(error)) from error
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ByteGraphFormatError("Invalid graph encoding or nesting.") from error
    except ValueError as error:
        if isinstance(error, ByteGraphError):
            raise
        raise ByteGraphFormatError("Invalid graph data.") from error
