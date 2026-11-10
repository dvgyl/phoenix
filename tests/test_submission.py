import json
import subprocess
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.protection import GUARD_ENV, GUARD_PROBE
from phoenix_eval.provenance import CHECKOUT
from phoenix_eval.submission import (
    EvaluationPending,
    SubmissionError,
    freeze_project,
    project_path,
    read_origin,
    submit,
)
from phoenix_eval.wire import encode_invocation, encode_result


def _project(path: Path) -> None:
    (path / "src").mkdir(parents=True)
    (path / "src/program.c").write_text("int main(void) { return 0; }\n")
    (path / "CMakeLists.txt").write_text(PROJECT_CMAKE)


def test_snapshot_does_not_follow_later_project_edits(tmp_path: Path) -> None:
    source = tmp_path / "original"
    snapshot = tmp_path / "snapshot"
    _project(source)
    assert freeze_project(source, snapshot) == freeze_project(source, snapshot)
    (source / "src/program.c").write_text("int main(void) { return 1; }\n")
    with pytest.raises(SubmissionError, match="different contents"):
        freeze_project(source, snapshot)
    assert (snapshot / "src/program.c").read_text() == "int main(void) { return 0; }\n"


def test_snapshot_rejects_a_custom_build(tmp_path: Path) -> None:
    source = tmp_path / "original"
    _project(source)
    (source / "CMakeLists.txt").write_text(PROJECT_CMAKE + "add_custom_target(other)\n")
    with pytest.raises(SubmissionError, match="fixed build configuration"):
        freeze_project(source, tmp_path / "snapshot")


def test_submission_resumes_after_the_provider_reports_a_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path
    directory = workspace / "runs/measure/submissions/case"
    original = workspace / "sealed/release/case.elf"
    project = project_path(workspace, "pipeline", "case")
    _project(project)
    development = workspace / "runs/pipeline/case/analyze/cases.json"
    development.parent.mkdir()
    outcome = Outcome(b"public", b"", Exited(0), TreeSnapshot())
    development.write_text(
        json.dumps(
            {"cases": [(encode_invocation(Invocation()), encode_result(outcome))]}
        )
    )
    runner = Mock(
        side_effect=[
            subprocess.CompletedProcess((), 75),
            subprocess.CompletedProcess((), 1),
        ]
    )
    monkeypatch.setattr(subprocess, "run", runner)
    monkeypatch.setattr(
        "phoenix_eval.submission.guarded_command", lambda _, command, **_unused: command
    )
    with pytest.raises(EvaluationPending):
        submit(workspace, directory, "pipeline", "case", original, "phoenix")
    first = runner.call_args
    assert first.args[0][-4:] == ("--run-id", "pipeline", "--method", "phoenix")
    assert first.kwargs["env"][GUARD_ENV] == str(directory / GUARD_PROBE)
    assert Path(first.kwargs["env"]["PYTHONPATH"]) == CHECKOUT
    checkpoint = workspace / "runs/pipeline/case/run.json"
    checkpoint.touch()
    result = submit(workspace, directory, "pipeline", "case", original, "phoenix")
    assert result.source_sha256 is not None
    assert runner.call_args.args[0][-2:] == ("--resume", "pipeline")
    assert (
        submit(workspace, directory, "pipeline", "case", original, "phoenix") == result
    )
    with pytest.raises(SubmissionError, match="checkpoint identity"):
        submit(
            workspace, directory, "pipeline", "case", original, "phoenix", "previous"
        )
    assert runner.call_count == 2


@pytest.mark.parametrize("change_before_freeze", [True, False])
def test_raw_lift_summary_is_bound_before_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change_before_freeze: bool
) -> None:
    directory = tmp_path / "runs/measure/submissions/raw"
    original = tmp_path / "original.elf"
    original.write_bytes(b"synthetic original")
    lift = tmp_path / "runs/pipeline/raw/recover"
    lift.mkdir(parents=True)
    origin = b'{"functions": []}'
    digest = sha256(origin).hexdigest()
    (lift / "program.json").write_bytes(b"changed" if change_before_freeze else origin)
    (lift / "evidence.json").write_text(
        json.dumps(
            {
                "sha256": digest,
                "binary_sha256": sha256(original.read_bytes()).hexdigest(),
            }
        )
    )
    monkeypatch.setattr(
        subprocess, "run", Mock(return_value=subprocess.CompletedProcess((), 2))
    )
    monkeypatch.setattr(
        "phoenix_eval.submission.guarded_command", lambda _, command, **_unused: command
    )
    if change_before_freeze:
        with pytest.raises(SubmissionError, match="summary changed"):
            submit(tmp_path, directory, "pipeline", "raw", original, "ghidra-raw")
    else:
        result = submit(tmp_path, directory, "pipeline", "raw", original, "ghidra-raw")
        assert result.origin_sha256 == digest
        snapshot = directory / "origin.json"
        (lift / "program.json").write_bytes(b"changed")
        assert read_origin(snapshot, digest) == origin
        snapshot.write_bytes(b"changed")
        with pytest.raises(SubmissionError, match="summary changed"):
            submit(tmp_path, directory, "pipeline", "raw", original, "ghidra-raw")
