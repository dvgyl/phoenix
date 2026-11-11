import copy
import json
import platform
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_m2 import results_fixture, scope_fixture
from test_m2 import synthetic_engine as synthetic_engine
from test_pair import IMAGES, FakeWorker

from phoenix_eval import m1, m2, pair
from phoenix_eval.build import PROJECT_CMAKE, snapshot_project
from phoenix_eval.case import CaseFailure, FailureKind
from phoenix_eval.docker import Engine, read_program
from phoenix_eval.integrity import IntegrityError, IntegrityReport
from phoenix_eval.model_ledger import freeze_identity
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.submission import Submission, freeze_package_report, freeze_project


def save_report(
    directory: Path, records: list[dict[str, Any]], scope: m2.Scope | None = None
) -> Path:
    scope = scope or scope_fixture()
    scores = m2.summarize(records, scope)
    identity = {
        "schema": 1,
        "pipeline_run": directory.name + "-rebuild",
        "sha256": None,
    }
    document = {
        "run_id": directory.name,
        "replay_of": None,
        "reproduced": None,
        "configuration": {"schema": 2, "scope": scope.record()},
        "corpus": "agent-sealed",
        "coverage_kind": "recovered_block_entries",
        "model_ledger": identity,
        "scores": scores,
        "results": records,
        "accepted": scores["accepted"],
        "report_kind": "m2",
        "source_adequacy": "separate_author_evidence",
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "model-ledger.json").write_text(json.dumps(identity))
    path = directory / "m2.json"
    path.write_text(json.dumps(document))
    return path


@pytest.mark.parametrize(
    "mutation",
    [
        "integrity_failure_category",
        "unchecked_executables",
        "missing_executable_hash",
        "behavior_failed",
        "extra_build",
        "invalid_model_counts",
        "invalid_case_counts",
    ],
)
def test_saved_report_rejects_each_original_contradiction(
    tmp_path: Path, mutation: str
) -> None:
    path = save_report(tmp_path, results_fixture(scope_fixture()))
    assert m2.recorded_kind(tmp_path) == "m2"
    document = json.loads(path.read_text())
    record = document["results"][0]
    if mutation == "integrity_failure_category":
        record["integrity"]["categories"] = {"embedded_text": 1}
    elif mutation == "unchecked_executables":
        record["integrity"].update(checked_executables=0, targets=[])
    elif mutation == "missing_executable_hash":
        for build in record["behavior"]["builds"]:
            build.pop("executable_sha256")
    elif mutation == "behavior_failed":
        record["behavior"]["behavior_passed"] = False
    elif mutation == "extra_build":
        record["behavior"]["builds"].append(
            {
                "architecture": "mips",
                "compiler": "gcc",
                "compiled": False,
                "matched_cases": 0,
                "evaluation_errors": 1,
            }
        )
    elif mutation == "invalid_model_counts":
        record["model"].update(calls=-1, cost_nanodollars=-1, usage="not token counts")
    else:
        record["behavior"].update(total_cases=0, emulator_disagreements=-1)
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="recorded evaluation report"):
        m2.recorded_kind(tmp_path)


@pytest.mark.parametrize(
    "field", ["warnings", "model", "coverage_kind", "source_sha256"]
)
def test_changed_root_cannot_hide_behind_valid_replay(
    tmp_path: Path, synthetic_engine: dict[str, Any], field: str
) -> None:
    original, passed = m1.evaluate_m2(tmp_path, "origin")
    assert passed
    assert m1.evaluate_m2(tmp_path, "first", "origin")[1]
    document = json.loads(original.read_text())
    if field == "warnings":
        document["results"][0]["behavior"]["builds"][0]["warnings"] = 17
    elif field == "model":
        document["results"][0]["model"]["calls"] += 1
    elif field == "source_sha256":
        document["results"][0][field] = "0" * 64
    else:
        document[field] = "changed"
    original.write_text(json.dumps(document))
    synthetic_engine["opened"].clear()
    submitted = len(synthetic_engine["submitted"])
    with pytest.raises(ValueError):
        m1.evaluate_m2(tmp_path, "second", "first")
    assert synthetic_engine["opened"] == []
    assert len(synthetic_engine["submitted"]) == submitted
    assert not (tmp_path / "runs/second/m2.json").exists()


def test_failed_replay_cannot_replace_original_reference(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original, passed = m1.evaluate_m2(tmp_path, "origin")
    assert passed
    measure = m1._measure

    def changed(*args: Any, **kwargs: Any) -> dict[str, object]:
        record = copy.deepcopy(measure(*args, **kwargs))
        behavior = cast(dict[str, Any], record["behavior"])
        behavior["builds"][0]["executable_sha256"] = "1" * 64
        return record

    monkeypatch.setattr(m1, "_measure", changed)
    first, passed = m1.evaluate_m2(tmp_path, "first", "origin")
    assert not passed
    assert json.loads(first.read_text())["reproduced"] is False
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError, match="lineage"):
        m1.evaluate_m2(tmp_path, "second", "first")
    assert synthetic_engine["opened"] == []
    assert json.loads(original.read_text())["reproduced"] is None


@pytest.mark.parametrize("source", ["missing", "origin", "../origin"])
def test_unknown_or_cyclic_replay_rejected_before_archive(
    tmp_path: Path, synthetic_engine: dict[str, Any], source: str
) -> None:
    path, _ = m1.evaluate_m2(tmp_path, "origin")
    document = json.loads(path.read_text())
    document.update(replay_of=source, reproduced=True)
    path.write_text(json.dumps(document))
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError):
        m1.evaluate_m2(tmp_path, "copy", "origin")
    assert synthetic_engine["opened"] == []


@pytest.mark.parametrize(
    "path_parts",
    [
        ("model", "calls"),
        ("model", "cost_nanodollars"),
        ("model", "unknown_cost_reservations"),
        ("model", "usage", "input_tokens"),
        ("model", "usage", "cached_input_tokens"),
        ("model", "usage", "output_tokens"),
        ("behavior", "total_cases"),
        ("behavior", "eligible_cases"),
        ("behavior", "emulator_disagreements"),
        ("behavior", "evaluation_errors"),
        ("behavior", "covered_blocks"),
        ("behavior", "recovered_blocks"),
        ("behavior", "builds", 0, "warnings"),
    ],
)
@given(value=st.sampled_from([-1, True, 1.5, "1", None]))
def test_saved_counts_are_nonnegative_integers(
    path_parts: tuple[str | int, ...], value: object
) -> None:
    with TemporaryDirectory() as scratch:
        directory = Path(scratch)
        path = save_report(directory, results_fixture(scope_fixture()))
        document = json.loads(path.read_text())
        target = document["results"][0]
        for key in path_parts[:-1]:
            target = target[key]
        target[path_parts[-1]] = value
        path.write_text(json.dumps(document))
        with pytest.raises(ValueError):
            m2.recorded_kind(directory)


@pytest.mark.parametrize(
    "failure",
    [
        "success",
        "pipeline",
        "compiler",
        "integrity",
        "integrity_error",
        "original",
        "artifact",
        "empty",
        "mismatch",
        "sandbox",
        "differences",
        "partial_original",
        "disagreements",
        "build_error",
    ],
)
def test_real_measure_records_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    worker = FakeWorker(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    worker.source.rename(worker.source.with_name("program.c"))
    (worker.project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    worker.snapshot = snapshot_project(worker.project)
    monkeypatch.setattr(pair, "run_cases", worker.run_cases)
    monkeypatch.setattr(pair, "inspect_x86", worker.inspect_x86)
    monkeypatch.setattr(pair, "build_project", worker.build_project)
    monkeypatch.setattr(m1, "inspect_project", lambda *_: ())
    monkeypatch.setattr(m1, "original_shapes", lambda *_, **kwargs: ())
    integrity = IntegrityReport(
        failure != "integrity",
        {"embedded_text": 1} if failure == "integrity" else {},
        0,
        4,
        ("x86_64-linux-gnu", "aarch64-linux-gnu"),
        ("synthetic", "synthetic"),
        (),
    )

    def check(*args: Any) -> IntegrityReport:
        if failure == "integrity_error":
            raise IntegrityError("Synthetic check failure.")
        if failure in (
            "compiler",
            "original",
            "artifact",
            "empty",
            "disagreements",
            "build_error",
        ):
            count = len(args[2])
            return replace(
                integrity,
                passed=False,
                categories={"missing_build": 1},
                checked_executables=count,
            )
        return integrity

    monkeypatch.setattr(m1, "check_integrity", check)
    if failure == "compiler":
        worker.failed_builds.add("arm64-clang.elf")
    elif failure == "original":
        worker.worker_errors.add(worker.original.name)
    elif failure == "mismatch":
        worker.worker_errors.add("amd64-gcc.elf")
    elif failure == "artifact":

        def unreadable(binary: Path | bytes) -> bytes:
            if isinstance(binary, Path) and binary.name == "arm64-clang.elf":
                raise ValueError("Synthetic artifact read failure.")
            return read_program(binary)

        monkeypatch.setattr(pair, "read_program", unreadable)
    elif failure == "sandbox":
        for case in worker.cases:
            worker.outcomes["amd64-gcc.elf", Engine.ROSETTA, False, case] = CaseFailure(
                FailureKind.TIMEOUT, "synthetic"
            )
    elif failure == "differences":
        for case in worker.cases:
            worker.outcomes["amd64-gcc.elf", Engine.ROSETTA, False, case] = Outcome(
                b"different", b"different", Exited(0), TreeSnapshot()
            )
    elif failure == "partial_original":
        worker.outcomes[
            worker.original.name, Engine.ROSETTA, False, worker.cases[0]
        ] = CaseFailure(FailureKind.TIMEOUT, "synthetic")
    elif failure == "disagreements":
        for case in worker.cases:
            worker.outcomes[worker.original.name, Engine.QEMU_X86_64, False, case] = (
                Outcome(b"different", b"different", Exited(0), TreeSnapshot())
            )
    elif failure == "build_error":
        build = worker.build_project

        def unavailable(*args: Any, **kwargs: Any) -> object:
            if args[1].name == "arm64-clang.elf":
                raise ValueError("Synthetic compiler error.")
            return build(*args, **kwargs)

        monkeypatch.setattr(pair, "build_project", unavailable)
    scope = scope_fixture()
    batch = scope.batches[0]
    variant = replace(
        batch.variants[0], sha256=sha256(worker.original_bytes).hexdigest()
    )
    scope = replace(
        scope,
        batches=(
            replace(batch, variants=(variant, *batch.variants[1:])),
            scope.batches[1],
        ),
    )
    records = results_fixture(scope)
    task = m1.Task(variant, "phoenix", batch.tier)
    run = tmp_path / "evaluation"
    capture = run / "submissions" / task.key / "capture"
    capture.mkdir(parents=True)
    (worker.project / "phoenix_report.json").write_text(
        json.dumps({"sha256": variant.sha256, "method": task.method, "wall_seconds": 1})
    )
    submission = Submission(task.method, task.key, None, "pipeline-failed")
    if failure != "pipeline":
        submission = replace(
            submission,
            source_sha256=freeze_project(worker.project, capture / "project"),
            category=None,
            report_sha256=freeze_package_report(worker.project, capture),
        )
    identity = freeze_identity(tmp_path, run, "synthetic")
    record = m1._measure(
        tmp_path,
        run,
        "synthetic",
        task,
        submission,
        worker.original_bytes,
        () if failure == "empty" else worker.cases,
        cast(m1._Configuration, {"worker_images": IMAGES, "checker_images": {}}),
        origin_bytes=b"opaque",
        model_ledger=identity,
    )
    record.update(tier=task.tier, variant_key=task.variant_key, task_key=task.key)
    assert record["fully_successful"] is (failure == "success")
    records[0] = record
    path = save_report(tmp_path / "saved", records, scope)
    assert m2.recorded_kind(path.parent) == "m2"
    assert json.loads(path.read_text())["results"][0] == json.loads(
        json.dumps(records[0])
    )


@pytest.mark.parametrize(
    "parts,value",
    [
        (("model", "usage", "cached_input_tokens"), 1),
        (("model", "usage", "input_tokens"), 1),
        (("model", "cost_nanodollars"), 1),
        (("behavior", "total_cases"), 4),
        (("behavior", "eligible_cases"), 4),
        (("behavior", "covered_blocks"), 6),
        (("behavior", "evaluation_errors"), 1),
        (("behavior", "original_error_categories"), {"worker_error": 1}),
        (("behavior", "builds", 0, "compiler"), "clang"),
        (("behavior", "builds", 0, "architecture"), "mips"),
        (("behavior", "builds", 0, "compiled"), 1),
        (("behavior", "builds", 0, "executable_sha256"), None),
        (("behavior", "builds", 0, "executable_sha256"), "invalid"),
        (("behavior", "builds", 0, "matched_cases"), 3),
        (("behavior", "builds", 0, "evaluation_errors"), 1),
        (("behavior", "builds", 0, "failure_categories"), {"stdout": 1}),
        (("behavior", "builds", 0, "failure_categories"), {"stdout": 0}),
        (("integrity", "checked_storage_records"), -1),
        (("integrity", "checked_executables"), 3),
        (("integrity", "targets"), ["x86_64-linux-gnu", "x86_64-linux-gnu"]),
        (("integrity", "clang_versions"), ["synthetic"]),
        (("integrity", "clang_versions"), ["synthetic", ""]),
        (("integrity", "justifications"), ["invalid"]),
        (("source_sha256",), None),
        (("fully_successful",), False),
    ],
)
def test_saved_evidence_must_be_internally_consistent(
    tmp_path: Path, parts: tuple[str | int, ...], value: object
) -> None:
    path = save_report(tmp_path, results_fixture(scope_fixture()))
    document = json.loads(path.read_text())
    target = document["results"][0]
    for key in parts[:-1]:
        target = target[key]
    target[parts[-1]] = value
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        m2.recorded_kind(tmp_path)


@pytest.mark.parametrize("failure", ["pipeline-failed", "invalid-project"])
def test_failed_capture_round_trip_with_reserved_model_cost(
    tmp_path: Path, failure: str
) -> None:
    records = results_fixture(scope_fixture())
    record = records[0]
    record.pop("behavior")
    record.pop("integrity")
    record.update(source_sha256=None, fully_successful=False, failure_category=failure)
    record["model"]["unknown_cost_reservations"] = 1000
    path = save_report(tmp_path, records)
    assert m2.recorded_kind(tmp_path) == "m2"
    assert json.loads(path.read_text())["results"][0] == record


@pytest.mark.parametrize("path_parts", [("integrity",), ("behavior",), ("model",), ()])
def test_unknown_saved_result_fields_are_rejected(
    tmp_path: Path, path_parts: tuple[str, ...]
) -> None:
    path = save_report(tmp_path, results_fixture(scope_fixture()))
    document = json.loads(path.read_text())
    target = document["results"][0]
    for key in path_parts:
        target = target[key]
    target["unknown"] = 1
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        m2.recorded_kind(tmp_path)


@pytest.mark.parametrize("target", ["score_count", "ledger_schema"])
def test_saved_numeric_identities_keep_their_types(tmp_path: Path, target: str) -> None:
    path = save_report(tmp_path, results_fixture(scope_fixture()))
    document = json.loads(path.read_text())
    if target == "score_count":
        document["scores"]["groups"][0]["variants"] = 20.0
    else:
        document["model_ledger"]["schema"] = True
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        m2.recorded_kind(tmp_path)


def test_exact_replay_chain_preserves_valid_failed_results(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    measure = m1._measure

    def failed(*args: Any, **kwargs: Any) -> dict[str, object]:
        record = copy.deepcopy(measure(*args, **kwargs))
        record["fully_successful"] = False
        integrity = cast(dict[str, Any], record["integrity"])
        integrity.update(passed=False, categories={"embedded_text": 1})
        return record

    monkeypatch.setattr(m1, "_measure", failed)
    original, passed = m1.evaluate_m2(tmp_path, "origin")
    assert not passed
    identity = json.loads(original.read_text())["model_ledger"]
    for name, source in (("first", "origin"), ("second", "first")):
        report, passed = m1.evaluate_m2(tmp_path, name, source)
        assert not passed
        document = json.loads(report.read_text())
        assert document["reproduced"] is True
        assert document["accepted"] is False
        assert document["model_ledger"] == identity
        assert not (tmp_path / f"runs/{name}-rebuild/llm.jsonl").exists()


@pytest.mark.parametrize(
    "contradiction", ["cost_without_tokens", "tokens_without_cost", "unaccounted_blob"]
)
def test_saved_accounting_counts_match_their_evidence(
    tmp_path: Path, contradiction: str
) -> None:
    records = results_fixture(scope_fixture())
    record = records[0]
    if contradiction == "cost_without_tokens":
        record["model"].update(calls=1, cost_nanodollars=1)
    elif contradiction == "tokens_without_cost":
        record["model"]["calls"] = 1
        record["model"]["usage"]["input_tokens"] = 1
    else:
        record["integrity"]["justifications"] = [
            {
                "target": "x86_64-linux-gnu",
                "artifact": "src/program.c",
                "offset": 0,
                "sha256": "a" * 64,
                "size": 4097,
                "reason": "The typed initializer contains only zero bytes.",
            }
        ]
    path = save_report(tmp_path, records)
    with pytest.raises(ValueError):
        m2.recorded_kind(path.parent)


def test_valid_model_charge_and_blob_evidence_round_trip(tmp_path: Path) -> None:
    records = results_fixture(scope_fixture())
    records[0]["model"].update(
        calls=1,
        cost_nanodollars=30500,
        usage={"input_tokens": 10, "cached_input_tokens": 5, "output_tokens": 2},
    )
    records[0]["integrity"].update(
        checked_storage_records=1,
        justifications=[
            {
                "target": "x86_64-linux-gnu",
                "artifact": "src/program.c",
                "offset": 0,
                "sha256": "a" * 64,
                "size": 4097,
                "reason": "The typed initializer contains only zero bytes.",
            }
        ],
    )
    path = save_report(tmp_path, records)
    assert m2.recorded_kind(path.parent) == "m2"
