import json
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix_eval import m1
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Variant
from phoenix_eval.model_ledger import freeze_identity, ledger_digest, read_identity
from phoenix_eval.submission import Submission
from phoenix_eval.toolchain import Compiler


@pytest.fixture
def synthetic_evaluator(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    events: list[str] = []
    variant = Variant("synthetic", Compiler.GCC, "-O0", "a" * 64, "fixture")
    monkeypatch.setattr(m1, "t0_manifest", lambda _: ((variant,), "b" * 64))
    monkeypatch.setattr(
        m1, "_configuration", lambda *_: {"heldout_archive_sha256": "c" * 64}
    )
    monkeypatch.setattr(m1, "_release_bytes", lambda *_: b"synthetic")

    def submit(*args: object) -> Submission:
        events.append("submit")
        return Submission("phoenix", "synthetic", None, "pipeline-failed")

    def cases(
        path: Path, digest: str, names: set[str]
    ) -> dict[str, tuple[Invocation, ...]]:
        root = path.parents[1]
        evaluations = [
            directory
            for directory in (root / "runs").iterdir()
            if not directory.name.endswith("-rebuild")
        ]
        assert evaluations
        for directory in evaluations:
            assert read_identity(directory / "model-ledger.json")["schema"] == 1
        events.append("cases")
        return {"synthetic": ()}

    monkeypatch.setattr(m1, "submit", submit)
    monkeypatch.setattr(m1, "heldout_cases", cases)
    monkeypatch.setattr(
        m1, "_measure", lambda *_: {"method": "phoenix", "fully_successful": False}
    )
    return events


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("replay", [False, True])
def test_changed_ledger_stops_resume_or_replay_before_submission(
    tmp_path: Path, synthetic_evaluator: list[str], present: bool, replay: bool
) -> None:
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    ledger.parent.mkdir(parents=True)
    if present:
        ledger.write_bytes(b"synthetic ledger\n")
    m1.evaluate_t0(tmp_path, "origin")
    synthetic_evaluator.clear()
    ledger.write_bytes(b"changed synthetic ledger\n")
    with pytest.raises(ValueError, match="model ledger changed"):
        m1.evaluate_t0(
            tmp_path, "replay" if replay else "origin", "origin" if replay else None
        )
    assert synthetic_evaluator == []


@pytest.mark.parametrize("present", [False, True])
def test_replay_preserves_origin_identity_and_creates_no_ledger(
    tmp_path: Path, synthetic_evaluator: list[str], present: bool
) -> None:
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    ledger.parent.mkdir(parents=True)
    if present:
        ledger.write_bytes(b"synthetic ledger\n")
    original, _ = m1.evaluate_t0(tmp_path, "origin")
    identity = json.loads(original.read_text())["model_ledger"]
    assert identity == {
        "schema": 1,
        "pipeline_run": "origin-rebuild",
        "sha256": sha256(b"synthetic ledger\n").hexdigest() if present else None,
    }
    assert read_identity(original.parent / "model-ledger.json") == identity
    replay, _ = m1.evaluate_t0(tmp_path, "replay", "origin")
    assert (
        json.loads(replay.read_text())["model_ledger"]
        == json.loads(original.read_text())["model_ledger"]
    )
    assert not (tmp_path / "runs/replay-rebuild/llm.jsonl").exists()


@pytest.mark.parametrize("phase", ["submit", "cases", "measure"])
def test_replay_rejects_fresh_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_evaluator: list[str],
    phase: str,
) -> None:
    m1.evaluate_t0(tmp_path, "origin")
    name = {"submit": "submit", "cases": "heldout_cases", "measure": "_measure"}[phase]
    original = getattr(m1, name)

    def changed(*args: object) -> object:
        ledger = tmp_path / "runs/replay-rebuild/llm.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(b"fresh synthetic ledger")
        return original(*args)

    monkeypatch.setattr(m1, name, changed)
    with pytest.raises(ValueError, match="fresh model ledger"):
        m1.evaluate_t0(tmp_path, "replay", "origin")


@pytest.mark.parametrize("phase", ["cases", "measure"])
def test_measurement_rejects_ledger_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_evaluator: list[str],
    phase: str,
) -> None:
    name = "heldout_cases" if phase == "cases" else "_measure"
    original = getattr(m1, name)

    def changed(*args: object) -> object:
        ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(b"changed synthetic ledger")
        return original(*args)

    monkeypatch.setattr(m1, name, changed)
    with pytest.raises(ValueError, match="model ledger changed"):
        m1.evaluate_t0(tmp_path, "origin")
    assert not (tmp_path / "runs/origin/m1.json").exists()


def test_identity_hashes_complete_large_file_and_rejects_symlinks(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "runs/pipeline/llm.jsonl"
    ledger.parent.mkdir(parents=True)
    content = b"synthetic\n" * 200_000
    ledger.write_bytes(content)
    run = tmp_path / "evaluation"
    identity = freeze_identity(tmp_path, run, "pipeline")
    assert identity["sha256"] == sha256(content).hexdigest()
    assert "synthetic" not in (run / "model-ledger.json").read_text()
    link = tmp_path / "link"
    link.symlink_to(ledger)
    with pytest.raises(ValueError, match="symbolic links"):
        ledger_digest(link)


def test_replay_rejects_missing_origin_identity(
    tmp_path: Path, synthetic_evaluator: list[str]
) -> None:
    m1.evaluate_t0(tmp_path, "origin")
    (tmp_path / "runs/origin/model-ledger.json").unlink()
    synthetic_evaluator.clear()
    with pytest.raises(ValueError, match="invalid or missing"):
        m1.evaluate_t0(tmp_path, "replay", "origin")
    assert synthetic_evaluator == []


def test_removed_original_ledger_stops_replay(
    tmp_path: Path, synthetic_evaluator: list[str]
) -> None:
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b"synthetic ledger")
    m1.evaluate_t0(tmp_path, "origin")
    ledger.unlink()
    synthetic_evaluator.clear()
    with pytest.raises(ValueError, match="model ledger changed"):
        m1.evaluate_t0(tmp_path, "replay", "origin")
    assert synthetic_evaluator == []


@pytest.mark.parametrize("content", [b"{}", b"[]", b" " * 4097])
def test_malformed_identity_is_rejected(tmp_path: Path, content: bytes) -> None:
    record = tmp_path / "model-ledger.json"
    record.write_bytes(content)
    with pytest.raises(ValueError, match="invalid or missing"):
        read_identity(record)


def test_nonregular_ledger_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "ledger"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        ledger_digest(directory)


def test_resume_rejects_missing_frozen_identity(
    tmp_path: Path, synthetic_evaluator: list[str]
) -> None:
    m1.evaluate_t0(tmp_path, "origin")
    (tmp_path / "runs/origin/model-ledger.json").unlink()
    synthetic_evaluator.clear()
    with pytest.raises(ValueError, match="invalid or missing"):
        m1.evaluate_t0(tmp_path, "origin")
    assert synthetic_evaluator == []
