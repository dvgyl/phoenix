import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval import integrity
from phoenix_eval.elf import Section
from phoenix_eval.integrity import (
    Call,
    CompilerEvidence,
    FunctionShape,
    IntegrityError,
    Storage,
    check_integrity,
    compiler_evidence,
    inspect_project,
)

TARGETS = ("x86_64-linux-gnu", "aarch64-linux-gnu")
ARTIFACT = "src/program.c"
SOURCE = {ARTIFACT: b"int main(void) { return 0; }"}
TEXT = bytes(range(128, 192))
TEST_OUTPUT = b"This text appears only in a development outcome."
ORIGIN = (FunctionShape("main", 0, 0, 0),)


@pytest.fixture(autouse=True)
def original_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        integrity,
        "elf_sections",
        lambda *_: {".text": Section(0, TEXT), ".rodata": Section(0, b"sample\0")},
    )


def _evidence(
    storage: tuple[Storage, ...] = (),
    calls: tuple[Call, ...] = (),
    functions: tuple[FunctionShape, ...] = ORIGIN,
) -> tuple[CompilerEvidence, ...]:
    return tuple(
        CompilerEvidence(target, "18.1.3", storage, calls, functions)
        for target in TARGETS
    )


def test_scans_all_four_builds_and_source_storage_for_exact_text() -> None:
    stored = Storage("storage", ARTIFACT, 0, b"!" + TEXT, "unsigned char[65]")
    report = check_integrity(
        b"",
        SOURCE,
        (b"prefix" + TEXT, b"", b"", b""),
        _evidence((stored,)),
        frozenset(),
        ORIGIN,
    )
    assert not report.passed
    assert report.categories["embedded_text"] == 3
    assert report.checked_executables == 4
    assert report.checked_storage_records == 2


def test_typed_wide_elements_are_not_decoded_as_single_bytes() -> None:
    payload = b"".join(number.to_bytes(4, "little") for number in TEXT)
    stored = Storage("storage", ARTIFACT, 0, payload, "unsigned int[64]")
    report = check_integrity(
        b"", SOURCE, (b"",) * 4, _evidence((stored,)), frozenset(), ORIGIN
    )
    assert "embedded_text" not in report.categories
    assert report.categories == {"unproven_constant_table": 2}


def test_checks_literal_payload_and_object_size_separately() -> None:
    records = (
        Storage("literal", ARTIFACT, 0, TEST_OUTPUT, ""),
        Storage("storage", ARTIFACT, 0, b"A" + bytes(4999), "char[5000]"),
        Storage("storage", ARTIFACT, 0, bytes(5000), "char[5000]"),
    )
    report = check_integrity(
        b"", SOURCE, (b"",) * 4, _evidence(records), frozenset((TEST_OUTPUT,)), ORIGIN
    )
    assert report.categories == {
        "memorized_output": 2,
        "unproven_literal": 2,
        "unproven_constant_table": 2,
        "unjustified_blob": 2,
    }
    assert len(report.justifications) == 2
    assert all(item.size == 5000 for item in report.justifications)


def test_incomplete_evidence_and_unapproved_calls_cannot_pass() -> None:
    calls = (
        Call("indirect", ""),
        Call("external_linkage", "dlopen"),
        Call("project", "helper"),
    )
    report = check_integrity(
        b"", SOURCE, (b"",), _evidence(calls=calls)[:1], frozenset(), ORIGIN
    )
    assert report.categories == {
        "missing_build": 1,
        "incomplete_source_check": 1,
        "unresolved_call": 1,
        "unapproved_call": 1,
    }


def test_checks_short_tables_and_the_newline_added_by_puts() -> None:
    literal = TEST_OUTPUT
    output = literal + b"\n"
    records = (
        Storage("literal", ARTIFACT, 0, literal, ""),
        Storage("constant_output", ARTIFACT, 0, output, "", literal),
        Storage("storage", ARTIFACT, 0, b"ab", "char[2]"),
    )
    report = check_integrity(
        b"", SOURCE, (b"",) * 4, _evidence(records), frozenset((output,)), ORIGIN
    )
    assert report.categories == {
        "memorized_output": 2,
        "unproven_literal": 2,
        "unproven_constant_table": 2,
    }


def test_preserves_output_provenance_when_the_library_adds_a_newline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        integrity,
        "elf_sections",
        lambda *_: {
            ".text": Section(0, TEXT),
            ".rodata": Section(0, TEST_OUTPUT + b"\0"),
        },
    )
    output = TEST_OUTPUT + b"\n"
    record = Storage("constant_output", ARTIFACT, 0, output, "", TEST_OUTPUT)
    report = check_integrity(
        b"", SOURCE, (b"",) * 4, _evidence((record,)), frozenset({output}), ORIGIN
    )
    assert report.passed


def test_rejects_added_control_flow_and_split_unproven_output() -> None:
    records = (
        Storage("literal", ARTIFACT, 0, b"first new chunk", ""),
        Storage("literal", ARTIFACT, 0, b"second new chunk", ""),
    )
    evidence = _evidence(records, functions=(FunctionShape("main", 0, 1, 1),))
    report = check_integrity(b"", SOURCE, (b"",) * 4, evidence, frozenset(), ORIGIN)
    assert report.categories == {
        "unproven_control_flow": 2,
        "unproven_literal": 4,
    }


def _document(target: str = TARGETS[0]) -> dict[str, object]:
    return {
        "schema": 1,
        "policy": "m1-v1",
        "status": "complete",
        "target": target,
        "translation_unit": ARTIFACT,
        "clang_version": "Ubuntu clang version 18.1.3",
        "record_count": 1,
        "records": [
            {"kind": "literal", "file": ARTIFACT, "offset": 0, "bytes_hex": "61"}
        ],
        "calls": [{"kind": "builtin", "name": "puts"}],
        "functions": [{"name": "main", "branches": 0, "loops": 0, "switches": 0}],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("status", "unchecked"),
        ("record_count", 2),
        ("target", "unknown"),
        ("calls", [None]),
    ),
)
def test_rejects_invalid_checker_results(field: str, value: object) -> None:
    document = {**_document(), field: value}
    with pytest.raises(IntegrityError):
        compiler_evidence(json.dumps(document).encode(), TARGETS[0], ARTIFACT, SOURCE)


def test_requires_both_target_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / ARTIFACT).write_bytes(SOURCE[ARTIFACT])
    (tmp_path / "CMakeLists.txt").touch()
    images = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
    runner = Mock(
        side_effect=[
            subprocess.CompletedProcess(
                (), 0, json.dumps(_document(target)).encode(), b""
            )
            for target in TARGETS
        ]
    )
    monkeypatch.setattr(subprocess, "run", runner)
    result = inspect_project(tmp_path, images)
    assert tuple(item.target for item in result) == TARGETS
    assert all(item.storage[0].data == b"a" for item in result)
    assert check_integrity(b"", SOURCE, (b"",) * 4, result, frozenset(), ORIGIN).passed
