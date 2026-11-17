import json
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
from phoenix_eval.model_ledger import read_events, summarize
from phoenix_eval.run_binary import task_key
from phoenix_eval.run_records import (
    BinaryResult,
    RunPlan,
    Selection,
    capture_ledger,
    digest,
    read_json,
    read_ledger,
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
            "heldout_hash": digest(
                json.dumps([tuple(range(100)), digest(b"fixture\n" * 100)]).encode()
            ),
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
    snapshot = capture_ledger(tmp_path, run, "pipeline")
    content = snapshot.content
    first = summarize(snapshot.events, "first").cost_nanodollars
    ledger.call("second", Request("second", model=ROLE_MODELS["runtime"]), Provider())
    assert read_ledger(tmp_path, run).content == content
    saved = capture_ledger(tmp_path, run, "pipeline")
    assert saved == snapshot
    assert summarize(saved.events, "first").cost_nanodollars == first
    assert {event.binary for event in saved.events} == {"first"}
    live = ledger.path.read_bytes()
    ledger.path.write_bytes(b"changed" + live)
    with pytest.raises(ValueError, match="published prefix"):
        read_ledger(tmp_path, run).content


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


@pytest.fixture
def publication_plan(
    harness: tuple[Path, tuple[DevBinary, ...]],
) -> tuple[Path, RunPlan]:
    from phoenix_eval.run_records import immutable, plan_record, record_result

    workspace, items = harness
    plan = RunPlan(
        "publication",
        Selection(),
        items,
        {
            "revision": "f" * 40,
            "row": 1,
            "loop": "full",
            "milestone": "R0",
            "experiment": [1, 3],
            "noise_ref": None,
            "case_counts": {task_key(item): 100 for item in items},
            "case_hashes": {
                task_key(item): measured(item).details["heldout_hash"] for item in items
            },
        },
        "b" * 64,
        "c" * 64,
        True,
        0,
        ("publication-p", "publication-check"),
    )
    run = workspace / "runs" / plan.run_id
    run.mkdir(parents=True)
    immutable(run / "plan.json", plan_record(plan))
    for item in items:
        record_result(run, task_key(item), measured(item))
    return workspace, plan


def test_require_existing_does_not_create_publication_evidence(
    publication_plan: tuple[Path, RunPlan],
) -> None:
    workspace, plan = publication_plan
    run = workspace / "runs" / plan.run_id
    with pytest.raises(ValueError, match="scoreboard is missing"):
        evaluation.publish(workspace, plan.run_id, require_existing=True)
    assert not (run / "scoreboard.json").exists()
    assert not list(run.glob("published-ledger.*"))


@pytest.mark.parametrize("field", ["task_key", "heldout_hash", "held_out_cases"])
@pytest.mark.parametrize("existing", [False, True])
def test_publication_binds_terminal_results_to_fixed_cases(
    publication_plan: tuple[Path, RunPlan], field: str, existing: bool
) -> None:
    import json

    workspace, plan = publication_plan
    run = workspace / "runs" / plan.run_id
    if existing:
        evaluation.publish(workspace, plan.run_id)
    key = task_key(plan.binaries[0])
    path = run / "results" / f"{key}.json"
    record = read_json(path)
    record[field] = {
        "task_key": "different",
        "heldout_hash": "e" * 64,
        "held_out_cases": [404, 404],
    }[field]
    path.write_text(json.dumps(record))
    if existing:
        scoreboard = run / "scoreboard.json"
        document = read_json(scoreboard)
        cast(dict[str, object], document["result_refs"])[key] = digest(
            path.read_bytes()
        )
        scoreboard.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="fixed cases"):
        evaluation.publish(workspace, plan.run_id)


@pytest.mark.parametrize(
    "corruption",
    ["duplicate", "task_collision", "hash_keys", "count_keys", "count", "hash", "cell"],
)
def test_publication_rejects_invalid_fixed_roster(
    publication_plan: tuple[Path, RunPlan], corruption: str
) -> None:
    import json

    workspace, plan = publication_plan
    path = workspace / "runs" / plan.run_id / "plan.json"
    record = read_json(path)
    binaries = cast(list[dict[str, object]], record["binaries"])
    config = cast(dict[str, dict[str, object]], record["configuration"])
    key = task_key(plan.binaries[0])
    if corruption in ("duplicate", "task_collision"):
        binaries.append({**binaries[0]})
        if corruption == "task_collision":
            binaries[-1]["sha256"] = "e" * 64
    elif corruption in ("hash_keys", "count_keys"):
        field = "case_hashes" if corruption == "hash_keys" else "case_counts"
        config[field]["unknown"] = config[field][key]
    elif corruption == "count":
        config["case_counts"][key] = True
    elif corruption == "hash":
        config["case_hashes"][key] = "invalid"
    else:
        binaries[0]["tier"] = "D3"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="fixed plan"):
        evaluation.publish(workspace, plan.run_id)
    assert not (path.parent / "scoreboard.json").exists()


@pytest.mark.parametrize("paid", [False, True])
def test_every_selected_key_has_an_independent_cost_including_zero(
    publication_plan: tuple[Path, RunPlan], paid: bool
) -> None:
    import json

    workspace, plan = publication_plan
    run = workspace / "runs" / plan.run_id
    for item in plan.binaries:
        path = run / "results" / f"{task_key(item)}.json"
        path.write_text(json.dumps({**read_json(path), "cost_nanodollars": 10**12}))
    if paid:
        Ledger(workspace / "runs" / plan.pipeline).call(
            task_key(plan.binaries[0]), Request("fixture"), Provider()
        )
    publication = evaluation.publish(workspace, plan.run_id)
    cost = 0.00002 if paid else 0
    assert publication.document["cost_usd"] == {
        "D0": {"median": cost, "q1": cost / 2, "q3": cost * 1.5}
    }
    assert publication.document["models"] == {
        "runtime": [ROLE_MODELS["runtime"]] if paid else []
    }
    assert evaluation.publish(workspace, plan.run_id).document == publication.document


@pytest.mark.parametrize("existing", [False, True])
def test_publication_rejects_unknown_ledger_keys(
    publication_plan: tuple[Path, RunPlan], existing: bool
) -> None:
    import json

    workspace, plan = publication_plan
    run = workspace / "runs" / plan.run_id
    if existing:
        evaluation.publish(workspace, plan.run_id)
    ledger = Ledger(workspace / "runs" / plan.pipeline)
    ledger.call("unknown", Request("fixture"), Provider())
    if existing:
        content = ledger.path.read_bytes()
        (run / "published-ledger.jsonl").write_bytes(content)
        (run / "published-ledger.json").write_text(
            json.dumps(
                {
                    "pipeline_run": plan.pipeline,
                    "bytes": len(content),
                    "sha256": digest(content),
                }
            )
        )
    with pytest.raises(ValueError, match="outside the fixed roster"):
        evaluation.publish(workspace, plan.run_id)


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "commit",
        "corpus_hash",
        "heldout_hash",
        "row",
        "loop",
        "cache",
        "milestone",
        "experiment",
        "noise_ref",
        "mode",
        "models",
        "configuration_identity",
        "success",
        "source_branch_coverage",
        "program_success",
        "maintainable",
        "held_out_cases",
        "failure_categories",
        "integrity_failures",
        "glibc_internal_symbols",
        "register_named_locals",
        "arm_gap_points",
        "dev_edge_coverage_median",
        "function_reachability_median",
        "dev_mutation_score_median",
        "escape_rate",
        "truth_transplant_rate",
        "transformed_interface_rate",
        "theseus_fraction_median",
        "function_status",
        "literal_mode_byte_share",
        "nondefault_type_share",
        "goto_per_100_lines",
        "edit_task",
        "cost_usd",
        "binary_minutes",
        "noise",
        "dev_set_hashes",
        "binaries",
        "run_state",
        "quick_set",
        "corpus",
        "tag",
        "resource_scope",
    ],
)
def test_publication_regenerates_stored_score_fields(
    publication_plan: tuple[Path, RunPlan], field: str
) -> None:
    import json

    workspace, plan = publication_plan
    document = evaluation.publish(workspace, plan.run_id).document
    document[field] = {"corrupted": True}
    path = workspace / "runs" / plan.run_id / "scoreboard.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="published score differs"):
        evaluation.publish(workspace, plan.run_id, require_existing=True)


def test_publication_keeps_only_the_six_score_observation_exclusions(
    publication_plan: tuple[Path, RunPlan],
) -> None:
    import json

    workspace, plan = publication_plan
    document = evaluation.publish(workspace, plan.run_id).document
    for field in (
        "loop_minutes",
        "peak_memory_gib",
        "peak_storage_gib",
        "free_storage_gib",
        "source_lines",
        "test_lines",
    ):
        document[field] = 123
    path = workspace / "runs" / plan.run_id / "scoreboard.json"
    path.write_text(json.dumps(document))
    assert evaluation.publish(workspace, plan.run_id).document == document
    del document["noise"]
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="published score differs"):
        evaluation.publish(workspace, plan.run_id)


@pytest.mark.parametrize("existing", [False, True])
def test_publication_hashes_and_parses_each_evidence_byte_sequence_once(
    publication_plan: tuple[Path, RunPlan],
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    from phoenix_eval import run_records

    workspace, plan = publication_plan
    if existing:
        evaluation.publish(workspace, plan.run_id)
    read_bytes = Path.read_bytes
    calls: list[Path] = []

    def counted(path: Path) -> bytes:
        calls.append(path)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    parser = Mock(wraps=read_events)
    monkeypatch.setattr(run_records, "read_events", parser)
    publication = evaluation.publish(workspace, plan.run_id)
    scoreboard = workspace / "runs" / plan.run_id / "scoreboard.json"
    assert calls.count(scoreboard) == 1
    assert publication.sha256 == digest(read_bytes(scoreboard))
    assert parser.call_count == 1
    for result in publication.results:
        key = task_key(result.binary)
        path = workspace / "runs" / plan.run_id / "results" / f"{key}.json"
        assert calls.count(path) == 1
        assert cast(dict[str, object], publication.document["result_refs"])[key] == (
            digest(read_bytes(path))
        )


def test_publication_obeys_evaluation_and_archive_locks(
    publication_plan: tuple[Path, RunPlan],
) -> None:
    import fcntl

    workspace, plan = publication_plan
    run = workspace / "runs" / plan.run_id
    with (run / "evaluation.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="still active"):
            evaluation.publish(workspace, plan.run_id)
    assert not (run / "scoreboard.json").exists()
    evaluation.publish(workspace, plan.run_id)
    assert not (run / ".active").exists()
    with (workspace / "runs/.archive.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_caller_metadata_cannot_replace_authoritative_configuration(
    harness: tuple[Path, tuple[DevBinary, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _ = harness
    authoritative = {"revision": "f" * 40, "worker_source_sha256": "a" * 64}
    monkeypatch.setattr(evaluation, "_configuration", lambda _: authoritative)
    document = evaluation.evaluate(
        workspace,
        "metadata",
        Selection(),
        True,
        metadata={"revision": "e" * 40, "worker_source_sha256": "b" * 64},
    )
    assert document["commit"] == authoritative["revision"]
    plan = evaluation.publish(workspace, "metadata").plan
    assert all(plan.configuration[key] == value for key, value in authoritative.items())


@pytest.mark.parametrize("corruption", ["pipeline", "prefix", "cycle"])
def test_publication_checks_original_replay_ledger_identity(
    publication_plan: tuple[Path, RunPlan], corruption: str
) -> None:
    import json
    from dataclasses import replace

    from phoenix_eval.run_records import immutable, plan_record, record_result

    workspace, original = publication_plan
    Ledger(workspace / "runs" / original.pipeline).call(
        task_key(original.binaries[0]), Request("fixture"), Provider()
    )
    source = evaluation.publish(workspace, original.run_id)
    prior = original
    for name in ("first-replay", "second-replay"):
        plan = replace(
            original,
            run_id=name,
            replay_of=prior.run_id,
            dependencies=(f"{name}-p", f"{name}-check", prior.run_id),
        )
        path = workspace / "runs" / name
        path.mkdir()
        immutable(path / "plan.json", plan_record(plan))
        for result in source.results:
            record_result(path, task_key(result.binary), result)
        assert (
            evaluation.publish(workspace, name).document["cost_usd"]
            == (source.document["cost_usd"])
        )
        prior = plan
    path = workspace / "runs/second-replay"
    ledger = path / "published-ledger.json"
    if corruption == "cycle":
        changed = replace(prior, replay_of=prior.run_id)
        (path / "plan.json").write_text(json.dumps(plan_record(changed)))
    else:
        record = read_json(ledger)
        if corruption == "pipeline":
            changed_pipeline = workspace / "runs" / prior.pipeline
            changed_pipeline.mkdir()
            (changed_pipeline / "llm.jsonl").write_bytes(
                (path / "published-ledger.jsonl").read_bytes()
            )
            record["pipeline_run"] = prior.pipeline
        else:
            (path / "published-ledger.jsonl").write_bytes(b"")
            record.update(bytes=0, sha256=digest(b""))
        ledger.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="ledger identity changed|cycle"):
        evaluation.publish(workspace, prior.run_id, require_existing=True)


@pytest.mark.parametrize("location", ["success", "binary_outcome", "denominator"])
def test_publication_rejects_boolean_number_substitution(
    publication_plan: tuple[Path, RunPlan], location: str
) -> None:
    import json

    workspace, plan = publication_plan
    document = evaluation.publish(workspace, plan.run_id).document
    if location == "success":
        cast(dict[str, dict[str, list[object]]], document["success"])["D0"]["O2"][0] = (
            False
        )
    elif location == "denominator":
        cast(dict[str, dict[str, list[object]]], document["success"])["D0"]["O0"][1] = (
            2.0
        )
    else:
        cast(list[dict[str, object]], document["binaries"])[0]["fully_successful"] = 1
    path = workspace / "runs" / plan.run_id / "scoreboard.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="published score differs"):
        evaluation.publish(workspace, plan.run_id)


def test_terminal_record_must_match_the_published_record_shape(
    publication_plan: tuple[Path, RunPlan],
) -> None:
    import json

    workspace, plan = publication_plan
    key = task_key(plan.binaries[0])
    path = workspace / "runs" / plan.run_id / "results" / f"{key}.json"
    record = read_json(path)
    del record["pending"]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="terminal result differs"):
        evaluation.publish(workspace, plan.run_id)


def test_replay_cannot_publish_an_active_source_run(
    publication_plan: tuple[Path, RunPlan],
) -> None:
    import fcntl

    workspace, plan = publication_plan
    source = workspace / "runs" / plan.run_id
    record = read_json(source / "plan.json")
    cast(dict[str, object], record["configuration"])["source_branch_coverage"] = {}
    (source / "plan.json").write_text(json.dumps(record))
    with (source / "evaluation.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="still active"):
            evaluation.evaluate(
                workspace,
                "active-source-replay",
                Selection(),
                True,
                replay_id=plan.run_id,
            )
    assert not (source / "scoreboard.json").exists()


def test_replay_of_replay_restores_an_archived_ancestor(
    harness: tuple[Path, tuple[DevBinary, ...]],
) -> None:
    from phoenix_eval.run_archive import archive_run

    workspace, _ = harness
    original = evaluation.evaluate(workspace, "ancestor", Selection(), True)
    first = evaluation.evaluate(
        workspace, "first-descendant", Selection(), True, replay_id="ancestor"
    )
    archive_run(workspace, "ancestor")
    assert not (workspace / "runs/ancestor").exists()
    second = evaluation.evaluate(
        workspace,
        "second-descendant",
        Selection(),
        True,
        replay_id="first-descendant",
    )
    assert second["reproduced"] is True
    assert second["success"] == first["success"] == original["success"]
    assert (workspace / "runs/ancestor").is_dir()
