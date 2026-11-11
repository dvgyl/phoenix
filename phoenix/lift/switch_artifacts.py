import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from phoenix.lift.index import LiftIndex, ram
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    array,
    bounded_read,
    digest,
    load_json,
    object_fields,
    text,
)
from phoenix.lift.switch_graph import MAX_GRAPH_BYTES, SwitchGraph, parse_switch_graph

_MAX_FUNCTIONS = 32
_MAX_BUNDLE_BYTES = 16 * 1024 * 1024
_MAX_MANIFEST_BYTES = 64 * 1024
_GAP_REASONS = frozenset(
    {
        "normalize_unavailable",
        "block_limit",
        "operation_limit",
        "unsupported_block",
        "unsupported_operation",
        "unsupported_conditional",
        "byte_limit",
    }
)


@dataclass(frozen=True, slots=True)
class SwitchBundle:
    graphs: tuple[SwitchGraph, ...]
    gaps: tuple[tuple[GhidraVA, str], ...]
    manifest_sha256: str
    artifact_bytes: int


def _read_file(path: Path, limit: int) -> bytes:
    try:
        return bounded_read(path, limit=limit, private=True)
    except OSError as error:
        raise MappingError("Cannot read the switch evidence file.") from error


def read_switch_bundle(directory: Path, lift: LiftIndex) -> SwitchBundle:
    directory = directory.absolute()
    try:
        physical = os.path.realpath(directory, strict=True) == str(directory)
    except OSError:
        physical = False
    if not physical or not directory.is_dir():
        raise MappingError("The switch evidence directory is invalid.")
    manifest_bytes = _read_file(directory / "manifest.json", _MAX_MANIFEST_BYTES)
    record = object_fields(
        load_json(manifest_bytes),
        "schema_version binary_sha256 lift_sha256 graphs gaps",
    )
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 1
        or digest(record["binary_sha256"]) != lift.binary_sha256
        or digest(record["lift_sha256"]) != lift.lift_sha256
    ):
        raise MappingError("The switch evidence manifest does not match the lift.")
    entries = array(record["graphs"], _MAX_FUNCTIONS)
    raw_gaps = array(record["gaps"], _MAX_FUNCTIONS)
    if len(entries) + len(raw_gaps) > _MAX_FUNCTIONS:
        raise MappingError("The switch evidence exceeds its function limit.")
    seen: set[GhidraVA] = set()
    names = {"manifest.json"}
    graphs = []
    remaining = _MAX_BUNDLE_BYTES
    for value in entries:
        entry = object_fields(value, "function file sha256")
        function = ram(entry["function"])
        name = text(entry["file"])
        if (
            function not in lift.functions
            or function in seen
            or name != f"graph-{function:x}.json"
        ):
            raise MappingError(
                "The switch graph record has an invalid function or file."
            )
        seen.add(function)
        names.add(name)
        raw = _read_file(directory / name, min(MAX_GRAPH_BYTES, remaining))
        remaining -= len(raw)
        if sha256(raw).hexdigest() != digest(entry["sha256"]):
            raise MappingError("The switch graph bytes differ from the manifest.")
        graph = parse_switch_graph(raw, lift)
        if graph.function != function:
            raise MappingError(
                "The switch graph and manifest name different functions."
            )
        graphs.append(graph)
    gaps = []
    for value in raw_gaps:
        gap = object_fields(value, "function reason")
        function = ram(gap["function"])
        reason = text(gap["reason"])
        if (
            function not in lift.functions
            or function in seen
            or reason not in _GAP_REASONS
        ):
            raise MappingError("The switch evidence gap is invalid.")
        seen.add(function)
        gaps.append((function, reason))
    try:
        with os.scandir(directory) as files:
            for entry_path in files:
                if entry_path.name not in names:
                    raise MappingError(
                        "The switch directory files do not match the manifest."
                    )
                names.remove(entry_path.name)
    except OSError as error:
        raise MappingError("Cannot list the switch evidence directory.") from error
    if names:
        raise MappingError("The switch directory files do not match the manifest.")
    return SwitchBundle(
        tuple(sorted(graphs, key=lambda graph: graph.function)),
        tuple(sorted(gaps)),
        sha256(manifest_bytes).hexdigest(),
        len(manifest_bytes) + _MAX_BUNDLE_BYTES - remaining,
    )
