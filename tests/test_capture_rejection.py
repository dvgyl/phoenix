import json
from collections.abc import Callable
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, TextIO

import pytest
from test_evaluation_freeze import SyntheticEngine, replace_source
from test_evaluation_freeze import engine as engine

from phoenix_eval import m1, submission
from phoenix_eval.corpus import Variant
from phoenix_eval.m1 import _measure as real_measure
from phoenix_eval.submission import Submission


def test_rejected_failure_cannot_publish_on_retry(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest: Callable[[Path], tuple[tuple[Variant, ...], str]] = getattr(
        m1, "t0_manifest"
    )
    variants, _ = manifest(engine.workspace)
    keys = tuple(m1.Task(v, method).key for v in variants for method in m1.METHODS)
    engine.failed.update(keys)
    target = engine.run / "submissions" / keys[0] / "capture/submission.json"
    returned: list[Submission] = []

    def change(_directory: Path, value: Submission) -> None:
        if value.key == keys[0]:
            returned.append(value)
        if value.key == keys[-1]:
            data = json.loads(target.read_bytes())
            data["category"] = "invalid-project"
            submission.write_report(target, data)

    engine.after_capture = change
    monkeypatch.setattr(m1, "_measure", real_measure)
    with pytest.raises(ValueError, match="capture checkpoint differs"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert not engine.opened
    report = engine.run / "m1.json"
    assert not report.exists()
    rejected = target.read_bytes()
    ledger = engine.ledger.read_bytes()
    identity = (engine.run / "model-ledger.json").read_bytes()
    assert returned[0].category == "pipeline-failed"
    assert json.loads(rejected)["category"] == "invalid-project"
    monkeypatch.setattr(m1, "submit", submission.submit)
    try:
        with pytest.raises(ValueError):
            m1.evaluate_t0(engine.workspace, "initial")
    finally:
        if report.exists():
            document = json.loads(report.read_bytes())
            binding = json.loads((engine.run / "capture-binding.json").read_bytes())
            print(
                json.dumps(
                    {
                        "returned_category": returned[0].category,
                        "rejected_category": json.loads(rejected)["category"],
                        "published_category": document["results"][0][
                            "failure_category"
                        ],
                        "results": len(document["results"]),
                        "archives_opened": len(engine.opened),
                        "checkpoint_unchanged": target.read_bytes() == rejected,
                        "frozen_digest_matches_rejected_bytes": (
                            binding["captures"][0]["files"]["submission.json"]
                            == sha256(rejected).hexdigest()
                        ),
                    },
                    sort_keys=True,
                )
            )
    assert not engine.opened
    assert not report.exists()
    assert target.read_bytes() == rejected
    assert engine.ledger.read_bytes() == ledger
    assert (engine.run / "model-ledger.json").read_bytes() == identity


@pytest.mark.parametrize("change", ["failure-category", "success-to-failure", "source"])
@pytest.mark.parametrize("restore", [False, True])
def test_contradiction_remains_rejected_before_submission_reuse(
    engine: SyntheticEngine,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    restore: bool,
) -> None:
    target = engine.run / "submissions/case-0-gcc-O0-phoenix/capture/submission.json"
    original: list[bytes] = []
    returned: list[Submission] = []
    if change == "failure-category":
        engine.failed.add("case-0-gcc-O0-phoenix")

    def change_checkpoint(_directory: Path, value: Submission) -> None:
        if len(engine.submitted) == 1:
            original.append(target.read_bytes())
            returned.append(value)
        if len(engine.submitted) != 40:
            return
        data = json.loads(target.read_bytes())
        if change == "source":
            replace_source(engine.run, engine.submitted[0])
        else:
            data.update(
                source_sha256=None,
                category="invalid-project",
                development_sha256=None,
                origin_sha256=None,
                report_sha256=None,
            )
            submission.write_report(target, data)

    engine.after_capture = change_checkpoint
    with pytest.raises(ValueError, match="capture checkpoint differs"):
        m1.evaluate_t0(engine.workspace, "initial")
    changed = target.read_bytes()
    marker = engine.run / "capture-rejected.json"
    rejected = marker.read_bytes()
    record = json.loads(rejected)
    assert len(rejected) <= 512
    assert record == {
        "schema": 1,
        "phase": "rejected",
        "reason": "checkpoint-mismatch",
        "task_key_sha256": sha256(returned[0].key.encode()).hexdigest(),
        "checkpoint_sha256": sha256(changed).hexdigest(),
        "returned_submission_sha256": sha256(
            json.dumps(asdict(returned[0]), sort_keys=True, allow_nan=False).encode()
        ).hexdigest(),
    }
    evidence = {
        path: path.read_bytes()
        for path in (
            engine.ledger,
            engine.run / "configuration.json",
            engine.run / "model-ledger.json",
        )
    }
    if restore:
        target.write_bytes(original[0])
    current = target.read_bytes()
    reads: list[str] = []
    real_read = submission.read_submission

    def read(path: Path) -> tuple[Submission, str]:
        reads.append(str(path))
        return real_read(path)

    monkeypatch.setattr(submission, "read_submission", read)
    monkeypatch.setattr(m1, "submit", submission.submit)
    for _ in range(2):
        with pytest.raises(ValueError, match="capture was rejected"):
            m1.evaluate_t0(engine.workspace, "initial")
        assert not reads
        assert not engine.opened
        assert not (engine.run / "m1.json").exists()
        assert target.read_bytes() == current
        assert marker.read_bytes() == rejected
        assert all(path.read_bytes() == content for path, content in evidence.items())


@pytest.mark.parametrize("when", ["empty", "partial", "complete"])
def test_interrupted_rejection_cannot_resume(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    target = engine.run / "submissions/case-0-gcc-O0-phoenix/capture/submission.json"
    engine.failed.add("case-0-gcc-O0-phoenix")

    def change(_directory: Path, _value: Submission) -> None:
        if len(engine.submitted) == 40:
            data = json.loads(target.read_bytes())
            data["category"] = "invalid-project"
            submission.write_report(target, data)

    engine.after_capture = change
    dump = json.dump

    def interrupted_dump(data: object, stream: TextIO, **kwargs: Any) -> None:
        if isinstance(data, dict) and data.get("phase") == "rejected":
            if when == "partial":
                stream.write('{"schema": 1, "phase": "rej')
            elif when == "complete":
                dump(data, stream, **kwargs)
            raise KeyboardInterrupt("Synthetic rejection publication interruption.")
        dump(data, stream, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(json, "dump", interrupted_dump)
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
    assert not engine.opened
    changed = target.read_bytes()
    marker = engine.run / "capture-rejected.json"
    rejected = marker.read_bytes()
    assert b'"capturing"' not in rejected
    ledger = engine.ledger.read_bytes()
    monkeypatch.setattr(m1, "submit", submission.submit)
    with pytest.raises(ValueError):
        m1.evaluate_t0(engine.workspace, "initial")
    assert not engine.opened
    assert not (engine.run / "m1.json").exists()
    assert target.read_bytes() == changed
    assert marker.read_bytes() == rejected
    assert engine.ledger.read_bytes() == ledger


@pytest.mark.parametrize("after_publication", [False, True])
def test_valid_failed_capture_survives_freeze_interruption_and_replay(
    engine: SyntheticEngine,
    monkeypatch: pytest.MonkeyPatch,
    after_publication: bool,
) -> None:
    manifest: Callable[[Path], tuple[tuple[Variant, ...], str]] = getattr(
        m1, "t0_manifest"
    )
    variants, _ = manifest(engine.workspace)
    keys = tuple(m1.Task(v, method).key for v in variants for method in m1.METHODS)
    engine.failed.update(keys)
    engine.failure_category = "invalid-project"
    monkeypatch.setattr(m1, "_measure", real_measure)
    replace = Path.replace

    def interrupted(path: Path, target: Path) -> Path:
        if target.name == "capture-binding.json" and b'"frozen"' in path.read_bytes():
            if after_publication:
                replace(path, target)
            raise KeyboardInterrupt("Synthetic valid binding interruption.")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupted)
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
    assert not engine.opened
    assert len(engine.submitted) == 40
    binding = engine.run / "capture-binding.json"
    assert json.loads(binding.read_bytes())["phase"] == (
        "frozen" if after_publication else "capturing"
    )
    ledger = engine.ledger.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(m1, "submit", submission.submit)
        report, accepted = m1.evaluate_t0(engine.workspace, "initial")
        assert not accepted
        original = report.read_bytes()
        records = json.loads(original)["results"]
        assert len(records) == 40
        assert {r["failure_category"] for r in records} == {"invalid-project"}
        assert sum(r["model"]["cost_nanodollars"] for r in records) == 1_600_000
        assert sum(r["model"]["calls"] for r in records) == 40
        frozen = binding.read_bytes()
        m1.evaluate_t0(engine.workspace, "initial")
        assert report.read_bytes() == original
        assert binding.read_bytes() == frozen
    replay, accepted = m1.evaluate_t0(engine.workspace, "replay", "initial")
    assert not accepted
    assert json.loads(replay.read_bytes())["reproduced"] is True
    assert report.read_bytes() == original
    assert binding.read_bytes() == frozen
    assert engine.ledger.read_bytes() == ledger
    assert not (engine.workspace / "runs/replay-rebuild/llm.jsonl").exists()


def test_rejection_keeps_the_original_binding_inode_unchanged(
    engine: SyntheticEngine,
) -> None:
    binding = engine.run / "capture-binding.json"
    alias = engine.workspace / "capture-control.json"
    target = engine.run / "submissions/case-0-gcc-O0-phoenix/capture/submission.json"
    engine.failed.add("case-0-gcc-O0-phoenix")
    saved: list[bytes] = []

    def change(_directory: Path, _value: Submission) -> None:
        if len(engine.submitted) == 40:
            saved.append(binding.read_bytes())
            alias.hardlink_to(binding)
            data = json.loads(target.read_bytes())
            data["category"] = "invalid-project"
            submission.write_report(target, data)

    engine.after_capture = change
    with pytest.raises(ValueError, match="capture checkpoint differs"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert binding.read_bytes() == alias.read_bytes() == saved[0]
    with pytest.raises(ValueError, match="capture was rejected"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert not engine.opened
    assert not (engine.run / "m1.json").exists()
