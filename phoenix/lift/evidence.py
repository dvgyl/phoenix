"""Read bounded Ghidra proposals without assigning verified C types."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

MAX_EXPORT_BYTES = 64 * 1024 * 1024
_MAX_BITS = 65536
type DecompilationStatus = Literal["ok", "timeout", "incomplete"]


class EvidenceError(ValueError):
    """The static evidence is invalid or exceeds a limit."""


@dataclass(frozen=True, slots=True)
class Address:
    space: str
    offset: str


@dataclass(frozen=True, slots=True)
class TypeEvidence:
    id: str
    path: str
    name: str
    kind: Literal[
        "opaque", "pointer", "typedef", "array", "structure", "union", "function"
    ]
    size: int
    target: str | None
    count: int | None


@dataclass(frozen=True, slots=True)
class RegisterEvidence:
    name: str
    address: Address
    bits: int
    base: str
    least_bit: int


@dataclass(frozen=True, slots=True)
class StoragePiece:
    address: Address
    size: int
    register: str | None
    stack_offset: int | None


@dataclass(frozen=True, slots=True)
class StorageEvidence:
    state: Literal["unknown", "bad", "unassigned", "void", "assigned"]
    size: int
    forced_indirect: bool
    auto_parameter: str | None
    pieces: tuple[StoragePiece, ...]


@dataclass(frozen=True, slots=True)
class Slot:
    name: str | None
    type: str | None
    storage: StorageEvidence


@dataclass(frozen=True, slots=True)
class PrototypeEvidence:
    source: Literal["listing", "decompiler"]
    calling_convention: str | None
    custom_storage: bool | None
    variadic: bool
    no_return: bool
    parameters: tuple[Slot, ...]
    result: Slot


@dataclass(frozen=True, slots=True)
class JumpEvidence:
    site: Address | None
    targets: tuple[Address | None, ...]
    labels: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StaticEvidence:
    schema_version: Literal[1]
    status: Literal["proposal"]
    listing: PrototypeEvidence
    decompiler: PrototypeEvidence | None
    types: tuple[TypeEvidence, ...]
    registers: tuple[RegisterEvidence, ...]
    jump_tables: tuple[JumpEvidence, ...]


@dataclass(frozen=True, slots=True)
class FunctionEvidence:
    entry: Address
    evidence: StaticEvidence | None
    decompilation_status: DecompilationStatus | None


def _object(value: object, keys: str | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise EvidenceError("Expected an object with text keys.")
    result = cast(dict[str, object], value)
    if keys is not None and result.keys() != set(keys.split()):
        raise EvidenceError("The evidence fields do not match the schema.")
    return result


def _array(value: object, limit: int) -> list[object]:
    if not isinstance(value, list) or len(value) > limit:
        raise EvidenceError("Expected an array within the evidence limit.")
    return cast(list[object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or len(value) > 1024:
        raise EvidenceError("Expected text within the evidence limit.")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise EvidenceError("The integer is outside the evidence bounds.")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise EvidenceError("Expected a boolean.")
    return value


def _choice[T: str](value: object, choices: tuple[T, ...]) -> T:
    for choice in choices:
        if type(value) is str and value == choice:
            return choice
    raise EvidenceError("The evidence value is not supported.")


def _address(value: object) -> Address:
    item = _object(value, "space offset")
    space, offset = _text(item["space"]), _text(item["offset"])
    if not space or re.fullmatch(r"0x(?:0|[1-9a-f][0-9a-f]{0,15})", offset) is None:
        raise EvidenceError("The address is invalid.")
    return Address(space, offset)


def _optional_address(value: object) -> Address | None:
    return None if value is None else _address(value)


def _type(value: object) -> TypeEvidence:
    item = _object(value, "id path name kind size target count")
    identifier = _text(item["id"])
    if re.fullmatch(r"t(?:0|[1-9][0-9]{0,2})", identifier) is None:
        raise EvidenceError("The type identity is invalid.")
    return TypeEvidence(
        identifier,
        _text(item["path"]),
        _text(item["name"]),
        _choice(
            item["kind"],
            ("opaque", "pointer", "typedef", "array", "structure", "union", "function"),
        ),
        _integer(item["size"], -1, 2**31 - 1),
        _optional_text(item["target"]),
        None if item["count"] is None else _integer(item["count"], 0, 2**31 - 1),
    )


def _register(value: object) -> RegisterEvidence:
    item = _object(value, "name address bits base least_bit")
    result = RegisterEvidence(
        _text(item["name"]),
        _address(item["address"]),
        _integer(item["bits"], 1, _MAX_BITS),
        _text(item["base"]),
        _integer(item["least_bit"], 0, _MAX_BITS - 1),
    )
    if not result.name or not result.base:
        raise EvidenceError("The register name is empty.")
    return result


def _piece(value: object) -> StoragePiece:
    item = _object(value, "address size register stack_offset")
    result = StoragePiece(
        _address(item["address"]),
        _integer(item["size"], 1, _MAX_BITS // 8),
        _optional_text(item["register"]),
        None
        if item["stack_offset"] is None
        else _integer(item["stack_offset"], -(2**63), 2**63 - 1),
    )
    if result.address.space == "stack":
        if (
            result.stack_offset is None
            or result.register is not None
            or result.stack_offset % 2**64 != int(result.address.offset, 16)
        ):
            raise EvidenceError("The stack offset does not match its address.")
        end = result.stack_offset + result.size
        if (result.stack_offset < 0 < end) or end > 2**63:
            raise EvidenceError("The stack span crosses an address boundary.")
    elif result.stack_offset is not None:
        raise EvidenceError("A non-stack piece has a stack offset.")
    if int(result.address.offset, 16) + result.size > 2**64:
        raise EvidenceError("The storage span wraps its address space.")
    return result


def _storage(value: object) -> StorageEvidence:
    item = _object(value, "state size forced_indirect auto_parameter pieces")
    result = StorageEvidence(
        _choice(item["state"], ("unknown", "bad", "unassigned", "void", "assigned")),
        _integer(item["size"], 0, _MAX_BITS // 8),
        _boolean(item["forced_indirect"]),
        _optional_text(item["auto_parameter"]),
        tuple(_piece(piece) for piece in _array(item["pieces"], 32)),
    )
    if sum(piece.size for piece in result.pieces) != result.size or (
        result.state == "assigned"
    ) != bool(result.pieces):
        raise EvidenceError("The storage size, state, or pieces are inconsistent.")
    intervals: list[tuple[str, int, int]] = []
    for piece in result.pieces:
        start = int(piece.address.offset, 16)
        end = start + piece.size
        if any(
            space == piece.address.space
            and start < previous_end
            and previous_start < end
            for space, previous_start, previous_end in intervals
        ):
            raise EvidenceError("The storage pieces overlap.")
        intervals.append((piece.address.space, start, end))
    if any(piece.register is None for piece in result.pieces[1:]):
        raise EvidenceError(
            "The compound storage order requires registers after the first piece."
        )
    return result


def _slot(value: object) -> Slot:
    item = _object(value, "name type storage")
    return Slot(
        _optional_text(item["name"]),
        _optional_text(item["type"]),
        _storage(item["storage"]),
    )


def _prototype(
    value: object, source: Literal["listing", "decompiler"]
) -> PrototypeEvidence:
    item = _object(
        value,
        "source calling_convention custom_storage variadic no_return parameters result",
    )
    if item["source"] != source:
        raise EvidenceError("The prototype source is incorrect.")
    custom = item["custom_storage"]
    if source == "decompiler" and custom is not None:
        raise EvidenceError("The decompiler API does not report custom storage.")
    if source == "listing" or custom is not None:
        custom = _boolean(custom)
    return PrototypeEvidence(
        source,
        _optional_text(item["calling_convention"]),
        custom,
        _boolean(item["variadic"]),
        _boolean(item["no_return"]),
        tuple(_slot(slot) for slot in _array(item["parameters"], 128)),
        _slot(item["result"]),
    )


def _jump(value: object) -> JumpEvidence:
    item = _object(value, "site targets labels")
    return JumpEvidence(
        _optional_address(item["site"]),
        tuple(_optional_address(target) for target in _array(item["targets"], 4096)),
        tuple(
            _integer(label, -(2**31), 2**31 - 1)
            for label in _array(item["labels"], 4096)
        ),
    )


def parse_static_evidence(value: object) -> StaticEvidence:
    """Validate one function's proposal record and all its local references."""
    item = _object(
        value, "schema_version status listing decompiler types registers jump_tables"
    )
    _integer(item["schema_version"], 1, 1)
    _choice(item["status"], ("proposal",))
    result = StaticEvidence(
        1,
        "proposal",
        _prototype(item["listing"], "listing"),
        None
        if item["decompiler"] is None
        else _prototype(item["decompiler"], "decompiler"),
        tuple(_type(data) for data in _array(item["types"], 256)),
        tuple(_register(register) for register in _array(item["registers"], 512)),
        tuple(_jump(jump) for jump in _array(item["jump_tables"], 256)),
    )
    types = {data.id: data for data in result.types}
    registers = {register.name: register for register in result.registers}
    sites = [jump.site for jump in result.jump_tables if jump.site is not None]
    if (
        len(types) != len(result.types)
        or len(registers) != len(result.registers)
        or len(set(sites)) != len(sites)
    ):
        raise EvidenceError("The evidence has duplicate identities.")
    for data in result.types:
        if (
            (data.target is not None and data.target not in types)
            or (
                data.target is not None
                and data.kind not in ("pointer", "typedef", "array")
            )
            or (data.kind in ("typedef", "array") and data.target is None)
            or (data.kind == "array") != (data.count is not None)
        ):
            raise EvidenceError("The type reference is invalid.")
    for data in result.types:
        seen: dict[str, int] = {}
        current = data
        while current.id not in seen:
            seen[current.id] = len(seen)
            if len(seen) > 32:
                raise EvidenceError("The type reference depth exceeds the limit.")
            if current.target is None:
                break
            current = types[current.target]
        else:
            if not any(
                types[key].kind == "pointer"
                for key, index in seen.items()
                if index >= seen[current.id]
            ):
                raise EvidenceError("A recursive type reference needs a pointer.")
    for register in result.registers:
        base = registers.get(register.base)
        if (
            base is None
            or base.base != base.name
            or base.least_bit != 0
            or register.least_bit + register.bits > base.bits
            or register.address.space != base.address.space
        ):
            raise EvidenceError("The base register reference or width is invalid.")
        start = int(register.address.offset, 16)
        base_start = int(base.address.offset, 16)
        span = (register.least_bit % 8 + register.bits + 7) // 8
        if (
            start != base_start + register.least_bit // 8
            or start + span > base_start + (base.bits + 7) // 8
            or start + span > 2**64
        ):
            raise EvidenceError("The register address and base bit range disagree.")
    for prototype in (result.listing, result.decompiler):
        if prototype is None:
            continue
        for slot in (*prototype.parameters, prototype.result):
            if slot.type is not None and slot.type not in types:
                raise EvidenceError("The slot has an unknown type reference.")
            for piece in slot.storage.pieces:
                if piece.register is not None:
                    stored_register = registers.get(piece.register)
                    if (
                        stored_register is None
                        or piece.address != stored_register.address
                        or piece.size * 8 > stored_register.bits
                    ):
                        raise EvidenceError(
                            "The storage register reference or width is invalid."
                        )
    if result.decompiler is None and result.jump_tables:
        raise EvidenceError("Jump tables require decompiler evidence.")
    if sum(len(jump.targets) + len(jump.labels) for jump in result.jump_tables) > 16384:
        raise EvidenceError("The jump-table evidence exceeds the total limit.")
    return result


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("The JSON object has a duplicate key.")
        result[key] = value
    return result


def read_static_evidence(path: Path) -> tuple[FunctionEvidence, ...]:
    """Read new evidence. A legacy function returns evidence=None."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_EXPORT_BYTES + 1)
    if len(raw) > MAX_EXPORT_BYTES:
        raise EvidenceError("The lift file exceeds the evidence reader limit.")
    try:
        document = _object(json.loads(raw, object_pairs_hook=_unique_keys))
    except (ValueError, RecursionError, UnicodeError) as error:
        raise EvidenceError("The lift JSON is invalid.") from error
    _integer(document.get("schema_version"), 1, 1)
    functions = _array(document.get("functions"), 65536)
    result = []
    entries: set[Address] = set()
    statuses: tuple[DecompilationStatus, ...] = ("ok", "timeout", "incomplete")
    for value in functions:
        function = _object(value)
        entry = _address(function.get("entry"))
        if entry in entries:
            raise EvidenceError("The lift has duplicate function entries.")
        entries.add(entry)
        evidence = None
        decompilation_status: DecompilationStatus | None = None
        if "static_evidence" in function:
            evidence = parse_static_evidence(function["static_evidence"])
            decompilation_status = _choice(
                _object(function.get("decompilation")).get("status"),
                statuses,
            )
            instructions = {
                _address(_object(instruction).get("address"))
                for instruction in _array(function.get("instructions"), 1_000_000)
            }
            if any(
                jump.site is not None and jump.site not in instructions
                for jump in evidence.jump_tables
            ):
                raise EvidenceError(
                    "A jump-table site is outside the function instructions."
                )
        result.append(FunctionEvidence(entry, evidence, decompilation_status))
    return tuple(result)
