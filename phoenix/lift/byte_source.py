"""Read source-token proposals. Parsing does not authorize C emission."""

import json
from dataclasses import dataclass, fields
from hashlib import sha256
from typing import Literal, cast

from phoenix.lift.byte_graph import (
    BlockKey,
    ByteGap,
    ByteGraph,
    Domain,
    FunctionKey,
    GapCode,
    OpKey,
    ValueKey,
)
from phoenix.lift.evidence import Address, StoragePiece
from phoenix.lift.index import LiftIndex, Sequence, location
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

type SourceStatus = Literal["exact_printer_bytes", "unavailable"]


class ByteSourceError(ValueError):
    """The source observation is invalid or exceeds a limit."""


@dataclass(frozen=True, slots=True)
class ByteSourceLimits:
    max_bytes: int = 16 * 1024 * 1024
    max_source_bytes: int = 1024 * 1024
    max_tokens: int = 65536
    max_storage_pieces: int = 4
    max_gaps: int = 256

    def __post_init__(self) -> None:
        for member in fields(self):
            value = getattr(self, member.name)
            maximum = member.default
            assert isinstance(maximum, int)
            if type(value) is not int or not 0 < value <= maximum:
                raise ByteSourceError(f"Invalid source limit: {member.name}.")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SourceToken:
    ordinal: int
    span: SourceSpan
    kind: str
    text_sha256: str
    operation: OpKey | None
    value: ValueKey | None
    formal_ordinal: int | None
    symbol_storage: tuple[StoragePiece, ...]


@dataclass(frozen=True, slots=True)
class ByteSourceObservation:
    schema: Literal[1]
    function: FunctionKey
    pass_id: str
    lift_sha256: str
    raw_c_sha256: str
    raw_c_bytes: int
    tokens: tuple[SourceToken, ...]
    source_status: SourceStatus
    gaps: tuple[ByteGap, ...]

    def record(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "function": _function_record(self.function),
            "pass_id": self.pass_id,
            "lift_sha256": self.lift_sha256,
            "raw_c_sha256": self.raw_c_sha256,
            "raw_c_bytes": self.raw_c_bytes,
            "tokens": [
                {
                    "ordinal": token.ordinal,
                    "span": {"start": token.span.start, "end": token.span.end},
                    "kind": token.kind,
                    "text_sha256": token.text_sha256,
                    "operation": _op_record(token.operation),
                    "value": _value_record(token.value),
                    "formal_ordinal": token.formal_ordinal,
                    "symbol_storage": [
                        {
                            "address": {
                                "space": piece.address.space,
                                "offset": piece.address.offset,
                            },
                            "size": piece.size,
                            "register": piece.register,
                            "stack_offset": piece.stack_offset,
                        }
                        for piece in token.symbol_storage
                    ],
                }
                for token in self.tokens
            ],
            "source_status": self.source_status,
            "gaps": [
                {
                    "code": gap.code,
                    "block": _block_record(gap.block),
                    "operation": _op_record(gap.operation),
                    "value": _value_record(gap.value),
                }
                for gap in self.gaps
            ],
        }

    def to_bytes(self) -> bytes:
        return _canonical(self.record())

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()


def _function_record(key: FunctionKey) -> dict[str, object]:
    return {"binary_sha256": key.binary_sha256, "ghidra_entry": hex(key.ghidra_entry)}


def _op_record(key: OpKey | None) -> dict[str, object] | None:
    if key is None:
        return None
    return {
        "function": _function_record(key.function),
        "domain": key.domain,
        "pass_id": key.pass_id,
        "sequence": {
            "address": {
                "space": key.sequence.address.space,
                "offset": hex(key.sequence.address.offset),
            },
            "index": key.sequence.index,
        },
    }


def _value_record(key: ValueKey | None) -> dict[str, object] | None:
    if key is None:
        return None
    return {
        "function": _function_record(key.function),
        "pass_id": key.pass_id,
        "local_id": key.local_id,
    }


def _block_record(key: BlockKey | None) -> dict[str, object] | None:
    if key is None:
        return None
    return {
        "function": _function_record(key.function),
        "pass_id": key.pass_id,
        "index": key.index,
    }


def _canonical(value: object) -> bytes:
    try:
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
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ByteSourceError("Invalid canonical source encoding.") from error


def _array(value: object, maximum: int) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        raise ByteSourceError("Invalid source array or exceeded count limit.")
    return cast(list[object], value)


def _choice[T: str](value: object, choices: tuple[T, ...]) -> T:
    for choice in choices:
        if type(value) is str and value == choice:
            return choice
    raise ByteSourceError("Unknown source discriminator.")


@dataclass(frozen=True, slots=True)
class _Reader:
    graph: ByteGraph

    def function(self, value: object) -> FunctionKey:
        item = object_fields(value, "binary_sha256 ghidra_entry")
        key = FunctionKey(
            digest(item["binary_sha256"]), GhidraVA(hex_address(item["ghidra_entry"]))
        )
        if key != self.graph.function:
            raise ByteSourceError("The source key names a different function.")
        return key

    def scope(self, item: dict[str, object]) -> FunctionKey:
        key = self.function(item["function"])
        if digest(item["pass_id"]) != self.graph.pass_id:
            raise ByteSourceError("The source key names a different pass.")
        return key

    def operation(self, value: object, *, analyzed: bool = False) -> OpKey | None:
        if value is None:
            return None
        item = object_fields(value, "function domain pass_id sequence")
        function = self.scope(item)
        domains: tuple[Domain, ...] = ("raw", "analyzed")
        domain = _choice(item["domain"], domains)
        if analyzed and domain != "analyzed":
            raise ByteSourceError("Source tokens require analyzed operations.")
        seq = object_fields(item["sequence"], "address index")
        return OpKey(
            function,
            domain,
            self.graph.pass_id,
            Sequence(location(seq["address"]), uint(seq["index"], 1_000_000)),
        )

    def value(self, value: object) -> ValueKey | None:
        if value is None:
            return None
        item = object_fields(value, "function pass_id local_id")
        return ValueKey(
            self.scope(item), self.graph.pass_id, uint(item["local_id"], 2**32 - 1)
        )

    def block(self, value: object) -> BlockKey | None:
        if value is None:
            return None
        item = object_fields(value, "function pass_id index")
        return BlockKey(
            self.scope(item), self.graph.pass_id, uint(item["index"], 2**31 - 1)
        )


def _storage_piece(value: object) -> StoragePiece:
    item = object_fields(value, "address size register stack_offset")
    address = location(item["address"])
    address.space.encode("utf-8")
    size = uint(item["size"], 8192)
    register = None if item["register"] is None else text(item["register"])
    if register is not None:
        register.encode("utf-8")
        if not register:
            raise ByteSourceError("The register name is empty.")
    offset = item["stack_offset"]
    if offset is not None and (
        type(offset) is not int or not -(2**63) <= offset < 2**63
    ):
        raise ByteSourceError("The stack offset is invalid.")
    if not size or address.offset + size > 2**64:
        raise ByteSourceError("The storage span is empty or wraps.")
    if address.space == "stack":
        if (
            offset is None
            or register is not None
            or offset % 2**64 != address.offset
            or offset < 0 < offset + size
            or offset + size > 2**63
        ):
            raise ByteSourceError("The stack storage is contradictory.")
    elif offset is not None:
        raise ByteSourceError("Non-stack storage has a stack offset.")
    return StoragePiece(
        Address(address.space, hex(address.offset)), size, register, offset
    )


def parse_byte_source(
    raw: bytes,
    lift: LiftIndex,
    graph: ByteGraph,
    *,
    limits: ByteSourceLimits = ByteSourceLimits(),
) -> ByteSourceObservation:
    """Check source bytes and references. Producer token associations are proposals."""
    if type(limits) is not ByteSourceLimits:
        raise ByteSourceError("Expected ByteSourceLimits.")
    limits.__post_init__()
    if type(raw) is not bytes or len(raw) > limits.max_bytes:
        raise ByteSourceError("Invalid source bytes or exceeded byte limit.")
    if type(graph) is not ByteGraph:
        raise ByteSourceError("Expected a structural ByteGraph proposal.")
    try:
        item = object_fields(
            load_json(raw),
            "schema function pass_id lift_sha256 raw_c_sha256 raw_c_bytes "
            "tokens source_status gaps",
        )
        if (
            _canonical(item) != raw
            or type(item["schema"]) is not int
            or item["schema"] != 1
        ):
            raise ByteSourceError("Expected canonical source schema 1 bytes.")
        reader = _Reader(graph)
        function_key = reader.scope(item)
        function = lift.functions.get(function_key.ghidra_entry)
        if (
            graph.binary_sha256 != lift.binary_sha256
            or function_key.binary_sha256 != lift.binary_sha256
            or graph.lift_sha256 != lift.lift_sha256
            or digest(item["lift_sha256"]) != lift.lift_sha256
            or function is None
            or function.raw_c is None
        ):
            raise ByteSourceError("The source observation does not bind the lift.")
        # UTF-8 uses at least one byte per character. Check this lower bound first.
        if len(function.raw_c) > limits.max_source_bytes:
            raise ByteSourceError("The source exceeds its byte limit.")
        source = function.raw_c.encode("utf-8")
        if len(source) > limits.max_source_bytes:
            raise ByteSourceError("The source exceeds its byte limit.")
        source_hash = sha256(source).hexdigest()
        if (
            uint(item["raw_c_bytes"], limits.max_source_bytes) != len(source)
            or digest(item["raw_c_sha256"]) != source_hash
            or graph.raw_c_sha256 != source_hash
        ):
            raise ByteSourceError("The exact source bytes or byte count disagree.")
        raw_tokens = _array(item["tokens"], limits.max_tokens)
        raw_gaps = _array(item["gaps"], limits.max_gaps)
        statuses: tuple[SourceStatus, ...] = ("exact_printer_bytes", "unavailable")
        status = _choice(item["source_status"], statuses)
        operations = {op.id for block in graph.blocks for op in block.operations}
        operations.update(graph.excluded_dead)
        all_operations = operations | {
            OpKey(graph.function, "raw", graph.pass_id, op.sequence)
            for instruction in function.instructions
            for op in instruction.pcode
        }
        values = {value.id for value in graph.values}
        blocks = {block.id: block for block in graph.blocks}
        tokens = []
        previous_end = 0
        for ordinal, raw_token in enumerate(raw_tokens):
            token = object_fields(
                raw_token,
                "ordinal span kind text_sha256 operation value "
                "formal_ordinal symbol_storage",
            )
            span = object_fields(token["span"], "start end")
            start, end = (
                uint(span["start"], len(source)),
                uint(span["end"], len(source)),
            )
            if (
                uint(token["ordinal"], limits.max_tokens - 1) != ordinal
                or not previous_end <= start < end
            ):
                raise ByteSourceError("Token ordinals or source spans are invalid.")
            fragment = source[start:end]
            fragment.decode("utf-8")
            kind = text(token["kind"])
            if not kind or len(kind.encode("utf-8")) > 128:
                raise ByteSourceError("The token kind is empty or too long.")
            token_hash = digest(token["text_sha256"])
            if token_hash != sha256(fragment).hexdigest():
                raise ByteSourceError("The token bytes do not match their digest.")
            operation, value = (
                reader.operation(token["operation"], analyzed=True),
                reader.value(token["value"]),
            )
            if (
                operation is not None
                and operation not in operations
                or value is not None
                and value not in values
            ):
                raise ByteSourceError("A token reference is absent from the graph.")
            formal = (
                None
                if token["formal_ordinal"] is None
                else uint(token["formal_ordinal"], 127)
            )
            storage = tuple(
                _storage_piece(piece)
                for piece in _array(token["symbol_storage"], limits.max_storage_pieces)
            )
            tokens.append(
                SourceToken(
                    ordinal,
                    SourceSpan(start, end),
                    kind,
                    token_hash,
                    operation,
                    value,
                    formal,
                    storage,
                )
            )
            previous_end = end
        gaps = []
        codes: tuple[GapCode, ...] = (
            "ssa_unbound",
            "cfg_unclosed",
            "unsupported_opcode",
            "volatile_or_unknown_memory",
            "source_unbound",
            "interface_unproved",
        )
        for raw_gap in raw_gaps:
            gap = object_fields(raw_gap, "code block operation value")
            code = _choice(gap["code"], codes)
            block, operation, value = (
                reader.block(gap["block"]),
                reader.operation(gap["operation"]),
                reader.value(gap["value"]),
            )
            if (
                block is not None
                and block not in blocks
                or operation is not None
                and operation not in all_operations
                or value is not None
                and value not in values
            ):
                raise ByteSourceError("A source gap reference is absent.")
            if (
                block is not None
                and operation is not None
                and operation not in {op.id for op in blocks[block].operations}
            ):
                raise ByteSourceError(
                    "The source gap block does not own its operation."
                )
            gaps.append(ByteGap(code, block, operation, value))
        if len(set(gaps)) != len(gaps):
            raise ByteSourceError("A source gap is duplicated.")
        if status == "unavailable" and (
            tokens or not any(gap.code == "source_unbound" for gap in gaps)
        ):
            raise ByteSourceError("Unavailable tokens require an explicit source gap.")
        return ByteSourceObservation(
            1,
            function_key,
            graph.pass_id,
            lift.lift_sha256,
            source_hash,
            len(source),
            tuple(tokens),
            status,
            tuple(gaps),
        )
    except (MappingError, UnicodeError, RecursionError, OverflowError) as error:
        raise ByteSourceError("Invalid source observation data.") from error
