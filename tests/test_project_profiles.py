"""Exercise the public pure profile boundary with independently authored data."""

from __future__ import annotations

import ast
import copy
import json
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, asdict, fields, is_dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phoenix_eval import project_profile as module
from phoenix_eval.project_profile import (
    DEFAULT_LIMITS,
    Anchor,
    CorrespondenceFileRow,
    CorrespondenceV1,
    FileRow,
    FunctionRow,
    GlobalRow,
    ParsedProjectV2,
    ProfileError,
    ProfileLimits,
    ProjectManifestV2,
    SharedTypeRow,
    Span,
    parse_profile_v2,
    render_cmake_v2,
    validate_cmake_v2,
)

type Document = dict[str, Any]
ORIGINAL = "a" * 64
ORIGIN = "b" * 64
ARTIFACT = "c" * 64
SPAN_HASH = "d" * 64
GOLDEN_CMAKE = b"""cmake_minimum_required(VERSION 3.22)
project(phoenix_rebuild LANGUAGES C)
add_executable(program
    src/main.c
    src/step.c
    src/total.c
)
target_include_directories(program PRIVATE include)
target_compile_definitions(program PRIVATE _POSIX_C_SOURCE=200809L)
target_compile_options(program PRIVATE -Wall -Wextra -O2 -fstack-protector-all)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(program PRIVATE LINKER:-z,relro,-z,now)
endif()
set_target_properties(program PROPERTIES
    C_STANDARD 11 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
"""


def canonical(value: object) -> bytes:
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


def identity(label: str, anchor: Document, original: str = ORIGINAL) -> str:
    payload = canonical({"original_sha256": original, "anchor": anchor})
    return sha256(label.encode("ascii") + bytes([0]) + payload).hexdigest()


def span(path: str, start: int, end: int) -> Document:
    return {"path": path, "start": start, "end": end, "sha256": SPAN_HASH}


def function(entry: str, name: str, path: str, ids: list[str]) -> Document:
    return {
        "origin_entry": entry,
        "c_name": name,
        "linkage": "external",
        "definition": span(path, 10, 100),
        "signature": span(path, 10, 25),
        "body": span(path, 30, 100),
        "shared_type_ids": ids,
    }


def documents() -> tuple[Document, Document]:
    sources = [
        {"path": path, "size": 500, "sha256": "e" * 64}
        for path in ("src/main.c", "src/step.c", "src/total.c")
    ]
    headers = [
        {"path": path, "size": 500, "sha256": "f" * 64}
        for path in ("include/api.h", "include/types.h")
    ]
    types: list[Document] = []
    for index, name in enumerate(("left_value", "right_value")):
        anchor = {"artifact_sha256": ARTIFACT, "record_id": f"type:{name}"}
        declaration = span("include/types.h", 10 + index * 50, 50 + index * 50)
        types.append(
            {
                "id": identity("phoenix-shared-type-id-v1", anchor),
                "anchor": anchor,
                "kind": "struct",
                "c_name": name,
                "definition": copy.deepcopy(declaration),
                "declarations": [declaration],
                "users": ["src/main.c", "src/step.c", "src/total.c"],
                "claim": "proposal",
            }
        )
    types.sort(key=lambda row: row["id"])
    ids = [row["id"] for row in types]
    anchor = {"artifact_sha256": ARTIFACT, "record_id": "global:tally"}
    corr = {
        "schema": 1,
        "profile": "phoenix-correspondence-v1",
        "original_sha256": ORIGINAL,
        "origin_sha256": ORIGIN,
        "address_space": "ghidra-ram",
        "declaration_version_sha256": sha256(
            b"phoenix-declarations-v1\x00" + canonical(headers)
        ).hexdigest(),
        "functions": [
            function(entry, name, path, ids.copy())
            for entry, name, path in (
                ("0x9", "main", "src/main.c"),
                ("0x10", "step", "src/step.c"),
                ("0xffffffffffffffff", "total", "src/total.c"),
            )
        ],
        "globals": [
            {
                "id": identity("phoenix-global-id-v1", anchor),
                "anchor": anchor,
                "c_name": "tally",
                "linkage": "external",
                "definition": span("src/step.c", 110, 140),
                "declarations": [span("include/api.h", 10, 30)],
                "shared_type_ids": ids.copy(),
            }
        ],
        "shared_types": types,
    }
    manifest = {
        "schema": 2,
        "profile": "phoenix-project-v2",
        "build_profile": "phoenix-c11-posix-o2-v2",
        "original_sha256": ORIGINAL,
        "origin_sha256": ORIGIN,
        "sources": sources,
        "headers": headers,
        "correspondence": {
            "path": "phoenix_correspondence.json",
            "size": 1,
            "sha256": "0" * 64,
        },
        "cmake_sha256": sha256(GOLDEN_CMAKE).hexdigest(),
    }
    return manifest, corr


def wire(manifest: Document, corr: Document) -> tuple[bytes, bytes]:
    raw = canonical(corr)
    manifest = copy.deepcopy(manifest)
    manifest["correspondence"]["size"] = len(raw)
    manifest["correspondence"]["sha256"] = sha256(raw).hexdigest()
    return canonical(manifest), raw


def parse(
    manifest: Document, corr: Document, limits: ProfileLimits = DEFAULT_LIMITS
) -> ParsedProjectV2:
    return parse_profile_v2(*wire(manifest, corr), limits)


def rejected(
    manifest: Document, corr: Document, category: str | None = None
) -> ProfileError:
    with pytest.raises(ProfileError) as caught:
        parse(manifest, corr)
    error = caught.value
    assert len(error.detail) <= 160
    assert error.phase in {"selection", "parse", "roster", "content", "correspondence"}
    if category is not None:
        assert error.category == category
    return error


def test_complete_records_and_independent_golden() -> None:
    manifest, corr = documents()
    m, c = wire(manifest, corr)
    profile = parse_profile_v2(m, c)
    assert profile.canonical_manifest is m
    assert profile.canonical_correspondence is c
    assert json.loads(json.dumps(asdict(profile.manifest))) == json.loads(m)
    assert json.loads(json.dumps(asdict(profile.correspondence))) == corr
    assert tuple(profile.manifest.sources) == tuple(
        FileRow(**row) for row in manifest["sources"]
    )
    assert tuple(profile.manifest.headers) == tuple(
        FileRow(**row) for row in manifest["headers"]
    )
    assert profile.manifest.correspondence == CorrespondenceFileRow(
        "phoenix_correspondence.json", len(c), sha256(c).hexdigest()
    )
    assert len(profile.correspondence.functions) == 3
    assert profile.correspondence.functions[1] == FunctionRow(
        "0x10",
        "step",
        "external",
        Span("src/step.c", 10, 100, SPAN_HASH),
        Span("src/step.c", 10, 25, SPAN_HASH),
        Span("src/step.c", 30, 100, SPAN_HASH),
        tuple(row["id"] for row in corr["shared_types"]),
    )
    assert profile.correspondence.globals[0].anchor == Anchor(ARTIFACT, "global:tally")
    types = profile.correspondence.shared_types
    assert types[0].id != types[1].id
    assert {row.c_name for row in types} == {"left_value", "right_value"}
    assert all(row.kind == "struct" and row.claim == "proposal" for row in types)
    assert all(row.definition == row.declarations[0] for row in types)
    assert render_cmake_v2(profile) == GOLDEN_CMAKE
    assert validate_cmake_v2(profile, GOLDEN_CMAKE) == GOLDEN_CMAKE
    assert not hasattr(profile, "integrity_passed")


def walk(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, tuple):
        for item in value:
            yield from walk(item)
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from walk(getattr(value, field.name))


def test_complete_tree_is_immutable_and_slotted() -> None:
    profile = parse(*documents())
    records = [
        value for value in walk(profile) if hasattr(value, "__dataclass_fields__")
    ]
    assert {type(value) for value in records} == {
        ParsedProjectV2,
        ProjectManifestV2,
        CorrespondenceFileRow,
        FileRow,
        CorrespondenceV1,
        FunctionRow,
        GlobalRow,
        SharedTypeRow,
        Span,
        Anchor,
    }
    for record in records:
        assert is_dataclass(record) and not isinstance(record, type)
        assert not hasattr(record, "__dict__")
        field = fields(record)[0]
        with pytest.raises(FrozenInstanceError):
            setattr(record, field.name, None)
    assert not any(
        isinstance(value, (list, dict, bytearray)) for value in walk(profile)
    )


@pytest.mark.parametrize("kind", ["struct", "union", "enum", "typedef"])
@pytest.mark.parametrize("definition", [False, True])
def test_optional_definition_and_type_kinds(kind: str, definition: bool) -> None:
    manifest, corr = documents()
    row = corr["shared_types"][0]
    row["kind"] = kind
    if not definition:
        row["definition"] = None
    if kind == "typedef" and not definition:
        rejected(manifest, corr, "profile_shared_identity")
    else:
        actual = parse(manifest, corr).correspondence.shared_types[0]
        assert actual.kind == kind
        assert (actual.definition is not None) == definition
        assert len(actual.declarations) == 1


def objects(
    value: object, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[tuple[str | int, ...], Document]]:
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from objects(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from objects(item, (*path, index))


def object_cases() -> list[tuple[str, tuple[str | int, ...], str]]:
    return [
        (which, path, key)
        for which, doc in zip(("manifest", "corr"), documents(), strict=True)
        for path, row in objects(doc)
        for key in row
    ]


def locate(doc: Document, path: tuple[str | int, ...]) -> Document:
    value: Any = doc
    for part in path:
        value = value[part]
    return cast(Document, value)


@pytest.mark.parametrize("which,path,key", object_cases())
@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate", "wrong_type"])
def test_every_object_field_is_closed_required_unique_and_typed(
    which: str, path: tuple[str | int, ...], key: str, mode: str
) -> None:
    manifest, corr = documents()
    m, c = wire(manifest, corr)
    manifest = json.loads(m)
    doc = manifest if which == "manifest" else corr
    row = locate(doc, path)
    if mode == "missing":
        del row[key]
    elif mode == "extra":
        row["extra"] = None
    elif mode == "wrong_type":
        row[key] = True
    else:
        needle = canonical(row).rstrip(b"\n")
        field = canonical(key).rstrip(b"\n") + b":" + canonical(row[key]).rstrip(b"\n")
        duplicate = needle[:-1] + b"," + field + b"}"
        if which == "manifest":
            m = m.replace(needle, duplicate)
        else:
            c = c.replace(needle, duplicate)
        with pytest.raises(ProfileError) as caught:
            parse_profile_v2(m, c)
        assert caught.value.category == "profile_duplicate_key"
        return
    if which == "manifest":
        m = canonical(manifest)
    else:
        m, c = wire(manifest, corr)
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(m, c)
    assert caught.value.category == (
        "profile_fields" if mode in ("missing", "extra") else "profile_type"
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/Main.c",
        "src/MAIN.c",
        "src/ä.c",
        "src/a.c/../b.c",
        "../src/a.c",
        "/src/a.c",
        "src//a.c",
        "src/./a.c",
        "src/a/b.c",
        "src\\a.c",
        "src/a.h",
        "include/a.c",
        "src/a.c\n",
        "src/a.c\x00",
        "src/1.c",
        "src/.c",
        "src/_a.c",
        "src/a-b.c",
        "src/a.c;message(x)",
        "src/${x}.c",
        "src/a" + "b" * 48 + ".c",
    ],
)
def test_whole_source_path_grammar(path: str) -> None:
    manifest, corr = documents()
    manifest["sources"][0]["path"] = path
    rejected(manifest, corr)


@pytest.mark.parametrize(
    "path",
    [
        "include/X.h",
        "include/a.c",
        "src/a.h",
        "include/a/b.h",
        "include//a.h",
        "include/1.h",
        "include/a.h\n",
        "../include/a.h",
        "include/é.h",
    ],
)
def test_whole_header_path_grammar(path: str) -> None:
    manifest, corr = documents()
    manifest["headers"][0]["path"] = path
    rejected(manifest, corr)


@pytest.mark.parametrize(
    "entry",
    [
        "0X1",
        "0x00",
        "0x01",
        "0xA",
        "0x10000000000000000",
        "0x",
        "0x-1",
        "1",
        " 0x1",
        "0x1\n",
        "0x１",
        True,
        1,
    ],
)
def test_canonical_u64_entries(entry: object) -> None:
    manifest, corr = documents()
    corr["functions"][0]["origin_entry"] = entry
    rejected(manifest, corr)


@pytest.mark.parametrize("name", ["", "1a", "a-b", "é", "a\n", "a()", "a" * 129])
def test_identifier_grammar(name: str) -> None:
    manifest, corr = documents()
    corr["functions"][1]["c_name"] = name
    rejected(manifest, corr)


@pytest.mark.parametrize("name", ["", "_a", ".a", "a/b", "a b", "é", "a\n", "a" * 129])
def test_anchor_grammar(name: str) -> None:
    manifest, corr = documents()
    corr["globals"][0]["anchor"]["record_id"] = name
    rejected(manifest, corr)


@pytest.mark.parametrize(
    "digest", ["A" * 64, "a" * 63, "a" * 65, "g" * 64, "a" * 63 + "\n", "", True, 0]
)
@pytest.mark.parametrize(
    "location",
    [
        "original",
        "origin",
        "source",
        "span",
        "anchor",
        "id",
        "version",
        "cmake",
        "binding",
    ],
)
def test_digest_forms(digest: object, location: str) -> None:
    manifest, corr = documents()
    destinations = {
        "original": (manifest, "original_sha256"),
        "origin": (manifest, "origin_sha256"),
        "source": (manifest["sources"][0], "sha256"),
        "span": (corr["functions"][0]["body"], "sha256"),
        "anchor": (corr["globals"][0]["anchor"], "artifact_sha256"),
        "id": (corr["globals"][0], "id"),
        "version": (corr, "declaration_version_sha256"),
        "cmake": (manifest, "cmake_sha256"),
        "binding": (manifest["correspondence"], "sha256"),
    }
    target, key = destinations[location]
    target[key] = digest
    if location == "binding":
        m, c = wire(manifest, corr)
        changed = json.loads(m)
        changed["correspondence"]["sha256"] = digest
        with pytest.raises(ProfileError):
            parse_profile_v2(canonical(changed), c)
    else:
        rejected(manifest, corr)


@pytest.mark.parametrize(
    "location",
    [
        "sources",
        "headers",
        "functions",
        "globals",
        "shared_types",
        "shared_type_ids",
        "users",
        "declarations",
    ],
)
def test_repeated_rows_and_references(location: str) -> None:
    manifest, corr = documents()
    if location in ("sources", "headers"):
        rows = manifest[location]
    elif location == "shared_type_ids":
        rows = corr["functions"][0][location]
    elif location in ("users", "declarations"):
        rows = corr["shared_types"][0][location]
    else:
        rows = corr[location]
    rows.insert(0, copy.deepcopy(rows[0]))
    rejected(manifest, corr)


@pytest.mark.parametrize(
    "change",
    [
        "signature_path",
        "body_path",
        "header_definition",
        "start_endpoint",
        "end_endpoint",
        "sig_overlap",
        "body_outside",
        "empty",
        "reverse",
        "negative",
        "end_size",
        "unlisted",
        "overlap",
        "same_entry",
        "same_key",
        "external_name",
        "no_main",
        "internal_main",
        "two_main",
        "global_name",
        "unknown_type",
        "unknown_global_type",
        "unknown_user",
        "header_user",
        "no_header_type",
        "no_header_global",
        "unlisted_definition",
        "definition_owner",
        "definition_owner_hash",
    ],
)
def test_correspondence_conflicts(change: str) -> None:
    manifest, corr = documents()
    row = corr["functions"][0]
    other = corr["functions"][1]
    typ = corr["shared_types"][0]
    glob = corr["globals"][0]
    if change == "signature_path":
        row["signature"]["path"] = "src/step.c"
    elif change == "body_path":
        row["body"]["path"] = "src/step.c"
    elif change == "header_definition":
        for field in ("definition", "signature", "body"):
            row[field]["path"] = "include/api.h"
    elif change == "start_endpoint":
        row["signature"]["start"] = 11
    elif change == "end_endpoint":
        row["body"]["end"] = 99
    elif change == "sig_overlap":
        row["signature"]["end"] = 31
    elif change == "body_outside":
        row["body"]["start"] = 9
    elif change == "empty":
        row["body"]["end"] = 30
    elif change == "reverse":
        row["body"]["end"] = 29
    elif change == "negative":
        row["definition"]["start"] = -1
    elif change == "end_size":
        row["definition"]["end"] = 501
    elif change == "unlisted":
        row["definition"]["path"] = "src/absent.c"
    elif change == "overlap":
        for field in ("definition", "signature", "body"):
            other[field]["path"] = "src/main.c"
    elif change == "same_entry":
        other["origin_entry"] = row["origin_entry"]
    elif change == "same_key":
        other["c_name"] = row["c_name"]
        other["linkage"] = row["linkage"]
        for field in ("definition", "signature", "body"):
            other[field]["path"] = row[field]["path"]
            other[field]["start"] += 100
            other[field]["end"] += 100
    elif change == "external_name":
        other["c_name"] = corr["functions"][2]["c_name"]
    elif change == "no_main":
        row["c_name"] = "other"
    elif change == "internal_main":
        row["linkage"] = "internal"
    elif change == "two_main":
        other["c_name"] = "main"
    elif change == "global_name":
        glob["c_name"] = "main"
    elif change == "unknown_type":
        row["shared_type_ids"] = ["0" * 64]
    elif change == "unknown_global_type":
        glob["shared_type_ids"] = ["0" * 64]
    elif change == "unknown_user":
        typ["users"] = ["src/absent.c"]
    elif change == "header_user":
        typ["users"] = ["include/api.h"]
    elif change == "no_header_type":
        typ["declarations"] = [span("src/main.c", 150, 190)]
    elif change == "no_header_global":
        glob["declarations"] = []
    elif change == "unlisted_definition":
        typ["definition"] = span("include/types.h", 300, 350)
    elif change in ("definition_owner", "definition_owner_hash"):
        second = corr["shared_types"][1]
        second["definition"] = copy.deepcopy(typ["definition"])
        if change == "definition_owner_hash":
            second["definition"]["sha256"] = "1" * 64
        second["declarations"] = [copy.deepcopy(second["definition"])]
    else:
        raise AssertionError(change)
    rejected(manifest, corr)


def test_touching_functions_repeated_local_names_and_local_global() -> None:
    manifest, corr = documents()
    for row in corr["functions"][1:]:
        row["c_name"] = "local"
        row["linkage"] = "internal"
    local = corr["globals"][0]
    local["linkage"] = "internal"
    local["declarations"] = []
    parse(manifest, corr)
    row = corr["functions"][1]
    for field in ("definition", "signature", "body"):
        row[field]["path"] = "src/main.c"
        row[field]["start"] += 90
        row[field]["end"] += 90
    parse(manifest, corr)


@pytest.mark.parametrize("field", ["original_sha256", "origin_sha256"])
def test_original_and_origin_must_agree(field: str) -> None:
    manifest, corr = documents()
    corr[field] = "9" * 64
    rejected(manifest, corr, "profile_origin")


@pytest.mark.parametrize("label", ["phoenix-global-id-v1", "phoenix-shared-type-id-v1"])
@pytest.mark.parametrize(
    "error",
    [
        "no_nul",
        "text_nul",
        "wrong_domain",
        "wrong_original",
        "partial_anchor",
        "no_final_lf",
    ],
)
def test_exact_nominal_hash_domain(label: str, error: str) -> None:
    manifest, corr = documents()
    row = corr["globals" if label == "phoenix-global-id-v1" else "shared_types"][0]
    anchor = copy.deepcopy(row["anchor"])
    original = ORIGINAL
    separator = b"\0"
    domain = label.encode()
    if error == "no_nul":
        separator = b""
    elif error == "text_nul":
        separator = b"\\0"
    elif error == "wrong_domain":
        domain += b"x"
    elif error == "wrong_original":
        original = ORIGIN
    elif error == "partial_anchor":
        del anchor["artifact_sha256"]
    data = canonical({"original_sha256": original, "anchor": anchor})
    if error == "no_final_lf":
        data = data[:-1]
    row["id"] = sha256(domain + separator + data).hexdigest()
    rejected(manifest, corr, "profile_shared_identity")


@pytest.mark.parametrize(
    "change", ["hash", "header_order", "header_size", "header_digest"]
)
def test_declaration_version_binds_complete_header_rows(change: str) -> None:
    manifest, corr = documents()
    if change == "hash":
        corr["declaration_version_sha256"] = "0" * 64
    elif change == "header_order":
        manifest["headers"].reverse()
    elif change == "header_size":
        manifest["headers"][0]["size"] += 1
    else:
        manifest["headers"][0]["sha256"] = "0" * 64
    rejected(manifest, corr)


@pytest.mark.parametrize("value", [True, False, 1.0, -1, -0.0, "500", None])
def test_exact_count_types_and_nonnegative_bounds(value: object) -> None:
    manifest, corr = documents()
    manifest["sources"][0]["size"] = value
    rejected(manifest, corr)


@pytest.mark.parametrize("which", ["manifest", "corr"])
@pytest.mark.parametrize(
    "change",
    [
        "bom",
        "no_lf",
        "two_lf",
        "spaces",
        "key_order",
        "escape_key",
        "escape_value",
        "raw_unicode",
        "escaped_unicode",
        "surrogate",
        "invalid_utf8",
        "nan",
        "infinity",
        "negative_zero",
        "float",
        "exponent",
        "trailing",
        "leading_zero",
        "truncated",
        "invalid_escape",
        "large_string",
        "large_integer",
        "deep",
    ],
)
def test_noncanonical_and_malformed_raw_wire(which: str, change: str) -> None:
    manifest, corr = documents()
    m, c = wire(manifest, corr)
    raw = m if which == "manifest" else c
    if change == "bom":
        raw = b"\xef\xbb\xbf" + raw
    elif change == "no_lf":
        raw = raw[:-1]
    elif change == "two_lf":
        raw += b"\n"
    elif change == "spaces":
        raw = raw.replace(b":", b": ", 1)
    elif change == "key_order":
        raw = (
            json.dumps(
                dict(reversed(list(json.loads(raw).items()))), separators=(",", ":")
            ).encode()
            + b"\n"
        )
    elif change == "escape_key":
        raw = raw.replace(b'"schema"', b'"\\u0073chema"')
    elif change == "escape_value":
        raw = raw.replace(b"phoenix-", b"\\u0070hoenix-", 1)
    elif change == "raw_unicode":
        raw = raw.replace(b"phoenix-", b"\xc3\xa9-", 1)
    elif change == "escaped_unicode":
        raw = raw.replace(b"phoenix-", b"\\u00e9-", 1)
    elif change == "surrogate":
        raw = raw.replace(b"phoenix-", b"\\ud800-", 1)
    elif change == "invalid_utf8":
        raw = raw.replace(b"phoenix-", b"\xff-", 1)
    elif change == "nan":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":NaN'
        )
    elif change == "infinity":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":Infinity'
        )
    elif change == "negative_zero":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":-0'
        )
    elif change == "float":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":1.0'
        )
    elif change == "exponent":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":1e0'
        )
    elif change == "trailing":
        raw = raw[:-1] + b"{}\n"
    elif change == "leading_zero":
        raw = raw.replace(
            b'"schema":' + (b"2" if which == "manifest" else b"1"), b'"schema":01'
        )
    elif change == "truncated":
        raw = raw[:20] + b"\n"
    elif change == "invalid_escape":
        raw = raw.replace(b"phoenix-", b"\\q-", 1)
    elif change == "large_string":
        raw = b'{"x":"' + b"x" * 129 + b'"}\n'
    elif change == "large_integer":
        raw = b'{"x":' + b"9" * 21 + b"}\n"
    elif change == "deep":
        raw = b"[" * 17 + b"0" + b"]" * 17 + b"\n"
    if which == "manifest":
        m = raw
    else:
        c = raw
    with pytest.raises(ProfileError):
        parse_profile_v2(m, c)


@pytest.mark.parametrize("which", ["manifest", "corr"])
@pytest.mark.parametrize(
    "value", [None, "", bytearray(b"{}\n"), memoryview(b"{}\n"), True, 1]
)
def test_exact_byte_inputs(which: str, value: Any) -> None:
    m, c = wire(*documents())
    with pytest.raises(ProfileError, match="bytes"):
        parse_profile_v2(
            value if which == "manifest" else m, value if which == "corr" else c
        )


@pytest.mark.parametrize("field", [field.name for field in fields(ProfileLimits)])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None, "raised"])
def test_limit_records_reject_invalid_values_before_parsing(
    field: str, value: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value == "raised":
        value = getattr(DEFAULT_LIMITS, field) + 1
    limits = replace(DEFAULT_LIMITS, **{field: value})
    scanner = Mock(side_effect=AssertionError("Parsing started."))
    monkeypatch.setattr(module, "_scan_json", scanner)
    with pytest.raises(ProfileError):
        parse_profile_v2(b"", b"", limits)
    scanner.assert_not_called()


@pytest.mark.parametrize("limits", [None, {}, (), 1])
def test_wrong_limit_record(limits: Any) -> None:
    with pytest.raises(ProfileError):
        parse_profile_v2(b"", b"", limits)


def edge_count(manifest: Document, corr: Document) -> int:
    def count(value: object) -> int:
        if isinstance(value, dict):
            return sum(
                (1 if key in ("path", "origin_entry") else 2 if key == "anchor" else 0)
                + count(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return sum(count(item) for item in value)
        return 0

    return (
        count(manifest)
        + count(corr)
        + sum(
            len(row["shared_type_ids"]) for row in corr["functions"] + corr["globals"]
        )
        + sum(len(row["users"]) for row in corr["shared_types"])
    )


def span_count(corr: Document) -> int:
    return (
        3 * len(corr["functions"])
        + sum(1 + len(row["declarations"]) for row in corr["globals"])
        + sum(
            (row["definition"] is not None) + len(row["declarations"])
            for row in corr["shared_types"]
        )
    )


def fixture_limits() -> dict[str, int]:
    manifest, corr = documents()
    m, c = wire(manifest, corr)
    return {
        "max_sources": 3,
        "max_headers": 2,
        "max_total_source_bytes": 2500 + len(GOLDEN_CMAKE),
        "max_cmake_bytes": len(GOLDEN_CMAKE),
        "max_manifest_bytes": len(m),
        "max_correspondence_bytes": len(c),
        "max_path_bytes": len("include/types.h"),
        "max_nesting": 5,
        "max_integer_digits": 4,
        "max_functions": 3,
        "max_globals": 1,
        "max_shared_types": 2,
        "max_spans": span_count(corr),
        "max_identifier_bytes": len("right_value"),
        "max_anchor_id_bytes": len("type:right_value"),
        "max_reference_edges": edge_count(manifest, corr),
    }


@pytest.mark.parametrize("field,bound", list(fixture_limits().items()))
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_inclusive_caller_limits(field: str, bound: int, delta: int) -> None:
    limits = replace(DEFAULT_LIMITS, **{field: bound + delta})
    if delta == -1:
        with pytest.raises(ProfileError) as caught:
            parse(*documents(), limits)
        assert caught.value.category == "profile_limit"
    else:
        assert parse(*documents(), limits).manifest.schema == 2


@pytest.mark.parametrize(
    "resource",
    [
        "sources",
        "headers",
        "functions",
        "globals",
        "shared_types",
        "spans",
        "edges",
        "manifest",
        "corr",
        "string",
        "digits",
        "nesting",
    ],
)
def test_count_limits_precede_tree_record_hash_and_render_work(
    resource: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, corr = documents()
    bounds = fixture_limits()
    mapping = {
        "sources": "max_sources",
        "headers": "max_headers",
        "functions": "max_functions",
        "globals": "max_globals",
        "shared_types": "max_shared_types",
        "spans": "max_spans",
        "edges": "max_reference_edges",
        "manifest": "max_manifest_bytes",
        "corr": "max_correspondence_bytes",
        "digits": "max_integer_digits",
        "nesting": "max_nesting",
    }
    limits = (
        DEFAULT_LIMITS
        if resource == "string"
        else replace(
            DEFAULT_LIMITS, **{mapping[resource]: max(1, bounds[mapping[resource]] - 1)}
        )
    )
    if resource == "globals":
        corr["globals"].append(copy.deepcopy(corr["globals"][0]))
    m, c = wire(manifest, corr)
    if resource == "string":
        m = b'{"x":"' + b"x" * 129 + b'"}\n'
    decoder = Mock(side_effect=AssertionError("Tree allocation started."))
    monkeypatch.setattr(json, "loads", decoder)
    monkeypatch.setattr(
        module, "sha256", Mock(side_effect=AssertionError("Hashing started."))
    )
    monkeypatch.setattr(
        module, "_cmake", Mock(side_effect=AssertionError("Rendering started."))
    )
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(m, c, limits)
    assert caught.value.category == "profile_limit"
    decoder.assert_not_called()


@pytest.mark.parametrize("field", ["max_total_source_bytes", "max_cmake_bytes"])
def test_size_sums_precede_hashing_and_rendering(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, c = wire(*documents())
    limits = replace(DEFAULT_LIMITS, **{field: fixture_limits()[field] - 1})
    hashing = Mock(side_effect=AssertionError("Hashing started."))
    rendering = Mock(side_effect=AssertionError("Rendering started."))
    monkeypatch.setattr(module, "sha256", hashing)
    monkeypatch.setattr(module, "_cmake", rendering)
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(m, c, limits)
    assert caught.value.category == "profile_limit"
    hashing.assert_not_called()
    rendering.assert_not_called()


def test_empty_header_and_positive_source_bounds() -> None:
    manifest, corr = documents()
    manifest["headers"].append(
        {"path": "include/unused.h", "size": 0, "sha256": sha256(b"").hexdigest()}
    )
    corr["declaration_version_sha256"] = sha256(
        b"phoenix-declarations-v1\0" + canonical(manifest["headers"])
    ).hexdigest()
    assert parse(manifest, corr).manifest.headers[-1].size == 0
    manifest["sources"][0]["size"] = 0
    rejected(manifest, corr, "profile_limit")


@pytest.mark.parametrize(
    "supplied",
    [
        b"",
        GOLDEN_CMAKE + b"\n",
        GOLDEN_CMAKE.replace(b"-O2", b"-O0"),
        GOLDEN_CMAKE + b"add_custom_target(x)\n",
        b"x" * 16385,
        bytearray(GOLDEN_CMAKE),
    ],
)
def test_supplied_cmake_must_match_exactly(supplied: Any) -> None:
    with pytest.raises(ProfileError):
        validate_cmake_v2(parse(*documents()), supplied)


@pytest.mark.parametrize("field", [field.name for field in fields(ParsedProjectV2)])
def test_direct_top_level_construction_cannot_override_raw_bytes(field: str) -> None:
    profile = parse(*documents())
    changes: dict[str, Any] = {field: None}
    forged = replace(profile, **changes)
    with pytest.raises(ProfileError):
        render_cmake_v2(forged)


@pytest.mark.parametrize(
    "path",
    [
        "src/x.c)\nexecute_process(COMMAND x)",
        "../x.c",
        "src/X.c",
        "src/a.c\x00",
        "src/é.c",
    ],
)
def test_direct_record_path_injection(path: str) -> None:
    profile = parse(*documents())
    source = replace(profile.manifest.sources[0], path=path)
    manifest = replace(
        profile.manifest, sources=(source, *profile.manifest.sources[1:])
    )
    with pytest.raises(ProfileError):
        render_cmake_v2(replace(profile, manifest=manifest))


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "profile",
        "build_profile",
        "original_sha256",
        "origin_sha256",
        "sources",
        "headers",
        "correspondence",
        "cmake_sha256",
    ],
)
def test_all_direct_manifest_changes_are_checked(field: str) -> None:
    profile = parse(*documents())
    changes: dict[str, Any] = {field: []}
    changed = replace(profile.manifest, **changes)
    with pytest.raises(ProfileError):
        render_cmake_v2(replace(profile, manifest=changed))


def test_nested_mutation_and_subclasses_grant_no_authority() -> None:
    profile = parse(*documents())
    object.__setattr__(
        profile.correspondence.functions[0].body, "path", "src/x.c)\nmessage(x)"
    )
    with pytest.raises(ProfileError):
        render_cmake_v2(profile)

    class Derived(ParsedProjectV2):
        pass

    valid = parse(*documents())
    with pytest.raises(ProfileError):
        render_cmake_v2(
            Derived(
                valid.manifest,
                valid.correspondence,
                valid.canonical_manifest,
                valid.canonical_correspondence,
            )
        )


@pytest.mark.parametrize("failure", [TypeError, ValueError, RuntimeError, OSError])
def test_hash_programming_errors_remain_visible(
    failure: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    m, c = wire(*documents())
    monkeypatch.setattr(
        module, "sha256", Mock(side_effect=failure("Synthetic hash fault."))
    )
    with pytest.raises(failure, match="Synthetic hash fault") as caught:
        parse_profile_v2(m, c)
    assert not isinstance(caught.value, ProfileError)


def test_json_programming_errors_remain_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m, c = wire(*documents())
    monkeypatch.setattr(
        json, "loads", Mock(side_effect=RuntimeError("Synthetic decoder fault."))
    )
    with pytest.raises(RuntimeError, match="decoder fault"):
        parse_profile_v2(m, c)


def test_no_phoenix_import_or_operating_boundary() -> None:
    tree = ast.parse(Path(module.__file__).read_bytes())
    imported = {
        item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)
    } | {
        alias.name
        for item in ast.walk(tree)
        if isinstance(item, ast.Import)
        for alias in item.names
    }
    assert imported == {"__future__", "json", "re", "dataclasses", "hashlib", "typing"}
    called = {
        item.func.id
        for item in ast.walk(tree)
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
    }
    assert not called & {"open", "exec", "eval", "__import__", "compile"}


def test_consistency_does_not_claim_source_semantics_or_origin_authority() -> None:
    manifest, corr = documents()
    corr["functions"][0]["signature"]["sha256"] = "0" * 64
    corr["functions"][0]["body"]["start"] = 25
    profile = parse(manifest, corr)
    assert profile.correspondence.functions[0].body.start == 25
    assert profile.manifest.original_sha256 == ORIGINAL
    # The parser receives no C bytes or trusted original-function inventory.
    assert not hasattr(profile, "approved")
    assert not hasattr(profile, "integrity_passed")
    corr["shared_types"][0]["users"] = []
    parse(manifest, corr)


@given(st.binary(max_size=1500), st.booleans())
@settings(max_examples=100, deadline=None)
def test_arbitrary_malformed_wire_is_controlled(
    raw: bytes, manifest_side: bool
) -> None:
    m, c = wire(*documents())
    try:
        result = parse_profile_v2(
            raw if manifest_side else m, c if manifest_side else raw
        )
    except ProfileError as error:
        assert len(error.detail) <= 160
    else:
        assert result.canonical_manifest == (raw if manifest_side else m)


@given(
    st.integers(min_value=0, max_value=2**64 - 1),
    st.integers(min_value=1, max_value=500),
)
@settings(max_examples=70, deadline=None)
def test_canonical_round_trip_with_independent_expected_fields(
    entry: int, start: int
) -> None:
    manifest, corr = documents()
    corr["functions"][0]["origin_entry"] = hex(entry)
    if entry in (0x10, 2**64 - 1):
        return
    corr["functions"].sort(key=lambda row: int(row["origin_entry"], 16))
    corr["globals"][0]["definition"] = span("src/step.c", start - 1, start)
    m, c = wire(manifest, corr)
    result = parse_profile_v2(m, c)
    assert result.manifest.original_sha256 == ORIGINAL
    assert {row.origin_entry for row in result.correspondence.functions} == {
        hex(entry),
        "0x10",
        "0xffffffffffffffff",
    }
    assert result.correspondence.globals[0].definition == Span(
        "src/step.c", start - 1, start, SPAN_HASH
    )
    assert canonical(json.loads(m)) == m
    assert canonical(json.loads(c)) == c
    assert (
        parse_profile_v2(result.canonical_manifest, result.canonical_correspondence)
        == result
    )


@given(st.permutations((0, 1, 2)))
def test_source_and_function_permutations_are_rejected(order: tuple[int, ...]) -> None:
    order = tuple(order)
    manifest, corr = documents()
    manifest["sources"] = [manifest["sources"][index] for index in order]
    if order == (0, 1, 2):
        parse(manifest, corr)
    else:
        rejected(manifest, corr, "profile_roster")
    manifest, corr = documents()
    corr["functions"] = [corr["functions"][index] for index in order]
    if order == (0, 1, 2):
        parse(manifest, corr)
    else:
        rejected(manifest, corr, "profile_origin")


@given(
    st.one_of(
        st.text(
            alphabet=st.characters(min_codepoint=0, max_codepoint=255), max_size=70
        ),
        st.from_regex(r"src/[a-z][a-z0-9_]{0,47}\.c", fullmatch=True),
    )
)
@settings(max_examples=100, deadline=None)
def test_path_safety_has_an_independent_grammar_oracle(path: str) -> None:
    import re

    manifest, corr = documents()
    manifest["sources"].append({"path": path, "size": 1, "sha256": "e" * 64})
    manifest["sources"].sort(key=lambda row: row["path"])
    if not re.fullmatch(r"src/[a-z][a-z0-9_]{0,47}\.c", path):
        rejected(manifest, corr)
    elif sum(row["path"] == path for row in manifest["sources"]) != 1:
        rejected(manifest, corr, "profile_roster")
    else:
        old_stanza = b"    src/main.c\n    src/step.c\n    src/total.c\n"
        new_stanza = b"".join(
            b"    " + row["path"].encode("ascii") + b"\n" for row in manifest["sources"]
        )
        golden = GOLDEN_CMAKE.replace(old_stanza, new_stanza)
        manifest["cmake_sha256"] = sha256(golden).hexdigest()
        profile = parse(manifest, corr)
        assert path in {row.path for row in profile.manifest.sources}
        assert render_cmake_v2(profile) == golden


def single_source() -> tuple[Document, Document, bytes]:
    manifest, corr = documents()
    manifest["sources"] = manifest["sources"][:1]
    manifest["headers"] = []
    corr["functions"] = corr["functions"][:1]
    corr["functions"][0]["shared_type_ids"] = []
    corr["functions"][0]["origin_entry"] = "0x0"
    corr["globals"] = []
    corr["shared_types"] = []
    corr["declaration_version_sha256"] = sha256(
        b"phoenix-declarations-v1\0" + canonical([])
    ).hexdigest()
    golden = GOLDEN_CMAKE.replace(b"    src/step.c\n    src/total.c\n", b"")
    manifest["cmake_sha256"] = sha256(golden).hexdigest()
    return manifest, corr, golden


def test_one_source_no_headers_no_globals_no_shared_types_and_zero_entry() -> None:
    manifest, corr, golden = single_source()
    profile = parse(manifest, corr)
    assert profile.manifest.headers == ()
    assert profile.correspondence.globals == ()
    assert profile.correspondence.shared_types == ()
    assert profile.correspondence.functions[0].origin_entry == "0x0"
    assert render_cmake_v2(profile) == golden
    assert validate_cmake_v2(profile, golden) == golden
    manifest["sources"] = []
    rejected(manifest, corr, "profile_limit")


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_actual_total_byte_cap(delta: int) -> None:
    manifest, corr, golden = single_source()
    manifest["sources"][0]["size"] = 4_194_304 - len(golden) + delta
    if delta <= 0:
        assert (
            parse(manifest, corr).manifest.sources[0].size + len(golden)
            == 4_194_304 + delta
        )
    else:
        rejected(manifest, corr, "profile_limit")


@pytest.mark.parametrize("kind", ["sources", "headers"])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_actual_file_count_caps(kind: str, delta: int) -> None:
    manifest, corr, _ = single_source()
    maximum = 64 if kind == "sources" else 128
    count = maximum + delta
    if kind == "sources":
        paths = [f"src/a{index:03}.c" for index in range(count)]
        manifest["sources"] = [
            {"path": path, "size": 500, "sha256": "e" * 64} for path in paths
        ]
        for field in ("definition", "signature", "body"):
            corr["functions"][0][field]["path"] = paths[0]
        golden = GOLDEN_CMAKE.replace(
            b"    src/main.c\n    src/step.c\n    src/total.c\n",
            b"".join(b"    " + path.encode() + b"\n" for path in paths),
        )
        manifest["cmake_sha256"] = sha256(golden).hexdigest()
    else:
        manifest["headers"] = [
            {
                "path": f"include/a{index:03}.h",
                "size": 0,
                "sha256": sha256(b"").hexdigest(),
            }
            for index in range(count)
        ]
        corr["declaration_version_sha256"] = sha256(
            b"phoenix-declarations-v1\0" + canonical(manifest["headers"])
        ).hexdigest()
    if delta <= 0:
        assert len(getattr(parse(manifest, corr).manifest, kind)) == count
    else:
        rejected(manifest, corr, "profile_limit")


@pytest.mark.parametrize("which", ["manifest", "corr"])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_actual_raw_byte_caps_before_tree_allocation(
    which: str, delta: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, c = wire(*documents())
    maximum = 262_144 if which == "manifest" else 1_048_576
    raw = b" " * (maximum + delta - 1) + b"\n"
    decoder = Mock(side_effect=AssertionError("Tree allocation started."))
    monkeypatch.setattr(json, "loads", decoder)
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(
            raw if which == "manifest" else m, c if which == "manifest" else raw
        )
    assert caught.value.category == (
        "profile_limit" if delta > 0 else "profile_noncanonical"
    )
    decoder.assert_not_called()


@pytest.mark.parametrize(
    "resource,maximum",
    [
        ("functions", 8192),
        ("globals", 8192),
        ("shared_types", 4096),
        ("declarations", 32768),
        ("unknown", 65536),
    ],
)
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_raw_array_count_caps_without_large_record_allocation(
    resource: str, maximum: int, delta: int
) -> None:
    m, c = wire(*documents())
    count = maximum + delta
    raw = b'{"' + resource.encode() + b'":[' + b",".join([b"null"] * count) + b"]}\n"
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(raw, c)
    assert caught.value.category == (
        "profile_limit" if delta > 0 or len(raw) > 262144 else "profile_fields"
    )
    assert m.endswith(b"\n")


@pytest.mark.parametrize("depth", [15, 16, 17])
def test_raw_container_depth_inclusive(depth: int) -> None:
    _, c = wire(*documents())
    raw = b"[" * depth + b"0" + b"]" * depth + b"\n"
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(raw, c)
    assert caught.value.category == ("profile_limit" if depth > 16 else "profile_type")


@pytest.mark.parametrize("digits", [19, 20, 21])
def test_decimal_token_cap_inclusive(digits: int) -> None:
    _, c = wire(*documents())
    raw = b'{"schema":' + b"9" * digits + b"}\n"
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(raw, c)
    assert caught.value.category == (
        "profile_limit" if digits > 20 else "profile_fields"
    )


@pytest.mark.parametrize("length", [127, 128, 129])
@pytest.mark.parametrize("field", ["c_name", "record_id"])
def test_identifier_and_anchor_actual_caps(field: str, length: int) -> None:
    manifest, corr = documents()
    if field == "c_name":
        corr["functions"][1][field] = "_" + "a" * (length - 1)
    else:
        row = corr["globals"][0]
        row["anchor"][field] = "a" * length
        row["id"] = identity("phoenix-global-id-v1", row["anchor"])
    if length <= 128:
        assert parse(manifest, corr).manifest.schema == 2
    else:
        rejected(manifest, corr, "profile_limit")


@pytest.mark.parametrize("length", [47, 48, 49])
@pytest.mark.parametrize("header", [False, True])
def test_actual_path_component_and_path_byte_caps(length: int, header: bool) -> None:
    manifest, corr, golden = single_source()
    stem = "a" * length
    if header:
        manifest["headers"] = [
            {"path": f"include/{stem}.h", "size": 0, "sha256": sha256(b"").hexdigest()}
        ]
        corr["declaration_version_sha256"] = sha256(
            b"phoenix-declarations-v1\0" + canonical(manifest["headers"])
        ).hexdigest()
    else:
        path = f"src/{stem}.c"
        manifest["sources"][0]["path"] = path
        for field in ("definition", "signature", "body"):
            corr["functions"][0][field]["path"] = path
        golden = golden.replace(b"src/main.c", path.encode())
        manifest["cmake_sha256"] = sha256(golden).hexdigest()
    if length <= 48:
        parse(manifest, corr)
    else:
        rejected(manifest, corr)


@pytest.mark.parametrize(
    "field",
    ["schema", "profile", "build_profile", "address_space", "claim", "kind", "linkage"],
)
def test_fixed_literals(field: str) -> None:
    manifest, corr = documents()
    if field in ("schema", "profile", "build_profile"):
        manifest[field] = 3 if field == "schema" else "unsupported"
    elif field == "address_space":
        corr[field] = "elf"
    elif field in ("claim", "kind"):
        corr["shared_types"][0][field] = "approved"
    else:
        corr["functions"][0][field] = "public"
    rejected(manifest, corr)


@pytest.mark.parametrize("change", ["size", "hash", "cmake"])
def test_exact_byte_binding_conflicts(change: str) -> None:
    m, c = wire(*documents())
    manifest = json.loads(m)
    if change == "size":
        manifest["correspondence"]["size"] += 1
    elif change == "hash":
        manifest["correspondence"]["sha256"] = "0" * 64
    else:
        manifest["cmake_sha256"] = "0" * 64
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(canonical(manifest), c)
    assert caught.value.category == (
        "profile_cmake" if change == "cmake" else "profile_digest"
    )


def test_two_declaration_spans_sort_by_all_fields() -> None:
    manifest, corr = documents()
    row = corr["shared_types"][0]
    original = row["declarations"][0]
    later = span(original["path"], original["end"] + 10, original["end"] + 20)
    row["declarations"].append(later)
    parsed = parse(manifest, corr)
    assert len(parsed.correspondence.shared_types[0].declarations) == 2
    row["declarations"].reverse()
    rejected(manifest, corr, "profile_correspondence")


@pytest.mark.parametrize(
    "field", ["headers", "shared_types", "shared_type_ids", "users"]
)
def test_required_string_array_order(field: str) -> None:
    manifest, corr = documents()
    if field == "headers":
        rows = manifest[field]
    elif field == "shared_type_ids":
        rows = corr["functions"][0][field]
    elif field == "users":
        rows = corr["shared_types"][0][field]
    else:
        rows = corr[field]
    rows.reverse()
    rejected(manifest, corr)


def test_default_limits_cannot_be_raised_with_a_subclass() -> None:
    class Derived(ProfileLimits):
        pass

    with pytest.raises(ProfileError):
        parse_profile_v2(b"", b"", Derived())


def test_uninitialized_direct_record_is_controlled() -> None:
    with pytest.raises(ProfileError):
        render_cmake_v2(object.__new__(ParsedProjectV2))


@pytest.mark.parametrize("index", range(6))
def test_each_hash_boundary_preserves_programming_error(
    index: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, c = wire(*documents())
    count = 0

    def hashing(data: bytes) -> Any:
        nonlocal count
        if count == index:
            raise ValueError("Synthetic hash boundary fault.")
        count += 1
        return sha256(data)

    monkeypatch.setattr(module, "sha256", hashing)
    with pytest.raises(ValueError, match="Synthetic hash boundary fault") as caught:
        parse_profile_v2(m, c)
    assert not isinstance(caught.value, ProfileError)


json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(10**25), max_value=10**25)
    | st.text(max_size=150)
)
json_values = st.recursive(
    json_scalars,
    lambda child: (
        st.lists(child, max_size=10)
        | st.dictionaries(st.text(max_size=20), child, max_size=10)
    ),
    max_leaves=30,
)


@given(json_values)
@settings(max_examples=100, deadline=None)
def test_structured_arbitrary_json_has_controlled_failures(value: Any) -> None:
    _, c = wire(*documents())
    with pytest.raises(ProfileError):
        parse_profile_v2(canonical(value), c)


@pytest.mark.parametrize(
    "field", ["max_identifier_bytes", "max_anchor_id_bytes", "max_path_bytes"]
)
def test_string_reductions_precede_json_tree(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    m, c = wire(*documents())
    limits = replace(DEFAULT_LIMITS, **{field: fixture_limits()[field] - 1})
    decoder = Mock(side_effect=AssertionError("Tree allocation started."))
    monkeypatch.setattr(json, "loads", decoder)
    with pytest.raises(ProfileError) as caught:
        parse_profile_v2(m, c, limits)
    assert caught.value.category == "profile_limit"
    decoder.assert_not_called()


def test_fixed_correspondence_path_does_not_use_source_path_limit() -> None:
    manifest, corr, golden = single_source()
    manifest["sources"][0]["path"] = "src/a.c"
    for field in ("definition", "signature", "body"):
        corr["functions"][0][field]["path"] = "src/a.c"
    golden = golden.replace(b"src/main.c", b"src/a.c")
    manifest["cmake_sha256"] = sha256(golden).hexdigest()
    profile = parse(manifest, corr, replace(DEFAULT_LIMITS, max_path_bytes=7))
    assert profile.manifest.correspondence.path == "phoenix_correspondence.json"
    assert render_cmake_v2(profile) == golden


def test_v2_template_matches_inspected_legacy_bytes_and_is_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phoenix_eval import build

    single_line = b"add_executable(program src/program.c)\n"
    multi_line = (
        b"add_executable(program\n    src/main.c\n    src/step.c\n    src/total.c\n)\n"
    )
    assert build.PROJECT_CMAKE.encode("ascii") == GOLDEN_CMAKE.replace(
        multi_line, single_line
    )
    profile = parse(*documents())
    monkeypatch.setattr(build, "PROJECT_CMAKE", "execute_process(COMMAND invalid)\n")
    assert render_cmake_v2(profile) == GOLDEN_CMAKE


def test_nominal_types_with_identical_fields_keep_distinct_complete_anchors() -> None:
    manifest, corr = documents()
    left = b"struct left_value { unsigned long value; };"
    right = b"struct right_value { unsigned long value; };"
    assert left[left.index(b"{") :] == right[right.index(b"{") :]
    header = left + b"\n" + right + b"\n"
    header_row = manifest["headers"][1]
    header_row["size"] = len(header)
    header_row["sha256"] = sha256(header).hexdigest()
    for row in corr["shared_types"]:
        declaration = left if row["c_name"] == "left_value" else right
        start = header.index(declaration)
        bound = {
            "path": "include/types.h",
            "start": start,
            "end": start + len(declaration),
            "sha256": sha256(declaration).hexdigest(),
        }
        row["definition"] = copy.deepcopy(bound)
        row["declarations"] = [bound]
    corr["declaration_version_sha256"] = sha256(
        b"phoenix-declarations-v1\0" + canonical(manifest["headers"])
    ).hexdigest()
    profile = parse(manifest, corr)
    actual = profile.correspondence.shared_types
    assert actual[0].anchor != actual[1].anchor
    assert actual[0].id != actual[1].id
    assert {row.anchor.record_id for row in actual} == {
        "type:left_value",
        "type:right_value",
    }
    assert all(row.anchor.artifact_sha256 == ARTIFACT for row in actual)
    assert json.loads(json.dumps(asdict(profile.correspondence))) == corr


def test_multiple_globals_sort_by_nominal_id() -> None:
    manifest, corr = documents()
    second = copy.deepcopy(corr["globals"][0])
    second["anchor"]["record_id"] = "global:other"
    second["id"] = identity("phoenix-global-id-v1", second["anchor"])
    second["c_name"] = "other"
    second["definition"] = span("src/total.c", 150, 180)
    corr["globals"].append(second)
    corr["globals"].sort(key=lambda row: row["id"])
    assert tuple(
        row.id for row in parse(manifest, corr).correspondence.globals
    ) == tuple(row["id"] for row in corr["globals"])
    corr["globals"].reverse()
    rejected(manifest, corr, "profile_shared_identity")


def test_independent_direct_construction_can_render_only_consistent_bytes() -> None:
    parsed = parse(*documents())
    direct = ParsedProjectV2(
        replace(parsed.manifest),
        replace(parsed.correspondence),
        bytes(bytearray(parsed.canonical_manifest)),
        bytes(bytearray(parsed.canonical_correspondence)),
    )
    assert direct is not parsed
    assert render_cmake_v2(direct) == GOLDEN_CMAKE
    assert not hasattr(direct, "integrity_passed")


@pytest.mark.parametrize(
    "field,category,phase",
    [
        ("path", "profile_path", "roster"),
        ("address_space", "profile_origin", "correspondence"),
        ("claim", "profile_shared_identity", "correspondence"),
        ("span", "profile_correspondence", "correspondence"),
    ],
)
def test_failures_identify_the_actual_consistency_boundary(
    field: str, category: str, phase: str
) -> None:
    manifest, corr = documents()
    if field == "path":
        manifest["correspondence"]["path"] = "other.json"
    elif field == "address_space":
        corr[field] = "elf"
    elif field == "claim":
        corr["shared_types"][0]["claim"] = "approved"
    else:
        corr["functions"][0]["body"]["end"] = 501
    error = rejected(manifest, corr, category)
    assert error.phase == phase


def test_uninitialized_limit_record_is_controlled_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = object.__new__(ProfileLimits)
    scanner = Mock(side_effect=AssertionError("Parsing started."))
    monkeypatch.setattr(module, "_scan_json", scanner)
    with pytest.raises(ProfileError):
        parse_profile_v2(b"", b"", limits)
    scanner.assert_not_called()


def test_deleted_null_field_in_direct_record_is_rejected() -> None:
    manifest, corr = documents()
    corr["shared_types"][0]["definition"] = None
    profile = parse(manifest, corr)
    object.__delattr__(profile.correspondence.shared_types[0], "definition")
    with pytest.raises(ProfileError):
        render_cmake_v2(profile)
