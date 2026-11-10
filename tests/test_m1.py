import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix_eval import m1
from phoenix_eval.__main__ import main
from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Variant
from phoenix_eval.integrity import IntegrityError
from phoenix_eval.model_ledger import LedgerIdentity, freeze_identity
from phoenix_eval.pair import PairReport
from phoenix_eval.platforms import RuntimeEvidence
from phoenix_eval.provenance import BuildEvidence
from phoenix_eval.submission import (
    Method,
    Submission,
    freeze_package_report,
    freeze_project,
    project_path,
)
from phoenix_eval.toolchain import Compiler


def test_freezes_every_submission_before_opening_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    variants = tuple(
        Variant(f"case-{index}", compiler, flag, "a" * 64, "fixture")
        for index in range(10)
        for compiler in Compiler
        for flag in ("-O0", "-O2")
    )
    submitted: list[tuple[str, str | None]] = []
    opened: list[Path] = []

    def submit(
        workspace: Path,
        directory: Path,
        pipeline_run: str,
        key: str,
        binary: Path,
        method: Method,
        replay_pipeline_run: str | None,
    ) -> Submission:
        assert not opened or replay_pipeline_run is not None
        submitted.append((key, replay_pipeline_run))
        return Submission(method, key, "b" * 64, None, replay_pipeline_run, "d" * 64)

    def cases(
        path: Path, digest: str, names: set[str]
    ) -> dict[str, tuple[Invocation, ...]]:
        opened.append(path)
        assert len(submitted) == 40 * len(opened)
        assert digest == "c" * 64
        return {name: (Invocation(("private synthetic case",)),) for name in names}

    def measure(
        _workspace: Path,
        run: Path,
        _pipeline_run: str,
        task: m1.Task,
        _submission: Submission,
        _binary: Path | bytes,
        _cases: tuple[Invocation, ...],
        _config: m1._Configuration,
        _dev_outputs: frozenset[bytes],
        _origin_bytes: bytes | None,
        _model_ledger: LedgerIdentity,
    ) -> dict[str, object]:
        assert opened
        return {
            "method": task.method,
            "fully_successful": task.method == "phoenix",
            "behavior": {"tuple": (True, False)},
            "reconstruction_seconds": 1 if run.name == "initial" else 2,
        }

    monkeypatch.setattr(m1, "t0_manifest", lambda _: (variants, "a" * 64))
    monkeypatch.setattr(
        m1,
        "_configuration",
        lambda *_: {"heldout_archive_sha256": "c" * 64, "worker_images": {}},
    )
    monkeypatch.setattr(m1, "submit", submit)
    monkeypatch.setattr(m1, "_release_bytes", lambda *_: b"synthetic original")
    monkeypatch.setattr(m1, "_validate_pipeline_record", lambda *_: None)
    monkeypatch.setattr(m1, "verify_development", lambda *_: frozenset({b"public"}))
    monkeypatch.setattr(m1, "heldout_cases", cases)
    monkeypatch.setattr(m1, "_measure", measure)

    report, passed = m1.evaluate_t0(tmp_path, "initial")
    assert passed
    data = json.loads(report.read_text())
    assert data["scores"] == {
        "phoenix": {"fully_successful": 20, "variants": 20},
        "ghidra-raw": {"fully_successful": 0, "variants": 20},
    }
    assert all("-O0-" in key for key, _ in submitted)
    replay, passed = m1.evaluate_t0(tmp_path, "replay", "initial")
    assert passed
    assert json.loads(replay.read_text())["reproduced"] is True
    assert all(source == "initial-rebuild" for _, source in submitted[40:])
    assert "private synthetic case" not in replay.read_text()
    with pytest.raises(ValueError, match="configuration changed"):
        m1.evaluate_t0(tmp_path, "replay")


def test_configuration_binds_archive_and_image_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commits = tmp_path / "docs/corpus_commitments.md"
    commits.parent.mkdir()
    commits.write_text(
        f"| `t0-source.tar.gz` | `{'a' * 64}` |\n"
        f"| `t0-inputs.tar.gz` | `{'b' * 64}` |\n"
    )
    monkeypatch.setattr(m1, "CHECKOUT", tmp_path)
    monkeypatch.setattr(
        subprocess, "run", lambda *_, **_kw: subprocess.CompletedProcess((), 0, b"")
    )
    monkeypatch.setattr(
        m1,
        "verify_runtime",
        lambda _: RuntimeEvidence("arm64", "1", "rosetta", "native"),
    )
    monkeypatch.setattr(
        m1, "evaluator_build", lambda: BuildEvidence("revision", "worker")
    )
    monkeypatch.setattr(m1, "checker_source_digest", lambda: "checker")
    monkeypatch.setattr(m1, "pipeline_source_digest", lambda _: "pipeline")
    monkeypatch.setattr(m1, "pinned_lifting_tools", lambda *_: (tmp_path, tmp_path))
    monkeypatch.setattr(m1, "lifting_tool_identity", lambda *_: {"tool": "identity"})
    monkeypatch.setattr(m1, "freeze_images", lambda _, digest, **_kw: {"amd64": digest})
    result = m1._configuration(tmp_path, "release")
    assert result["revision"] == "revision"
    assert result["source_archive_sha256"] == "a" * 64
    assert result["heldout_archive_sha256"] == "b" * 64
    assert result["worker_images"] != result["checker_images"]
    assert result["pipeline_source_sha256"] == "pipeline"
    assert result["lifting_tool_identity"] == {"tool": "identity"}
    variant = Variant("fixture", Compiler.GCC, "-O0", "a" * 64, "synthetic")
    task = m1.Task(variant, "ghidra-raw")
    record = {
        **result["pipeline_settings"],
        "binary_sha256": variant.sha256,
        "method": "ghidra-raw",
        "revision": "revision",
        "worker_source_sha256": "worker",
        "checker_source_sha256": "checker",
        "pipeline_source_sha256": "pipeline",
        "lifting_tool_identity": {"tool": "identity"},
        "images": {"amd64": "worker"},
        "checker_images": {"amd64": "checker"},
        "replay_from": None,
    }
    checkpoint = tmp_path / "run.json"
    checkpoint.write_text(json.dumps(record))
    m1._validate_pipeline_record(tmp_path, task, None, result)
    for change in (
        {"method": "phoenix"},
        {"checker_source_sha256": "different"},
        {"checker_images": {"amd64": "different"}},
    ):
        checkpoint.write_text(json.dumps({**record, **change}))
        with pytest.raises(ValueError, match="does not match the evaluation plan"):
            m1._validate_pipeline_record(tmp_path, task, None, result)


def test_measurement_does_not_pass_with_incomplete_integrity_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = b"synthetic original"
    variant = Variant(
        "fixture", Compiler.GCC, "-O0", sha256(original).hexdigest(), "synthetic"
    )
    task = m1.Task(variant, "phoenix")
    project = project_path(tmp_path, "pipeline", task.key)
    (project / "src").mkdir(parents=True)
    (project / "src/program.c").write_text("int main(void) { return 0; }\n")
    (project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    (project / "phoenix_report.json").write_text(
        json.dumps(
            {
                "sha256": variant.sha256,
                "method": "phoenix",
                "llm": {},
                "wall_seconds": 1,
            }
        )
    )
    run = tmp_path / "eval"
    snapshot = run / "submissions" / task.key / "capture/project"
    snapshot.parent.mkdir(parents=True)
    submission = Submission(
        "phoenix",
        task.key,
        freeze_project(project, snapshot),
        None,
        report_sha256=freeze_package_report(project, snapshot.parent),
    )
    monkeypatch.setattr(
        m1, "evaluate_pair", lambda *_: PairReport(1, 1, 0, 0, {}, 1, 1, (), True)
    )

    def missing(*_: object) -> None:
        raise IntegrityError("The source check is incomplete.")

    monkeypatch.setattr(m1, "inspect_project", missing)
    configuration: m1._Configuration = {
        "schema": 1,
        "revision": "revision",
        "worker_source_sha256": "worker",
        "checker_source_sha256": "checker",
        "pipeline_source_sha256": "pipeline",
        "lifting_tool_identity": {},
        "pipeline_settings": {},
        "release_manifest_sha256": "release",
        "source_archive_sha256": "source",
        "heldout_archive_sha256": "heldout",
        "worker_images": {},
        "checker_images": {},
        "runtime": {},
    }
    freeze_identity(tmp_path, run, "pipeline")
    result = m1._measure(
        tmp_path,
        run,
        "pipeline",
        task,
        submission,
        original,
        (),
        configuration,
    )
    assert result["fully_successful"] is False
    assert result["integrity"] == {
        "passed": False,
        "categories": {"incomplete_source_check": 1},
    }


def test_cli_replay_dispatches_the_recorded_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "m1.json"
    saved = tmp_path / "runs/recorded/m1.json"
    saved.parent.mkdir(parents=True)
    saved.write_text(
        json.dumps(
            {
                "run_id": "recorded",
                "configuration": {"schema": 1},
                "results": [],
                "scores": {},
                "accepted": False,
            }
        )
    )

    def evaluate(workspace: Path, run_id: str, replay_id: str) -> tuple[Path, bool]:
        assert workspace == tmp_path
        assert run_id.startswith("m1-")
        assert replay_id == "recorded"
        return report, True

    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["phoenix-eval", "--replay", "recorded"])
    monkeypatch.setattr("phoenix_eval.__main__.evaluate_t0", evaluate)
    assert main() == 0
    assert capsys.readouterr().out.strip() == str(report)
