import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval import submission as module
from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.submission import EvaluationPending, Method, SubmissionError, submit
from phoenix_eval.wire import encode_invocation, encode_result


@dataclass(frozen=True)
class Scenario:
    directory: Path
    project: Path
    original: Path
    runner: Mock
    clock: Mock


@pytest.fixture
def scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Scenario:
    directory = tmp_path / "evaluation/submissions/case"
    project = module.project_path(tmp_path, "pipeline", "case")
    (project / "src").mkdir(parents=True)
    (project / "src/program.c").write_text("int main(void) { return 0; }\n")
    (project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    (tmp_path / "runs/pipeline/case/run.json").write_text("{}")
    development = tmp_path / "runs/pipeline/case/analyze/cases.json"
    development.parent.mkdir()
    development.write_text(
        json.dumps(
            {
                "cases": [
                    [
                        encode_invocation(Invocation()),
                        encode_result(Outcome(b"", b"", Exited(0), TreeSnapshot())),
                    ]
                ]
            }
        )
    )
    original = tmp_path / "original.elf"
    original.write_bytes(b"Synthetic input.")
    clock = Mock(return_value=100.0)
    runner = Mock()

    def pipeline(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        clock.return_value += 5.0
        (project / "phoenix_report.json").write_text(
            json.dumps({"wall_seconds": runner.call_count})
        )
        return subprocess.CompletedProcess((), 0, b"", b"")

    runner.side_effect = pipeline
    monkeypatch.setattr(subprocess, "run", runner)
    monkeypatch.setattr(time, "time", clock)
    monkeypatch.setattr(
        module, "guarded_command", lambda _, command, **_kwargs: command
    )
    return Scenario(directory, project, original, runner, clock)


@pytest.mark.parametrize("method", ("phoenix", "ghidra-raw"))
@pytest.mark.parametrize("point", ("source", "report", "record", "publish"))
@pytest.mark.parametrize("failure", (KeyboardInterrupt, OSError))
def test_interrupted_capture_resumes_as_a_valid_submission(
    scenario: Scenario,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: Method,
    point: str,
    failure: type[BaseException],
) -> None:
    args = (tmp_path, scenario.directory, "pipeline", "case", scenario.original, method)
    with monkeypatch.context() as patch:
        if point in ("source", "report"):
            name = "freeze_project" if point == "source" else "freeze_package_report"
            original = getattr(module, name)

            def interrupted(*args: object) -> str:
                original(*args)
                raise failure("Synthetic capture interruption.")

            patch.setattr(module, name, interrupted)
        elif point == "record":
            write = module.write_report

            def interrupted_record(path: Path, data: object) -> None:
                write(path, data)
                if path.name == "submission.json":
                    raise failure("Synthetic commit interruption.")

            patch.setattr(module, "write_report", interrupted_record)
        else:
            replace = Path.replace

            def interrupted_publish(path: Path, target: Path) -> Path:
                result = replace(path, target)
                if target == scenario.directory / "capture":
                    raise failure("Synthetic post-publication interruption.")
                return result

            patch.setattr(Path, "replace", interrupted_publish)
        with pytest.raises(failure):
            submit(*args)

    resumed = submit(*args)
    assert resumed.category is None
    assert resumed.source_sha256 is not None
    assert resumed.report_sha256 is not None
    assert resumed.reconstruction_seconds > 0
    capture = scenario.directory / "capture"
    assert (capture / "project/src/program.c").read_bytes() == (
        scenario.project / "src/program.c"
    ).read_bytes()
    record = json.loads((capture / "submission.json").read_text())
    assert record["report_sha256"] == resumed.report_sha256
    assert record["source_sha256"] == resumed.source_sha256
    assert submit(*args) == resumed
    assert scenario.runner.call_count == (1 if point == "publish" else 2)


def test_provider_wait_and_failed_pipeline_have_recorded_time(
    scenario: Scenario, tmp_path: Path
) -> None:
    codes = iter((75, 2))

    def pipeline(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        scenario.clock.return_value += 5.0
        return subprocess.CompletedProcess((), next(codes), b"", b"")

    scenario.runner.side_effect = pipeline
    args: tuple[Path, Path, str, str, Path, Method] = (
        tmp_path,
        scenario.directory,
        "pipeline",
        "case",
        scenario.original,
        "phoenix",
    )
    with pytest.raises(EvaluationPending):
        submit(*args)
    scenario.clock.return_value = 120.0
    result = submit(*args)
    assert result.category == "pipeline-failed"
    assert result.reconstruction_seconds == 25.0
    scenario.clock.return_value = 200.0
    assert submit(*args).reconstruction_seconds == 25.0
    assert scenario.runner.call_count == 2


@pytest.mark.parametrize(
    "value", (True, -1, float("inf"), "invalid", 101.0, 10**1000, -(10**1000))
)
def test_invalid_start_time_stops_before_pipeline_execution(
    scenario: Scenario, tmp_path: Path, value: object
) -> None:
    scenario.directory.mkdir(parents=True)
    (scenario.directory / "reconstruction-start.json").write_text(
        json.dumps({"started": value})
    )
    with pytest.raises(SubmissionError, match="reconstruction"):
        submit(
            tmp_path,
            scenario.directory,
            "pipeline",
            "case",
            scenario.original,
            "phoenix",
        )
    scenario.runner.assert_not_called()


def test_abandoned_staging_directory_does_not_block_capture(
    scenario: Scenario, tmp_path: Path
) -> None:
    abandoned = scenario.directory / ".capture-abandoned/capture"
    abandoned.mkdir(parents=True)
    stale = abandoned / "report.json"
    stale.write_text('{"wall_seconds": 1}')
    result = submit(
        tmp_path, scenario.directory, "pipeline", "case", scenario.original, "phoenix"
    )
    assert result.category is None
    assert result.source_sha256 is not None
    assert stale.read_text() == '{"wall_seconds": 1}'
