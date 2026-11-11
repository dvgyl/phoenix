"""Read pinned capture declarations. A manifest does not prove execution."""

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from phoenix.lift.mapping import (
    MappingError,
    array,
    digest,
    load_json,
    object_fields,
    text,
    uint,
)

_MAX_BYTES = 65536
_SCHEMA = "phoenix-frame-runtime-1"
_RECEIPT = "phoenix-frame-capture-1"
_REGISTERS = (
    ("rdi", 64),
    ("rsi", 64),
    ("rdx", 64),
    ("rcx", 64),
    ("rax", 64),
    ("rsp", 64),
)


def canonical(record: object) -> bytes:
    raw = (
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")
    if len(raw) > _MAX_BYTES:
        raise MappingError("The capture record exceeds 65,536 bytes.")
    return raw


def _image(value: object) -> str:
    result = text(value)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", result) is None:
        raise MappingError("The capture image needs a pinned SHA-256 ID.")
    return result


def guard_profile_sha256(collector: str, plugin: str) -> str:
    return sha256(
        canonical(
            {
                "policy": "main-window-six-v1",
                "receipt_schema": _RECEIPT,
                "semantics": "pre-instruction-all-positions-v1",
                "collector_source_sha256": digest(collector),
                "plugin_sha256": digest(plugin),
            }
        )
    ).hexdigest()


def admission_implementation_sha256() -> str:
    root = Path(__file__).resolve().parents[2]
    names = (
        "phoenix/observe/admission.py",
        "phoenix/observe/runtime.py",
        "phoenix/observe/capture.py",
        "phoenix/observe/frames.py",
        "phoenix/observe/mapping.py",
        "phoenix/observe/wire.py",
        "phoenix_eval/case.py",
        "phoenix_eval/outcome.py",
        "phoenix_eval/trace.py",
        "phoenix_eval/wire.py",
    )
    sources = []
    for name in names:
        path = root / name
        if path.resolve() != path or not path.is_file():
            raise MappingError("The capture admission source must be a regular file.")
        sources.append((name, sha256(path.read_bytes()).hexdigest()))
    return sha256(canonical(sources)).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    schema: str
    receipt_schema: str
    full_plan_sha256: str
    scope_sha256: str
    policy_implementation_sha256: str
    admission_implementation_sha256: str
    guard_profile_sha256: str
    registers: tuple[tuple[str, int], ...]
    collector_source_sha256: str
    plugin_sha256: str
    qemu_sha256: str
    qemu_version: str
    qemu_commit: str
    image_id: str
    accepted_worker_image_id: str
    guest_runtime_sha256: str

    def to_bytes(self) -> bytes:
        return canonical(asdict(self))


def parse_runtime_manifest(raw: bytes, expected_sha256: str) -> RuntimeManifest:
    if not 0 < len(raw) <= _MAX_BYTES:
        raise MappingError("The runtime manifest exceeds its byte limit.")
    if sha256(raw).hexdigest() != digest(expected_sha256):
        raise MappingError("The runtime manifest differs from the runner pin.")
    record = object_fields(
        load_json(raw),
        "schema receipt_schema full_plan_sha256 scope_sha256 "
        "policy_implementation_sha256 admission_implementation_sha256 "
        "guard_profile_sha256 registers "
        "collector_source_sha256 plugin_sha256 qemu_sha256 qemu_version "
        "qemu_commit image_id accepted_worker_image_id guest_runtime_sha256",
    )
    if (
        record["schema"] != _SCHEMA
        or record["receipt_schema"] != _RECEIPT
        or record["qemu_version"] != "9.2.0"
        or record["qemu_commit"] != "ae35f033b874c627d81d51070187fbf55f0bf1a7"
    ):
        raise MappingError("The capture runtime profile is unsupported.")
    registers = []
    for value in array(record["registers"], 6):
        pair = array(value, 2)
        if len(pair) != 2:
            raise MappingError("The runtime register declaration is invalid.")
        registers.append((text(pair[0]), uint(pair[1], 64)))
    if tuple(registers) != _REGISTERS:
        raise MappingError("The runtime register profile is unsupported.")
    manifest = RuntimeManifest(
        _SCHEMA,
        _RECEIPT,
        digest(record["full_plan_sha256"]),
        digest(record["scope_sha256"]),
        digest(record["policy_implementation_sha256"]),
        digest(record["admission_implementation_sha256"]),
        digest(record["guard_profile_sha256"]),
        tuple(registers),
        digest(record["collector_source_sha256"]),
        digest(record["plugin_sha256"]),
        digest(record["qemu_sha256"]),
        "9.2.0",
        "ae35f033b874c627d81d51070187fbf55f0bf1a7",
        _image(record["image_id"]),
        _image(record["accepted_worker_image_id"]),
        digest(record["guest_runtime_sha256"]),
    )
    if (
        manifest.guard_profile_sha256
        != guard_profile_sha256(
            manifest.collector_source_sha256, manifest.plugin_sha256
        )
        or manifest.to_bytes() != raw
    ):
        raise MappingError("The runtime guard identity or canonical bytes differ.")
    return manifest
