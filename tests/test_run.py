from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from phoenix.config import ROLE_MODELS
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Request, Usage
from phoenix_eval import run as evaluation
from phoenix_eval.case import Invocation
from phoenix_eval.dev_corpus import DevBinary, ValidatedCases
from phoenix_eval.run_binary import task_key
from phoenix_eval.run_records import (
    BinaryResult,
    RunPlan,
    Selection,
    ledger_snapshot,
    read_json,
    verify_ledger,
)
from phoenix_eval.run_resources import Resources
from phoenix_eval.submission import EvaluationPending


class Provider:
    name = "fixture"

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: Request) -> Completion:
        return Completion("fixture", Usage(5, 0, 3), request.model)


def binary(name: str = "fixturealpha") -> DevBinary:
    return DevBinary(
        name, "D0", "gcc", ("-std=c11", "-O0", "-lm"), "a" * 64, "fixture", True
    )


def measured(item: DevBinary, categories: tuple[str, ...] = ()) -> BinaryResult:
    builds = [
        {
            "architecture": arch,
            "compiler": cc,
            "compiled": True,
            "matched_cases": 0
            if categories == ("behavior_arm_only",) and arch == "arm64"
            else 100,
            "evaluation_errors": 0,
        }
        for arch in ("amd64", "arm64")
        for cc in ("gcc", "clang")
    ]
    passed = sum(cast(int, build["matched_cases"]) for build in builds)
    return BinaryResult(
        item,
        not categories,
        categories,
        (passed, 400),
        False,
        {
            "task_key": task_key(item),
            "source_sha256": "b" * 64,
            "heldout_hash": "c" * 64,
            "dev_passed": True,
            "dev_set_hash": "d" * 64,
            "replay_identical": True,
            "reconstruction_seconds": 6.0,
            "integrity_categories": {"embedded_text": 1}
            if categories == ("integrity",)
            else {},
            "register_named_locals": 0,
            "goto_per_100_lines": 0.0,
            "behavior": {"total_cases": 100, "builds": builds},
            "package_files": {"src/program.c": "e" * 64},
        },
    )


@pytest.fixture
def harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, tuple[DevBinary, ...]]:
    root = tmp_path / "repo"
    items = (binary(), binary("fixturebeta"))
    for item in items:
        holdout = root / "corpus_dev" / item.name / "holdout"
        holdout.mkdir(parents=True)
        (holdout / "cases.jsonl").write_text("fixture\n" * 100)
        (holdout.parent / "adequacy.json").write_text(
            '{"coverage": {"covered": 91, "total": 100}}'
        )
    monkeypatch.setenv("PHOENIX_JOBS", "1")
    monkeypatch.setattr(evaluation, "CHECKOUT", root)
    monkeypatch.setattr(evaluation, "_configuration", lambda _: {"revision": "f" * 40})
    monkeypatch.setattr(
        evaluation, "_selection", lambda *_: (items, "b" * 64, "c" * 64)
    )
    monkeypatch.setattr(
        evaluation,
        "load_validated_cases",
        lambda *_: ValidatedCases((Invocation(),) * 100, tuple(range(100)), (), 100),
    )
    monkeypatch.setattr(Resources, "start", lambda _: None)
    monkeypatch.setattr(Resources, "finish", lambda _: None)
    monkeypatch.setattr(Resources, "sample", lambda _: None)
    monkeypatch.setattr(
        evaluation, "measure", lambda workspace, run, item, plan, replay: measured(item)
    )
    return tmp_path, items


def test_fixture_projects_keep_architecture_and_integrity_failures(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, items = harness

    def measure(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        return measured(item, () if item == items[0] else ("behavior_arm_only",))

    monkeypatch.setattr(evaluation, "measure", measure)
    result = evaluation.evaluate(workspace, "original", Selection(), True)
    assert result["success"] == {"D0": {"O0": [1, 2], "O2": [0, 0], "Os": [0, 0]}}
    assert result["held_out_cases"] == [600, 800]
    assert result["failure_categories"] == {"behavior_arm_only": 1}
    assert result["arm_gap_points"] == {"D0": 50.0}
    coverage = cast(dict[str, dict[str, object]], result["source_branch_coverage"])
    assert coverage[items[0].name]["coverage"] == {"covered": 91, "total": 100}
    monkeypatch.setattr(
        evaluation,
        "measure",
        lambda workspace, run, item, plan, replay: measured(item, ("integrity",)),
    )
    failed = evaluation.evaluate(workspace, "integrity", Selection(), True)
    assert failed["integrity_failures"] == 2
    assert failed["success"]["D0"]["O0"] == [0, 2]  # type: ignore[index]


def test_stopped_run_keeps_roster_and_published_row_after_resume(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, items = harness

    def stopped(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        if item == items[1]:
            raise EvaluationPending("fixture service stop")
        return measured(item)

    monkeypatch.setattr(evaluation, "measure", stopped)
    original = evaluation.evaluate(workspace, "stopped", Selection(), True)
    path = workspace / "runs/stopped/scoreboard.json"
    published = path.read_bytes()
    assert original["run_state"] == "stopped"
    assert original["success"]["D0"]["O0"] == [1, 2]  # type: ignore[index]
    assert original["held_out_cases"] == [400, 800]
    calls = []

    def resumed(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        calls.append(item.name)
        return measured(item)

    monkeypatch.setattr(evaluation, "measure", resumed)
    resumed_score = evaluation.evaluate(
        workspace, "stopped", Selection(), True, resume=True
    )
    assert resumed_score == original
    assert path.read_bytes() == published
    assert calls == [items[1].name]
    assert list(path.parent.glob("continuation-*.json"))


def test_resume_never_retries_a_terminal_failure(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _ = harness
    monkeypatch.setattr(
        evaluation,
        "measure",
        lambda workspace, run, item, plan, replay: measured(item, ("behavior_x86",)),
    )
    original = evaluation.evaluate(workspace, "failure", Selection(), True)
    runner = Mock(side_effect=AssertionError("A terminal result was retried."))
    monkeypatch.setattr(evaluation, "measure", runner)
    assert (
        evaluation.evaluate(workspace, "failure", Selection(), True, resume=True)
        == original
    )
    runner.assert_not_called()


def test_changed_published_result_stops_resume_before_execution(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, items = harness
    evaluation.evaluate(workspace, "tampered", Selection(), True)
    result = workspace / "runs/tampered/results" / f"{task_key(items[0])}.json"
    result.write_bytes(result.read_bytes() + b"\n")
    runner = Mock(side_effect=AssertionError("The changed capture was used."))
    monkeypatch.setattr(evaluation, "measure", runner)
    with pytest.raises(ValueError, match="terminal result changed"):
        evaluation.evaluate(workspace, "tampered", Selection(), True, resume=True)
    runner.assert_not_called()


def test_replay_preserves_stopped_placeholders_after_later_resume(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, items = harness

    def stopped(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        if item == items[1]:
            raise EvaluationPending("fixture")
        return measured(item)

    monkeypatch.setattr(evaluation, "measure", stopped)
    original = evaluation.evaluate(workspace, "origin", Selection(), True)
    monkeypatch.setattr(
        evaluation, "measure", lambda workspace, run, item, plan, replay: measured(item)
    )
    evaluation.evaluate(workspace, "origin", Selection(), True, resume=True)
    replay = evaluation.evaluate(
        workspace, "replay", Selection(), True, replay_id="origin"
    )
    assert replay["success"] == original["success"]
    assert replay["held_out_cases"] == original["held_out_cases"]
    assert replay["reproduced"] is True


def test_ledger_prefix_keeps_cost_when_live_run_appends(tmp_path: Path) -> None:
    run = tmp_path / "runs/evaluation"
    run.mkdir(parents=True)
    pipeline = tmp_path / "runs/pipeline"
    ledger = Ledger(pipeline)
    ledger.call("first", Request("first", model=ROLE_MODELS["runtime"]), Provider())
    content, costs = ledger_snapshot(tmp_path, run, "pipeline")
    first = costs["first"].cost_nanodollars
    ledger.call("second", Request("second", model=ROLE_MODELS["runtime"]), Provider())
    assert verify_ledger(tmp_path, run) == content
    again, saved = ledger_snapshot(tmp_path, run, "pipeline")
    assert again == content
    assert saved["first"].cost_nanodollars == first
    assert "second" not in saved
    live = ledger.path.read_bytes()
    ledger.path.write_bytes(b"changed" + live)
    with pytest.raises(ValueError, match="published prefix"):
        verify_ledger(tmp_path, run)


def test_plan_round_trip_keeps_typed_boundaries(
    harness: tuple[Path, tuple[DevBinary, ...]],
) -> None:
    workspace, items = harness
    evaluation.evaluate(workspace, "typed", Selection(), True)
    plan = RunPlan.load(workspace / "runs/typed/plan.json")
    assert plan.binaries == items
    assert plan.selection == Selection()
    result = BinaryResult.parse(
        read_json(workspace / "runs/typed/results" / f"{task_key(items[0])}.json")
    )
    assert result.binary == items[0]
    assert result.fully_successful


def test_result_cannot_claim_success_with_missing_cases() -> None:
    result = measured(binary()).record()
    result["held_out_cases"] = [399, 400]
    with pytest.raises(ValueError, match="Invalid binary result"):
        BinaryResult.parse(result)


def test_failed_results_use_ledger_costs_instead_of_reported_costs(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _ = harness

    def failed(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        Ledger(workspace / "runs" / plan.pipeline).call(
            task_key(item), Request("fixture"), Provider()
        )
        raise ValueError("Fixture failure after a charged call.")

    monkeypatch.setattr(evaluation, "measure", failed)
    result = evaluation.evaluate(workspace, "charged", Selection(), True)
    assert result["cost_usd"] == {
        "D0": {"median": 0.00004, "q1": 0.00004, "q3": 0.00004}
    }
    assert result["held_out_cases"] == [0, 800]
    assert result["failure_categories"] == {"pipeline_error": 2}


def test_replay_of_replay_uses_the_original_ledger_prefix(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _ = harness

    def score(
        workspace: Path,
        run: Path,
        item: DevBinary,
        plan: RunPlan,
        replay: RunPlan | None,
    ) -> BinaryResult:
        if replay is None:
            Ledger(workspace / "runs" / plan.pipeline).call(
                task_key(item), Request("fixture"), Provider()
            )
        return measured(item)

    monkeypatch.setattr(evaluation, "measure", score)
    original = evaluation.evaluate(workspace, "original", Selection(), True)
    first = evaluation.evaluate(
        workspace, "first-replay", Selection(), True, replay_id="original"
    )
    second = evaluation.evaluate(
        workspace, "second-replay", Selection(), True, replay_id="first-replay"
    )
    assert first["reproduced"] is True
    assert second["reproduced"] is True
    assert second["cost_usd"] == original["cost_usd"]
    assert (
        read_json(workspace / "runs/second-replay/published-ledger.json")[
            "pipeline_run"
        ]
        == "original-p"
    )


def test_replay_restores_a_verified_archive(
    harness: tuple[Path, tuple[DevBinary, ...]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fcntl

    from phoenix_eval import run_archive
    from phoenix_eval.run_archive import archive_run

    workspace, _ = harness
    original = evaluation.evaluate(workspace, "archived", Selection(), True)
    plan = (workspace / "runs/archived/plan.json").read_bytes()
    archive = archive_run(workspace, "archived")
    assert archive.is_file()
    assert not (workspace / "runs/archived").exists()
    restore = run_archive.restore_run

    def unlocked_restore(workspace: Path, run_id: str) -> Path:
        with (workspace / "runs/.archive.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return restore(workspace, run_id)

    monkeypatch.setattr(run_archive, "restore_run", unlocked_restore)
    replay = evaluation.evaluate(
        workspace, "restored-replay", Selection(), True, replay_id="archived"
    )
    assert replay["reproduced"] is True
    assert replay["success"] == original["success"]
    assert (workspace / "runs/archived/plan.json").read_bytes() == plan


@pytest.mark.parametrize("field", ["success", "cost_usd"])
def test_resume_rejects_changed_published_totals(
    harness: tuple[Path, tuple[DevBinary, ...]],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    import json

    workspace, _ = harness
    evaluation.evaluate(workspace, "published", Selection(), True)
    path = workspace / "runs/published/scoreboard.json"
    saved = read_json(path)
    saved[field] = (
        {"D0": {"O0": [99, 99]}} if field == "success" else {"D0": {"median": 9}}
    )
    path.write_text(json.dumps(saved))
    measure = Mock()
    monkeypatch.setattr(evaluation, "measure", measure)
    with pytest.raises(ValueError, match="published score differs"):
        evaluation.evaluate(workspace, "published", Selection(), True, resume=True)
    measure.assert_not_called()


def test_source_checker_rejections_count_as_integrity_failures(
    harness: tuple[Path, tuple[DevBinary, ...]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phoenix_eval.integrity import IntegrityError

    workspace, items = harness
    measure = Mock(side_effect=IntegrityError("Synthetic source rejection."))
    monkeypatch.setattr(evaluation, "measure", measure)
    score = evaluation.evaluate(workspace, "rejected", Selection(), True)
    assert score["integrity_failures"] == len(items)
    assert score["failure_categories"] == {"integrity": len(items)}
    assert measure.call_count == len(items)


@pytest.mark.parametrize("change", ["count", "input"])
def test_replay_keeps_the_source_case_identity(
    harness: tuple[Path, tuple[DevBinary, ...]],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    workspace, items = harness
    evaluation.evaluate(workspace, "fixed-source", Selection(), True)
    source = workspace / "runs/fixed-source/scoreboard.json"
    published = source.read_bytes()
    if change == "count":
        monkeypatch.setattr(
            evaluation,
            "load_validated_cases",
            lambda *_: ValidatedCases(
                (Invocation(),) * 95,
                tuple(range(95)),
                tuple(range(95, 100)),
                100,
            ),
        )
    else:
        path = workspace / "repo/corpus_dev" / items[0].name / "holdout/cases.jsonl"
        path.write_text("changed\n" * 100)
    measure = Mock(return_value=measured(items[0]))
    monkeypatch.setattr(evaluation, "measure", measure)
    with pytest.raises(ValueError, match="source run plan"):
        evaluation.evaluate(
            workspace, "changed-replay", Selection(), True, replay_id="fixed-source"
        )
    measure.assert_not_called()
    assert source.read_bytes() == published
