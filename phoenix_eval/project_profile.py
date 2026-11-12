"""Read profile 2 consistency data without granting build or integrity authority."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
from typing import Literal, cast

type FailureCategory = Literal[
    "profile_limit",
    "profile_json",
    "profile_duplicate_key",
    "profile_fields",
    "profile_type",
    "profile_noncanonical",
    "profile_path",
    "profile_roster",
    "profile_digest",
    "profile_cmake",
    "profile_origin",
    "profile_correspondence",
    "profile_shared_identity",
    "profile_mismatch",
]
type FailurePhase = Literal["selection", "parse", "roster", "content", "correspondence"]
type Linkage = Literal["external", "internal"]
type TypeKind = Literal["struct", "union", "enum", "typedef"]


class ProfileError(ValueError):
    """Report a bounded input failure, without an integrity verdict."""

    def __init__(
        self, category: FailureCategory, phase: FailurePhase, detail: str
    ) -> None:
        self.category = category
        self.phase = phase
        self.detail = detail[:160]
        super().__init__(self.detail)


@dataclass(frozen=True, slots=True)
class ProfileLimits:
    max_sources: int = 64
    max_headers: int = 128
    max_total_source_bytes: int = 4_194_304
    max_cmake_bytes: int = 16_384
    max_manifest_bytes: int = 262_144
    max_correspondence_bytes: int = 1_048_576
    max_path_bytes: int = 58
    max_nesting: int = 16
    max_integer_digits: int = 20
    max_functions: int = 8_192
    max_globals: int = 8_192
    max_shared_types: int = 4_096
    max_spans: int = 32_768
    max_identifier_bytes: int = 128
    max_anchor_id_bytes: int = 128
    max_reference_edges: int = 65_536


DEFAULT_LIMITS = ProfileLimits()


@dataclass(frozen=True, slots=True)
class FileRow:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CorrespondenceFileRow:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ProjectManifestV2:
    schema: int
    profile: str
    build_profile: str
    original_sha256: str
    origin_sha256: str
    sources: tuple[FileRow, ...]
    headers: tuple[FileRow, ...]
    correspondence: CorrespondenceFileRow
    cmake_sha256: str


@dataclass(frozen=True, slots=True)
class Span:
    path: str
    start: int
    end: int
    sha256: str


@dataclass(frozen=True, slots=True)
class Anchor:
    artifact_sha256: str
    record_id: str


@dataclass(frozen=True, slots=True)
class FunctionRow:
    origin_entry: str
    c_name: str
    linkage: Linkage
    definition: Span
    signature: Span
    body: Span
    shared_type_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GlobalRow:
    id: str
    anchor: Anchor
    c_name: str
    linkage: Linkage
    definition: Span
    declarations: tuple[Span, ...]
    shared_type_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SharedTypeRow:
    id: str
    anchor: Anchor
    kind: TypeKind
    c_name: str
    definition: Span | None
    declarations: tuple[Span, ...]
    users: tuple[str, ...]
    claim: Literal["proposal"]


@dataclass(frozen=True, slots=True)
class CorrespondenceV1:
    schema: int
    profile: str
    original_sha256: str
    origin_sha256: str
    address_space: str
    declaration_version_sha256: str
    functions: tuple[FunctionRow, ...]
    globals: tuple[GlobalRow, ...]
    shared_types: tuple[SharedTypeRow, ...]


@dataclass(frozen=True, slots=True)
class ParsedProjectV2:
    """Retain complete consistency data. Public construction grants no authority."""

    manifest: ProjectManifestV2
    correspondence: CorrespondenceV1
    canonical_manifest: bytes
    canonical_correspondence: bytes


_SOURCE = re.compile(r"src/[a-z][a-z0-9_]{0,47}\.c")
_HEADER = re.compile(r"include/[a-z][a-z0-9_]{0,47}\.h")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_ANCHOR_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_ENTRY = re.compile(r"0x(?:0|[1-9a-f][0-9a-f]{0,15})")

# This literal freezes the inspected v1 bytes for the separate v2 policy.
_CMAKE_PREFIX = b"""cmake_minimum_required(VERSION 3.22)
project(phoenix_rebuild LANGUAGES C)
"""
_CMAKE_SUFFIX = b"""target_include_directories(program PRIVATE include)
target_compile_definitions(program PRIVATE _POSIX_C_SOURCE=200809L)
target_compile_options(program PRIVATE -Wall -Wextra -O2 -fstack-protector-all)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(program PRIVATE LINKER:-z,relro,-z,now)
endif()
set_target_properties(program PROPERTIES
    C_STANDARD 11 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
"""


def _limit(ok: bool) -> None:
    if not ok:
        raise ProfileError("profile_limit", "parse", "A profile limit was exceeded.")


def _limits(value: ProfileLimits) -> None:
    if type(value) is not ProfileLimits:
        raise ProfileError("profile_type", "parse", "ProfileLimits is required.")
    for field in fields(ProfileLimits):
        count = getattr(value, field.name, None)
        _limit(type(count) is int and 0 < count <= getattr(DEFAULT_LIMITS, field.name))


class _WireScan:
    """Bound raw tokens and occurrences before JSON tree allocation."""

    def __init__(self, data: bytes, limits: ProfileLimits) -> None:
        self.data = data
        self.limits = limits
        self.pos = 0
        self.spans = 0
        self.edges = 0

    def edge(self, count: int = 1) -> None:
        self.edges += count
        _limit(self.edges <= self.limits.max_reference_edges)

    def byte(self) -> int:
        return self.data[self.pos] if self.pos < len(self.data) else -1

    def require(self, expected: int) -> None:
        if self.byte() != expected:
            self.invalid()
        self.pos += 1

    def invalid(self) -> None:
        if self.byte() in (9, 10, 13, 32):
            raise ProfileError(
                "profile_noncanonical", "parse", "JSON whitespace is not canonical."
            )
        raise ProfileError("profile_json", "parse", "The JSON syntax is invalid.")

    def string(self) -> str:
        self.require(34)
        start = self.pos
        while self.byte() != 34:
            char = self.byte()
            if char == 92:
                raise ProfileError(
                    "profile_noncanonical", "parse", "Metadata escapes are not allowed."
                )
            if char < 32:
                self.invalid()
            if char > 126:
                raise ProfileError(
                    "profile_type", "parse", "Metadata must use ASCII characters."
                )
            self.pos += 1
            _limit(self.pos - start <= 128)
        result = self.data[start : self.pos].decode("ascii")
        self.pos += 1
        return result

    def array_max(self, key: str) -> int:
        limits = self.limits
        bounds = {
            "sources": limits.max_sources,
            "headers": limits.max_headers,
            "functions": limits.max_functions,
            "globals": limits.max_globals,
            "shared_types": limits.max_shared_types,
            "shared_type_ids": limits.max_shared_types,
            "users": limits.max_sources,
            "declarations": limits.max_spans,
        }
        return bounds.get(key, limits.max_reference_edges)

    def value(self, depth: int, key: str = "", owner: str = "") -> None:
        char = self.byte()
        if char in (123, 91):
            _limit(depth < self.limits.max_nesting)
        if char == 123:
            if key in ("definition", "signature", "body", "declarations"):
                self.spans += 1
                _limit(self.spans <= self.limits.max_spans)
            if key == "anchor":
                self.edge(2)
            self.pos += 1
            keys: set[str] = set()
            if self.byte() != 125:
                while True:
                    name = self.string()
                    if name in keys:
                        raise ProfileError(
                            "profile_duplicate_key", "parse", "A JSON key is repeated."
                        )
                    keys.add(name)
                    # No closed P1 object has more than nine fields.
                    if len(keys) > 9:
                        raise ProfileError(
                            "profile_fields", "parse", "The object has extra fields."
                        )
                    self.require(58)
                    if name in ("path", "origin_entry"):
                        self.edge()
                    self.value(depth + 1, name, key)
                    if self.byte() != 44:
                        break
                    self.pos += 1
            self.require(125)
        elif char == 91:
            self.pos += 1
            count = 0
            if self.byte() != 93:
                while True:
                    count += 1
                    _limit(count <= self.array_max(key))
                    if key in ("shared_type_ids", "users"):
                        self.edge()
                    self.value(depth + 1, key)
                    if self.byte() != 44:
                        break
                    self.pos += 1
            self.require(93)
        elif char == 34:
            start = self.pos
            self.string()
            length = self.pos - start - 2
            if key == "c_name":
                _limit(length <= self.limits.max_identifier_bytes)
            elif key == "record_id":
                _limit(length <= self.limits.max_anchor_id_bytes)
            elif key == "users" or (key == "path" and owner != "correspondence"):
                _limit(length <= self.limits.max_path_bytes)
        elif char == 45 or 48 <= char <= 57:
            start = self.pos
            if char == 45:
                self.pos += 1
            digits = self.pos
            while 48 <= self.byte() <= 57:
                self.pos += 1
                _limit(self.pos - digits <= self.limits.max_integer_digits)
            if self.pos == digits:
                self.invalid()
            token = self.data[start : self.pos]
            if token == b"-0" or (self.pos - digits > 1 and self.data[digits] == 48):
                raise ProfileError(
                    "profile_noncanonical", "parse", "The integer is not canonical."
                )
            if self.byte() in (46, 69, 101):
                raise ProfileError(
                    "profile_type", "parse", "Floating point numbers are not allowed."
                )
        else:
            for token in (b"null", b"true", b"false"):
                if self.data.startswith(token, self.pos):
                    self.pos += len(token)
                    return
            self.invalid()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _scan_json(data: bytes, maximum: int, limits: ProfileLimits) -> _WireScan:
    if type(data) is not bytes:
        raise ProfileError("profile_type", "parse", "Profile input must be bytes.")
    _limit(0 < len(data) <= maximum)
    if not data.endswith(b"\n") or data.startswith(b"\xef\xbb\xbf"):
        raise ProfileError(
            "profile_noncanonical", "parse", "Canonical JSON needs one final LF."
        )
    scan = _WireScan(data[:-1], limits)
    scan.value(0)
    if scan.pos != len(scan.data):
        scan.invalid()
    return scan


def _read_json(data: bytes) -> object:
    # The scanner has bounded every token, container, array, and occurrence.
    try:
        value: object = json.loads(data)
    except json.JSONDecodeError as error:
        raise ProfileError(
            "profile_json", "parse", "The JSON syntax is invalid."
        ) from error
    if data != _canonical(value):
        raise ProfileError(
            "profile_noncanonical", "parse", "The JSON bytes are not canonical."
        )
    return value


def _object(value: object, names: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ProfileError("profile_type", "parse", "A JSON object is required.")
    result = cast(dict[str, object], value)
    if set(result) != set(names.split()):
        raise ProfileError("profile_fields", "parse", "The object fields are invalid.")
    return result


def _array(value: object, maximum: int) -> list[object]:
    if type(value) is not list:
        raise ProfileError("profile_type", "parse", "A JSON array is required.")
    result = cast(list[object], value)
    _limit(len(result) <= maximum)
    return result


def _text(value: object) -> str:
    if type(value) is not str:
        raise ProfileError("profile_type", "parse", "A JSON string is required.")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ProfileError("profile_type", "parse", "An exact integer is required.")
    return value


def _count(value: object, maximum: int, minimum: int = 0) -> int:
    result = _integer(value)
    _limit(minimum <= result <= maximum)
    return result


def _literal(
    value: object,
    expected: str | int,
    *,
    category: FailureCategory = "profile_mismatch",
    phase: FailurePhase = "selection",
) -> None:
    if type(value) is not type(expected):
        raise ProfileError("profile_type", "parse", "The literal type is invalid.")
    if value != expected:
        raise ProfileError(category, phase, "A required literal differs.")


def _digest(value: object) -> str:
    result = _text(value)
    if not _DIGEST.fullmatch(result):
        raise ProfileError("profile_digest", "content", "The digest form is invalid.")
    return result


def _path(value: object, limits: ProfileLimits, *, header: bool | None = None) -> str:
    result = _text(value)
    _limit(len(result) <= limits.max_path_bytes)
    valid = (
        _HEADER.fullmatch(result)
        if header is True
        else _SOURCE.fullmatch(result)
        if header is False
        else _SOURCE.fullmatch(result) or _HEADER.fullmatch(result)
    )
    if not valid:
        raise ProfileError("profile_path", "roster", "The source path is invalid.")
    return result


def _identifier(value: object, limits: ProfileLimits) -> str:
    result = _text(value)
    _limit(len(result) <= limits.max_identifier_bytes)
    if not _IDENTIFIER.fullmatch(result):
        raise ProfileError(
            "profile_correspondence", "correspondence", "The C identifier is invalid."
        )
    return result


def _linkage(value: object) -> Linkage:
    result = _text(value)
    if result not in ("external", "internal"):
        raise ProfileError(
            "profile_correspondence", "correspondence", "The linkage is invalid."
        )
    return cast(Linkage, result)


def _ordered[T: (str, int, tuple[str, int, int, str])](
    values: tuple[T, ...], category: FailureCategory
) -> None:
    if any(left >= right for left, right in zip(values, values[1:])):
        raise ProfileError(
            category, "correspondence", "Rows must be sorted and unique."
        )


def _file_rows(
    value: object, limits: ProfileLimits, *, header: bool
) -> tuple[FileRow, ...]:
    rows = _array(value, limits.max_headers if header else limits.max_sources)
    if not header:
        _limit(bool(rows))
    result = []
    for raw in rows:
        row = _object(raw, "path size sha256")
        result.append(
            FileRow(
                _path(row["path"], limits, header=header),
                _count(row["size"], limits.max_total_source_bytes, 0 if header else 1),
                _digest(row["sha256"]),
            )
        )
    paths = tuple(row.path for row in result)
    if any(left >= right for left, right in zip(paths, paths[1:])):
        raise ProfileError(
            "profile_roster", "roster", "File paths must be sorted and unique."
        )
    return tuple(result)


def _cmake_size(sources: tuple[FileRow, ...]) -> int:
    return (
        len(_CMAKE_PREFIX)
        + len(b"add_executable(program\n")
        + sum(5 + len(row.path) for row in sources)
        + len(b")\n")
        + len(_CMAKE_SUFFIX)
    )


def _cmake(sources: tuple[FileRow, ...]) -> bytes:
    return (
        _CMAKE_PREFIX
        + b"add_executable(program\n"
        + b"".join(b"    " + row.path.encode("ascii") + b"\n" for row in sources)
        + b")\n"
        + _CMAKE_SUFFIX
    )


def _manifest(value: object, limits: ProfileLimits) -> ProjectManifestV2:
    row = _object(
        value,
        "schema profile build_profile original_sha256 origin_sha256 "
        "sources headers correspondence cmake_sha256",
    )
    _literal(row["schema"], 2)
    _literal(row["profile"], "phoenix-project-v2")
    _literal(row["build_profile"], "phoenix-c11-posix-o2-v2")
    sources = _file_rows(row["sources"], limits, header=False)
    headers = _file_rows(row["headers"], limits, header=True)
    size = _cmake_size(sources)
    _limit(size <= limits.max_cmake_bytes)
    _limit(
        sum(file.size for file in (*sources, *headers)) + size
        <= limits.max_total_source_bytes
    )
    binding = _object(row["correspondence"], "path size sha256")
    _literal(
        binding["path"],
        "phoenix_correspondence.json",
        category="profile_path",
        phase="roster",
    )
    return ProjectManifestV2(
        2,
        "phoenix-project-v2",
        "phoenix-c11-posix-o2-v2",
        _digest(row["original_sha256"]),
        _digest(row["origin_sha256"]),
        sources,
        headers,
        CorrespondenceFileRow(
            "phoenix_correspondence.json",
            _count(binding["size"], limits.max_correspondence_bytes, 1),
            _digest(binding["sha256"]),
        ),
        _digest(row["cmake_sha256"]),
    )


class _CorrespondenceReader:
    def __init__(self, manifest: ProjectManifestV2, limits: ProfileLimits) -> None:
        self.manifest = manifest
        self.limits = limits
        self.files = {row.path: row for row in (*manifest.sources, *manifest.headers)}
        self.sources = frozenset(row.path for row in manifest.sources)

    def span(self, value: object) -> Span:
        row = _object(value, "path start end sha256")
        path = _path(row["path"], self.limits)
        if path not in self.files:
            raise ProfileError(
                "profile_correspondence",
                "correspondence",
                "The span file is not listed.",
            )
        start = _integer(row["start"])
        end = _integer(row["end"])
        if not 0 <= start < end <= self.files[path].size:
            raise ProfileError(
                "profile_correspondence",
                "correspondence",
                "The span range is outside its declared file.",
            )
        return Span(path, start, end, _digest(row["sha256"]))

    def declarations(self, value: object) -> tuple[Span, ...]:
        result = tuple(self.span(item) for item in _array(value, self.limits.max_spans))
        _ordered(tuple(_span_key(item) for item in result), "profile_correspondence")
        return result

    def ids(self, value: object) -> tuple[str, ...]:
        result = tuple(
            _digest(item) for item in _array(value, self.limits.max_shared_types)
        )
        _ordered(result, "profile_correspondence")
        return result

    def anchor(self, value: object) -> Anchor:
        row = _object(value, "artifact_sha256 record_id")
        record_id = _text(row["record_id"])
        _limit(len(record_id) <= self.limits.max_anchor_id_bytes)
        if not _ANCHOR_ID.fullmatch(record_id):
            raise ProfileError(
                "profile_shared_identity",
                "correspondence",
                "The evidence record ID is invalid.",
            )
        return Anchor(_digest(row["artifact_sha256"]), record_id)

    def identity(self, row: dict[str, object], domain: bytes) -> tuple[str, Anchor]:
        identity = _digest(row["id"])
        anchor = self.anchor(row["anchor"])
        expected = sha256(
            domain
            + b"\0"
            + _canonical(
                {
                    "original_sha256": self.manifest.original_sha256,
                    "anchor": {
                        "artifact_sha256": anchor.artifact_sha256,
                        "record_id": anchor.record_id,
                    },
                }
            )
        ).hexdigest()
        if identity != expected:
            raise ProfileError(
                "profile_shared_identity",
                "correspondence",
                "The nominal identity differs.",
            )
        return identity, anchor

    def function(self, value: object) -> FunctionRow:
        row = _object(
            value,
            "origin_entry c_name linkage definition signature body shared_type_ids",
        )
        entry = _text(row["origin_entry"])
        if not _ENTRY.fullmatch(entry):
            raise ProfileError(
                "profile_origin", "correspondence", "The original entry is invalid."
            )
        definition, signature, body = (
            self.span(row[name]) for name in ("definition", "signature", "body")
        )
        if (
            definition.path not in self.sources
            or signature.path != definition.path
            or body.path != definition.path
            or signature.start != definition.start
            or body.end != definition.end
            or signature.end > body.start
        ):
            raise ProfileError(
                "profile_correspondence",
                "correspondence",
                "The function spans do not agree.",
            )
        return FunctionRow(
            entry,
            _identifier(row["c_name"], self.limits),
            _linkage(row["linkage"]),
            definition,
            signature,
            body,
            self.ids(row["shared_type_ids"]),
        )

    def global_row(self, value: object) -> GlobalRow:
        row = _object(
            value, "id anchor c_name linkage definition declarations shared_type_ids"
        )
        identity, anchor = self.identity(row, b"phoenix-global-id-v1")
        definition = self.span(row["definition"])
        declarations = self.declarations(row["declarations"])
        linkage = _linkage(row["linkage"])
        if definition.path not in self.sources or (
            linkage == "external"
            and not any(span.path.startswith("include/") for span in declarations)
        ):
            raise ProfileError(
                "profile_correspondence",
                "correspondence",
                "The global definition or declarations are invalid.",
            )
        return GlobalRow(
            identity,
            anchor,
            _identifier(row["c_name"], self.limits),
            linkage,
            definition,
            declarations,
            self.ids(row["shared_type_ids"]),
        )

    def shared_type(self, value: object) -> SharedTypeRow:
        row = _object(
            value, "id anchor kind c_name definition declarations users claim"
        )
        identity, anchor = self.identity(row, b"phoenix-shared-type-id-v1")
        kind = _text(row["kind"])
        if kind not in ("struct", "union", "enum", "typedef"):
            raise ProfileError(
                "profile_shared_identity",
                "correspondence",
                "The shared type kind is invalid.",
            )
        _literal(
            row["claim"],
            "proposal",
            category="profile_shared_identity",
            phase="correspondence",
        )
        definition = None if row["definition"] is None else self.span(row["definition"])
        declarations = self.declarations(row["declarations"])
        if (
            not any(span.path.startswith("include/") for span in declarations)
            or (definition is not None and definition not in declarations)
            or (definition is None and kind == "typedef")
        ):
            raise ProfileError(
                "profile_shared_identity",
                "correspondence",
                "The shared declarations are incomplete.",
            )
        users = tuple(
            _path(item, self.limits, header=False)
            for item in _array(row["users"], self.limits.max_sources)
        )
        _ordered(users, "profile_correspondence")
        if any(user not in self.sources for user in users):
            raise ProfileError(
                "profile_correspondence",
                "correspondence",
                "A shared type user is not listed.",
            )
        return SharedTypeRow(
            identity,
            anchor,
            cast(TypeKind, kind),
            _identifier(row["c_name"], self.limits),
            definition,
            declarations,
            users,
            "proposal",
        )


def _span_key(span: Span) -> tuple[str, int, int, str]:
    return span.path, span.start, span.end, span.sha256


def _correspondence(
    value: object, manifest: ProjectManifestV2, limits: ProfileLimits
) -> CorrespondenceV1:
    row = _object(
        value,
        "schema profile original_sha256 origin_sha256 address_space "
        "declaration_version_sha256 functions globals shared_types",
    )
    _literal(row["schema"], 1)
    _literal(row["profile"], "phoenix-correspondence-v1")
    _literal(
        row["address_space"],
        "ghidra-ram",
        category="profile_origin",
        phase="correspondence",
    )
    original = _digest(row["original_sha256"])
    origin = _digest(row["origin_sha256"])
    if original != manifest.original_sha256 or origin != manifest.origin_sha256:
        raise ProfileError(
            "profile_origin",
            "correspondence",
            "The original or origin identity differs.",
        )
    reader = _CorrespondenceReader(manifest, limits)
    functions = tuple(
        reader.function(item) for item in _array(row["functions"], limits.max_functions)
    )
    globals_ = tuple(
        reader.global_row(item) for item in _array(row["globals"], limits.max_globals)
    )
    types = tuple(
        reader.shared_type(item)
        for item in _array(row["shared_types"], limits.max_shared_types)
    )
    _ordered(tuple(int(item.origin_entry, 16) for item in functions), "profile_origin")
    _ordered(tuple(item.id for item in globals_), "profile_shared_identity")
    _ordered(tuple(item.id for item in types), "profile_shared_identity")
    keys = tuple(
        (item.definition.path, item.c_name, item.linkage) for item in functions
    )
    if len(set(keys)) != len(keys):
        raise ProfileError(
            "profile_correspondence", "correspondence", "A function key is repeated."
        )
    named: tuple[FunctionRow | GlobalRow, ...] = (*functions, *globals_)
    external = tuple(item.c_name for item in named if item.linkage == "external")
    if (
        len(set(external)) != len(external)
        or sum(
            item.c_name == "main" and item.linkage == "external" for item in functions
        )
        != 1
    ):
        raise ProfileError(
            "profile_correspondence",
            "correspondence",
            "External definitions or main are invalid.",
        )
    definitions = sorted(_span_key(item.definition) for item in functions)
    if any(a[0] == b[0] and a[2] > b[1] for a, b in zip(definitions, definitions[1:])):
        raise ProfileError(
            "profile_correspondence", "correspondence", "Function definitions overlap."
        )
    type_ids = frozenset(item.id for item in types)
    if any(
        identity not in type_ids for item in named for identity in item.shared_type_ids
    ):
        raise ProfileError(
            "profile_correspondence",
            "correspondence",
            "A shared type reference is unresolved.",
        )
    owned = tuple(
        _span_key(item.definition)[:3] for item in types if item.definition is not None
    )
    if len(set(owned)) != len(owned):
        raise ProfileError(
            "profile_shared_identity",
            "correspondence",
            "A type definition has two owners.",
        )
    declaration_version = _digest(row["declaration_version_sha256"])
    expected_version = sha256(
        b"phoenix-declarations-v1\0"
        + _canonical(
            [
                {"path": item.path, "size": item.size, "sha256": item.sha256}
                for item in manifest.headers
            ]
        )
    ).hexdigest()
    if declaration_version != expected_version:
        raise ProfileError(
            "profile_shared_identity",
            "correspondence",
            "The declaration version differs.",
        )
    return CorrespondenceV1(
        1,
        "phoenix-correspondence-v1",
        original,
        origin,
        "ghidra-ram",
        declaration_version,
        functions,
        globals_,
        types,
    )


def parse_profile_v2(
    manifest_bytes: bytes,
    correspondence_bytes: bytes,
    limits: ProfileLimits = DEFAULT_LIMITS,
) -> ParsedProjectV2:
    """Parse bounded canonical records. No source contents or authority are supplied."""
    _limits(limits)
    manifest_scan = _scan_json(manifest_bytes, limits.max_manifest_bytes, limits)
    correspondence_scan = _scan_json(
        correspondence_bytes, limits.max_correspondence_bytes, limits
    )
    _limit(
        manifest_scan.edges + correspondence_scan.edges <= limits.max_reference_edges
    )
    raw_manifest = _read_json(manifest_bytes)
    manifest = _manifest(raw_manifest, limits)
    raw_correspondence = _read_json(correspondence_bytes)
    if (
        len(correspondence_bytes) != manifest.correspondence.size
        or sha256(correspondence_bytes).hexdigest() != manifest.correspondence.sha256
    ):
        raise ProfileError(
            "profile_digest",
            "content",
            "The correspondence bytes differ from the binding.",
        )
    correspondence = _correspondence(raw_correspondence, manifest, limits)
    if sha256(_cmake(manifest.sources)).hexdigest() != manifest.cmake_sha256:
        raise ProfileError(
            "profile_cmake", "content", "The canonical CMake digest differs."
        )
    return ParsedProjectV2(
        manifest, correspondence, manifest_bytes, correspondence_bytes
    )


def _same_record(value: object, expected: object) -> bool:
    if type(value) is not type(expected):
        return False
    if is_dataclass(expected) and not isinstance(expected, type):
        return all(
            hasattr(value, field.name)
            and _same_record(getattr(value, field.name), getattr(expected, field.name))
            for field in fields(expected)
        )
    if isinstance(expected, tuple):
        actual = cast(tuple[object, ...], value)
        return len(actual) == len(expected) and all(
            _same_record(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return bool(value == expected)


def render_cmake_v2(profile: ParsedProjectV2) -> bytes:
    """Derive fixed CMake bytes after checking the complete public record again."""
    if type(profile) is not ParsedProjectV2:
        raise ProfileError("profile_type", "parse", "ParsedProjectV2 is required.")
    manifest_bytes = getattr(profile, "canonical_manifest", None)
    correspondence_bytes = getattr(profile, "canonical_correspondence", None)
    if type(manifest_bytes) is not bytes or type(correspondence_bytes) is not bytes:
        raise ProfileError(
            "profile_type", "parse", "Canonical profile bytes are required."
        )
    parsed = parse_profile_v2(manifest_bytes, correspondence_bytes)
    if not _same_record(profile, parsed):
        raise ProfileError(
            "profile_correspondence",
            "correspondence",
            "The public records differ from their canonical bytes.",
        )
    return _cmake(parsed.manifest.sources)


def validate_cmake_v2(profile: ParsedProjectV2, supplied_cmake: bytes) -> bytes:
    """Require the supplied package to retain the exact canonical build file."""
    if type(supplied_cmake) is not bytes:
        raise ProfileError("profile_type", "parse", "CMake input must be bytes.")
    _limit(len(supplied_cmake) <= DEFAULT_LIMITS.max_cmake_bytes)
    expected = render_cmake_v2(profile)
    if supplied_cmake != expected:
        raise ProfileError(
            "profile_cmake", "content", "The supplied CMake bytes differ."
        )
    return expected
