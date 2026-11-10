"""Read and publish committed source mapping companions."""

import json
import os
import re
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import NewType, cast
from uuid import uuid4

GhidraVA = NewType("GhidraVA", int)
FileOffset = NewType("FileOffset", int)
MAX_BYTES = 64 * 1024 * 1024
_SELECTOR = "evidence-current"


class MappingError(ValueError):
    """Evidence is invalid, incomplete, or outside the supported bounds."""


def object_fields(value: object, fields: str | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise MappingError("Expected an object with text keys.")
    result = cast(dict[str, object], value)
    if fields is not None and result.keys() != set(fields.split()):
        raise MappingError("The evidence fields do not match the schema.")
    return result


def array(value: object, limit: int = 1_000_000) -> list[object]:
    if not isinstance(value, list) or len(value) > limit:
        raise MappingError("The array exceeds the supported bound.")
    return cast(list[object], value)


def uint(value: object, maximum: int = (1 << 64) - 1) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise MappingError("Expected an unsigned integer within the supported bound.")
    return value


def text(value: object) -> str:
    if not isinstance(value, str) or len(value) > 4096 or "\0" in value:
        raise MappingError("Invalid evidence text.")
    return value


def hex_address(value: object) -> int:
    value = text(value)
    if re.fullmatch(r"0x(?:0|[1-9a-f][0-9a-f]{0,15})", value) is None:
        raise MappingError("Expected a canonical unsigned hexadecimal address.")
    return int(value, 16)


def digest(value: object) -> str:
    value = text(value)
    if re.fullmatch("[0-9a-f]{64}", value) is None:
        raise MappingError("Expected a SHA-256 digest.")
    return value


def _read_regular(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise MappingError("The evidence artifact must be a regular file.")
    with os.fdopen(descriptor, "rb") as stream:
        return stream.read(limit)


def bounded_read(path: Path) -> bytes:
    raw = _read_regular(path, MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise MappingError("The artifact exceeds 64 MiB.")
    return raw


def _keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MappingError("The JSON object has a duplicate key.")
        result[key] = value
    return result


def load_json(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_BYTES:
        raise MappingError("The artifact exceeds 64 MiB.")
    try:
        return object_fields(json.loads(raw, object_pairs_hook=_keys))
    except (ValueError, RecursionError, UnicodeError) as error:
        raise MappingError("Invalid evidence JSON.") from error


@dataclass(frozen=True, slots=True)
class LiftSpan:
    ghidra_start: GhidraVA
    file_offset: FileOffset
    length: int
    memory_sha256: str
    original_sha256: str


@dataclass(frozen=True, slots=True)
class LiftMapping:
    binary_sha256: str
    lift_sha256: str
    image_base: GhidraVA
    startup: GhidraVA
    spans: tuple[LiftSpan, ...]


def parse_mapping(raw: bytes, binary: bytes, lift: bytes) -> LiftMapping:
    item = object_fields(
        load_json(raw),
        "schema_version binary_sha256 lift_sha256 image_base startup spans",
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise MappingError("Unsupported mapping schema.")
    binary_hash, lift_hash = digest(item["binary_sha256"]), digest(item["lift_sha256"])
    if (
        binary_hash != sha256(binary).hexdigest()
        or lift_hash != sha256(lift).hexdigest()
    ):
        raise MappingError("The mapping does not bind these binary and lift bytes.")
    spans = []
    total = 0
    for value in array(item["spans"], 65536):
        span = object_fields(
            value,
            "ghidra_start length source_file_offset source_size source_sha256 "
            "source_start source_end memory_sha256 original_sha256",
        )
        start = hex_address(span["ghidra_start"])
        length = uint(span["length"], MAX_BYTES)
        offset = uint(span["source_start"])
        total += length
        if total > MAX_BYTES:
            raise MappingError("The source spans exceed 64 MiB in total.")
        if (
            not length
            or start + length > 1 << 64
            or offset + length > len(binary)
            or uint(span["source_file_offset"]) != 0
            or uint(span["source_size"]) != len(binary)
            or digest(span["source_sha256"]) != binary_hash
            or uint(span["source_end"]) != offset + length - 1
            or digest(span["original_sha256"])
            != sha256(binary[offset : offset + length]).hexdigest()
        ):
            raise MappingError("Invalid source-backed span.")
        spans.append(
            LiftSpan(
                GhidraVA(start),
                FileOffset(offset),
                length,
                digest(span["memory_sha256"]),
                digest(span["original_sha256"]),
            )
        )
    spans.sort(key=lambda span: span.ghidra_start)
    if not spans or any(
        left.ghidra_start + left.length > right.ghidra_start
        for left, right in zip(spans, spans[1:])
    ):
        raise MappingError("The source spans are empty or overlap.")
    return LiftMapping(
        binary_hash,
        lift_hash,
        GhidraVA(hex_address(item["image_base"])),
        GhidraVA(hex_address(item["startup"])),
        tuple(spans),
    )


def _validate_pair(lift: bytes, mapping: bytes, binary: bytes) -> LiftMapping:
    from phoenix.lift.index import parse_lift

    parsed = parse_mapping(mapping, binary, lift)
    index = parse_lift(lift, binary)
    if (index.image_base, index.startup) != (parsed.image_base, parsed.startup):
        raise MappingError("The lift and mapping addresses disagree.")
    return parsed


def check_publication_paths(directory: Path, binary: Path) -> None:
    for name in (
        "lift.json",
        "mapping.json",
        "evidence-commit.json",
        "ghidra.log",
        _SELECTOR,
    ):
        path = directory / name
        try:
            aliases_binary = path.samefile(binary)
        except FileNotFoundError:
            aliases_binary = False
        if aliases_binary:
            raise ValueError(f"The publication path {name} aliases the input binary.")


def publish_generation(
    lift: Path, directory: Path, binary: Path, original: bytes, log: str
) -> Path:
    """Publish a complete generation from a private staging directory."""
    staging = lift.parent
    for artifact in (lift, staging / "mapping.json"):
        if (
            artifact.is_symlink()
            or not artifact.is_file()
            or artifact.stat().st_nlink != 1
        ):
            raise MappingError("A staged artifact needs a private regular file.")
    lift_raw = bounded_read(lift)
    mapping_raw = bounded_read(staging / "mapping.json")
    _validate_pair(lift_raw, mapping_raw, original)
    with (staging / "ghidra.log").open("x", encoding="utf-8") as stream:
        stream.write(log)
    with (staging / "evidence-commit.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "schema_version": 1,
                "lift_sha256": sha256(lift_raw).hexdigest(),
                "mapping_sha256": sha256(mapping_raw).hexdigest(),
            },
            stream,
            sort_keys=True,
        )
        stream.write("\n")
    name = f"generation-{uuid4().hex}"
    selection = staging / _SELECTOR
    with selection.open("x", encoding="ascii") as stream:
        stream.write(name + "\n")
    generation = directory / name
    artifacts = staging / name
    artifacts.mkdir()
    for filename in ("lift.json", "mapping.json", "ghidra.log", "evidence-commit.json"):
        (staging / filename).rename(artifacts / filename)
    check_publication_paths(directory, binary)
    if bounded_read(binary) != original:
        raise MappingError("The input binary changed during the lift.")
    artifacts.rename(generation)
    selection.replace(directory / _SELECTOR)
    return generation / "lift.json"


def read_companion(directory: Path, binary: bytes) -> tuple[bytes, LiftMapping]:
    """Read the selected generation and check its lift and mapping."""
    try:
        selection = _read_regular(directory / _SELECTOR, 45)
    except OSError as error:
        raise MappingError("The evidence publication is incomplete.") from error
    if re.fullmatch(rb"generation-[0-9a-f]{32}\n", selection) is None:
        raise MappingError("Invalid evidence generation selection.")
    generation = directory / selection[:-1].decode("ascii")
    if generation.is_symlink():
        raise MappingError("An evidence generation cannot be a symbolic link.")
    for name in ("lift.json", "mapping.json", "evidence-commit.json", "ghidra.log"):
        artifact = generation / name
        if artifact.is_symlink() or not artifact.is_file():
            raise MappingError("The evidence publication is incomplete.")
    try:
        record = object_fields(
            load_json(bounded_read(generation / "evidence-commit.json")),
            "schema_version lift_sha256 mapping_sha256",
        )
        lift, mapping = (
            bounded_read(generation / "lift.json"),
            bounded_read(generation / "mapping.json"),
        )
    except OSError as error:
        raise MappingError("The evidence publication is incomplete.") from error
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or digest(record["lift_sha256"]) != sha256(lift).hexdigest()
        or digest(record["mapping_sha256"]) != sha256(mapping).hexdigest()
    ):
        raise MappingError("The evidence commit does not match its artifacts.")
    return lift, _validate_pair(lift, mapping, binary)
