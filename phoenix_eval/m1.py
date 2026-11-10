import fcntl
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from phoenix_eval.build import snapshot_project
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Variant, committed_hash, heldout_cases, t0_manifest
from phoenix_eval.development import DevelopmentError, verify_development
from phoenix_eval.docker import Engine, freeze_images, read_program
from phoenix_eval.integrity import (
    IntegrityError,
    check_integrity,
    inspect_project,
    original_shapes,
)
from phoenix_eval.m0 import SEED
from phoenix_eval.pair import evaluate_pair
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import (
    CHECKER_SOURCE_LABEL,
    CHECKOUT,
    checker_source_digest,
    evaluator_build,
    lifting_tool_identity,
    pinned_lifting_tools,
    pipeline_source_digest,
)
from phoenix_eval.submission import (
    Method,
    Submission,
    project_path,
    read_origin,
    source_digest,
    submit,
    write_report,
)

METHODS: tuple[Method, ...] = ("phoenix", "ghidra-raw")
_RUN_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}")


class _Configuration(TypedDict):
    schema: int
    revision: str
    worker_source_sha256: str
    checker_source_sha256: str
    pipeline_source_sha256: str
    lifting_tool_identity: dict[str, str]
    pipeline_settings: dict[str, object]
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
    ghidra, java = pinned_lifting_tools(workspace, CHECKOUT)
    engines = (Engine.ROSETTA, Engine.ARM64)
    commitments = CHECKOUT / "docs/corpus_commitments.md"
    if workspace.resolve() != workspace:
        raise ValueError("Use the physical workspace path.")
    return {
        "schema": 1,
        "revision": build.commit,
        "worker_source_sha256": build.worker_source_sha256,
        "checker_source_sha256": checker,
        "pipeline_source_sha256": pipeline_source_digest(CHECKOUT),
        "lifting_tool_identity": lifting_tool_identity(ghidra, java),
        "pipeline_settings": {
            "seed": SEED,
            "repair_limit": 20,
            "astra_repair": False,
            "budget_binary": 5_000_000_000,
            "budget_run": 200_000_000_000,
            "ghidra": str(ghidra),
            "java_home": str(java),
        },
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


def _validate_pipeline_record(
    directory: Path, task: Task, replay_of: str | None, config: _Configuration
) -> None:
    try:
        record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        expected = {
            **config["pipeline_settings"],
            "binary_sha256": task.variant.sha256,
            "method": task.method,
            "revision": config["revision"],
            "worker_source_sha256": config["worker_source_sha256"],
            "pipeline_source_sha256": config["pipeline_source_sha256"],
            "lifting_tool_identity": config["lifting_tool_identity"],
            "images": config["worker_images"],
            "replay_from": replay_of,
        }
        if any(
            name not in record or record[name] != value
            for name, value in expected.items()
        ):
            raise ValueError
    except (OSError, TypeError, ValueError):
        raise ValueError(
            "The pipeline checkpoint does not match the evaluation plan."
        ) from None


def _measure(
    workspace: Path,
    run: Path,
    pipeline_run: str,
    task: Task,
    submission: Submission,
    binary: Path | bytes,
    cases: tuple[Invocation, ...],
    config: _Configuration,
    dev_outputs: frozenset[bytes] = frozenset(),
    origin_bytes: bytes | None = None,
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
    snapshot = snapshot_project(directory / "project")
    files = dict(snapshot.files)
    if source_digest(files) != submission.source_sha256:
        raise ValueError("The submitted project changed before evaluation.")
    original = read_program(binary)
    if sha256(original).hexdigest() != variant.sha256:
        raise ValueError("The original bytes do not match the release manifest.")
    original_project = project_path(workspace, pipeline_run, task.key)
    record = json.loads(
        (original_project / "phoenix_report.json").read_text(encoding="utf-8")
    )
    if record.get("sha256") != variant.sha256 or record.get("method") != task.method:
        raise ValueError("The project report does not match the input hash and method.")
    result["model"] = record["llm"]
    result["reconstruction_seconds"] = record["wall_seconds"]
    builds = directory / f"build-{uuid4().hex}"
    builds.mkdir(mode=0o700)
    pair = evaluate_pair(original, snapshot, cases, builds, config["worker_images"])
    result["behavior"] = asdict(pair)
    try:
        evidence = inspect_project(snapshot, config["checker_images"])
        if origin_bytes is None:
            raise IntegrityError(
                "The frozen lift summary is missing.", "incomplete_origin"
            )
        origin = original_shapes(origin_bytes, raw=task.method == "ghidra-raw")
        executables = []
        for build in pair.builds:
            if build.executable_sha256 is None:
                continue
            executable = read_program(
                builds / f"{build.architecture}-{build.compiler}.elf"
            )
            if sha256(executable).hexdigest() != build.executable_sha256:
                raise IntegrityError(
                    "The tested executable changed.", "tested_artifact_changed"
                )
            executables.append(executable)
        integrity = check_integrity(
            original,
            files,
            tuple(executables),
            evidence,
            dev_outputs,
            origin,
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


def _release_bytes(variant: Variant, release: Path) -> bytes:
    program = read_program(variant.executable(release))
    if sha256(program).hexdigest() != variant.sha256:
        raise ValueError("A released executable changed before measurement.")
    return program


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
    plan = {
        "configuration": config,
        "replay_of": replay.name if replay is not None else None,
    }
    if (
        config_file.exists()
        and json.loads(config_file.read_text(encoding="utf-8")) != plan
    ):
        raise ValueError("The evaluation configuration changed after it was recorded.")
    prior = None
    if replay is not None:
        prior = json.loads((replay / "m1.json").read_text(encoding="utf-8"))
        if prior["configuration"] != config:
            raise ValueError("Replay requires the same evaluation configuration.")
    write_report(config_file, plan)
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
    originals = {
        variant.key: _release_bytes(variant, release)
        for variant in variants
        if variant.flag == "-O0"
    }
    development = {}
    origins = {}
    for task in tasks:
        submission = submissions[task.key]
        if submission.source_sha256 is not None or submission.origin_sha256 is not None:
            _validate_pipeline_record(
                workspace / "runs" / pipeline_run / task.key,
                task,
                replay_pipeline,
                config,
            )
        if task.method == "ghidra-raw" and submission.origin_sha256 is not None:
            origins[task.variant.key] = read_origin(
                run / "submissions" / task.key / "origin.json", submission.origin_sha256
            )
        if task.method == "phoenix" and submission.source_sha256 is not None:
            digest = submission.development_sha256
            if digest is None:
                raise DevelopmentError("The submission has no development evidence.")
            development[task.variant.key] = verify_development(
                originals[task.variant.key],
                run / "submissions" / task.key / "development.json",
                digest,
                config["worker_images"],
            )
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
            originals[task.variant.key],
            cases[task.variant.name],
            config,
            development.get(task.variant.key, frozenset()),
            origins.get(task.variant.key),
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
