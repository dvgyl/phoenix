"""Read schema 2 observations. These records grant no semantic authority."""

import json
import re
from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
from typing import Literal, cast

from phoenix.lift.index import Function, LiftIndex, Location, Operand, Sequence
from phoenix.lift.mapping import GhidraVA

type Domain = Literal["raw", "analyzed"]
type GapCode = Literal[
    "native_state_unavailable",
    "native_inventory_unavailable",
    "native_cover_unavailable",
    "entry_effect_binding_unproved",
    "memory_effects_unproved",
    "unowned_operation",
    "ssa_unbound",
    "phi_binding_unproved",
    "cfg_unclosed",
    "unsupported_opcode",
    "volatile_or_unknown_memory",
    "source_unbound",
    "interface_unproved",
]

PROFILE = "ordinary-byte-adapter/1"
_GAP_CODES: tuple[GapCode, ...] = (
    "native_state_unavailable",
    "native_inventory_unavailable",
    "native_cover_unavailable",
    "entry_effect_binding_unproved",
    "memory_effects_unproved",
    "unowned_operation",
    "ssa_unbound",
    "phi_binding_unproved",
    "cfg_unclosed",
    "unsupported_opcode",
    "volatile_or_unknown_memory",
    "source_unbound",
    "interface_unproved",
)
_MANDATORY: tuple[GapCode, ...] = _GAP_CODES[:5]
_KNOWN_OPCODES = frozenset(
    """
UNIMPLEMENTED COPY LOAD STORE BRANCH CBRANCH BRANCHIND CALL CALLIND CALLOTHER RETURN
INT_EQUAL INT_NOTEQUAL INT_SLESS INT_SLESSEQUAL INT_LESS INT_LESSEQUAL INT_ZEXT
INT_SEXT INT_ADD INT_SUB INT_CARRY INT_SCARRY INT_SBORROW INT_2COMP INT_NEGATE
INT_XOR INT_AND INT_OR INT_LEFT INT_RIGHT INT_SRIGHT INT_MULT INT_DIV INT_SDIV
INT_REM INT_SREM BOOL_NEGATE BOOL_XOR BOOL_AND BOOL_OR FLOAT_EQUAL FLOAT_NOTEQUAL
FLOAT_LESS FLOAT_LESSEQUAL FLOAT_NAN FLOAT_ADD FLOAT_DIV FLOAT_MULT FLOAT_SUB
FLOAT_NEG FLOAT_ABS FLOAT_SQRT INT2FLOAT FLOAT2FLOAT TRUNC
CEIL FLOOR ROUND MULTIEQUAL INDIRECT PIECE SUBPIECE CAST PTRADD
PTRSUB SEGMENTOP CPOOLREF NEW INSERT ZPULL POPCOUNT LZCOUNT SPULL
""".split()
)


class ByteGraphV2Error(ValueError):
    """The observation cannot be read under this contract."""


class ByteGraphV2FormatError(ByteGraphV2Error):
    """The structure or a local relation is invalid."""


class ByteGraphV2LimitError(ByteGraphV2Error):
    """A limit is invalid or exceeded."""


class ByteGraphV2PinError(ByteGraphV2Error):
    """The supplied pass differs from the fixed profile."""


class ByteGraphV2BindingError(ByteGraphV2Error):
    """The graph does not match the supplied pass or lift."""


@dataclass(frozen=True, slots=True)
class ByteGraphV2Limits:
    max_graph_bytes: int = 16 * 1024 * 1024
    max_source_bytes: int = 1024 * 1024
    max_functions: int = 32
    max_blocks: int = 32
    max_listing_blocks: int = 32
    max_operations: int = 256
    max_raw_operations: int = 256
    max_raw_instructions: int = 256
    max_inputs: int = 256
    max_values: int = 65792
    max_references: int = 65792
    max_edges: int = 1024
    max_gaps: int = 256
    max_json_depth: int = 32

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            maximum = field.default
            assert isinstance(maximum, int)
            if type(value) is not int or not 0 < value <= maximum:
                raise ByteGraphV2LimitError("A graph limit is invalid.")


class _Record:
    __slots__ = ()

    def record(self) -> dict[str, object]:
        result = _wire(self)
        assert isinstance(result, dict)
        return cast(dict[str, object], result)

    def to_bytes(self) -> bytes:
        return _canonical(self.record())

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()


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
class PassRecord(_Record):
    schema: Literal[1]
    profile: Literal["ordinary-byte-adapter/1"]
    function: FunctionKey
    call_ordinal: int
    ghidra_version: str
    ghidra_revision: str
    java_runtime_version: str
    language_id: str
    compiler_spec_id: str
    simplification_style: str
    configured_options: None
    timeout_seconds: Literal[60]
    printer_transformer: str
    line_separator: Literal["\n", "\r\n"]
    source_manifest_sha256: str
    tool_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class EntryV2:
    ordinary_entry: Location
    analyzed_block: BlockKey
    selection: Literal["pinned_native_index_zero"]
    native_entry_address: None


@dataclass(frozen=True, slots=True)
class BlockV2:
    id: BlockKey
    cover_min: Location | None
    cover_max: Location | None
    incoming: tuple[EdgeSlot, ...]
    outgoing: tuple[EdgeSlot, ...]
    operations: tuple[OpKey, ...]


@dataclass(frozen=True, slots=True)
class OperationV2:
    id: OpKey
    opcode: str
    output: ValueKey | None
    inputs: tuple[ValueKey, ...]
    java_is_dead: bool
    parent: BlockKey | None
    java_order: int


@dataclass(frozen=True, slots=True)
class ValueV2:
    id: ValueKey
    storage: Location
    size_bytes: int
    definition: OpKey | None
    bits: str | None
    is_constant: bool
    is_input: bool
    is_free: bool
    address_tied: bool
    persistent: bool
    unaffected: bool


@dataclass(frozen=True, slots=True)
class NativeInventory:
    operation_flags: Literal["not_exported"]
    operation_bank: Literal["not_exported"]
    removed_operations: Literal["not_exported"]
    block_cover_ranges: Literal["not_exported"]


@dataclass(frozen=True, slots=True)
class GapV2:
    code: GapCode
    block: BlockKey | None
    operation: OpKey | None
    value: ValueKey | None
    item_ordinal: None


@dataclass(frozen=True, slots=True)
class ByteGraphV2(_Record):
    schema: Literal[2]
    profile: Literal["ordinary-byte-adapter/1"]
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
    entry: EntryV2
    blocks: tuple[BlockV2, ...]
    operations: tuple[OperationV2, ...]
    values: tuple[ValueV2, ...]
    raw_instruction_sites: tuple[Location, ...]
    raw_operation_keys: tuple[OpKey, ...]
    explicit_volatile_sites: tuple[OpKey, ...]
    native_inventory: NativeInventory
    gaps: tuple[GapV2, ...]


def _wire(value: object) -> object:
    if isinstance(value, Location):
        return {"space": value.space, "offset": hex(value.offset)}
    if isinstance(value, FunctionKey):
        return {
            "binary_sha256": value.binary_sha256,
            "ghidra_entry": hex(value.ghidra_entry),
        }
    if isinstance(value, tuple):
        return [_wire(child) for child in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _wire(getattr(value, field.name)) for field in fields(value)
        }
    return value


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _object(value: object, names: str) -> dict[str, object]:
    if type(value) is not dict or value.keys() != set(names.split()):
        raise ByteGraphV2FormatError("The object fields do not match the schema.")
    return cast(dict[str, object], value)


def _array(value: object, maximum: int) -> list[object]:
    if type(value) is not list:
        raise ByteGraphV2FormatError("Expected an array.")
    _count(len(value), maximum)
    return cast(list[object], value)


def _count(count: int, maximum: int) -> None:
    if count > maximum:
        raise ByteGraphV2LimitError("An observation count or byte limit is exceeded.")


def _int(value: object, low: int = 0, high: int = 2**64 - 1) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ByteGraphV2FormatError("Expected an integer within the field bounds.")
    return value


def _text(value: object, maximum: int) -> str:
    if type(value) is not str or not value:
        raise ByteGraphV2FormatError("Expected nonempty text.")
    try:
        data = value.encode("utf-8")
    except UnicodeError as error:
        raise ByteGraphV2FormatError(
            "Text contains an invalid Unicode scalar."
        ) from error
    if len(data) > maximum:
        raise ByteGraphV2FormatError("Text exceeds its field bound.")
    return value


def _hex(value: object) -> int:
    text = _text(value, 18)
    if re.fullmatch(r"0x(?:0|[1-9a-f][0-9a-f]{0,15})", text) is None:
        raise ByteGraphV2FormatError("Expected canonical unsigned hexadecimal text.")
    return int(text, 16)


def _digest(value: object) -> str:
    text = _text(value, 64)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ByteGraphV2FormatError("Expected a lowercase SHA-256 digest.")
    return text


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ByteGraphV2FormatError("Expected an actual Boolean.")
    return value


def _fixed(value: object, expected: object) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ByteGraphV2FormatError("A fixed graph field is invalid.")


def _choice[T: str](value: object, choices: tuple[T, ...]) -> T:
    for choice in choices:
        if type(value) is str and value == choice:
            return choice
    raise ByteGraphV2FormatError("An observation discriminator is unknown.")


def _location(value: object) -> Location:
    item = _object(value, "space offset")
    return Location(_text(item["space"], 128), _hex(item["offset"]))


def _function(value: object) -> FunctionKey:
    item = _object(value, "binary_sha256 ghidra_entry")
    return FunctionKey(
        _digest(item["binary_sha256"]), GhidraVA(_hex(item["ghidra_entry"]))
    )


def _sequence(value: object) -> Sequence:
    item = _object(value, "address index")
    return Sequence(_location(item["address"]), _int(item["index"], high=1_000_000))


def _opcode(value: object) -> str:
    text = _text(value, 64)
    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", text) is None:
        raise ByteGraphV2FormatError("Expected an ASCII opcode identifier.")
    return text


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ByteGraphV2FormatError("A JSON object has a duplicate key.")
        result[key] = value
    return result


def _no_float(value: str) -> object:
    raise ByteGraphV2FormatError("JSON floating-point values are not permitted.")


def _load(raw: bytes, maximum: int, depth_limit: int) -> object:
    if type(raw) is not bytes:
        raise ByteGraphV2FormatError("Expected immutable bytes.")
    _count(len(raw), maximum)
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            _count(depth, depth_limit)
        elif byte in (93, 125):
            depth -= 1
    try:
        value: object = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_float=_no_float,
            parse_constant=_no_float,
        )
    except ByteGraphV2Error:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ByteGraphV2FormatError("The JSON encoding is invalid.") from error
    return value


def _limits(limits: ByteGraphV2Limits) -> None:
    if type(limits) is not ByteGraphV2Limits:
        raise ByteGraphV2LimitError("Expected graph limits.")
    limits.__post_init__()


def _pass(value: object) -> PassRecord:
    item = _object(
        value,
        "schema profile function call_ordinal ghidra_version "
        "ghidra_revision java_runtime_version language_id compiler_spec_id "
        "simplification_style configured_options timeout_seconds "
        "printer_transformer line_separator source_manifest_sha256 "
        "tool_manifest_sha256",
    )
    for name, expected in (
        ("schema", 1),
        ("profile", PROFILE),
        ("ghidra_version", "12.2"),
        ("ghidra_revision", "8ca9077040cc43cd790babcfccf19475622a3e9a"),
        ("java_runtime_version", "25.0.5+8-LTS"),
        ("language_id", "x86:LE:64:default"),
        ("compiler_spec_id", "gcc"),
        ("simplification_style", "decompile"),
        ("configured_options", None),
        ("timeout_seconds", 60),
        (
            "printer_transformer",
            "ghidra.program.model.symbol.IllegalCharCppTransformer",
        ),
    ):
        if type(item[name]) is not type(expected) or item[name] != expected:
            raise ByteGraphV2PinError(
                "The supplied pass differs from the pinned profile."
            )
    return PassRecord(
        1,
        "ordinary-byte-adapter/1",
        _function(item["function"]),
        _int(item["call_ordinal"], high=31),
        "12.2",
        "8ca9077040cc43cd790babcfccf19475622a3e9a",
        "25.0.5+8-LTS",
        "x86:LE:64:default",
        "gcc",
        "decompile",
        None,
        60,
        "ghidra.program.model.symbol.IllegalCharCppTransformer",
        _choice(item["line_separator"], ("\n", "\r\n")),
        _digest(item["source_manifest_sha256"]),
        _digest(item["tool_manifest_sha256"]),
    )


def parse_pass_record(raw: bytes) -> PassRecord:
    """Check supplied pass data. A matching hash does not authenticate a call."""
    return _pass(_load(raw, 64 * 1024, 32))


@dataclass(frozen=True, slots=True)
class _Reader:
    function: FunctionKey
    pass_id: str
    limits: ByteGraphV2Limits

    def scope(self, item: dict[str, object]) -> None:
        if (
            _function(item["function"]) != self.function
            or _digest(item["pass_id"]) != self.pass_id
        ):
            raise ByteGraphV2FormatError("A key names a foreign function or pass.")

    def op_key(self, value: object, domain: Domain | None = None) -> OpKey:
        item = _object(value, "function pass_id domain sequence")
        self.scope(item)
        domains: tuple[Domain, ...] = ("raw", "analyzed")
        actual = _choice(item["domain"], domains)
        if domain is not None and actual != domain:
            raise ByteGraphV2FormatError("An operation key has the wrong domain.")
        return OpKey(self.function, actual, self.pass_id, _sequence(item["sequence"]))

    def value_key(self, value: object) -> ValueKey:
        item = _object(value, "function pass_id local_id")
        self.scope(item)
        return ValueKey(
            self.function, self.pass_id, _int(item["local_id"], high=2**32 - 1)
        )

    def block_key(self, value: object) -> BlockKey:
        item = _object(value, "function pass_id index")
        self.scope(item)
        return BlockKey(
            self.function, self.pass_id, _int(item["index"], high=2**31 - 1)
        )

    def entry(self, value: object) -> EntryV2:
        item = _object(
            value, "ordinary_entry analyzed_block selection native_entry_address"
        )
        _fixed(item["selection"], "pinned_native_index_zero")
        _fixed(item["native_entry_address"], None)
        return EntryV2(
            _location(item["ordinary_entry"]),
            self.block_key(item["analyzed_block"]),
            "pinned_native_index_zero",
            None,
        )

    def edges(self, value: object) -> tuple[EdgeSlot, ...]:
        result = []
        for edge in _array(value, self.limits.max_edges):
            item = _object(edge, "other reciprocal_slot")
            result.append(
                EdgeSlot(
                    self.block_key(item["other"]),
                    _int(item["reciprocal_slot"], high=self.limits.max_edges - 1),
                )
            )
        return tuple(result)

    def block(self, value: object) -> BlockV2:
        item = _object(value, "id cover_min cover_max incoming outgoing operations")
        lower = None if item["cover_min"] is None else _location(item["cover_min"])
        upper = None if item["cover_max"] is None else _location(item["cover_max"])
        if (lower is None) != (upper is None) or (
            lower is not None
            and upper is not None
            and (lower.space != upper.space or lower.offset > upper.offset)
        ):
            raise ByteGraphV2FormatError("The block cover endpoints disagree.")
        return BlockV2(
            self.block_key(item["id"]),
            lower,
            upper,
            self.edges(item["incoming"]),
            self.edges(item["outgoing"]),
            tuple(
                self.op_key(v, "analyzed")
                for v in _array(item["operations"], self.limits.max_operations)
            ),
        )

    def operation(self, value: object) -> OperationV2:
        item = _object(value, "id opcode output inputs java_is_dead parent java_order")
        return OperationV2(
            self.op_key(item["id"], "analyzed"),
            _opcode(item["opcode"]),
            None if item["output"] is None else self.value_key(item["output"]),
            tuple(
                self.value_key(v)
                for v in _array(item["inputs"], self.limits.max_inputs)
            ),
            _boolean(item["java_is_dead"]),
            None if item["parent"] is None else self.block_key(item["parent"]),
            _int(item["java_order"], -(2**31), 2**31 - 1),
        )

    def value(self, value: object) -> ValueV2:
        item = _object(
            value,
            "id storage size_bytes definition bits is_constant is_input "
            "is_free address_tied persistent unaffected",
        )
        constant = _boolean(item["is_constant"])
        storage = _location(item["storage"])
        size = _int(item["size_bytes"], 1, 65536)
        bits = None
        if constant:
            number = _hex(item["bits"])
            if number != storage.offset or number.bit_length() > size * 8:
                raise ByteGraphV2FormatError(
                    "The constant bits do not match the storage width or offset."
                )
            bits = hex(number)
        elif item["bits"] is not None:
            raise ByteGraphV2FormatError("A nonconstant value has literal bits.")
        return ValueV2(
            self.value_key(item["id"]),
            storage,
            size,
            None
            if item["definition"] is None
            else self.op_key(item["definition"], "analyzed"),
            bits,
            constant,
            _boolean(item["is_input"]),
            _boolean(item["is_free"]),
            _boolean(item["address_tied"]),
            _boolean(item["persistent"]),
            _boolean(item["unaffected"]),
        )

    def gap(self, value: object) -> GapV2:
        item = _object(value, "code block operation value item_ordinal")
        _fixed(item["item_ordinal"], None)
        return GapV2(
            _choice(item["code"], _GAP_CODES),
            None if item["block"] is None else self.block_key(item["block"]),
            None if item["operation"] is None else self.op_key(item["operation"]),
            None if item["value"] is None else self.value_key(item["value"]),
            None,
        )


def _check_operand(value: ValueV2, operand: Operand) -> None:
    definition = None if value.definition is None else value.definition.sequence
    if (value.storage, value.size_bytes, definition) != (
        operand.address,
        operand.size,
        operand.definition,
    ):
        raise ByteGraphV2BindingError("An operand differs from the ordinary lift.")


def _bound_location(value: Location) -> None:
    if type(value) is not Location:
        raise ByteGraphV2FormatError("Expected an ordinary address record.")
    _text(value.space, 128)
    _int(value.offset)


def _bound_sequence(value: Sequence) -> None:
    if type(value) is not Sequence:
        raise ByteGraphV2FormatError("Expected an ordinary sequence record.")
    _bound_location(value.address)
    _int(value.index, high=1_000_000)


def _bound_function(
    lift: LiftIndex, record: PassRecord, limits: ByteGraphV2Limits
) -> Function:
    if type(lift) is not LiftIndex:
        raise ByteGraphV2FormatError("Expected an ordinary lift index.")
    _count(len(lift.functions), limits.max_functions)
    roster = tuple(lift.functions)
    for entry in roster:
        _int(entry)
    if (
        record.call_ordinal >= len(roster)
        or roster[record.call_ordinal] != record.function.ghidra_entry
        or lift.binary_sha256 != record.function.binary_sha256
    ):
        raise ByteGraphV2BindingError(
            "The pass does not bind the ordinary function roster."
        )
    function = lift.functions[record.function.ghidra_entry]
    if type(function) is not Function:
        raise ByteGraphV2BindingError("The ordinary function identity is invalid.")
    _int(function.entry)
    if function.entry != record.function.ghidra_entry:
        raise ByteGraphV2BindingError("The ordinary function identity is invalid.")
    _count(len(function.blocks), limits.max_listing_blocks)
    _count(len(function.instructions), limits.max_raw_instructions)
    _count(len(function.ranges), limits.max_raw_instructions)
    _count(
        sum(len(block.ranges) for block in function.blocks), limits.max_raw_instructions
    )
    for edge in lift.edges:
        if edge.caller is not None:
            _int(edge.caller)
    _count(sum(edge.caller == function.entry for edge in lift.edges), limits.max_edges)
    for start, end in (
        *function.ranges,
        *(region for block in function.blocks for region in block.ranges),
    ):
        _int(start)
        _int(end, start)
    for block in function.blocks:
        _int(block.entry)
    for instruction in function.instructions:
        _int(instruction.address)
        _int(instruction.size, 1, 15)
        if instruction.address + instruction.size > 2**64:
            raise ByteGraphV2FormatError("An instruction interval wraps.")
    _count(
        sum(len(ins.pcode) for ins in function.instructions), limits.max_raw_operations
    )
    for operations, maximum in (
        (function.analyzed, limits.max_operations),
        (
            tuple(op for ins in function.instructions for op in ins.pcode),
            limits.max_raw_operations,
        ),
    ):
        _count(len(operations), maximum)
        references = 0
        for operation in operations:
            _bound_sequence(operation.sequence)
            _opcode(operation.opcode)
            _count(len(operation.inputs), limits.max_inputs)
            references += len(operation.inputs) + (operation.output is not None)
            _count(references, limits.max_references)
            for operand in (
                *operation.inputs,
                *((operation.output,) if operation.output is not None else ()),
            ):
                _bound_location(operand.address)
                _int(operand.size, 1, 65536)
                if operand.definition is not None:
                    _bound_sequence(operand.definition)
    return function


def _check_graph(
    graph: ByteGraphV2, function: Function, limits: ByteGraphV2Limits
) -> None:
    blocks = {block.id: block for block in graph.blocks}
    operations = {op.id: op for op in graph.operations}
    values = {value.id: value for value in graph.values}
    if (
        not blocks
        or len(blocks) != len(graph.blocks)
        or any(block.id.index != slot for slot, block in enumerate(graph.blocks))
    ):
        raise ByteGraphV2FormatError(
            "The block inventory has a missing slot or duplicate identity."
        )
    if len(operations) != len(graph.operations) or len(values) != len(graph.values):
        raise ByteGraphV2FormatError("An operation or value identity is duplicated.")
    if graph.entry.analyzed_block != graph.blocks[
        0
    ].id or graph.entry.ordinary_entry != Location("ram", function.entry):
        raise ByteGraphV2BindingError(
            "The entry does not bind the ordinary entry and block zero."
        )
    expected_keys = tuple(
        OpKey(graph.function, "analyzed", graph.pass_id, op.sequence)
        for op in function.analyzed
    )
    if tuple(op.id for op in graph.operations) != expected_keys:
        raise ByteGraphV2BindingError(
            "The operation bank differs from the ordinary roster."
        )
    raw_keys = tuple(
        OpKey(graph.function, "raw", graph.pass_id, op.sequence)
        for ins in function.instructions
        for op in ins.pcode
    )
    if (
        graph.raw_operation_keys != raw_keys
        or len(set(raw_keys)) != len(raw_keys)
        or len(set(expected_keys)) != len(expected_keys)
    ):
        raise ByteGraphV2BindingError(
            "The raw operation roster differs or has duplicate identities."
        )
    if graph.raw_instruction_sites != tuple(
        Location("ram", ins.address) for ins in function.instructions
    ) or len(set(graph.raw_instruction_sites)) != len(graph.raw_instruction_sites):
        raise ByteGraphV2BindingError(
            "The raw instruction roster differs or has duplicate sites."
        )
    _count(
        sum(len(op.inputs) + (op.output is not None) for op in graph.operations),
        limits.max_references,
    )
    _count(sum(len(block.outgoing) for block in graph.blocks), limits.max_edges)
    _count(sum(len(block.incoming) for block in graph.blocks), limits.max_edges)
    _count(sum(len(block.operations) for block in graph.blocks), limits.max_operations)
    owned: set[OpKey] = set()
    for block in graph.blocks:
        for slot, key in enumerate(block.operations):
            op = operations.get(key)
            if (
                key in owned
                or op is None
                or op.parent != block.id
                or op.java_order != slot
            ):
                raise ByteGraphV2FormatError(
                    "The block membership or operation order is contradictory."
                )
            owned.add(key)
        for edges, incoming in ((block.incoming, True), (block.outgoing, False)):
            for slot, edge in enumerate(edges):
                other = blocks.get(edge.other)
                if other is None:
                    raise ByteGraphV2FormatError("An edge names an absent block.")
                reverse = other.outgoing if incoming else other.incoming
                if edge.reciprocal_slot >= len(reverse) or reverse[
                    edge.reciprocal_slot
                ] != EdgeSlot(block.id, slot):
                    raise ByteGraphV2FormatError(
                        "The ordered edges are not reciprocal."
                    )
    for op, ordinary in zip(graph.operations, function.analyzed, strict=True):
        if (op.parent is None) != (op.id not in owned):
            raise ByteGraphV2FormatError(
                "The operation parent and block list disagree."
            )
        if (
            op.opcode != ordinary.opcode
            or len(op.inputs) != len(ordinary.inputs)
            or (op.output is None) != (ordinary.output is None)
        ):
            raise ByteGraphV2BindingError(
                "An operation differs from the ordinary lift."
            )
        for value_key, operand in zip(op.inputs, ordinary.inputs, strict=True):
            value = values.get(value_key)
            if value is None:
                raise ByteGraphV2FormatError("An input value is absent.")
            _check_operand(value, operand)
        if op.output is not None:
            output = values.get(op.output)
            if output is None or output.definition != op.id:
                raise ByteGraphV2FormatError("The output has no matching definition.")
            assert ordinary.output is not None
            _check_operand(output, ordinary.output)
    for value in graph.values:
        if value.definition is not None:
            definition = operations.get(value.definition)
            if definition is None or definition.output != value.id:
                raise ByteGraphV2FormatError(
                    "A value definition has a different output identity."
                )
    all_operations = set(operations) | set(raw_keys)
    if len(set(graph.explicit_volatile_sites)) != len(
        graph.explicit_volatile_sites
    ) or any(key not in all_operations for key in graph.explicit_volatile_sites):
        raise ByteGraphV2FormatError("A volatile site is absent or duplicated.")
    _check_gaps(graph, blocks, operations, values, all_operations, function)


def _check_gaps(
    graph: ByteGraphV2,
    blocks: dict[BlockKey, BlockV2],
    operations: dict[OpKey, OperationV2],
    values: dict[ValueKey, ValueV2],
    all_operations: set[OpKey],
    function: Function,
) -> None:
    canonical = tuple(_canonical(_wire(gap)) for gap in graph.gaps)
    if canonical != tuple(sorted(set(canonical))):
        raise ByteGraphV2FormatError("Gaps must be unique and in canonical order.")
    gaps = set(graph.gaps)
    required = {GapV2(code, None, None, None, None) for code in _MANDATORY}
    for gap in graph.gaps:
        if (
            (gap.block is not None and gap.block not in blocks)
            or (gap.operation is not None and gap.operation not in all_operations)
            or (gap.value is not None and gap.value not in values)
        ):
            raise ByteGraphV2FormatError("A gap reference is absent.")
        if (
            gap.block is not None
            and gap.operation is not None
            and gap.operation not in blocks[gap.block].operations
        ):
            raise ByteGraphV2FormatError("The gap block does not own its operation.")
    for op in operations.values():
        if op.parent is None:
            required.add(GapV2("unowned_operation", None, op.id, None, None))
        if op.opcode == "MULTIEQUAL" and (
            op.parent is None or len(op.inputs) != len(blocks[op.parent].incoming)
        ):
            required.add(GapV2("phi_binding_unproved", None, op.id, None, None))
        if op.opcode not in _KNOWN_OPCODES:
            required.add(GapV2("unsupported_opcode", None, op.id, None, None))
    for key, raw_op in zip(
        graph.raw_operation_keys,
        (op for ins in function.instructions for op in ins.pcode),
        strict=True,
    ):
        if raw_op.opcode not in _KNOWN_OPCODES:
            required.add(GapV2("unsupported_opcode", None, key, None, None))
    for value in values.values():
        interpretations = (
            int(value.is_constant)
            + int(value.is_input)
            + int(value.definition is not None)
        )
        if interpretations != 1 or (value.is_free and not value.is_constant):
            required.add(GapV2("ssa_unbound", None, None, value.id, None))
    if not required <= gaps:
        raise ByteGraphV2FormatError("A required observation gap is absent.")


def parse_byte_graph_v2(
    raw_bytes: bytes,
    *,
    lift: LiftIndex,
    pass_record: PassRecord,
    limits: ByteGraphV2Limits = ByteGraphV2Limits(),
) -> ByteGraphV2:
    """Check structure and supplied bindings. No producer or effect is certified."""
    _limits(limits)
    item = _object(
        _load(raw_bytes, limits.max_graph_bytes, limits.max_json_depth),
        "schema profile binary_sha256 lift_sha256 function pass_id "
        "raw_c_sha256 ram_space_id ram_word_bytes address_bits byte_bits "
        "endian entry blocks operations values raw_instruction_sites "
        "raw_operation_keys explicit_volatile_sites native_inventory gaps",
    )
    for name, expected in (
        ("schema", 2),
        ("profile", PROFILE),
        ("ram_word_bytes", 1),
        ("address_bits", 64),
        ("byte_bits", 8),
        ("endian", "little"),
    ):
        _fixed(item[name], expected)
    if type(pass_record) is not PassRecord:
        raise ByteGraphV2FormatError("Expected a supplied pass record.")
    if type(pass_record.function) is not FunctionKey:
        raise ByteGraphV2FormatError("Expected a pass function key.")
    pass_fields = {
        field.name: getattr(pass_record, field.name) for field in fields(pass_record)
    }
    pass_fields["function"] = {
        "binary_sha256": pass_record.function.binary_sha256,
        "ghidra_entry": hex(_int(pass_record.function.ghidra_entry)),
    }
    record = _pass(pass_fields)
    function = _bound_function(lift, record, limits)
    function_key = _function(item["function"])
    if (
        function_key != record.function
        or _digest(item["pass_id"]) != record.sha256
        or _digest(item["binary_sha256"]) != lift.binary_sha256
        or _digest(item["lift_sha256"]) != lift.lift_sha256
    ):
        raise ByteGraphV2BindingError(
            "The graph does not bind the supplied lift and pass."
        )
    if function.raw_c is None or type(function.raw_c) is not str:
        raise ByteGraphV2BindingError("Ordinary source bytes are unavailable.")
    _count(len(function.raw_c), limits.max_source_bytes)
    try:
        source = function.raw_c.encode("utf-8")
    except UnicodeError as error:
        raise ByteGraphV2FormatError(
            "Ordinary source text has an invalid Unicode scalar."
        ) from error
    _count(len(source), limits.max_source_bytes)
    source_hash = _digest(item["raw_c_sha256"])
    if source_hash != sha256(source).hexdigest():
        raise ByteGraphV2BindingError(
            "The graph does not bind the exact ordinary source bytes."
        )
    reader = _Reader(function_key, record.sha256, limits)
    native = _object(
        item["native_inventory"],
        "operation_flags operation_bank removed_operations block_cover_ranges",
    )
    for value in native.values():
        _fixed(value, "not_exported")
    result = ByteGraphV2(
        2,
        "ordinary-byte-adapter/1",
        function_key.binary_sha256,
        lift.lift_sha256,
        function_key,
        reader.pass_id,
        source_hash,
        _int(item["ram_space_id"], -(2**31), 2**31 - 1),
        1,
        64,
        8,
        "little",
        reader.entry(item["entry"]),
        tuple(reader.block(v) for v in _array(item["blocks"], limits.max_blocks)),
        tuple(
            reader.operation(v)
            for v in _array(item["operations"], limits.max_operations)
        ),
        tuple(reader.value(v) for v in _array(item["values"], limits.max_values)),
        tuple(
            _location(v)
            for v in _array(item["raw_instruction_sites"], limits.max_raw_instructions)
        ),
        tuple(
            reader.op_key(v, "raw")
            for v in _array(item["raw_operation_keys"], limits.max_raw_operations)
        ),
        tuple(
            reader.op_key(v)
            for v in _array(
                item["explicit_volatile_sites"],
                limits.max_operations + limits.max_raw_operations,
            )
        ),
        NativeInventory("not_exported", "not_exported", "not_exported", "not_exported"),
        tuple(reader.gap(v) for v in _array(item["gaps"], limits.max_gaps)),
    )
    _check_graph(result, function, limits)
    _count(len(result.to_bytes()), limits.max_graph_bytes)
    return result
