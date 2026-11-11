import json
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, TextIO, cast

import pytest
from test_evaluation_freeze import ledger_attempt
from test_m2 import synthetic_engine as synthetic_engine

from phoenix_eval import m1, submission
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Tier
from phoenix_eval.model_ledger import LedgerIdentity, bound_summaries, read_identity
from phoenix_eval.submission import Submission

REAL_MEASURE = m1._measure


def test_all_m2_captures_and_costs_are_bound_before_each_archive(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_cases = cast(
        Callable[..., dict[str, tuple[Invocation, ...]]], getattr(m1, "heldout_cases")
    )
    checked: list[Tier] = []

    def cases(
        path: Path, digest: str, names: set[str], *, tier: Tier
    ) -> dict[str, tuple[Invocation, ...]]:
        run = tmp_path / "runs/origin"
        binding = json.loads((run / "capture-binding.json").read_text())
        keys = tuple(record["key"] for record in binding["captures"])
        assert binding["phase"] == "frozen"
        assert list(keys) == synthetic_engine["scope"].record()["task_keys"]
        assert len(keys) == len(set(keys)) == 260
        summaries = bound_summaries(
            tmp_path, keys, read_identity(run / "model-ledger.json")
        )
        assert sum(summary.calls for summary in summaries.values()) == 130
        checked.append(tier)
        return original_cases(path, digest, names, tier=tier)

    monkeypatch.setattr(m1, "heldout_cases", cases)
    report, passed = m1.evaluate_m2(tmp_path, "origin")
    assert passed and checked == [Tier.T0, Tier.T1]
    document = json.loads(report.read_text())
    keys = tuple(row["task_key"] for row in document["results"])
    summaries = bound_summaries(
        tmp_path, keys, read_identity(report.parent / "model-ledger.json")
    )
    assert [row["model"] for row in document["results"]] == [
        asdict(summaries[key]) for key in keys
    ]


def test_later_m2_capture_cannot_change_an_earlier_failure(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_submit = cast(Callable[..., Submission], getattr(m1, "submit"))
    keys = synthetic_engine["scope"].record()["task_keys"]
    run = tmp_path / "runs/origin"
    first = run / "submissions" / keys[0] / "capture/submission.json"

    def submit(*args: Any) -> Submission:
        result = replace(
            original_submit(*args),
            source_sha256=None,
            category="pipeline-failed",
            development_sha256=None,
            origin_sha256=None,
            report_sha256=None,
        )
        checkpoint = args[1] / "capture/submission.json"
        checkpoint.write_text(json.dumps(asdict(result)))
        if result.key == keys[-1]:
            record = json.loads(first.read_text())
            record["category"] = "invalid-project"
            first.write_text(json.dumps(record))
        return result

    monkeypatch.setattr(m1, "submit", submit)
    monkeypatch.setattr(m1, "_measure", REAL_MEASURE)
    with pytest.raises(ValueError, match="differs from the returned submission"):
        m1.evaluate_m2(tmp_path, "origin")
    assert len(synthetic_engine["submitted"]) == 260
    assert synthetic_engine["opened"] == []
    assert not (run / "m2.json").exists()
    assert (
        json.loads((run / "capture-binding.json").read_text())["phase"] == "capturing"
    )
    marker = run / "capture-rejected.json"
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    retained = {path: path.read_bytes() for path in (first, marker, ledger)}
    monkeypatch.setattr(m1, "submit", submission.submit)
    with pytest.raises(ValueError, match="capture was rejected"):
        m1.evaluate_m2(tmp_path, "origin")
    assert len(synthetic_engine["submitted"]) == 260
    assert synthetic_engine["opened"] == []
    assert not (run / "m2.json").exists()
    assert all(path.read_bytes() == content for path, content in retained.items())


@pytest.mark.parametrize("change", ["capture", "ledger"])
def test_change_between_archives_stops_before_second_archive(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    original_cases = cast(
        Callable[..., dict[str, tuple[Invocation, ...]]], getattr(m1, "heldout_cases")
    )

    def cases(
        path: Path, digest: str, names: set[str], *, tier: Tier
    ) -> dict[str, tuple[Invocation, ...]]:
        result = original_cases(path, digest, names, tier=tier)
        if tier == Tier.T0:
            if change == "capture":
                key = synthetic_engine["submitted"][-1][1]
                capture = tmp_path / "runs/origin/submissions" / key / "capture"
                (capture / "retained-evidence.bin").write_bytes(b"changed evidence")
            else:
                ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
                with ledger.open("a") as stream:
                    for event in ledger_attempt("unknown-task"):
                        stream.write(json.dumps(event) + "\n")
        return result

    monkeypatch.setattr(m1, "heldout_cases", cases)
    with pytest.raises(ValueError):
        m1.evaluate_m2(tmp_path, "origin")
    assert synthetic_engine["opened"] == [Tier.T0]
    assert not (tmp_path / "runs/origin/m2.json").exists()


@pytest.mark.parametrize("state", ["completed", "retry"])
def test_unknown_m2_attempt_stops_before_any_archive(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    original_submit = getattr(m1, "submit")

    def submit(*args: Any) -> Any:
        result = original_submit(*args)
        if len(synthetic_engine["submitted"]) == 260:
            events = ledger_attempt("unknown-task", state)
            if state == "retry":
                events[-1]["cost_nanodollars"] = 0
            ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
            with ledger.open("a") as stream:
                for event in events:
                    stream.write(json.dumps(event) + "\n")
        return result

    monkeypatch.setattr(m1, "submit", submit)
    with pytest.raises(ValueError, match="task keys"):
        m1.evaluate_m2(tmp_path, "origin")
    assert synthetic_engine["opened"] == []
    assert not (tmp_path / "runs/origin/m2.json").exists()


@pytest.mark.parametrize("reference", ["origin", "first"])
def test_changed_ancestor_capture_stops_before_replay_work(
    tmp_path: Path, synthetic_engine: dict[str, Any], reference: str
) -> None:
    report, _ = m1.evaluate_m2(tmp_path, "origin")
    if reference == "first":
        m1.evaluate_m2(tmp_path, "first", "origin")
    before = report.read_bytes()
    key = synthetic_engine["submitted"][0][1]
    capture = tmp_path / "runs/origin/submissions" / key / "capture"
    (capture / "retained-evidence.bin").write_bytes(b"changed evidence")
    submitted = len(synthetic_engine["submitted"])
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError, match="capture binding"):
        m1.evaluate_m2(tmp_path, "copy", reference)
    assert synthetic_engine["opened"] == []
    assert len(synthetic_engine["submitted"]) == submitted
    assert report.read_bytes() == before
    assert not (tmp_path / "runs/copy/m2.json").exists()


@pytest.mark.parametrize(
    ("ancestor", "evidence", "boundary", "opened", "diagnostic"),
    [
        ("first", "checkpoint", "archive", [Tier.T0], "capture binding"),
        ("origin", "checkpoint", "report", [Tier.T0, Tier.T1], "capture binding"),
        ("origin", "report", "report", [Tier.T0, Tier.T1], "ancestor report"),
    ],
)
def test_m2_replay_rechecks_ancestor_evidence_at_use(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    ancestor: str,
    evidence: str,
    boundary: str,
    opened: list[Tier],
    diagnostic: str,
) -> None:
    origin, _ = m1.evaluate_m2(tmp_path, "origin")
    first, _ = m1.evaluate_m2(tmp_path, "first", "origin")
    ancestor_run = tmp_path / "runs" / ancestor
    key = synthetic_engine["submitted"][0][1]
    path = (
        ancestor_run / "submissions" / key / "capture/submission.json"
        if evidence == "checkpoint"
        else ancestor_run / "m2.json"
    )
    before = path.read_bytes()
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    preserved = {
        item: item.read_bytes()
        for item in (origin, first, ledger, ancestor_run / "capture-binding.json")
        if item != path
    }
    read_cases = cast(
        Callable[..., dict[str, tuple[Invocation, ...]]], getattr(m1, "heldout_cases")
    )
    dump = json.dump

    def cases(
        path_arg: Path, digest: str, names: set[str], *, tier: Tier
    ) -> dict[str, tuple[Invocation, ...]]:
        result = read_cases(path_arg, digest, names, tier=tier)
        if tier == Tier.T0:
            path.write_bytes(before + b"\n")
        return result

    def stage(document: object, stream: TextIO, **options: Any) -> None:
        dump(document, stream, **options)
        if isinstance(document, dict) and document.get("run_id") == "copy":
            path.write_bytes(before + b"\n")

    if boundary == "archive":
        monkeypatch.setattr(m1, "heldout_cases", cases)
    else:
        monkeypatch.setattr(json, "dump", stage)
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError, match=diagnostic):
        m1.evaluate_m2(tmp_path, "copy", "first")
    assert synthetic_engine["opened"] == opened
    assert not (tmp_path / "runs/copy/m2.json").exists()
    assert path.read_bytes() == before + b"\n"
    assert all(item.read_bytes() == old for item, old in preserved.items())


def test_m2_task_charge_transfer_cannot_hide_in_the_total(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_measure = m1._measure
    changes: list[int] = []

    def measure(*args: Any) -> dict[str, object]:
        result = original_measure(*args)
        if result["method"] == "phoenix" and len(changes) < 2:
            model = result["model"]
            assert isinstance(model, dict)
            difference = 1 if not changes else -1
            model["cost_nanodollars"] += difference
            changes.append(difference)
        return result

    monkeypatch.setattr(m1, "_measure", measure)
    with pytest.raises(ValueError, match="reconcile"):
        m1.evaluate_m2(tmp_path, "origin")
    assert changes == [1, -1] and sum(changes) == 0
    assert synthetic_engine["opened"] == [Tier.T0, Tier.T1]
    assert not (tmp_path / "runs/origin/m2.json").exists()


def test_m2_replay_cannot_refreeze_a_changed_origin_ledger(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original, _ = m1.evaluate_m2(tmp_path, "origin")
    first, _ = m1.evaluate_m2(tmp_path, "first", "origin")
    log = tmp_path / "runs/origin-rebuild/llm.jsonl"
    before = log.read_bytes()
    preserved = {path: path.read_bytes() for path in (original, first)}
    identity = read_identity(original.parent / "model-ledger.json")
    freeze = getattr(m1, "freeze_identity")

    def edit(
        workspace: Path,
        run: Path,
        pipeline_run: str,
        *,
        expected: LedgerIdentity | None = None,
    ) -> LedgerIdentity:
        assert expected == identity
        log.write_bytes(b" " + before)
        return cast(
            LedgerIdentity, freeze(workspace, run, pipeline_run, expected=expected)
        )

    copy = tmp_path / "runs/copy"
    synthetic_engine["opened"].clear()
    with monkeypatch.context() as change:
        change.setattr(m1, "freeze_identity", edit)
        with pytest.raises(ValueError, match="original model ledger changed"):
            m1.evaluate_m2(tmp_path, "copy", "first")
    assert synthetic_engine["opened"] == []
    assert not (copy / "model-ledger.json").exists()
    assert not (copy / "m2.json").exists()
    assert log.read_bytes() == b" " + before
    assert all(path.read_bytes() == content for path, content in preserved.items())
    log.write_bytes(before)
    final, accepted = m1.evaluate_m2(tmp_path, "copy", "first")
    assert accepted and json.loads(final.read_bytes())["reproduced"] is True
    assert read_identity(copy / "model-ledger.json") == identity
    assert not (tmp_path / "runs/copy-rebuild/llm.jsonl").exists()
