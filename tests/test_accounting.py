import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Model, ProviderError, Request, Usage
from phoenix_eval import m1
from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.corpus import Variant
from phoenix_eval.integrity import IntegrityError
from phoenix_eval.model_ledger import freeze_identity
from phoenix_eval.pair import PairReport
from phoenix_eval.submission import Submission, freeze_project, project_path
from phoenix_eval.toolchain import Compiler


class Provider:
    name = "synthetic"

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: Request) -> Completion:
        return Completion("answer", Usage(5, 2, 3), request.model)


@pytest.mark.parametrize("operation", ["call", "summary"])
def test_completed_attempt_cannot_be_retried(tmp_path: Path, operation: str) -> None:
    ledger = Ledger(tmp_path)
    request = Request("synthetic")
    ledger.call("case", request, Provider())
    start = json.loads(ledger.path.read_text().splitlines()[0])
    with ledger.path.open("a") as stream:
        stream.write(
            json.dumps({**start, "state": "retry", "cost_nanodollars": 0}) + "\n"
        )
    with pytest.raises(ProviderError):
        if operation == "call":
            ledger.call("case", request, Provider(), replay=True)
        else:
            ledger.summary("case")


def test_live_model_mismatch_keeps_reservation(tmp_path: Path) -> None:
    class WrongModel(Provider):
        def complete(self, request: Request) -> Completion:
            return Completion("answer", Usage(5, 2, 3), Model.ASTRA)

    ledger = Ledger(tmp_path)
    with pytest.raises(ProviderError):
        ledger.call("case", Request("synthetic"), WrongModel())
    assert ledger.summary("case").unknown_cost_reservations == 120_000
    assert ledger.summary("case").calls == 0


@pytest.mark.parametrize("failed", [False, True])
def test_measurement_uses_ledger_for_all_submissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    original = b"synthetic original"
    task = m1.Task(
        Variant(
            "fixture", Compiler.GCC, "-O0", sha256(original).hexdigest(), "synthetic"
        ),
        "phoenix",
    )
    ledger = Ledger(tmp_path / "runs/pipeline")
    ledger.call(task.key, Request("synthetic"), Provider())
    run = tmp_path / "evaluation"
    freeze_identity(tmp_path, run, "pipeline")
    project = project_path(tmp_path, "pipeline", task.key)
    (project / "src").mkdir(parents=True)
    (project / "src/program.c").write_text("int main(void) { return 0; }\n")
    (project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    report = {
        "sha256": task.variant.sha256,
        "method": "phoenix",
        "llm": {"cost_nanodollars": 0},
        "wall_seconds": 1,
    }
    (project / "phoenix_report.json").write_text(json.dumps(report))
    directory = run / "submissions" / task.key
    directory.mkdir(parents=True)
    submission = Submission("phoenix", task.key, None, "pipeline-failed")
    if not failed:
        submission = replace(
            submission,
            source_sha256=freeze_project(project, directory / "project"),
            category=None,
        )
        # Bind the synthetic report without calling the pipeline.
        content = (project / "phoenix_report.json").read_bytes()
        (directory / "report.json").write_bytes(content)
        if "report_sha256" in Submission.__dataclass_fields__:
            submission = replace(submission, report_sha256=sha256(content).hexdigest())
    monkeypatch.setattr(
        m1, "evaluate_pair", lambda *_: PairReport(1, 1, 0, 0, {}, 1, 1, (), True)
    )

    def unavailable(*_: object) -> None:
        raise IntegrityError("Synthetic checker failure.")

    monkeypatch.setattr(m1, "inspect_project", unavailable)
    config = cast(m1._Configuration, {"worker_images": {}, "checker_images": {}})
    result = m1._measure(
        tmp_path, run, "pipeline", task, submission, original, (), config
    )
    assert result["model"] == {
        "calls": 1,
        "usage": {"input_tokens": 5, "cached_input_tokens": 2, "output_tokens": 3},
        "cost_nanodollars": 36_200,
        "unknown_cost_reservations": 0,
    }
    report["wall_seconds"] = 999
    (project / "phoenix_report.json").write_text(json.dumps(report))
    after = m1._measure(
        tmp_path, run, "pipeline", task, submission, original, (), config
    )
    assert after == result


@pytest.mark.parametrize("terminal", ["completed", "retry", "failed", "limit-exceeded"])
@pytest.mark.parametrize("following", ["started", "completed", "retry", "failed"])
def test_terminal_attempt_rejects_all_later_events(
    tmp_path: Path, terminal: str, following: str
) -> None:
    ledger = Ledger(tmp_path)
    ledger.call("case", Request("synthetic"), Provider())
    start, completed = [
        json.loads(line) for line in ledger.path.read_text().splitlines()
    ]
    if terminal == "limit-exceeded":
        start["cost_nanodollars"] = 1
    end = {**start, "state": terminal}
    if terminal in ("completed", "limit-exceeded"):
        end = {**completed, "state": terminal}
    ledger.path.write_text("".join(json.dumps(event) + "\n" for event in (start, end)))
    ledger.summary("case")
    with ledger.path.open("a") as stream:
        stream.write(json.dumps({**start, "state": following}) + "\n")
    with pytest.raises(ProviderError):
        ledger.summary("another-task")


@pytest.mark.parametrize(
    "change", ["binary", "provider", "request", "cost", "orphan", "duplicate"]
)
def test_attempt_history_rejects_rewritten_start_or_terminal(
    tmp_path: Path, change: str
) -> None:
    ledger = Ledger(tmp_path)
    ledger.call("case", Request("synthetic"), Provider())
    start, completed = [
        json.loads(line) for line in ledger.path.read_text().splitlines()
    ]
    end = {**start, "state": "failed"}
    events = [start, end]
    if change in ("binary", "provider"):
        end[change] = "other"
    elif change == "request":
        end["request"] = {**start["request"], "prompt": "other"}
    elif change == "cost":
        end["cost_nanodollars"] = 0
    elif change == "orphan":
        events = [completed]
    else:
        events = [start, start]
    ledger.path.write_text("".join(json.dumps(event) + "\n" for event in events))
    with pytest.raises(ProviderError):
        ledger.summary("case")


def test_crash_and_failed_attempts_keep_budget_reservations(tmp_path: Path) -> None:
    from phoenix.llm.ledger import Budget, BudgetExceeded
    from phoenix_eval.model_ledger import bound_summary

    ledger = Ledger(tmp_path / "runs/pipeline", Budget(120_000, 120_000))
    request = Request("synthetic")
    ledger.call("case", request, Provider())
    start = ledger.path.read_text().splitlines()[0]
    ledger.path.write_text(start + "\n")
    assert ledger.summary("case").unknown_cost_reservations == 120_000
    with pytest.raises(BudgetExceeded):
        ledger.call("case", request, Provider())
    run = tmp_path / "evaluation"
    freeze_identity(tmp_path, run, "pipeline")
    assert bound_summary(tmp_path, run, "case").unknown_cost_reservations == 120_000
    assert bound_summary(tmp_path, run, "case-ghidra-raw").calls == 0
    assert bound_summary(tmp_path, run, "case-ghidra-raw").cost_nanodollars == 0


@pytest.mark.parametrize("model", list(Model))
@pytest.mark.parametrize("inputs", [0, 272_000, 272_001])
def test_shared_charges_match_provider_contract(model: Model, inputs: int) -> None:
    from phoenix.llm.provider import cost_nanodollars
    from phoenix_eval.model_ledger import TokenUsage, completion_charge

    assert completion_charge(
        model, TokenUsage(inputs, inputs // 2, 7)
    ) == cost_nanodollars(model, Usage(inputs, inputs // 2, 7))


@pytest.mark.parametrize(
    ("model", "inputs", "cached", "outputs", "expected"),
    (
        (Model.SOL, 100, 20, 10, 262_000),
        (Model.ASTRA, 100, 20, 10, 1_310_000),
        (Model.SOL, 272_001, 1_000, 100, 1_085_704_000),
        (Model.ASTRA, 272_001, 1_000, 100, 5_428_520_000),
    ),
)
def test_recorded_token_rates(
    model: Model, inputs: int, cached: int, outputs: int, expected: int
) -> None:
    from phoenix.llm.provider import cost_nanodollars

    assert cost_nanodollars(model, Usage(inputs, cached, outputs)) == expected


def test_bound_summary_rejects_a_changed_complete_log(tmp_path: Path) -> None:
    from phoenix_eval.model_ledger import bound_summary

    ledger = Ledger(tmp_path / "runs/pipeline")
    ledger.call("case", Request("synthetic"), Provider())
    run = tmp_path / "evaluation"
    freeze_identity(tmp_path, run, "pipeline")
    ledger.call("other", Request("synthetic"), Provider())
    with pytest.raises(ValueError, match="ledger changed"):
        bound_summary(tmp_path, run, "case")


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_tier", "priority"),
        ("usage", Usage(True, 0, 3)),
        ("usage", Usage(5, 2, cast(int, 3.5))),
        ("text", 42),
    ],
)
def test_live_completion_uses_cache_validation(
    tmp_path: Path, field: str, value: object
) -> None:
    class InvalidProvider(Provider):
        def complete(self, request: Request) -> Completion:
            completion = super().complete(request)
            object.__setattr__(completion, field, value)
            return completion

    ledger = Ledger(tmp_path)
    with pytest.raises(ProviderError, match="malformed or inconsistent"):
        ledger.call("case", Request("synthetic"), InvalidProvider())
    summary = ledger.summary("case")
    assert summary.calls == 0
    assert summary.unknown_cost_reservations == 120_000


def test_frozen_report_mutation_fails_closed(tmp_path: Path) -> None:
    from phoenix_eval.submission import (
        SubmissionError,
        freeze_package_report,
        read_package_report,
    )

    project = tmp_path / "project"
    project.mkdir()
    source = project / "phoenix_report.json"
    source.write_text('{"wall_seconds": 1, "llm": {"cost_nanodollars": 99}}')
    snapshot = tmp_path / "submission"
    snapshot.mkdir()
    digest = freeze_package_report(project, snapshot)
    source.write_text('{"wall_seconds": 999}')
    assert read_package_report(snapshot / "report.json", digest)["wall_seconds"] == 1
    (snapshot / "report.json").write_text(source.read_text())
    with pytest.raises(SubmissionError, match="changed after submission"):
        read_package_report(snapshot / "report.json", digest)


@pytest.mark.parametrize("mode", ["zero", "unknown", "exceeded"])
def test_failed_measurement_includes_reservations_and_limit_charges(
    tmp_path: Path, mode: str
) -> None:
    from phoenix.llm.ledger import BudgetExceeded
    from phoenix.llm.provider import RetryLater

    class AttemptProvider(Provider):
        def complete(self, request: Request) -> Completion:
            if mode == "unknown":
                raise RetryLater("Synthetic retry.", cost_unknown=True)
            return Completion("answer", Usage(5, 2, 20), request.model)

    task = m1.Task(
        Variant("fixture", Compiler.GCC, "-O0", "a" * 64, "synthetic"),
        "ghidra-raw" if mode == "zero" else "phoenix",
    )
    ledger = Ledger(tmp_path / "runs/pipeline")
    if mode != "zero":
        with pytest.raises((RetryLater, BudgetExceeded)):
            ledger.call(task.key, Request("synthetic"), AttemptProvider())
    run = tmp_path / "evaluation"
    freeze_identity(tmp_path, run, "pipeline")
    result = m1._measure(
        tmp_path,
        run,
        "pipeline",
        task,
        Submission(task.method, task.key, None, "pipeline-failed"),
        b"",
        (),
        cast(m1._Configuration, {}),
    )
    assert result["model"] == {
        "calls": 1 if mode == "exceeded" else 0,
        "usage": {
            "input_tokens": 5 if mode == "exceeded" else 0,
            "cached_input_tokens": 2 if mode == "exceeded" else 0,
            "output_tokens": 20 if mode == "exceeded" else 0,
        },
        "cost_nanodollars": 206_200 if mode == "exceeded" else 0,
        "unknown_cost_reservations": 120_000 if mode == "unknown" else 0,
    }


def test_measurement_uses_independently_frozen_identity(tmp_path: Path) -> None:
    from phoenix_eval.model_ledger import bound_summary

    ledger = Ledger(tmp_path / "runs/pipeline")
    ledger.call("case", Request("synthetic"), Provider())
    run = tmp_path / "evaluation"
    identity = freeze_identity(tmp_path, run, "pipeline")
    ledger.path.write_bytes(b"")
    (run / "model-ledger.json").write_text(
        json.dumps({**identity, "sha256": sha256(b"").hexdigest()})
    )
    with pytest.raises(ValueError, match="ledger changed"):
        bound_summary(tmp_path, run, "case", identity)
