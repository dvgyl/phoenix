import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from phoenix_eval import run_binary as scoring
from phoenix_eval.build import PROJECT_CMAKE, snapshot_project
from phoenix_eval.case import Invocation
from phoenix_eval.dev_corpus import DevBinary, ValidatedCases
from phoenix_eval.integrity import IntegrityReport
from phoenix_eval.pair import BuildReport, PairReport
from phoenix_eval.run_plan import case_identity
from phoenix_eval.run_records import RunPlan, Selection
from phoenix_eval.submission import Submission, freeze_project, project_path
from phoenix_eval.toolchain import Compiler


@pytest.fixture
def capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]]:
    original = b"Synthetic bytes. Never execute on the host."
    binary = DevBinary(
        "fixture",
        "D0",
        "gcc",
        ("-std=c11", "-O0", "-lm"),
        sha256(original).hexdigest(),
        "fixture",
        True,
    )
    source = tmp_path / "dev_bin/fixture/gcc-O0/fixture"
    source.parent.mkdir(parents=True)
    source.write_bytes(original)
    root = tmp_path / "repo"
    holdout = root / "corpus_dev/fixture/holdout"
    holdout.mkdir(parents=True)
    (holdout / "cases.jsonl").write_text("fixture\n" * 100)
    monkeypatch.setattr(scoring, "CHECKOUT", root)
    monkeypatch.setattr(
        scoring,
        "load_validated_cases",
        lambda *_: ValidatedCases((Invocation(),) * 100, tuple(range(100)), (), 100),
    )
    images = {arch: "sha256:" + "a" * 64 for arch in ("amd64", "arm64")}
    configuration: dict[str, object] = {
        "revision": "f" * 40,
        "worker_source_sha256": "a" * 64,
        "checker_source_sha256": "b" * 64,
        "pipeline_source_sha256": "c" * 64,
        "worker_images": images,
        "checker_images": images,
        "lifting_tool_identity": {"fixture": "d" * 64},
        "pipeline_settings": {
            "seed": 17,
            "repair_limit": 20,
            "strongest_repair": False,
        },
        "case_counts": {scoring.task_key(binary): 100},
        "case_hashes": {
            scoring.task_key(binary): case_identity(
                root / "corpus_dev",
                binary,
                ValidatedCases((Invocation(),) * 100, tuple(range(100)), (), 100),
            )[1],
        },
    }
    plan = RunPlan(
        "measure",
        Selection(),
        (binary,),
        configuration,
        "e" * 64,
        "f" * 64,
        True,
        1.0,
        ("measure-p", "measure-check"),
    )
    flags = {
        "arm_failure": False,
        "integrity_failure": False,
        "break_report": False,
        "tamper": False,
        "guard": True,
        "drop_case": False,
    }

    def submit(
        workspace: Path,
        directory: Path,
        pipeline: str,
        key: str,
        path: Path,
        method: str,
        replay: str | None = None,
        **_: object,
    ) -> Submission:
        project = project_path(workspace, pipeline, key)
        (project / "src").mkdir(parents=True)
        (project / "src/program.c").write_text("int main(void) { return 0; }\n")
        (project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
        snapshot = snapshot_project(project)
        report = {
            "wall_seconds": 1,
            "sha256": binary.sha256,
            "method": method,
            "project_sha256": sha256(snapshot.archive).hexdigest(),
            "development_behavior_passed": True,
        }
        report_bytes = json.dumps(report).encode()
        (project / "phoenix_report.json").write_bytes(report_bytes)
        (project / "PHOENIX_REPORT.md").write_text(
            "changed" if replay and flags["break_report"] else "fixture"
        )
        capture = directory / "capture"
        capture.mkdir(parents=True)
        source_hash = freeze_project(project, capture / "project")
        (capture / "report.json").write_bytes(report_bytes)
        development = b"fixture development"
        (capture / "development.json").write_bytes(development)
        origin = json.dumps(
            {"functions": [{"name": "main", "raw_c": "return 0;"}]}
        ).encode()
        (capture / "origin.json").write_bytes(origin)
        checkpoint = {
            **configuration,
            **cast(dict[str, object], configuration["pipeline_settings"]),
            "version": 1,
            "binary_sha256": binary.sha256,
            "images": images,
            "checker_images": images,
            "protection": {"profile": "pipeline", "probe_denied": flags["guard"]},
            "method": method,
            "replay_from": replay,
            "budget_binary": 3_000_000_000,
        }
        (workspace / "runs" / pipeline / key / "run.json").write_text(
            json.dumps(checkpoint)
        )
        return Submission(
            "phoenix",
            key,
            source_hash,
            None,
            replay,
            sha256(development).hexdigest(),
            sha256(origin).hexdigest(),
            sha256(report_bytes).hexdigest(),
            1.0,
        )

    def pair(
        original: bytes,
        snapshot: object,
        cases: object,
        builds: Path,
        images: dict[str, str],
    ) -> PairReport:
        reports = []
        for arch in ("amd64", "arm64"):
            for cc in (Compiler.GCC, Compiler.CLANG):
                executable = f"fixture-{arch}-{cc}".encode()
                (builds / f"{arch}-{cc}.elf").write_bytes(
                    executable + (b"changed" if flags["tamper"] else b"")
                )
                matched = 0 if arch == "arm64" and flags["arm_failure"] else 100
                reports.append(
                    BuildReport(
                        arch,
                        cc,
                        True,
                        0,
                        matched,
                        0,
                        {},
                        sha256(executable).hexdigest(),
                    )
                )
        return PairReport(
            100,
            99 if flags["drop_case"] else 100,
            0,
            0,
            {},
            1,
            1,
            tuple(reports),
            not flags["arm_failure"],
        )

    monkeypatch.setattr(scoring, "submit", submit)
    monkeypatch.setattr(scoring, "verify_development", lambda *_: frozenset())
    monkeypatch.setattr(scoring, "evaluate_pair", pair)
    monkeypatch.setattr(scoring, "inspect_project", lambda *_: ())
    monkeypatch.setattr(
        scoring,
        "check_integrity",
        lambda *_: IntegrityReport(
            not flags["integrity_failure"],
            {"embedded_text": 1} if flags["integrity_failure"] else {},
            0,
            4,
            (),
            (),
            (),
        ),
    )
    monkeypatch.setattr(scoring, "register_named_locals", lambda *_, **__: 0)
    run = tmp_path / "runs/measure"
    run.mkdir(parents=True)
    return tmp_path, run, binary, plan, flags


def test_complete_capture_is_scored_against_all_valid_cases(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
) -> None:
    workspace, run, binary, plan, _ = capture
    result = scoring.measure(workspace, run, binary, plan)
    assert result.fully_successful
    assert result.held_out_cases == (400, 400)
    assert result.details["replay_identical"] is True


@pytest.mark.parametrize(
    "flag,category",
    [
        ("arm_failure", "behavior_arm_only"),
        ("integrity_failure", "integrity"),
        ("break_report", "pipeline_error"),
        ("drop_case", "pipeline_error"),
    ],
)
def test_each_failed_success_condition_stays_a_failure(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
    flag: str,
    category: str,
) -> None:
    workspace, run, binary, plan, flags = capture
    flags[flag] = True
    result = scoring.measure(workspace, run, binary, plan)
    assert not result.fully_successful
    assert category in result.categories
    assert result.held_out_cases[1] == 400


@pytest.mark.parametrize(
    "flag,message", [("guard", "checkpoint"), ("tamper", "tested executable")]
)
def test_changed_or_unprotected_evidence_cannot_pass(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
    flag: str,
    message: str,
) -> None:
    workspace, run, binary, plan, flags = capture
    flags[flag] = flag != "guard"
    with pytest.raises(ValueError, match=message):
        scoring.measure(workspace, run, binary, plan)


def test_cold_binary_uses_its_own_empty_cache_root(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, run, binary, plan, _ = capture
    submit = Mock(wraps=getattr(scoring, "submit"))
    monkeypatch.setattr(scoring, "submit", submit)
    result = scoring.measure(workspace, run, binary, replace(plan, llm_cache=False))
    assert result.fully_successful
    assert submit.call_args_list[0].kwargs[
        "cache_root"
    ] == run / "cold-cache" / scoring.task_key(binary)
    assert "cache_root" not in submit.call_args_list[1].kwargs


def test_checkpoint_rejects_a_different_seed(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
) -> None:
    workspace, run, binary, plan, _ = capture
    scoring.measure(workspace, run, binary, plan)
    path = workspace / "runs" / plan.pipeline / scoring.task_key(binary) / "run.json"
    record = json.loads(path.read_bytes())
    record["seed"] = 18
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="checkpoint"):
        scoring.validate_checkpoint(path.parent, binary, plan, None)


@pytest.mark.parametrize("change", ["count", "input"])
def test_scoring_rejects_changed_frozen_cases(
    capture: tuple[Path, Path, DevBinary, RunPlan, dict[str, bool]],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    workspace, run, binary, plan, _ = capture
    if change == "count":
        monkeypatch.setattr(
            scoring,
            "load_validated_cases",
            lambda *_: ValidatedCases(
                (Invocation(),) * 95,
                tuple(range(95)),
                tuple(range(95, 100)),
                100,
            ),
        )
    else:
        (workspace / "repo/corpus_dev/fixture/holdout/cases.jsonl").write_text(
            "changed\n" * 100
        )
    submit = Mock()
    monkeypatch.setattr(scoring, "submit", submit)
    with pytest.raises(ValueError, match="held-out cases differ"):
        scoring.measure(workspace, run, binary, plan)
    submit.assert_not_called()
