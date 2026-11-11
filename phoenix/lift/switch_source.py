import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, cast

from phoenix.lift.index import LiftIndex, Location, Operation, Sequence, location, ram
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    array,
    digest,
    load_json,
    object_fields,
    text,
    uint,
)

_MAX_BYTES = 16 * 1024 * 1024
_MAX_SOURCE_BYTES = 1024 * 1024
_MAX_FUNCTIONS = 32
_MAX_MARKERS = 4100
_MAX_NEIGHBORS = 32
_GAPS = frozenset(
    {
        "ordinary_source_unavailable",
        "ordinary_source_limit",
        "ordinary_token_limit",
        "ordinary_marker_limit",
        "ordinary_block_limit",
        "ordinary_switch_unavailable",
        "ordinary_source_mismatch",
        "unbound_ordinary_operation",
        "unbound_ordinary_selector",
        "ordinary_evidence_limit",
    }
)

type MarkerKind = Literal["switch", "parameter", "case", "default", "return"]


@dataclass(frozen=True, slots=True)
class Storage:
    address: Location
    size: int


@dataclass(frozen=True, slots=True)
class Parameter:
    ordinal: int
    storage: tuple[Storage, ...]
    operand: Storage
    definition: Operation | None


@dataclass(frozen=True, slots=True)
class Block:
    index: int
    entry: GhidraVA
    indirect_entries: tuple[Operation, ...]
    successors: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Marker:
    start: int
    end: int
    kind: MarkerKind
    value: int | None
    operation: Operation
    block: Block | None
    parameter: Parameter | None


@dataclass(frozen=True, slots=True)
class OrdinaryBody:
    function: GhidraVA
    source_sha256: str
    source_bytes: int
    markers: tuple[Marker, ...]


@dataclass(frozen=True, slots=True)
class OrdinarySwitches:
    binary_sha256: str
    lift_sha256: str
    bodies: tuple[OrdinaryBody, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]
    sha256: str


def _operation(value: object, operations: dict[Sequence, Operation]) -> Operation:
    item = object_fields(value, "address index opcode")
    sequence = Sequence(location(item["address"]), uint(item["index"], 1_000_000))
    original = operations.get(sequence)
    if original is None or original.opcode != text(item["opcode"]):
        raise MappingError("The ordinary marker operation does not match the lift.")
    return original


def _storage(value: object) -> Storage:
    item = object_fields(value, "address size")
    size = uint(item["size"], 65536)
    if not size:
        raise MappingError("The ordinary selector storage is empty.")
    return Storage(location(item["address"]), size)


def _parameter(value: object, operations: dict[Sequence, Operation]) -> Parameter:
    item = object_fields(value, "ordinal storage operand definition")
    storage = tuple(_storage(part) for part in array(item["storage"], 4))
    if not storage:
        raise MappingError("The ordinary parameter has no storage.")
    return Parameter(
        uint(item["ordinal"], 127),
        storage,
        _storage(item["operand"]),
        None
        if item["definition"] is None
        else _operation(item["definition"], operations),
    )


def _block(value: object, operations: dict[Sequence, Operation]) -> Block:
    item = object_fields(value, "index entry indirect_entries successors")
    predecessors = tuple(
        _operation(record, operations)
        for record in array(item["indirect_entries"], _MAX_NEIGHBORS)
    )
    if any(op.opcode != "BRANCHIND" for op in predecessors):
        raise MappingError("An ordinary switch predecessor is not indirect.")
    return Block(
        uint(item["index"], 65_535),
        ram(item["entry"]),
        predecessors,
        tuple(uint(i, 65_535) for i in array(item["successors"], _MAX_NEIGHBORS)),
    )


def _marker(
    value: object, operations: dict[Sequence, Operation], source_size: int
) -> Marker:
    item = object_fields(value, "start end kind value operation block parameter")
    start, end = uint(item["start"], source_size), uint(item["end"], source_size)
    name = text(item["kind"])
    if start >= end or name not in ("switch", "parameter", "case", "default", "return"):
        raise MappingError("The ordinary switch marker has an invalid kind or span.")
    kind = cast(MarkerKind, name)
    number = None
    if kind == "case":
        spelling = text(item["value"])
        if re.fullmatch(r"0|[1-9][0-9]{0,19}", spelling) is None:
            raise MappingError("The ordinary case value is invalid.")
        number = uint(int(spelling))
    elif item["value"] is not None:
        raise MappingError("Only a case marker can have a value.")
    block = None if item["block"] is None else _block(item["block"], operations)
    parameter = (
        None if item["parameter"] is None else _parameter(item["parameter"], operations)
    )
    if (block is not None) != (kind in ("case", "default", "return")) or (
        parameter is not None
    ) != (kind == "parameter"):
        raise MappingError("The ordinary marker fields do not match its kind.")
    return Marker(
        start,
        end,
        kind,
        number,
        _operation(item["operation"], operations),
        block,
        parameter,
    )


def _body(value: object, lift: LiftIndex) -> OrdinaryBody:
    item = object_fields(value, "function source_sha256 source_bytes markers")
    entry = ram(item["function"])
    function = lift.functions.get(entry)
    if function is None:
        raise MappingError("The ordinary switch function is absent from the lift.")
    source_size = uint(item["source_bytes"], _MAX_SOURCE_BYTES)
    operations = {operation.sequence: operation for operation in function.analyzed}
    markers = []
    previous = 0
    blocks: dict[int, Block] = {}
    for value_marker in array(item["markers"], _MAX_MARKERS):
        marker = _marker(value_marker, operations, source_size)
        if marker.start < previous:
            raise MappingError("The ordinary source marker spans overlap.")
        previous = marker.end
        if marker.block is not None:
            block = marker.block
            if (
                lift.owners(block.entry) != (entry,)
                or blocks.setdefault(block.index, block) != block
            ):
                raise MappingError("An ordinary marker block is inconsistent.")
        markers.append(marker)
    if not markers:
        raise MappingError("The ordinary switch body has no source markers.")
    return OrdinaryBody(
        entry, digest(item["source_sha256"]), source_size, tuple(markers)
    )


def parse_ordinary_switches(raw: bytes, lift: LiftIndex) -> OrdinarySwitches:
    if not 0 < len(raw) <= _MAX_BYTES:
        raise MappingError("The ordinary switch artifact exceeds its size limit.")
    item = object_fields(
        load_json(raw), "schema_version binary_sha256 lift_sha256 bodies gaps"
    )
    binary_sha256 = digest(item["binary_sha256"])
    lift_sha256 = digest(item["lift_sha256"])
    if (
        type(item["schema_version"]) is not int
        or item["schema_version"] != 1
        or binary_sha256 != lift.binary_sha256
        or lift_sha256 != lift.lift_sha256
    ):
        raise MappingError("The ordinary switch artifact does not match the lift.")
    raw_bodies = array(item["bodies"], _MAX_FUNCTIONS)
    raw_gaps = array(item["gaps"], _MAX_FUNCTIONS)
    if len(raw_bodies) + len(raw_gaps) > _MAX_FUNCTIONS:
        raise MappingError("The ordinary switch scope exceeds 32 functions.")
    bodies = tuple(_body(value, lift) for value in raw_bodies)
    gaps = []
    for value in raw_gaps:
        gap = object_fields(value, "function reason")
        entry, reason = ram(gap["function"]), text(gap["reason"])
        if entry not in lift.functions or reason not in _GAPS:
            raise MappingError("The ordinary switch gap is invalid.")
        gaps.append((entry, reason))
    entries = [body.function for body in bodies] + [entry for entry, _ in gaps]
    if len(entries) != len(set(entries)):
        raise MappingError("The ordinary switch artifact repeats a function.")
    return OrdinarySwitches(
        binary_sha256,
        lift_sha256,
        tuple(sorted(bodies, key=lambda body: body.function)),
        tuple(sorted(gaps)),
        sha256(raw).hexdigest(),
    )
