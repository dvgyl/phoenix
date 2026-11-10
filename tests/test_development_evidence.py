import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix import pipeline
from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.generate import Candidate, Definition, write_project
from phoenix.verify import Check, Verification
from phoenix_eval.build import BuildResult, ProjectSnapshot, snapshot_project
from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.toolchain import Compiler
from phoenix_eval.trace import CodeTrace
from phoenix_eval.wire import encode_result


@pytest.fixture
def checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings]:
    project = tmp_path / "project"
    write_project(
        project,
        Candidate("", (Definition(0, "int main(void)", "return 0;", "Fixture"),)),
    )
    expected = Outcome(
        b"expected", b"", Exited(0), TreeSnapshot(), CodeTrace(0, 1, (0,))
    )
    analysis = Analysis((DevelopmentCase(Invocation(), expected),), 1, 1, 1, 0, 0)
    builds = tmp_path / "builds"
    builds.mkdir()
    checks = []
    for engine in (Engine.ROSETTA, Engine.ARM64):
        for compiler in Compiler:
            executable = builds / f"{engine.value}-{compiler}.elf"
            executable.write_bytes(b"synthetic executable")
            checks.append(
                Check(
                    BuildResult(engine, compiler, executable, 0, ""),
                    (expected,),
                    ((),),
                    executable.read_bytes(),
                )
            )
    live = Mock(return_value=Verification(tuple(checks), 1))
    monkeypatch.setattr(pipeline, "verify_project", live)
    args = (
        snapshot_project(project),
        builds,
        tmp_path / "result.json",
        analysis,
        pipeline.Settings({}, 0, tmp_path, tmp_path, 0, False, {}),
    )
    assert pipeline._verify(*args).passed
    live.side_effect = AssertionError("A saved checkpoint must not run a build.")
    return args


def test_cached_differences_are_derived_from_outcomes(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    wrong = Outcome(b"wrong", b"", Exited(1), TreeSnapshot())
    for check in saved["checks"]:
        check["outcomes"] = [encode_result(wrong)]
        check["differences"] = [[]]
    path.write_text(json.dumps(saved))
    result = pipeline._verify(*checkpoint)
    assert not result.passed
    assert not result.passed_cases
    assert all(
        check.differences == (("stdout", "termination"),) for check in result.checks
    )


@pytest.mark.parametrize("change", ["duplicate", "wrong", "missing", "extra"])
def test_cached_build_matrix_must_be_complete_and_distinct(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
    change: str,
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    checks = saved["checks"]
    if change == "duplicate":
        checks[3] = checks[0]
    elif change == "wrong":
        checks[3]["build"].update(
            engine=Engine.QEMU_X86_64, executable=None, executable_sha256=None
        )
        checks[3]["outcomes"] = []
        checks[3]["differences"] = []
    elif change == "missing":
        checks.pop()
    else:
        checks.append(checks[0])
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="configuration"):
        pipeline._verify(*checkpoint)


@pytest.mark.parametrize("change", ["input", "expected", "trace", "count"])
def test_checkpoint_binds_development_cases(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
    change: str,
) -> None:
    project, builds, path, analysis, settings = checkpoint
    case = analysis.cases[0]
    if change == "input":
        case = replace(case, invocation=Invocation(stdin=b"changed"))
    elif change == "expected":
        case = replace(case, expected=replace(case.expected, stdout=b"changed"))
    elif change == "trace":
        case = replace(
            case, expected=replace(case.expected, trace=CodeTrace(0, 2, (1,)))
        )
    changed = replace(analysis, cases=(case, case) if change == "count" else (case,))
    with pytest.raises(ValueError, match="development"):
        pipeline._verify(project, builds, path, changed, settings)


@pytest.mark.parametrize("change", ["short", "long", "failed", "missing_hash"])
def test_checkpoint_rejects_inconsistent_build_observations(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
    change: str,
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    check = saved["checks"][0]
    if change == "short":
        check["outcomes"] = []
    elif change == "long":
        check["outcomes"] *= 2
    elif change == "failed":
        check["build"].update(executable=None, executable_sha256=None)
    else:
        check["build"]["executable_sha256"] = None
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        pipeline._verify(*checkpoint)


def test_new_checkpoints_store_observations_without_verdicts(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
) -> None:
    saved = json.loads(checkpoint[2].read_text())
    assert all("differences" not in check for check in saved["checks"])
    assert pipeline._verify(*checkpoint).passed


def test_saved_false_failures_do_not_override_matching_observations(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    for check in saved["checks"]:
        check["differences"] = [["stdout"]]
    path.write_text(json.dumps(saved))
    assert pipeline._verify(*checkpoint).passed


def test_failed_build_has_no_results_or_executable_identity(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    check = saved["checks"][0]
    check["build"]["executable"] = None
    check["outcomes"] = []
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="failed build"):
        pipeline._verify(*checkpoint)
    check["build"]["executable_sha256"] = None
    path.write_text(json.dumps(saved))
    result = pipeline._verify(*checkpoint)
    assert not result.passed
    assert not result.passed_cases


def test_unbound_legacy_checkpoint_is_rejected(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
) -> None:
    path = checkpoint[2]
    saved = json.loads(path.read_text())
    del saved["development_sha256"]
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="development"):
        pipeline._verify(*checkpoint)


@pytest.mark.parametrize("change", ["source", "executable", "missing_executable"])
def test_checkpoint_keeps_tested_source_and_executable_identities(
    checkpoint: tuple[ProjectSnapshot, Path, Path, Analysis, pipeline.Settings],
    change: str,
) -> None:
    snapshot, builds, path, analysis, settings = checkpoint
    if change == "source":
        snapshot = replace(snapshot, archive=snapshot.archive + b"changed")
    else:
        executable = builds / "rosetta-gcc.elf"
        if change == "executable":
            executable.write_bytes(b"changed")
        else:
            executable.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        pipeline._verify(snapshot, builds, path, analysis, settings)
