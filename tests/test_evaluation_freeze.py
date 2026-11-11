import io
import json
import os
import tarfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phoenix_eval import capture_binding, m1, submission
from phoenix_eval.build import PROJECT_CMAKE, project_files
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Variant, heldout_cases
from phoenix_eval.m1 import _measure as measure_submission
from phoenix_eval.model_ledger import (
    LedgerIdentity,
    bound_summaries,
    bound_summary,
    freeze_identity,
    read_events,
)
from phoenix_eval.submission import Method, Submission, source_digest
from phoenix_eval.toolchain import Compiler
from phoenix_eval.wire import encode_invocation


@pytest.mark.parametrize("phase", ["capturing", "frozen"])
@pytest.mark.parametrize(
    "change", ["boolean", "float", "duplicate-schema", "duplicate-phase"]
)
def test_malformed_capture_binding_stops_before_archive_access(
    engine: "SyntheticEngine", phase: str, change: str
) -> None:
    report = engine.run / "m1.json"
    if phase == "capturing":
        engine.interrupt_after = 3
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
        engine.interrupt_after = None
        before = None
    else:
        m1.evaluate_t0(engine.workspace, "initial")
        before = report.read_bytes()
    path = engine.run / "capture-binding.json"
    content = path.read_text()
    replacements = {
        "boolean": ('"schema": 1', '"schema": true'),
        "float": ('"schema": 1', '"schema": 1.0'),
        "duplicate-schema": ('"schema": 1', '"schema": 99, "schema": 1'),
        "duplicate-phase": (
            f'"phase": "{phase}"',
            f'"phase": "invalid", "phase": "{phase}"',
        ),
    }
    original, replacement = replacements[change]
    assert content.count(original) == 1
    path.write_text(content.replace(original, replacement))
    engine.opened.clear()
    with pytest.raises(ValueError, match="capture binding"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    if before is None:
        assert not report.exists()
    else:
        assert report.read_bytes() == before


@pytest.mark.parametrize(
    "field,value", [("budget_binary", 5_000_000_000.0), ("astra_repair", 0)]
)
@pytest.mark.parametrize("resume", [False, True])
def test_saved_configuration_preserves_json_types(
    engine: "SyntheticEngine", field: str, value: object, resume: bool
) -> None:
    config = m1._configuration(engine.workspace, "synthetic")
    config["pipeline_settings"] = {
        "budget_binary": 5_000_000_000,
        "astra_repair": False,
    }
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    document = json.loads(report.read_text())
    document["configuration"]["pipeline_settings"][field] = value
    report.write_text(json.dumps(document))
    before = report.read_bytes()
    submitted = len(engine.submitted)
    engine.opened.clear()
    with pytest.raises(ValueError, match="configuration"):
        if resume:
            m1.evaluate_t0(engine.workspace, "initial")
        else:
            m1.evaluate_t0(engine.workspace, "replay", "initial")
    assert engine.opened == []
    assert len(engine.submitted) == submitted
    assert report.read_bytes() == before


def ledger_attempt(binary: str, state: str = "completed") -> list[dict[str, object]]:
    request = {"prompt": "synthetic", "model": "gpt-6.1-sol", "max_output_tokens": 10}
    start: dict[str, object] = {
        "attempt": f"{binary}-{state}",
        "key": sha256(
            json.dumps((binary, "synthetic", request), sort_keys=True).encode()
        ).hexdigest(),
        "binary": binary,
        "provider": "synthetic",
        "request": request,
        "service_tier": "standard",
        "state": "started",
        "cost_nanodollars": 1 if state == "limit-exceeded" else 120_000,
    }
    if state == "started":
        return [start]
    terminal = {**start, "state": state}
    if state in ("completed", "limit-exceeded"):
        terminal.update(
            cost_nanodollars=40_000,
            completion={
                "text": "synthetic answer",
                "model": "gpt-6.1-sol",
                "service_tier": "standard",
                "usage": {
                    "input_tokens": 5,
                    "cached_input_tokens": 0,
                    "output_tokens": 3,
                },
            },
        )
    return [start, terminal]


@dataclass
class SyntheticEngine:
    workspace: Path
    submitted: list[str] = field(default_factory=list)
    opened: list[Path] = field(default_factory=list)
    extra_events: list[dict[str, object]] = field(default_factory=list)
    failed: set[str] = field(default_factory=set)
    failure_category: str = "pipeline-failed"
    interrupt_after: int | None = None
    before_measure: Callable[[], None] = lambda: None
    after_capture: Callable[[Path, Submission], None] = lambda _path, _value: None

    @property
    def run(self) -> Path:
        return self.workspace / "runs/initial"

    @property
    def ledger(self) -> Path:
        return self.workspace / "runs/initial-rebuild/llm.jsonl"


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SyntheticEngine:
    engine = SyntheticEngine(tmp_path)
    original = b"opaque synthetic original"
    variants = tuple(
        Variant(
            f"case-{index}", compiler, "-O0", sha256(original).hexdigest(), "synthetic"
        )
        for index in range(10)
        for compiler in Compiler
    )
    archive = tmp_path / "synthetic-inputs.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for name in sorted({variant.name for variant in variants}):
            content = (
                encode_invocation(Invocation(("synthetic private input",))) + "\n"
            ).encode()
            member = tarfile.TarInfo(f"t0/cases/{name}.jsonl")
            member.size = len(content)
            stream.addfile(member, io.BytesIO(content))
    config = {
        "heldout_archive_sha256": sha256(archive.read_bytes()).hexdigest(),
        "worker_images": {},
    }

    def capture(
        workspace: Path,
        directory: Path,
        pipeline_run: str,
        key: str,
        binary: Path,
        method: Method,
        replay_pipeline_run: str | None,
    ) -> Submission:
        stored = directory / "capture"
        if stored.exists():
            return submission.submit(
                workspace,
                directory,
                pipeline_run,
                key,
                binary,
                method,
                replay_pipeline_run,
            )
        if engine.interrupt_after == len(engine.submitted):
            raise KeyboardInterrupt("Synthetic capture interruption.")
        engine.submitted.append(key)
        stored.mkdir(parents=True)
        if key in engine.failed:
            result = Submission(
                method,
                key,
                None,
                engine.failure_category,
                replay_pipeline_run,
                reconstruction_seconds=1 if replay_pipeline_run is None else 2,
            )
        else:
            project = stored / "project"
            (project / "src").mkdir(parents=True)
            (project / "src/program.c").write_text("int main(void) { return 0; }\n")
            (project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
            report = json.dumps(
                {
                    "sha256": sha256(original).hexdigest(),
                    "method": method,
                    "wall_seconds": 1,
                }
            ).encode()
            (stored / "report.json").write_bytes(report)
            development = b"synthetic development evidence"
            origin = b"synthetic origin evidence"
            (stored / "development.json").write_bytes(development)
            (stored / "origin.json").write_bytes(origin)
            result = Submission(
                method,
                key,
                source_digest(project_files(project)),
                None,
                replay_pipeline_run,
                sha256(development).hexdigest(),
                sha256(origin).hexdigest(),
                sha256(report).hexdigest(),
                1,
            )
        submission.write_report(stored / "submission.json", asdict(result))
        if replay_pipeline_run is None:
            ledger = workspace / "runs" / pipeline_run / "llm.jsonl"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a") as stream:
                for event in [*ledger_attempt(key), *engine.extra_events]:
                    stream.write(json.dumps(event) + "\n")
            engine.extra_events.clear()
        engine.after_capture(stored, result)
        return result

    def cases(
        path: Path, digest: str, names: set[str]
    ) -> dict[str, tuple[Invocation, ...]]:
        engine.opened.append(path)
        return heldout_cases(archive, digest, names)

    def measure(
        workspace: Path,
        run: Path,
        pipeline_run: str,
        task: m1.Task,
        captured: Submission,
        binary: Path | bytes,
        cases: tuple[Invocation, ...],
        config: m1._Configuration,
        dev_outputs: frozenset[bytes],
        origin: bytes | None,
        identity: LedgerIdentity,
    ) -> dict[str, object]:
        engine.before_measure()
        return {
            **asdict(task.variant),
            "method": task.method,
            "source_sha256": captured.source_sha256,
            "fully_successful": captured.source_sha256 is not None,
            "model": asdict(bound_summary(workspace, run, task.key, identity)),
            "reconstruction_seconds": 1 if run.name == "initial" else 2,
        }

    monkeypatch.setattr(m1, "t0_manifest", lambda _: (variants, "a" * 64))
    monkeypatch.setattr(m1, "_configuration", lambda *_: config)
    monkeypatch.setattr(m1, "submit", capture)
    monkeypatch.setattr(m1, "_release_bytes", lambda *_: original)
    monkeypatch.setattr(m1, "_validate_pipeline_record", lambda *_: None)
    monkeypatch.setattr(
        m1, "verify_development", lambda *_: frozenset({b"synthetic output"})
    )
    monkeypatch.setattr(m1, "heldout_cases", cases)
    monkeypatch.setattr(m1, "_measure", measure)
    return engine


def replace_source(run: Path, key: str) -> None:
    capture = run / "submissions" / key / "capture"
    (capture / "project/src/program.c").write_text("int main(void) { return 7; }\n")
    checkpoint = capture / "submission.json"
    data = json.loads(checkpoint.read_text())
    data["source_sha256"] = source_digest(project_files(capture / "project"))
    submission.write_report(checkpoint, data)


def test_resume_rejects_source_and_checkpoint_replacement(
    engine: SyntheticEngine,
) -> None:
    report, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert passed
    before = report.read_bytes()
    replace_source(engine.run, engine.submitted[0])
    engine.opened.clear()
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert report.read_bytes() == before
    assert len(engine.submitted) == 40


def test_unknown_ledger_task_stops_before_archive(engine: SyntheticEngine) -> None:
    engine.extra_events = ledger_attempt("outside-roster")
    with pytest.raises(ValueError, match="roster"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()
    assert (
        sum(
            event.cost_nanodollars
            for event in read_events(engine.ledger.read_text().splitlines())
        )
        == 1_640_000
    )


@pytest.mark.parametrize("evidence", ["report", "development", "origin"])
def test_resume_rejects_evidence_and_checkpoint_replacement(
    engine: SyntheticEngine, evidence: str
) -> None:
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    before = report.read_bytes()
    capture = engine.run / "submissions" / engine.submitted[0] / "capture"
    target = capture / f"{evidence}.json"
    content = b'{"wall_seconds": 7}' if evidence == "report" else b"changed evidence"
    target.write_bytes(content)
    checkpoint = capture / "submission.json"
    data = json.loads(checkpoint.read_text())
    data[f"{evidence}_sha256"] = sha256(content).hexdigest()
    submission.write_report(checkpoint, data)
    engine.opened.clear()
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert report.read_bytes() == before


@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize(
    "change", ["missing-checkpoint", "missing-capture", "category"]
)
def test_frozen_roster_rejects_missing_or_changed_tasks(
    engine: SyntheticEngine, failed: bool, change: str
) -> None:
    key = "case-0-gcc-O0-phoenix"
    if failed:
        engine.failed.add(key)
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    assert key in engine.submitted
    before = report.read_bytes()
    capture = engine.run / "submissions" / key / "capture"
    checkpoint = capture / "submission.json"
    if change == "missing-checkpoint":
        checkpoint.unlink()
    elif change == "missing-capture":
        capture.rename(capture.with_name("removed"))
    else:
        data = json.loads(checkpoint.read_text())
        data["category"] = "replacement-failure"
        submission.write_report(checkpoint, data)
    engine.opened.clear()
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 40
    assert report.read_bytes() == before


def test_interrupted_capture_resumes_before_freeze(engine: SyntheticEngine) -> None:
    engine.interrupt_after = 7
    with pytest.raises(KeyboardInterrupt):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 7
    engine.interrupt_after = None
    report, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert passed and len(engine.submitted) == 40
    assert len(json.loads(report.read_text())["results"]) == 40


@pytest.mark.parametrize("after_publication", [False, True])
def test_binding_publication_is_atomic_and_resumable(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, after_publication: bool
) -> None:
    replace = Path.replace

    def interrupted(path: Path, target: Path) -> Path:
        if target.name == "capture-binding.json" and b'"frozen"' in path.read_bytes():
            if after_publication:
                replace(path, target)
            raise KeyboardInterrupt("Synthetic binding publication interruption.")
        return replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupted)
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 40
    report, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert passed and report.is_file()
    assert len(engine.submitted) == 40


@pytest.mark.parametrize("changed", [False, True])
def test_interrupted_measurement_keeps_the_capture_binding(
    engine: SyntheticEngine, changed: bool
) -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt("Synthetic measurement interruption.")

    engine.before_measure = interrupted
    with pytest.raises(KeyboardInterrupt):
        m1.evaluate_t0(engine.workspace, "initial")
    assert len(engine.opened) == 1
    assert not (engine.run / "m1.json").exists()
    engine.before_measure = lambda: None
    engine.opened.clear()
    if changed:
        replace_source(engine.run, engine.submitted[0])
        with pytest.raises(ValueError, match="capture"):
            m1.evaluate_t0(engine.workspace, "initial")
        assert engine.opened == []
        assert not (engine.run / "m1.json").exists()
    else:
        report, passed = m1.evaluate_t0(engine.workspace, "initial")
        assert passed and report.is_file()
    assert len(engine.submitted) == 40


@pytest.mark.parametrize("completed", [False, True])
def test_missing_binding_is_not_backfilled(
    engine: SyntheticEngine, completed: bool
) -> None:
    if completed:
        report, _ = m1.evaluate_t0(engine.workspace, "initial")
        before = report.read_bytes()
    else:
        engine.interrupt_after = 1
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
        engine.interrupt_after = None
    binding = engine.run / "capture-binding.json"
    binding.unlink()
    replace_source(engine.run, engine.submitted[0])
    engine.opened.clear()
    with pytest.raises(ValueError, match="binding is missing"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not binding.exists()
    if completed:
        assert report.read_bytes() == before


def test_measurement_rechecks_frozen_evidence_without_overwriting_report(
    engine: SyntheticEngine,
) -> None:
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    before = report.read_bytes()
    engine.before_measure = lambda: replace_source(engine.run, engine.submitted[0])
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert report.read_bytes() == before


def test_evidence_change_during_development_stops_before_archive(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def changed(*_: object) -> frozenset[bytes]:
        replace_source(engine.run, engine.submitted[0])
        return frozenset()

    monkeypatch.setattr(m1, "verify_development", changed)
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()


def test_same_sources_replay_with_the_original_ledger(engine: SyntheticEngine) -> None:
    original, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert passed
    original_bytes = original.read_bytes()
    ledger = engine.ledger.read_bytes()
    report, passed = m1.evaluate_t0(engine.workspace, "replay", "initial")
    assert passed and json.loads(report.read_text())["reproduced"] is True
    assert engine.ledger.read_bytes() == ledger
    assert original.read_bytes() == original_bytes
    assert not (engine.workspace / "runs/replay-rebuild/llm.jsonl").exists()


@pytest.mark.parametrize(
    "state", ["started", "failed", "retry", "completed", "limit-exceeded"]
)
def test_unknown_keys_are_rejected_in_every_attempt_state(
    engine: SyntheticEngine, state: str
) -> None:
    engine.extra_events = ledger_attempt("outside-roster", state)
    with pytest.raises(ValueError, match="roster"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()
    assert any(
        event.binary == "outside-roster"
        for event in read_events(engine.ledger.read_text().splitlines())
    )


def test_all_attempt_charges_reach_successful_and_failed_task_summaries(
    engine: SyntheticEngine,
) -> None:
    key = "case-0-gcc-O0-phoenix"
    engine.failed.add(key)
    engine.extra_events = [
        event
        for state in ("started", "failed", "retry", "limit-exceeded")
        for event in ledger_attempt(key, state)
    ]
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    records = json.loads(report.read_text())["results"]
    model = records[0]["model"]
    assert model == {
        "calls": 2,
        "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 6},
        "cost_nanodollars": 80_000,
        "unknown_cost_reservations": 360_000,
    }
    assert (
        sum(
            record["model"]["cost_nanodollars"]
            + record["model"]["unknown_cost_reservations"]
            for record in records
        )
        == 2_000_000
    )


def test_report_accounting_must_match_each_task(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    before = report.read_bytes()
    record = json.loads(before)["results"][0]
    record["model"]["cost_nanodollars"] = 0
    monkeypatch.setattr(m1, "_measure", lambda *_: record)
    with pytest.raises(ValueError, match="reconcile"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert report.read_bytes() == before


@settings(max_examples=30)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["one", "two", "three"]),
            st.sampled_from(
                ["started", "failed", "retry", "completed", "limit-exceeded"]
            ),
        ),
        max_size=20,
    )
)
def test_partitioned_summaries_preserve_all_charges(
    attempts: list[tuple[str, str]],
) -> None:
    with TemporaryDirectory() as directory:
        workspace = Path(directory).resolve()
        ledger = workspace / "runs/pipeline/llm.jsonl"
        ledger.parent.mkdir(parents=True)
        events: list[dict[str, object]] = []
        for index, (key, state) in enumerate(attempts):
            events.extend(
                {**event, "attempt": str(index)} for event in ledger_attempt(key, state)
            )
        ledger.write_text("".join(json.dumps(event) + "\n" for event in events))
        before = ledger.read_bytes()
        identity = freeze_identity(workspace, workspace / "evaluation", "pipeline")
        summaries = bound_summaries(
            workspace, ("one", "two", "three", "unused"), identity
        )
        measured = sum(
            state in ("completed", "limit-exceeded") for _, state in attempts
        )
        reserved = len(attempts) - measured
        assert (
            sum(value.cost_nanodollars for value in summaries.values())
            == measured * 40_000
        )
        assert (
            sum(value.unknown_cost_reservations for value in summaries.values())
            == reserved * 120_000
        )
        assert sum(value.calls for value in summaries.values()) == measured
        assert (
            sum(value.usage.input_tokens for value in summaries.values())
            == measured * 5
        )
        assert (
            sum(value.usage.output_tokens for value in summaries.values())
            == measured * 3
        )
        assert summaries["unused"].calls == 0
        assert ledger.read_bytes() == before


@settings(max_examples=20)
@given(st.binary(min_size=1, max_size=64))
def test_capture_binding_rejects_any_replacement(content: bytes) -> None:
    with TemporaryDirectory() as directory:
        run = Path(directory).resolve()
        assert capture_binding.open_binding(run, ("task",)) is None
        submission.write_report(run / "configuration.json", {})
        submission.write_report(run / "model-ledger.json", {})
        capture = run / "submissions/task/capture"
        capture.mkdir(parents=True)
        checkpoint = capture / "submission.json"
        returned = Submission("phoenix", "task", sha256(b"").hexdigest(), None)
        submission.write_report(checkpoint, asdict(returned))
        source = capture / "source.c"
        source.write_bytes(b"")
        bound = capture_binding.freeze_binding(run, ("task",), None, {"task": returned})
        source.write_bytes(content)
        submission.write_report(
            checkpoint,
            {**asdict(returned), "source_sha256": sha256(content).hexdigest()},
        )
        with pytest.raises(ValueError, match="capture"):
            capture_binding.verify_binding(run, ("task",), bound)


@pytest.mark.parametrize("change", ["source", "binding", "roster"])
def test_frozen_resume_rejects_changes_before_first_archive_read(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    freeze = capture_binding.freeze_binding

    def interrupted(
        run: Path,
        keys: tuple[str, ...],
        bound: bytes | None,
        submissions: Mapping[str, Submission],
    ) -> bytes:
        freeze(run, keys, bound, submissions)
        raise KeyboardInterrupt("Synthetic interruption after the freeze.")

    with monkeypatch.context() as patch:
        patch.setattr(m1, "freeze_binding", interrupted)
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    if change == "source":
        replace_source(engine.run, engine.submitted[0])
    elif change == "binding":
        (engine.run / "capture-binding.json").unlink()
    else:
        manifest: Callable[[Path], tuple[tuple[Variant, ...], str]] = getattr(
            m1, "t0_manifest"
        )
        variants, digest = manifest(engine.workspace)
        monkeypatch.setattr(m1, "t0_manifest", lambda _: (variants[::-1], digest))
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 40
    assert not (engine.run / "m1.json").exists()


def test_binding_contains_all_capture_files_before_archive_access(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_key = "case-0-gcc-O0-phoenix"
    engine.failed.add(failed_key)

    def checked(
        path: Path, digest: str, names: set[str]
    ) -> dict[str, tuple[Invocation, ...]]:
        document = json.loads((engine.run / "capture-binding.json").read_text())
        assert document["phase"] == "frozen"
        assert [record["key"] for record in document["captures"]] == engine.submitted
        assert document["captures"][0]["files"].keys() == {"submission.json"}
        assert document["captures"][1]["files"].keys() == {
            "submission.json",
            "project/CMakeLists.txt",
            "project/src/program.c",
            "report.json",
            "development.json",
            "origin.json",
        }
        engine.opened.append(path)
        return heldout_cases(
            engine.workspace / "synthetic-inputs.tar.gz", digest, names
        )

    monkeypatch.setattr(m1, "heldout_cases", checked)
    m1.evaluate_t0(engine.workspace, "initial")
    assert len(engine.opened) == 1


@pytest.mark.parametrize("change", ["capture", "binding"])
def test_replay_rejects_changed_or_unbound_origin(
    engine: SyntheticEngine, change: str
) -> None:
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    before = report.read_bytes()
    if change == "capture":
        replace_source(engine.run, engine.submitted[0])
    else:
        (engine.run / "capture-binding.json").unlink()
    engine.opened.clear()
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "replay", "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 40
    assert report.read_bytes() == before


def test_unknown_zero_charge_retry_still_stops_before_archive(
    engine: SyntheticEngine,
) -> None:
    events = ledger_attempt("outside-roster", "retry")
    events[-1]["cost_nanodollars"] = 0
    engine.extra_events = events
    with pytest.raises(ValueError, match="roster"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []


@settings(max_examples=20)
@given(
    st.text(alphabet="abcxyz012", min_size=1, max_size=12),
    st.sampled_from(["started", "failed", "retry", "completed", "limit-exceeded"]),
)
def test_any_unknown_task_key_is_rejected(key: str, state: str) -> None:
    with TemporaryDirectory() as directory:
        workspace = Path(directory).resolve()
        ledger = workspace / "runs/pipeline/llm.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            "".join(json.dumps(event) + "\n" for event in ledger_attempt(key, state))
        )
        before = ledger.read_bytes()
        identity = freeze_identity(workspace, workspace / "evaluation", "pipeline")
        with pytest.raises(ValueError, match="roster"):
            bound_summaries(workspace, ("known",), identity)
        assert ledger.read_bytes() == before


@pytest.mark.parametrize("change", ["binding", "added-file", "symlink", "identity"])
def test_measurement_rejects_replaced_or_added_frozen_evidence(
    engine: SyntheticEngine, change: str
) -> None:
    report, _ = m1.evaluate_t0(engine.workspace, "initial")
    before = report.read_bytes()

    def changed() -> None:
        engine.before_measure = lambda: None
        capture = engine.run / "submissions" / engine.submitted[0] / "capture"
        if change == "binding":
            path = engine.run / "capture-binding.json"
            path.write_bytes(path.read_bytes() + b"\n")
        elif change == "added-file":
            (capture / "extra.txt").write_text("New synthetic evidence.")
        elif change == "symlink":
            (capture / "link").symlink_to(capture / "report.json")
        else:
            path = engine.run / "model-ledger.json"
            path.write_bytes(path.read_bytes() + b"\n")

    engine.before_measure = changed
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert report.read_bytes() == before


@pytest.mark.parametrize(
    "change", ["success-to-failure", "source-identity", "failure-category"]
)
def test_later_capture_cannot_replace_returned_submission(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    if change == "failure-category":
        manifest: Callable[[Path], tuple[tuple[Variant, ...], str]] = getattr(
            m1, "t0_manifest"
        )
        variants, _ = manifest(engine.workspace)
        engine.failed.update(
            m1.Task(variant, method).key
            for variant in variants
            for method in m1.METHODS
        )
        monkeypatch.setattr(m1, "_measure", measure_submission)

    def changed(_directory: Path, _returned: Submission) -> None:
        if len(engine.submitted) != 40:
            return
        first = engine.run / "submissions" / engine.submitted[0] / "capture"
        checkpoint = first / "submission.json"
        data = json.loads(checkpoint.read_bytes())
        if change == "source-identity":
            replace_source(engine.run, engine.submitted[0])
        else:
            data.update(
                source_sha256=None,
                category="invalid-project",
                development_sha256=None,
                origin_sha256=None,
                report_sha256=None,
            )
            submission.write_report(checkpoint, data)

    engine.after_capture = changed
    with pytest.raises(ValueError, match="checkpoint"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert len(engine.submitted) == 40
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()
    assert json.loads((engine.run / "capture-binding.json").read_bytes())["phase"] == (
        "capturing"
    )
    assert (engine.run / "capture-rejected.json").is_file()


@pytest.mark.parametrize("category", ["pipeline-failed", "invalid-project"])
def test_failed_captures_keep_exact_category_through_resume_and_replay(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, category: str
) -> None:
    manifest: Callable[[Path], tuple[tuple[Variant, ...], str]] = getattr(
        m1, "t0_manifest"
    )
    variants, _ = manifest(engine.workspace)
    engine.failed.update(
        m1.Task(variant, method).key for variant in variants for method in m1.METHODS
    )
    engine.failure_category = category
    engine.extra_events = ledger_attempt("case-0-gcc-O0-phoenix", "failed")
    monkeypatch.setattr(m1, "_measure", measure_submission)
    engine.interrupt_after = 7
    with pytest.raises(KeyboardInterrupt):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert len(engine.submitted) == 7
    engine.interrupt_after = None
    report, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert not passed
    original = json.loads(report.read_bytes())
    assert len(original["results"]) == 40
    assert {record["failure_category"] for record in original["results"]} == {category}
    assert all(record["source_sha256"] is None for record in original["results"])
    assert all(record["fully_successful"] is False for record in original["results"])
    assert (
        sum(
            record["model"]["unknown_cost_reservations"]
            for record in original["results"]
        )
        == 120_000
    )
    assert (
        sum(record["model"]["cost_nanodollars"] for record in original["results"])
        == 1_600_000
    )
    ledger = engine.ledger.read_bytes()
    binding = (engine.run / "capture-binding.json").read_bytes()
    m1.evaluate_t0(engine.workspace, "initial")
    assert len(engine.submitted) == 40
    assert json.loads(report.read_bytes()) == original
    assert (engine.run / "capture-binding.json").read_bytes() == binding
    before = report.read_bytes()
    replay, passed = m1.evaluate_t0(engine.workspace, "replay", "initial")
    replayed = json.loads(replay.read_bytes())
    assert not passed and replayed["reproduced"] is True
    assert {record["failure_category"] for record in replayed["results"]} == {category}
    assert {record["reconstruction_seconds"] for record in original["results"]} == {1}
    assert {record["reconstruction_seconds"] for record in replayed["results"]} == {2}
    assert report.read_bytes() == before
    assert engine.ledger.read_bytes() == ledger
    assert not (engine.workspace / "runs/replay-rebuild/llm.jsonl").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("method", "ghidra-raw"),
        ("key", "another-task"),
        ("replay_of", "another-rebuild"),
        ("development_sha256", "a" * 64),
        ("origin_sha256", "a" * 64),
        ("report_sha256", "a" * 64),
        ("reconstruction_seconds", 7),
    ],
)
def test_later_capture_cannot_change_returned_metadata(
    engine: SyntheticEngine, field: str, value: object
) -> None:
    def changed(_directory: Path, _returned: Submission) -> None:
        if len(engine.submitted) == 40:
            checkpoint = (
                engine.run
                / "submissions"
                / engine.submitted[0]
                / "capture/submission.json"
            )
            data = json.loads(checkpoint.read_bytes())
            data[field] = value
            submission.write_report(checkpoint, data)

    engine.after_capture = changed
    with pytest.raises(ValueError, match="checkpoint"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()


@pytest.mark.parametrize("phase", ["later-capture", "interrupted-resume"])
@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "missing",
        "extra",
        "non-object",
        "invalid-json",
        "bad-utf8",
        "method-type",
        "key-type",
        "replay-type",
        "source-type",
        "digest-shape",
        "category-type",
        "success-category",
        "boolean-time",
        "negative-time",
        "nonfinite-time",
        "huge-time",
        "missing-time",
        "oversized",
        "nested",
    ],
)
def test_invalid_checkpoint_stops_before_archive(
    engine: SyntheticEngine, phase: str, change: str
) -> None:
    def corrupt() -> None:
        checkpoint = (
            engine.run / "submissions" / engine.submitted[0] / "capture/submission.json"
        )
        data = json.loads(checkpoint.read_bytes())
        content: bytes | None = None
        if change == "duplicate":
            content = checkpoint.read_bytes().replace(
                b'"method": "phoenix"', b'"method": "wrong", "method": "phoenix"'
            )
        elif change == "missing":
            del data["category"]
        elif change == "missing-time":
            del data["reconstruction_seconds"]
        elif change == "extra":
            data["unknown"] = None
        elif change == "non-object":
            content = b"[]"
        elif change == "invalid-json":
            content = b"{"
        elif change == "bad-utf8":
            content = b"\xff"
        elif change == "oversized":
            content = b" " * (64 * 1024 + 1) + checkpoint.read_bytes()
        elif change == "nested":
            content = b"[" * 2000 + b"]" * 2000
        else:
            replacements: dict[str, tuple[str, object]] = {
                "method-type": ("method", []),
                "key-type": ("key", True),
                "replay-type": ("replay_of", 1),
                "source-type": ("source_sha256", []),
                "digest-shape": ("report_sha256", "not-a-digest"),
                "category-type": ("category", []),
                "success-category": ("category", "invalid-project"),
                "boolean-time": ("reconstruction_seconds", True),
                "negative-time": ("reconstruction_seconds", -1),
                "nonfinite-time": ("reconstruction_seconds", float("nan")),
                "huge-time": ("reconstruction_seconds", 10**1000),
            }
            name, value = replacements[change]
            data[name] = value
        checkpoint.write_bytes(
            content if content is not None else json.dumps(data).encode()
        )

    if phase == "interrupted-resume":
        engine.interrupt_after = 1
        with pytest.raises(KeyboardInterrupt):
            m1.evaluate_t0(engine.workspace, "initial")
        engine.interrupt_after = None
        corrupt()
    else:

        def changed(_directory: Path, _returned: Submission) -> None:
            if len(engine.submitted) == 40:
                corrupt()

        engine.after_capture = changed
    with pytest.raises(ValueError, match="checkpoint"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()


@pytest.mark.parametrize("seconds", [0, 1, 1.25])
def test_checkpoint_whitespace_and_numeric_time_normalization_are_valid(
    engine: SyntheticEngine, seconds: float
) -> None:
    engine.interrupt_after = 1
    with pytest.raises(KeyboardInterrupt):
        m1.evaluate_t0(engine.workspace, "initial")
    checkpoint = (
        engine.run / "submissions" / engine.submitted[0] / "capture/submission.json"
    )
    data = json.loads(checkpoint.read_bytes())
    data["reconstruction_seconds"] = seconds
    content = json.dumps(data, indent=4).encode() + b" \n"
    checkpoint.write_bytes(content)
    engine.interrupt_after = None
    report, passed = m1.evaluate_t0(engine.workspace, "initial")
    assert passed and report.is_file()
    binding = json.loads((engine.run / "capture-binding.json").read_bytes())
    assert (
        binding["captures"][0]["files"]["submission.json"]
        == sha256(content).hexdigest()
    )
    assert checkpoint.read_bytes() == content
    assert len(engine.submitted) == 40


def test_checkpoint_validation_and_binding_use_the_same_read(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    loads = json.loads
    target: Path | None = None
    original: bytes | None = None
    changed = False

    def ready(_directory: Path, _returned: Submission) -> None:
        nonlocal target, original
        if len(engine.submitted) == 40:
            target = (
                engine.run
                / "submissions"
                / engine.submitted[0]
                / "capture/submission.json"
            )
            original = target.read_bytes()

    def replace_after_read(
        content: str | bytes,
        *,
        object_pairs_hook: Callable[[list[tuple[str, object]]], dict[str, object]]
        | None = None,
    ) -> object:
        nonlocal changed
        data = loads(content, object_pairs_hook=object_pairs_hook)
        if target is not None and content == original and not changed:
            changed = True
            replacement = loads(content)
            replacement.update(
                source_sha256=None,
                category="invalid-project",
                development_sha256=None,
                origin_sha256=None,
                report_sha256=None,
            )
            submission.write_report(target, replacement)
        return data

    engine.after_capture = ready
    monkeypatch.setattr(json, "loads", replace_after_read)
    with pytest.raises(ValueError, match="capture"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert changed and target is not None and original is not None
    binding = loads((engine.run / "capture-binding.json").read_bytes())
    digest = binding["captures"][0]["files"]["submission.json"]
    assert digest == sha256(original).hexdigest()
    assert digest != sha256(target.read_bytes()).hexdigest()
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()


@pytest.mark.parametrize(
    "kind", ["symlink", "symlink-loop", "fifo", "directory", "missing"]
)
def test_checkpoint_requires_a_regular_file_on_resume(
    engine: SyntheticEngine, kind: str
) -> None:
    engine.interrupt_after = 1
    with pytest.raises(KeyboardInterrupt):
        m1.evaluate_t0(engine.workspace, "initial")
    engine.interrupt_after = None
    checkpoint = (
        engine.run / "submissions" / engine.submitted[0] / "capture/submission.json"
    )
    saved = checkpoint.with_name("saved.json")
    checkpoint.rename(saved)
    if kind == "symlink":
        checkpoint.symlink_to(saved)
    elif kind == "symlink-loop":
        checkpoint.symlink_to(checkpoint.name)
    elif kind == "fifo":
        os.mkfifo(checkpoint)
    elif kind == "directory":
        checkpoint.mkdir()
    with pytest.raises(ValueError, match="checkpoint"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()


@pytest.mark.parametrize("when", ["after-capture", "after-path-check"])
def test_checkpoint_symlink_loop_stops_the_capture_freeze(
    engine: SyntheticEngine, monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    pending: Path | None = None
    is_symlink = Path.is_symlink

    def replace(path: Path) -> None:
        path.unlink()
        path.symlink_to(path.name)

    def check(path: Path) -> bool:
        nonlocal pending
        result = is_symlink(path)
        if path == pending:
            assert not result
            replace(path)
            pending = None
        return result

    def replace_checkpoint(_directory: Path, _returned: Submission) -> None:
        nonlocal pending
        if len(engine.submitted) == 40:
            checkpoint = (
                engine.run
                / "submissions"
                / engine.submitted[0]
                / "capture/submission.json"
            )
            if when == "after-capture":
                replace(checkpoint)
            else:
                pending = checkpoint

    engine.after_capture = replace_checkpoint
    monkeypatch.setattr(Path, "is_symlink", check)
    with pytest.raises(ValueError, match="capture cannot contain symbolic links"):
        m1.evaluate_t0(engine.workspace, "initial")
    assert pending is None
    assert engine.opened == []
    assert not (engine.run / "m1.json").exists()
