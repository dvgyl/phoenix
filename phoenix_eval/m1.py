import fcntl
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from phoenix_eval.build import project_files
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Variant, committed_hash, heldout_cases, t0_manifest
from phoenix_eval.docker import Engine, freeze_images
from phoenix_eval.integrity import IntegrityError, check_integrity, inspect_project
from phoenix_eval.outcome import Outcome
from phoenix_eval.pair import evaluate_pair
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import (
    CHECKER_SOURCE_LABEL,
    CHECKOUT,
    checker_source_digest,
    evaluator_build,
)
from phoenix_eval.submission import (
    Method,
    Submission,
    project_path,
    source_digest,
    submit,
    write_report,
)
from phoenix_eval.wire import decode_result

METHODS: tuple[Method, ...] = ("phoenix", "ghidra-raw")
_RUN_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}")


class _Configuration(TypedDict):
    schema: int
    revision: str
    worker_source_sha256: str
    checker_source_sha256: str
    release_manifest_sha256: str
    source_archive_sha256: str
    heldout_archive_sha256: str
    worker_images: dict[str, str]
    checker_images: dict[str, str]
    runtime: dict[str, object]


@dataclass(frozen=True, slots=True)
class Task:
    variant: Variant
    method: Method

    @property
    def key(self) -> str:
        return f"{self.variant.key}-{self.method}"


def _directory(runs: Path, run_id: str) -> Path:
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("Use a valid evaluation run ID.")
    directory = runs / run_id
    if directory.resolve() != directory:
        raise ValueError("The evaluation run cannot be a symbolic link.")
    return directory


def _configuration(workspace: Path, release_hash: str) -> _Configuration:
    status = subprocess.run(
        (
            "git",
            "-C",
            str(CHECKOUT),
            "status",
            "--porcelain",
            "--untracked-files=normal",
        ),
        capture_output=True,
        check=True,
        timeout=15,
    )
    if status.stdout:
        raise ValueError("The sealed evaluation requires a clean checkout.")
    runtime = verify_runtime("apple-silicon")
    build = evaluator_build()
    checker = checker_source_digest()
    engines = (Engine.ROSETTA, Engine.ARM64)
    commitments = CHECKOUT / "docs/corpus_commitments.md"
    if workspace.resolve() != workspace:
        raise ValueError("Use the physical workspace path.")
    return {
        "schema": 1,
        "revision": build.commit,
        "worker_source_sha256": build.worker_source_sha256,
        "checker_source_sha256": checker,
        "release_manifest_sha256": release_hash,
        "source_archive_sha256": committed_hash(commitments, "t0-source.tar.gz"),
        "heldout_archive_sha256": committed_hash(commitments, "t0-inputs.tar.gz"),
        "worker_images": freeze_images(engines, build.worker_source_sha256),
        "checker_images": freeze_images(
            engines,
            checker,
            repository="phoenix-c-integrity",
            source_label=CHECKER_SOURCE_LABEL,
        ),
        "runtime": asdict(runtime),
    }


def _development_outputs(path: Path, *, required: bool) -> frozenset[bytes]:
    if not path.is_file():
        if required:
            raise IntegrityError("The original development outcomes are missing.")
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        outputs: set[bytes] = set()
        if not data["cases"]:
            raise ValueError
        for _, record in data["cases"]:
            outcome = decode_result(record)
            if not isinstance(outcome, Outcome):
                raise ValueError
            outputs.update((outcome.stdout, outcome.stderr))
        return frozenset(outputs)
    except (TypeError, KeyError, ValueError, OSError):
        raise IntegrityError("The saved development evidence is invalid.") from None


def _measure(
    workspace: Path,
    run: Path,
    pipeline_run: str,
    task: Task,
    submission: Submission,
    binary: Path,
    cases: tuple[Invocation, ...],
    config: _Configuration,
) -> dict[str, object]:
    variant = task.variant
    result: dict[str, object] = {
        **asdict(variant),
        "method": task.method,
        "source_sha256": submission.source_sha256,
        "fully_successful": False,
    }
    if submission.source_sha256 is None:
        return {**result, "failure_category": submission.category}
    directory = run / "submissions" / task.key
    snapshot = directory / "project"
    files = project_files(snapshot)
    if source_digest(files) != submission.source_sha256:
        raise ValueError("The submitted project changed before evaluation.")
    original_project = project_path(workspace, pipeline_run, task.key)
    record = json.loads(
        (original_project / "phoenix_report.json").read_text(encoding="utf-8")
    )
    if record.get("sha256") != variant.sha256:
        raise ValueError("The project report does not match the released input hash.")
    result["model"] = record["llm"]
    result["reconstruction_seconds"] = record["wall_seconds"]
    builds = directory / f"build-{uuid4().hex}"
    builds.mkdir(mode=0o700)
    pair = evaluate_pair(binary, snapshot, cases, builds, config["worker_images"])
    result["behavior"] = asdict(pair)
    try:
        evidence = inspect_project(snapshot, config["checker_images"])
        executable_paths = tuple(
            builds / f"{build.architecture}-{build.compiler}.elf"
            for build in pair.builds
            if build.compiled
        )
        development = (
            workspace
            / "runs"
            / pipeline_run
            / f"{variant.key}-phoenix"
            / "analyze/cases.json"
        )
        integrity = check_integrity(
            binary.read_bytes(),
            files,
            tuple(path.read_bytes() for path in executable_paths),
            evidence,
            _development_outputs(development, required=task.method == "phoenix"),
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        category = (
            error.category if isinstance(error, IntegrityError) else "integrity_error"
        )
        result["integrity"] = {"passed": False, "categories": {category: 1}}
    else:
        result["integrity"] = asdict(integrity)
        result["fully_successful"] = pair.behavior_passed and integrity.passed
    return result


def _scores(records: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    return {
        method: {
            "fully_successful": sum(
                record["method"] == method and record["fully_successful"] is True
                for record in records
            ),
            "variants": sum(record["method"] == method for record in records),
        }
        for method in METHODS
    }


def _stable_records(records: list[dict[str, object]]) -> str:
    stable = [
        {key: value for key, value in record.items() if key != "reconstruction_seconds"}
        for record in records
    ]
    return json.dumps(stable, ensure_ascii=True, sort_keys=True)


def _evaluate(workspace: Path, run: Path, replay: Path | None) -> tuple[Path, bool]:
    release = workspace / "sealed/release/t0"
    variants, release_hash = t0_manifest(release)
    config = _configuration(workspace, release_hash)
    config_file = run / "configuration.json"
    if (
        config_file.exists()
        and json.loads(config_file.read_text(encoding="utf-8")) != config
    ):
        raise ValueError("The evaluation configuration changed after it was recorded.")
    prior = None
    if replay is not None:
        prior = json.loads((replay / "m1.json").read_text(encoding="utf-8"))
        if prior["configuration"] != config:
            raise ValueError("Replay requires the same evaluation configuration.")
    write_report(config_file, config)
    pipeline_run = f"{run.name}-rebuild"
    replay_pipeline = f"{replay.name}-rebuild" if replay is not None else None
    tasks = tuple(
        Task(variant, method)
        for variant in variants
        if variant.flag == "-O0"
        for method in METHODS
    )
    submissions = {
        task.key: submit(
            workspace,
            run / "submissions" / task.key,
            pipeline_run,
            task.key,
            task.variant.executable(release),
            task.method,
            replay_pipeline,
        )
        for task in tasks
    }
    if _configuration(workspace, release_hash) != config:
        raise ValueError("The evaluation configuration changed before measurement.")
    if t0_manifest(release) != (variants, release_hash):
        raise ValueError("The released binaries changed before measurement.")
    cases = heldout_cases(
        workspace / "holdout/t0-inputs.tar.gz",
        config["heldout_archive_sha256"],
        {task.variant.name for task in tasks},
    )
    records = [
        _measure(
            workspace,
            run,
            pipeline_run,
            task,
            submissions[task.key],
            task.variant.executable(release),
            cases[task.variant.name],
            config,
        )
        for task in tasks
    ]
    scores = _scores(records)
    phoenix = scores["phoenix"]
    accepted = phoenix["variants"] == 20 and phoenix["fully_successful"] >= 16
    reproduced = (
        _stable_records(records)
        == _stable_records(cast(list[dict[str, object]], prior["results"]))
        if prior is not None
        else None
    )
    report = run / "m1.json"
    write_report(
        report,
        {
            "run_id": run.name,
            "replay_of": replay.name if replay is not None else None,
            "reproduced": reproduced,
            "configuration": config,
            "corpus": "agent-sealed",
            "coverage_kind": "recovered_block_entries",
            "scores": scores,
            "results": records,
            "accepted": accepted,
        },
    )
    return report, accepted and reproduced is not False


def evaluate_t0(
    workspace: Path, run_id: str | None = None, replay_id: str | None = None
) -> tuple[Path, bool]:
    workspace = workspace.resolve()
    runs = workspace / "runs"
    if runs.resolve() != runs:
        raise ValueError("The evaluation run directory cannot be a symbolic link.")
    run = _directory(runs, run_id or f"m1-{uuid4().hex}")
    replay = _directory(runs, replay_id) if replay_id is not None else None
    if run == replay:
        raise ValueError("Replay requires a new evaluation run ID.")
    run.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        run / "evaluation.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _evaluate(workspace, run, replay)
