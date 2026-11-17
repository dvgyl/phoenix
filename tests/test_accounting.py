import json
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix.config import ROLE_MODELS
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, ProviderError, Request, Usage
from phoenix_eval.model_ledger import summarize
from phoenix_eval.run_records import capture_ledger, read_ledger


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
            return Completion("answer", Usage(5, 2, 3), ROLE_MODELS["strongest"])

    ledger = Ledger(tmp_path)
    with pytest.raises(ProviderError):
        ledger.call("case", Request("synthetic"), WrongModel())
    assert ledger.summary("case").unknown_cost_reservations == 120_000
    assert ledger.summary("case").calls == 0


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

    ledger = Ledger(tmp_path / "runs/pipeline", Budget(120_000, 120_000))
    request = Request("synthetic")
    ledger.call("case", request, Provider())
    start = ledger.path.read_text().splitlines()[0]
    ledger.path.write_text(start + "\n")
    assert ledger.summary("case").unknown_cost_reservations == 120_000
    with pytest.raises(BudgetExceeded):
        ledger.call("case", request, Provider())
    run = tmp_path / "evaluation"
    run.mkdir()
    snapshot = capture_ledger(tmp_path, run, "pipeline")
    assert read_ledger(tmp_path, run) == snapshot
    assert summarize(snapshot.events, "case").unknown_cost_reservations == 120_000
    baseline = summarize(snapshot.events, "case-ghidra-raw")
    assert baseline.calls == 0
    assert baseline.cost_nanodollars == 0
    assert baseline.unknown_cost_reservations == 0


@pytest.mark.parametrize("model", list(ROLE_MODELS.values()))
@pytest.mark.parametrize("inputs", [0, 272_000, 272_001])
def test_shared_charges_match_provider_contract(model: str, inputs: int) -> None:
    from phoenix.llm.provider import cost_nanodollars
    from phoenix_eval.model_ledger import TokenUsage, completion_charge

    assert completion_charge(
        model, TokenUsage(inputs, inputs // 2, 7)
    ) == cost_nanodollars(model, Usage(inputs, inputs // 2, 7))


@pytest.mark.parametrize(
    ("model", "inputs", "cached", "outputs", "expected"),
    (
        (ROLE_MODELS["runtime"], 100, 20, 10, 262_000),
        (ROLE_MODELS["strongest"], 100, 20, 10, 1_048_000),
        (ROLE_MODELS["runtime"], 272_001, 1_000, 100, 1_085_704_000),
        (ROLE_MODELS["strongest"], 272_001, 1_000, 100, 4_342_816_000),
    ),
)
def test_recorded_token_rates(
    model: str, inputs: int, cached: int, outputs: int, expected: int
) -> None:
    from phoenix.llm.provider import cost_nanodollars

    assert cost_nanodollars(model, Usage(inputs, cached, outputs)) == expected


def test_published_summary_keeps_cost_when_valid_events_append(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "runs/pipeline")
    ledger.call("case", Request("synthetic"), Provider())
    run = tmp_path / "evaluation"
    run.mkdir()
    snapshot = capture_ledger(tmp_path, run, "pipeline")
    prefix = snapshot.content
    assert summarize(snapshot.events, "case").cost_nanodollars == 36_200
    ledger.call("other", Request("synthetic"), Provider())
    assert read_ledger(tmp_path, run).content == prefix
    saved = capture_ledger(tmp_path, run, "pipeline")
    assert saved == snapshot
    assert {event.binary for event in saved.events} == {"case"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("service_tier", "priority"),
        ("usage.input_tokens", True),
        ("usage.output_tokens", 3.5),
        ("text", 42),
    ],
)
def test_live_completion_uses_cache_validation(
    tmp_path: Path, field: str, value: object
) -> None:
    class InvalidProvider(Provider):
        def complete(self, request: Request) -> Completion:
            completion = super().complete(request)
            if field.startswith("usage."):
                object.__setattr__(completion.usage, field.split(".")[1], value)
            else:
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

    key = "fixture-gcc-O0"
    ledger = Ledger(tmp_path / "runs/pipeline")
    if mode != "zero":
        with pytest.raises((RetryLater, BudgetExceeded)):
            ledger.call(key, Request("synthetic"), AttemptProvider())
    run = tmp_path / "evaluation"
    from dataclasses import asdict

    run.mkdir()
    snapshot = capture_ledger(tmp_path, run, "pipeline")
    result = {"model": asdict(summarize(snapshot.events, key))}
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


def test_replay_uses_independent_published_prefix(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "runs/pipeline")
    ledger.call("case", Request("synthetic"), Provider())
    run = tmp_path / "evaluation"
    run.mkdir()
    snapshot = capture_ledger(tmp_path, run, "pipeline")
    prefix = snapshot.content
    assert summarize(snapshot.events, "case").cost_nanodollars == 36_200
    ledger.path.write_bytes(b"")
    (run / "published-ledger.jsonl").write_bytes(b"")
    (run / "published-ledger.json").write_text(
        json.dumps(
            {"pipeline_run": "pipeline", "bytes": 0, "sha256": sha256(b"").hexdigest()}
        )
    )
    replay = tmp_path / "replay"
    replay.mkdir()
    with pytest.raises(ValueError, match="published prefix"):
        capture_ledger(tmp_path, replay, "pipeline", prefix=prefix)
