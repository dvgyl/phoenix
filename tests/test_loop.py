"""Exercise loop publication with synthetic repositories and fixed run records."""

from __future__ import annotations

import fcntl
import hashlib
import importlib
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest

from phoenix.config import ROLE_MODELS
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Usage
from phoenix.llm.provider import Request as ModelRequest
from phoenix_eval import run as evaluation
from phoenix_eval import run_plan
from phoenix_eval.dev_corpus import DevBinary
from phoenix_eval.loop import (
    HEADER,
    Loop,
    Request,
    append_row,
    format_row,
    main,
    noise_document,
    revision,
    table,
)
from phoenix_eval.run_binary import task_key
from phoenix_eval.run_records import Selection

REAL_EVALUATE = evaluation.evaluate


class Provider:
    name = "fixture"

    def maximum_usage(self, request: ModelRequest) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: ModelRequest) -> Completion:
        return Completion("fixture", Usage(5, 0, 3), request.model)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def read(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_bytes()))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *args),
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        },
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


class SyntheticExecution:
    def __init__(self, checkout: Path):
        self.checkout = checkout
        self.calls: list[str] = []
        self.data = "data"
        self.heldout = "heldout"
        self.models = {"runtime": ROLE_MODELS["runtime"]}
        self.effort = {"runtime": "default"}
        self.stop = False
        self.crash = False
        self.after: Callable[[str], None] = lambda _: None
        self.outcome: Callable[[str, int], bool] = lambda _run, index: index % 2 == 0

    def noise_identity(self, workspace: Path) -> tuple[str, str]:
        return digest(self.data), digest(self.heldout)

    def configuration_identity(self) -> dict[str, object]:
        return {"models": dict(self.models), "effort": dict(self.effort)}

    def evaluate(
        self,
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        assert metadata is not None
        self.calls.append(run_id)
        binaries: list[dict[str, object]] = []
        results: list[dict[str, object]] = []
        counts: dict[str, int] = {}
        hashes: dict[str, str] = {}
        for tier in selection.tiers:
            for level in selection.levels:
                for compiler in ("gcc", "clang"):
                    for number in range(2):
                        index = len(binaries)
                        entry = DevBinary(
                            f"sample{tier.lower()}{number}",
                            tier,
                            compiler,
                            ("-std=c11", f"-{level}", "-lm"),
                            digest(f"{self.data}-{tier}-{level}-{compiler}-{number}"),
                            "fixture",
                            True,
                        )
                        binary = asdict(entry)
                        key = task_key(entry)
                        binaries.append(binary)
                        counts[key] = 2
                        hashes[key] = digest(f"{self.heldout}-{binary['name']}")
                        successful = self.outcome(run_id, index)
                        results.append(
                            {
                                **binary,
                                "task_key": key,
                                "heldout_hash": hashes[key],
                                "held_out_cases": [8 if successful else 0, 8],
                                "fully_successful": successful,
                                "categories": [] if successful else ["behavior_x86"],
                                "pending": False,
                            }
                        )
        corpus, heldout = self.noise_identity(workspace)
        run = workspace / "runs" / run_id
        write(
            run / "plan.json",
            {
                "run_id": run_id,
                "selection": asdict(selection),
                "binaries": binaries,
                "corpus_hash": corpus,
                "heldout_hash": heldout,
                "configuration": {
                    "revision": revision(self.checkout),
                    **metadata,
                    "case_counts": counts,
                    "case_hashes": hashes,
                },
                "llm_cache": llm_cache,
                "dependencies": [f"{run_id}-p", f"{run_id}-check"],
                "started": 0,
                "replay_of": None,
            },
        )
        for result in results[:1] if self.stop or self.crash else results:
            key = str(result["task_key"])
            Ledger(workspace / "runs" / f"{run_id}-p").call(
                key, ModelRequest("fixture"), Provider()
            )
            write(run / "results" / f"{key}.json", result)
        self.after(run_id)
        if self.crash:
            raise RuntimeError("Synthetic interruption after selection.")


@pytest.fixture
def environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Loop, SyntheticExecution]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "docs").mkdir()
    (checkout / "docs/STATUS.md").write_text("Milestone: R0, experiment 0 of 3\n")
    for source in ("phoenix", "phoenix_eval"):
        (checkout / source).mkdir()
        (checkout / source / "tracked.py").write_text("value = 1\n")
    git(checkout, "init", "-q")
    git(checkout, "config", "user.name", "Synthetic test")
    git(checkout, "config", "user.email", "synthetic@example.invalid")
    git(checkout, "add", ".")
    git(checkout, "commit", "-qm", "test: create synthetic repository")
    monkeypatch.setattr(evaluation, "CHECKOUT", checkout)
    execution = SyntheticExecution(checkout)
    monkeypatch.setattr(evaluation, "evaluate", execution.evaluate)
    monkeypatch.setattr(run_plan, "model_identity", execution.configuration_identity)
    monkeypatch.setattr(
        run_plan,
        "_selection",
        lambda workspace, _: ((), *execution.noise_identity(workspace)),
    )
    return Loop(tmp_path, checkout), execution


def test_exact_header_and_null_row() -> None:
    assert HEADER == (
        "| row | run_id | commit | corpus | data hash | loop | cache | milestone | "
        "exp | main metric | tier 0 | tier 1 | tier 2 | tier 3 | maintainable | "
        "held-out passed | integrity | edge cov | escape | literal % | goto/100 | "
        "cost median | free GiB |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    document: dict[str, object] = {
        "row": 1,
        "run_id": "example",
        "commit": "a" * 40,
        "corpus": "corpus_dev",
        "corpus_hash": "b" * 64,
        "heldout_hash": "c" * 64,
        "loop": "probe",
        "cache": "warm",
        "milestone": "R0",
        "experiment": None,
        "success": {"D0": {"O0": [2, 4], "O2": [0, 4], "Os": [1, 4]}},
        "held_out_cases": [24, 96],
        "integrity_failures": 1,
    }
    assert format_row(document) == (
        "| 1 | example | aaaaaaaaaaaa | corpus_dev | bbbbbbbb/cccccccc | "
        "probe | warm | R0 | - | D0 -O0 binary success rate = 50% (gate 80%) | "
        "O0 2/4; O2 0/4; Os 1/4 | - | - | - | "
        "- | 24/96 | 1 | - | - | - | - | - | - |\n"
    )


def test_publication_is_idempotent_and_preserves_cost(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    request = Request(label="measured example")
    document = loop.execute(request, "same-id")
    scoreboard = loop.scoreboard.read_bytes()
    published = (loop.workspace / "runs/same-id/scoreboard.json").read_bytes()
    assert loop.execute(request, "same-id") == document
    assert execution.calls == ["same-id"]
    assert loop.scoreboard.read_bytes() == scoreboard
    assert (loop.workspace / "runs/same-id/scoreboard.json").read_bytes() == published
    assert document["experiment"] == [1, 3]
    assert cast(dict[str, object], document["cost_usd"])["D0"] == {
        "median": 0.00004,
        "q1": 0.00004,
        "q3": 0.00004,
    }
    plan = read(loop.workspace / "runs/same-id/plan.json")
    assert cast(dict[str, object], plan["configuration"])["label"] == "measured example"


def test_conflicting_id_does_not_evaluate(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    loop.execute(Request(), "existing")
    with pytest.raises(ValueError, match="conflicting"):
        loop.execute(Request(label="changed"), "existing")
    with pytest.raises(ValueError, match="conflicting"):
        loop.execute(Request(kind="probe"), "existing")
    assert len(execution.calls) == 1


def test_duplicate_and_conflicting_rows(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, _ = environment
    document = loop.execute(Request(), "example")
    with pytest.raises(ValueError, match="conflicting"):
        append_row(loop.scoreboard, {**document, "integrity_failures": 99})
    loop.scoreboard.write_text(
        loop.scoreboard.read_text() + format_row({**document, "row": 2})
    )
    with pytest.raises(ValueError, match="Duplicate"):
        table(loop.scoreboard)


def test_stopped_run_keeps_every_denominator(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.stop = True
    document = loop.execute(Request(), "stopped")
    assert document["run_state"] == "stopped"
    assert document["success"] == {
        tier: {
            level: [1 if tier == "D0" and level == "O0" else 0, 4]
            for level in ("O0", "O2", "Os")
        }
        for tier in ("D0", "D1")
    }
    assert document["held_out_cases"] == [8, 192]
    assert document["failure_categories"] == {"pipeline_error": 23}
    execution.stop = False
    assert loop.execute(Request(), "stopped") == document
    assert execution.calls == ["stopped"]


def test_active_recovery_publishes_before_new_work(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError, match="interruption"):
        loop.execute(Request(), "abandoned")
    assert loop.active.exists()
    assert not loop.scoreboard.exists()
    execution.crash = False

    def observe(_: str) -> None:
        rows = table(loop.scoreboard)[1]
        assert len(rows) == 1
        assert rows[0][1] == "abandoned"
        assert (
            read(loop.workspace / "runs/abandoned/scoreboard.json")["run_state"]
            == "stopped"
        )

    execution.after = observe
    document = loop.execute(Request(), "next")
    assert document["experiment"] == [2, 3]
    assert [row[1] for row in table(loop.scoreboard)[1]] == ["abandoned", "next"]
    assert not loop.active.exists()


def test_crash_after_append_does_not_duplicate_row(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    document = loop.execute(Request(), "written")
    write(loop.active, {"schema": 1, "run_id": "written"})
    assert loop.execute(Request(), "written") == document
    assert len(table(loop.scoreboard)[1]) == 1
    assert execution.calls == ["written"]


@pytest.mark.parametrize("active", [{"schema": 99}, {"schema": 1, "run_id": "unknown"}])
def test_unknown_recovery_preserves_state(
    environment: tuple[Loop, SyntheticExecution], active: dict[str, object]
) -> None:
    loop, execution = environment
    write(loop.active, active)
    content = loop.active.read_bytes()
    with pytest.raises((ValueError, OSError)):
        loop.execute(Request(), "new")
    assert loop.active.read_bytes() == content
    assert not execution.calls


def test_missing_fixed_plan_does_not_erase_allocation(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError):
        loop.execute(Request(), "unselected")
    (loop.workspace / "runs/unselected/plan.json").unlink()
    with pytest.raises(ValueError, match="no fixed plan"):
        loop.execute(Request(), "new")
    assert loop.active.exists()


def test_full_budget_counts_failed_and_stopped_only_once(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.outcome = lambda _run, _index: False
    failed = loop.execute(Request(), "failed")
    assert failed["experiment"] == [1, 3]
    execution.stop = True
    stopped = loop.execute(Request(), "stopped")
    assert stopped["experiment"] == [2, 3]
    assert loop.execute(Request(), "stopped") == stopped
    for kind in ("probe", "quick"):
        assert loop.execute(Request(kind=kind), kind)["experiment"] is None
    assert loop.execute(Request(), "third")["experiment"] == [3, 3]
    with pytest.raises(ValueError, match="budget of 3"):
        loop.execute(Request(), "fourth")
    assert "fourth" not in execution.calls


def test_noise_flips_and_reference_without_committing_rows(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    full = loop.execute(Request(), "full")
    execution.outcome = lambda run, index: (
        not (run.endswith("-b") and index in (0, 1, 12))
    )
    noise = loop.execute(Request(kind="noise", llm_cache=False), "noise")
    assert noise["noise"] == {"D0": [2, 12], "D1": [1, 12]}
    assert noise["noise_rate"] == {"D0": 2.5 / 13, "D1": 1.5 / 13}
    assert noise["commit"] == full["commit"] == revision(loop.checkout)
    assert noise["quick_set"] == 1
    assert noise["experiment"] is None
    assert noise["dependencies"] == ["noise-a", "noise-b"]
    assert read(loop.workspace / "runs/noise/plan.json")["dependencies"] == [
        "noise-a",
        "noise-b",
    ]
    assert set(cast(dict[str, object], noise["child_cost_usd"])) == {
        "noise-a",
        "noise-b",
    }
    audit = cast(list[dict[str, object]], noise["binaries"])
    assert audit[0]["noise_outcomes"] == [True, False]
    assert audit[0]["sha256"] and audit[0]["heldout_hash"]
    assert [row[5] for row in table(loop.scoreboard)[1]] == ["full", "noise"]
    assert "| 2/12 | 1/12 | - | - |" in format_row(noise)
    assert loop.execute(Request(kind="noise", llm_cache=False), "noise") == noise
    assert len(execution.calls) == 3
    later = loop.execute(Request(), "later")
    assert later["noise_ref"] == 2
    assert later["experiment"] == [2, 3]


@pytest.mark.parametrize("change", ["commit", "binary", "heldout", "models", "effort"])
@pytest.mark.parametrize("when", ["-a", "-b"])
def test_changed_noise_commit_or_data_is_rejected(
    environment: tuple[Loop, SyntheticExecution], change: str, when: str
) -> None:
    loop, execution = environment

    def mutate(run_id: str) -> None:
        if not run_id.endswith(when):
            return
        if change == "commit":
            git(
                loop.checkout, "commit", "--allow-empty", "-qm", "test: change revision"
            )
        elif change == "binary":
            execution.data = "changed"
        elif change == "heldout":
            execution.heldout = "changed"
        elif change == "models":
            execution.models["runtime"] = "changed"
        else:
            execution.effort["runtime"] = "high"

    execution.after = mutate
    with pytest.raises(ValueError, match="changed during noise"):
        loop.execute(Request(kind="noise", llm_cache=False), "unstable")
    assert loop.active.exists()
    assert not loop.scoreboard.exists()
    with pytest.raises(ValueError):
        loop.execute(Request(kind="probe"), "new")
    assert not loop.scoreboard.exists()


def test_noise_rejects_different_frozen_binary_identity(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    loop.execute(Request(kind="quick", llm_cache=False), "left")
    execution.data = "changed"
    loop.execute(Request(kind="quick", llm_cache=False), "right")
    left = evaluation.publish(loop.workspace, "left")
    right = evaluation.publish(loop.workspace, "right")
    right.document["row"] = left.document["row"]
    with pytest.raises(ValueError, match="identities changed"):
        noise_document("noise", [left, right], execution.configuration_identity())


def test_noise_recovery_publishes_unstarted_trial_as_failures(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.crash = True
    request = Request(kind="noise", llm_cache=False)
    with pytest.raises(RuntimeError):
        loop.execute(request, "interrupted-noise")
    execution.crash = False
    document = loop.execute(request, "interrupted-noise")
    assert execution.calls == ["interrupted-noise-a"]
    assert document["run_state"] == "stopped"
    assert document["noise"] == {"D0": [1, 12], "D1": [0, 12]}
    assert read(loop.workspace / "runs/interrupted-noise-b/scoreboard.json")[
        "held_out_cases"
    ] == [0, 192]
    assert len(table(loop.scoreboard)[1]) == 1
    assert not loop.active.exists()


def test_quick_probe_is_not_an_experiment(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, _ = environment
    document = loop.execute(Request(kind="probe", quick=True), "quick-probe")
    assert document["loop"] == "probe"
    assert document["quick_set"] == 1
    assert document["experiment"] is None


def test_existing_unallocated_id_is_rejected(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    run = loop.workspace / "runs/existing"
    run.mkdir(parents=True)
    write(run / "untouched.json", {"cost": 19})
    with pytest.raises(ValueError, match="without a loop allocation"):
        loop.execute(Request(), "existing")
    assert read(run / "untouched.json") == {"cost": 19}
    assert not execution.calls


def test_existing_id_cannot_move_to_a_different_commit(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    loop.execute(Request(), "existing")
    git(loop.checkout, "commit", "--allow-empty", "-qm", "test: change revision")
    with pytest.raises(ValueError, match="conflicting request or commit"):
        loop.execute(Request(), "existing")
    assert execution.calls == ["existing"]


def test_fixed_plan_run_id_cannot_change(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError):
        loop.execute(Request(), "original")
    path = loop.workspace / "runs/original/plan.json"
    write(path, {**read(path), "run_id": "different"})
    with pytest.raises(ValueError, match="conflicting run ID"):
        loop.execute(Request(), "original")
    assert not loop.scoreboard.exists()
    assert loop.active.exists()


def test_hash_validation_precedes_row_publication(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment

    def corrupted(run_id: str) -> None:
        document = evaluation.publish(loop.workspace, run_id).document
        refs = cast(dict[str, object], document["result_refs"])
        refs[next(iter(refs))] = "f" * 64
        write(loop.workspace / "runs" / run_id / "scoreboard.json", document)

    execution.after = corrupted
    with pytest.raises(ValueError, match="terminal result changed"):
        loop.execute(Request(), "corrupt")
    assert not loop.scoreboard.exists()
    assert loop.active.exists()


def test_new_publication_normalizes_tuple_fields(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError):
        loop.execute(Request(), "stopped")
    document = loop.execute(Request(), "stopped")
    records = cast(list[dict[str, object]], document["binaries"])
    assert all(isinstance(record["flags"], list) for record in records)
    assert evaluation.publish(loop.workspace, "stopped").document == document
    assert document["run_state"] == "stopped"
    assert len(table(loop.scoreboard)[1]) == 1
    assert execution.calls == ["stopped"]


@pytest.mark.parametrize("source", ["phoenix", "phoenix_eval"])
@pytest.mark.parametrize("state", ["tracked", "staged", "untracked", "deleted"])
def test_dirty_source_is_rejected(
    environment: tuple[Loop, SyntheticExecution], source: str, state: str
) -> None:
    loop, execution = environment
    path = loop.checkout / source / "tracked.py"
    if state == "deleted":
        path.unlink()
    elif state == "untracked":
        (path.parent / "new.py").write_text("value = 2\n")
    else:
        path.write_text("value = 2\n")
        if state == "staged":
            git(loop.checkout, "add", str(path))
    with pytest.raises(ValueError, match="tracked and untracked"):
        loop.execute(Request(kind="probe"), "dirty")
    assert not execution.calls
    assert not loop.active.exists()


@pytest.mark.parametrize(
    "corruption",
    ["binary", "heldout", "denominator", "aggregate", "reference", "terminal"],
)
def test_corrupt_identity_or_denominator_is_rejected(
    environment: tuple[Loop, SyntheticExecution], corruption: str
) -> None:
    loop, _ = environment
    document = loop.execute(Request(), "record")
    run = loop.workspace / "runs/record"
    records = cast(list[dict[str, object]], document["binaries"])
    key = str(records[0]["task_key"])
    if corruption == "binary":
        records[0]["sha256"] = "f" * 64
    elif corruption == "heldout":
        records[0]["heldout_hash"] = "e" * 64
    elif corruption == "denominator":
        records[0]["held_out_cases"] = [8, 9]
    elif corruption == "aggregate":
        document["success"] = {"D0": {"O0": [1, 1]}}
    elif corruption == "reference":
        cast(dict[str, object], document["result_refs"])[key] = "f" * 64
    else:
        write(run / "results" / f"{key}.json", {**records[0], "extra": "changed"})
    write(run / "scoreboard.json", document)
    with pytest.raises(ValueError):
        evaluation.publish(loop.workspace, "record")


def test_workspace_lock_blocks_other_loop(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment
    runs = loop.workspace / "runs"
    runs.mkdir()
    with (runs / ".loop.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="Another workspace loop"):
            loop.execute(Request(), "blocked")
    assert not execution.calls


def test_loop_keeps_archive_lock_until_publication(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, execution = environment

    def attempt_archive(_: str) -> None:
        with (loop.workspace / "runs/.archive.lock").open("a+b") as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    execution.after = attempt_archive
    loop.execute(Request(kind="probe"), "protected")
    with (loop.workspace / "runs/.archive.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_cli_help_loads_without_evaluator(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    assert "--run-id" in capsys.readouterr().out


@pytest.mark.parametrize(
    "run_id", ["../escape", "m1-t0-reserved", "sealed/forbidden", ".", "x" * 97]
)
def test_invalid_run_id_has_no_run_writes(
    environment: tuple[Loop, SyntheticExecution], run_id: str
) -> None:
    loop, execution = environment
    with pytest.raises(ValueError):
        loop.execute(Request(), run_id)
    assert not execution.calls
    assert not loop.active.exists()


@pytest.mark.parametrize("kind", ["full", "noise"])
def test_real_preflight_failure_releases_only_unselected_run(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    loop, execution = environment
    monkeypatch.setattr(evaluation, "evaluate", REAL_EVALUATE)

    def unavailable(_: Path) -> dict[str, object]:
        raise ValueError("worker image unavailable")

    monkeypatch.setattr(evaluation, "_configuration", unavailable)
    request = Request(kind=kind, llm_cache=kind != "noise")
    with pytest.raises(ValueError, match="worker image unavailable"):
        loop.execute(request, "preflight-failed")
    assert not loop.active.exists()
    assert not loop.scoreboard.exists()
    failed = loop.workspace / "runs/preflight-failed/loop.json"
    record = read(failed)
    assert record["failure"] == ["ValueError", "worker image unavailable"]
    assert record["experiment"] == (1 if kind == "full" else None)
    content = failed.read_bytes()
    monkeypatch.setattr(evaluation, "evaluate", execution.evaluate)
    document = loop.execute(Request(), "after-preflight")
    assert document["row"] == 1
    assert document["experiment"] == [1, 3]
    assert failed.read_bytes() == content
    assert len(table(loop.scoreboard)[1]) == 1


@pytest.mark.parametrize(
    "artifact",
    [
        "unknown.json",
        "results/paid.json",
        "../unsafe-p/llm.jsonl",
        ".active",
        "../unsafe-check/paid.json",
        "plan.json",
        "loop.json",
    ],
)
def test_known_preselection_error_preserves_unknown_or_paid_state(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    loop, execution = environment
    path = loop.workspace / "runs/unsafe" / artifact

    def fail(
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        write(path, {"reserved_cost": 19})
        raise ValueError("Fixture preflight error with uncertain state.")

    monkeypatch.setattr(evaluation, "evaluate", fail)
    with pytest.raises(ValueError, match="uncertain state"):
        loop.execute(Request(), "unsafe")
    active, content = loop.active.read_bytes(), path.read_bytes()
    if artifact != "loop.json":
        assert read(loop.workspace / "runs/unsafe/loop.json")["failure"] is None
    with pytest.raises((ValueError, KeyError)):
        loop.execute(Request(), "new")
    assert loop.active.read_bytes() == active
    assert path.read_bytes() == content
    assert not loop.scoreboard.exists()


def test_known_error_after_selection_preserves_plan_and_experiment(
    environment: tuple[Loop, SyntheticExecution], monkeypatch: pytest.MonkeyPatch
) -> None:
    loop, execution = environment
    evaluate = evaluation.evaluate

    def fail(
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        evaluate(workspace, run_id, selection, llm_cache, metadata=metadata)
        raise ValueError("Fixture error after selection.")

    monkeypatch.setattr(evaluation, "evaluate", fail)
    with pytest.raises(ValueError, match="after selection"):
        loop.execute(Request(), "fixed")
    run = loop.workspace / "runs/fixed"
    original = (run / "plan.json").read_bytes()
    assert loop.active.exists()
    assert read(run / "loop.json")["failure"] is None
    monkeypatch.setattr(evaluation, "evaluate", evaluate)
    assert loop.execute(Request(), "fixed")["experiment"] == [1, 3]
    assert (run / "plan.json").read_bytes() == original


def test_unknown_exception_before_selection_keeps_active_pointer(
    environment: tuple[Loop, SyntheticExecution], monkeypatch: pytest.MonkeyPatch
) -> None:
    loop, execution = environment

    def fail(
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        raise RuntimeError("Fixture unknown interruption.")

    monkeypatch.setattr(evaluation, "evaluate", fail)
    with pytest.raises(RuntimeError, match="unknown interruption"):
        loop.execute(Request(), "unknown-error")
    active = loop.active.read_bytes()
    with pytest.raises(ValueError, match="no fixed plan"):
        loop.execute(Request(), "new")
    assert loop.active.read_bytes() == active
    assert read(loop.workspace / "runs/unknown-error/loop.json")["failure"] is None


@pytest.mark.parametrize("paid_after_record", [False, True])
def test_preselection_record_recovery_rechecks_work_before_clearing_pointer(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
    paid_after_record: bool,
) -> None:
    loop, execution = environment
    evaluate = evaluation.evaluate

    def fail(
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        raise ValueError("Fixture preflight failure.")

    monkeypatch.setattr(evaluation, "evaluate", fail)
    with pytest.raises(ValueError, match="preflight failure"):
        loop.execute(Request(), "preflight")
    write(loop.active, {"schema": 1, "run_id": "preflight"})
    monkeypatch.setattr(evaluation, "evaluate", evaluate)
    if paid_after_record:
        path = loop.workspace / "runs/preflight-p/llm.jsonl"
        write(path, {"reserved_cost": 19})
        with pytest.raises(ValueError, match="Unknown preselection"):
            loop.execute(Request(), "new")
        assert loop.active.exists()
        assert read(path) == {"reserved_cost": 19}
        assert not execution.calls
    else:
        document = loop.execute(Request(), "new")
        assert document["row"] == 1
        assert document["experiment"] == [1, 3]
        assert not loop.active.exists()


def test_noise_reference_requires_current_quick_set(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, _ = environment
    noise = loop.execute(Request(kind="noise", llm_cache=False), "noise")
    write(loop.workspace / "runs/noise/scoreboard.json", {**noise, "quick_set": 2})
    assert loop.execute(Request(), "changed")["noise_ref"] is None


@pytest.mark.parametrize("change", ["corpus", "heldout", "models", "effort"])
def test_noise_reference_requires_current_identity(
    environment: tuple[Loop, SyntheticExecution], change: str
) -> None:
    loop, execution = environment
    loop.execute(Request(kind="noise", llm_cache=False), "old-noise")
    if change == "corpus":
        execution.data = "changed"
    elif change == "heldout":
        execution.heldout = "changed"
    elif change == "models":
        execution.models["runtime"] = "changed"
    else:
        execution.effort["runtime"] = "high"
    document = loop.execute(Request(), "changed")
    assert document["noise_ref"] is None


def test_noise_reference_can_use_an_earlier_commit(
    environment: tuple[Loop, SyntheticExecution],
) -> None:
    loop, _ = environment
    noise = loop.execute(Request(kind="noise", llm_cache=False), "old-noise")
    git(loop.checkout, "commit", "--allow-empty", "-qm", "test: change revision")
    document = loop.execute(Request(), "later")
    assert document["commit"] != noise["commit"]
    assert document["noise_ref"] == noise["row"]


def test_real_noise_recovery_keeps_empty_model_trial_and_paid_cost(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phoenix.config import ROLE_MODELS
    from phoenix.llm.ledger import Ledger
    from phoenix.llm.provider import Completion, Usage
    from phoenix.llm.provider import Request as ModelRequest
    from phoenix_eval.submission import EvaluationPending

    loop, execution = environment
    from phoenix_eval import run_records as records

    corpus = importlib.import_module("phoenix_eval.dev_corpus")
    binary_module = importlib.import_module("phoenix_eval.run_binary")
    resources = importlib.import_module("phoenix_eval.run_resources")
    binaries = tuple(
        corpus.DevBinary(
            f"sample{tier.lower()}{number}",
            tier,
            compiler,
            ("-std=c11", f"-{level}", "-lm"),
            digest(f"{tier}{level}{compiler}{number}"),
            "fixture",
            True,
        )
        for tier in ("D0", "D1")
        for level in ("O0", "O2", "Os")
        for compiler in ("gcc", "clang")
        for number in range(2)
    )
    monkeypatch.setattr(evaluation, "CHECKOUT", loop.checkout)
    monkeypatch.setattr(
        evaluation, "_configuration", lambda _: {"revision": revision(loop.checkout)}
    )
    monkeypatch.setattr(
        evaluation,
        "_selection",
        lambda *_: (binaries, *execution.noise_identity(loop.workspace)),
    )
    monkeypatch.setattr(evaluation, "load_validated_cases", lambda *_: None)
    monkeypatch.setattr(
        evaluation, "case_identity", lambda _, item, __: (2, digest(item.name))
    )
    monkeypatch.setattr(evaluation, "adequacy_snapshot", lambda *_: {})
    for method in ("start", "finish", "sample"):
        monkeypatch.setattr(resources.Resources, method, lambda _: None)
    monkeypatch.setenv("PHOENIX_JOBS", "1")

    class Provider:
        name = "fixture"

        def maximum_usage(self, request: ModelRequest) -> Usage:
            return Usage(10, 0, 10)

        def complete(self, request: ModelRequest) -> Completion:
            return Completion("fixture", Usage(5, 0, 3), request.model)

    def measure(
        workspace: Path, run: Path, item: DevBinary, plan: object, replay: object
    ) -> object:
        if item != binaries[0]:
            raise EvaluationPending("Fixture interruption.")
        key = str(binary_module.task_key(item))
        Ledger(workspace / "runs" / f"{run.name}-p").call(
            key, ModelRequest("fixture"), Provider()
        )
        return records.BinaryResult(
            item,
            True,
            (),
            (8, 8),
            False,
            {"task_key": key, "heldout_hash": digest(binaries[0].name)},
        )

    monkeypatch.setattr(evaluation, "measure", measure)

    def interrupted(
        workspace: Path,
        run_id: str,
        selection: Selection,
        llm_cache: bool,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        REAL_EVALUATE(workspace, run_id, selection, llm_cache, metadata=metadata)
        raise RuntimeError("Fixture stop between trials.")

    monkeypatch.setattr(evaluation, "evaluate", interrupted)
    request = Request(kind="noise", llm_cache=False)
    with pytest.raises(RuntimeError, match="between trials"):
        loop.execute(request, "real-noise")
    paid = loop.workspace / "runs/real-noise-a/scoreboard.json"
    original = paid.read_bytes()
    ledger = paid.parent / "published-ledger.jsonl"
    charges = ledger.read_bytes()
    assert any(
        json.loads(line)["cost_nanodollars"] > 0 for line in charges.splitlines()
    )
    document = loop.execute(request, "real-noise")
    assert paid.read_bytes() == original
    assert ledger.read_bytes() == charges
    assert document["run_state"] == "stopped"
    assert document["noise"] == {"D0": [1, 12], "D1": [0, 12]}
    unstarted = read(loop.workspace / "runs/real-noise-b/scoreboard.json")
    assert unstarted["models"] == {"runtime": []}
    assert unstarted["held_out_cases"] == [0, 192]
    assert unstarted["failure_categories"] == {"pipeline_error": 24}
    assert unstarted["success"] == {
        tier: {level: [0, 4] for level in ("O0", "O2", "Os")} for tier in ("D0", "D1")
    }
    assert document["child_models"] == {
        "real-noise-a": {"runtime": [ROLE_MODELS["runtime"]]},
        "real-noise-b": {"runtime": []},
    }
    assert (
        cast(dict[str, object], document["child_cost_usd"])["real-noise-a"]
        == read(paid)["cost_usd"]
    )
    assert not loop.active.exists()
    assert len(table(loop.scoreboard)[1]) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("extra", "unknown"),
        ("row", "1"),
        ("row", None),
        ("experiment", True),
        ("noise_ref", 1),
        ("failure", ["ValueError"]),
        ("failure", {"type": "unknown"}),
        ("noise_verified", True),
        ("noise_verified", "unknown"),
        ("noise_data", ["a" * 64, "b" * 64]),
        ("checkout", "/unknown"),
        ("run_id", "other"),
        ("request", {"kind": "unknown"}),
    ],
)
def test_unknown_claim_blocks_recovery_without_changes(
    environment: tuple[Loop, SyntheticExecution], field: str, value: object
) -> None:
    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError):
        loop.execute(Request(), "unknown-claim")
    path = loop.workspace / "runs/unknown-claim/loop.json"
    write(path, {**read(path), field: value})
    active, claim = loop.active.read_bytes(), path.read_bytes()
    with pytest.raises((ValueError, KeyError)):
        loop.execute(Request(), "new")
    assert loop.active.read_bytes() == active
    assert path.read_bytes() == claim
    assert execution.calls == ["unknown-claim"]
    assert not loop.scoreboard.exists()


@pytest.mark.parametrize("phase", ["failure", "noise_data", "noise_verified"])
def test_interrupted_claim_update_preserves_the_allocation(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    from phoenix_eval import loop as module

    loop, execution = environment
    atomic = module._atomic

    def interrupted(path: Path, content: bytes) -> None:
        if path.name == "loop.json":
            record = json.loads(content)
            if record[phase] not in (None, False):
                raise RuntimeError("Fixture interruption before claim update.")
        atomic(path, content)

    monkeypatch.setattr(module, "_atomic", interrupted)
    if phase == "failure":

        def fail(*args: object, **kwargs: object) -> None:
            raise ValueError("Fixture preselection failure.")

        monkeypatch.setattr(evaluation, "evaluate", fail)
    request = Request(kind="noise", llm_cache=False)
    with pytest.raises(RuntimeError, match="before claim update"):
        loop.execute(request, "claim-update")
    assert loop.active.exists()
    allocation = loop.workspace / "runs/claim-update/loop.json"
    assert read(allocation)[phase] in (None, False)
    monkeypatch.setattr(module, "_atomic", atomic)
    if phase == "noise_verified":
        calls = list(execution.calls)
        document = loop.execute(request, "claim-update")
        assert document["row"] == 1
        assert execution.calls == calls
    else:
        content = allocation.read_bytes()
        with pytest.raises(ValueError, match="no fixed plan"):
            loop.execute(Request(), "new")
        assert allocation.read_bytes() == content
        assert loop.active.exists()


@pytest.mark.parametrize("boundary", ["child", "parent", "markdown"])
def test_noise_publication_recovers_each_boundary_without_execution(
    environment: tuple[Loop, SyntheticExecution],
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    from phoenix_eval import loop as module

    loop, execution = environment
    atomic = module._atomic

    def interrupted(path: Path, content: bytes) -> None:
        if (
            boundary == "child"
            and path.name == "loop.json"
            and json.loads(content)["noise_verified"]
            or boundary == "parent"
            and path.name == "scoreboard.json"
            or boundary == "markdown"
            and path == loop.scoreboard
        ):
            raise RuntimeError("Fixture publication interruption.")
        atomic(path, content)

    monkeypatch.setattr(module, "_atomic", interrupted)
    request = Request(kind="noise", llm_cache=False)
    with pytest.raises(RuntimeError, match="publication interruption"):
        loop.execute(request, "publication")
    assert loop.active.exists()
    child = loop.workspace / "runs/publication-a/scoreboard.json"
    child_bytes = child.read_bytes()
    charges = (child.parent / "published-ledger.jsonl").read_bytes()
    calls = list(execution.calls)
    monkeypatch.setattr(module, "_atomic", atomic)
    if boundary != "child":
        execution.data = "changed after verification"
    document = loop.execute(request, "publication")
    assert document["row"] == 1
    assert document["noise"] == {"D0": [0, 12], "D1": [0, 12]}
    assert child.read_bytes() == child_bytes
    assert (child.parent / "published-ledger.jsonl").read_bytes() == charges
    assert execution.calls == calls
    assert len(table(loop.scoreboard)[1]) == 1
    assert not loop.active.exists()


@pytest.mark.parametrize(
    "artifact", ["unknown.json", "../noise-b-p/llm.jsonl", ".active"]
)
def test_unstarted_noise_trial_preserves_unknown_work(
    environment: tuple[Loop, SyntheticExecution], artifact: str
) -> None:
    loop, execution = environment
    execution.crash = True
    request = Request(kind="noise", llm_cache=False)
    with pytest.raises(RuntimeError):
        loop.execute(request, "noise")
    path = loop.workspace / "runs/noise-b" / artifact
    write(path, {"reserved_cost": 19})
    content = path.read_bytes()
    with pytest.raises(ValueError, match="Unknown unfinished noise child"):
        loop.execute(request, "noise")
    assert path.read_bytes() == content
    assert not (loop.workspace / "runs/noise-b/plan.json").exists()
    assert loop.active.exists()
    assert not loop.scoreboard.exists()
    assert execution.calls == ["noise-a"]


def test_loop_rejects_replay_before_archive_restore(
    environment: tuple[Loop, SyntheticExecution], monkeypatch: pytest.MonkeyPatch
) -> None:
    from phoenix_eval import run_archive

    loop, execution = environment
    execution.crash = True
    with pytest.raises(RuntimeError):
        loop.execute(Request(), "replay")
    path = loop.workspace / "runs/replay/plan.json"
    write(path, {**read(path), "replay_of": "missing-ancestor"})

    def restore(*args: object) -> None:
        pytest.fail("Archive restore under the shared loop archive lock.")

    monkeypatch.setattr(run_archive, "restore_run", restore)
    content = path.read_bytes()
    with pytest.raises(ValueError, match="cannot use a replay plan"):
        loop.execute(Request(), "new")
    assert path.read_bytes() == content
    assert loop.active.exists()
    assert not loop.scoreboard.exists()
    assert execution.calls == ["replay"]
