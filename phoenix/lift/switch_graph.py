from dataclasses import dataclass
from hashlib import sha256

from phoenix.lift.index import LiftIndex, Operation, Sequence, parse_operations, ram
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    array,
    digest,
    load_json,
    object_fields,
    uint,
)

MAX_GRAPH_BYTES = 4 * 1024 * 1024
MAX_BLOCKS = 512
MAX_OPERATIONS = 4096


@dataclass(frozen=True, slots=True)
class SwitchBlock:
    index: int
    start: GhidraVA
    successors: tuple[int, ...]
    true_out: int | None
    false_out: int | None
    operations: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class SwitchGraph:
    binary_sha256: str
    lift_sha256: str
    function: GhidraVA
    memory_space_id: int
    blocks: tuple[SwitchBlock, ...]
    sha256: str


def _block_index(value: object) -> int:
    return uint(value, MAX_BLOCKS - 1)


def _optional_index(value: object) -> int | None:
    return None if value is None else _block_index(value)


def parse_switch_graph(raw: bytes, lift: LiftIndex) -> SwitchGraph:
    if not 0 < len(raw) <= MAX_GRAPH_BYTES:
        raise MappingError("The normalized switch graph exceeds its size bound.")
    item = object_fields(
        load_json(raw),
        "schema_version binary_sha256 lift_sha256 style "
        "memory_space_id function blocks",
    )
    if (
        type(item["schema_version"]) is not int
        or item["schema_version"] != 1
        or item["style"] != "normalize"
    ):
        raise MappingError("The normalized switch graph schema or style is invalid.")
    binary_sha256 = digest(item["binary_sha256"])
    lift_sha256 = digest(item["lift_sha256"])
    function = ram(item["function"])
    memory_space_id = uint(item["memory_space_id"], (1 << 31) - 1)
    if (
        binary_sha256 != lift.binary_sha256
        or lift_sha256 != lift.lift_sha256
        or function not in lift.functions
        or not memory_space_id
    ):
        raise MappingError("The normalized switch graph does not match the lift.")
    blocks: dict[int, SwitchBlock] = {}
    operations: set[Sequence] = set()
    remaining = MAX_OPERATIONS
    for raw_block in array(item["blocks"], MAX_BLOCKS):
        block = object_fields(
            raw_block, "index start successors true_out false_out operations"
        )
        index = _block_index(block["index"])
        if index in blocks:
            raise MappingError("The normalized graph has a repeated block index.")
        successors = tuple(
            _block_index(value) for value in array(block["successors"], MAX_OPERATIONS)
        )
        true_out = _optional_index(block["true_out"])
        false_out = _optional_index(block["false_out"])
        body = parse_operations(block["operations"], remaining)
        remaining -= len(body)
        for operation in body:
            if operation.sequence in operations:
                raise MappingError(
                    "The normalized graph repeats an operation identity."
                )
            operations.add(operation.sequence)
        conditional = bool(body) and body[-1].opcode == "CBRANCH"
        if conditional:
            if (
                true_out is None
                or false_out is None
                or true_out == false_out
                or len(successors) != 2
                or set(successors) != {true_out, false_out}
            ):
                raise MappingError("The normalized conditional edges are invalid.")
        elif true_out is not None or false_out is not None:
            raise MappingError("Only a conditional block has true and false edges.")
        blocks[index] = SwitchBlock(
            index, ram(block["start"]), successors, true_out, false_out, body
        )
    if not blocks or any(
        target not in blocks for block in blocks.values() for target in block.successors
    ):
        raise MappingError("The normalized graph refers to an unavailable block.")
    return SwitchGraph(
        binary_sha256,
        lift_sha256,
        function,
        memory_space_id,
        tuple(sorted(blocks.values(), key=lambda block: block.index)),
        sha256(raw).hexdigest(),
    )
