import fcntl
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import NotRequired, TypedDict, cast
from uuid import uuid4

from phoenix_eval.build import snapshot_project
from phoenix_eval.capture_binding import freeze_binding, open_binding, verify_binding
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import (
    Tier,
    Variant,
    committed_hash,
    heldout_cases,
    release_manifest,
    t0_manifest,
)
from phoenix_eval.development import DevelopmentError, verify_development
from phoenix_eval.docker import Engine, freeze_images, read_program
from phoenix_eval.integrity import (
    IntegrityError,
    check_integrity,
    inspect_project,
    original_shapes,
)
from phoenix_eval.m0 import SEED
from phoenix_eval.m2 import Batch, ReportKind, Scope, recorded_kind, summarize
from phoenix_eval.model_ledger import (
    LedgerIdentity,
    bound_summaries,
    bound_summary,
    freeze_identity,
    read_identity,
    require_no_replay_ledger,
    verify_identity,
)
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
    read_origin,
    read_package_report,
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
    scope: NotRequired[dict[str, object]]


@dataclass(frozen=True, slots=True)
class Task:
    variant: Variant
    method: Method
    tier: Tier | None = None

    @property
    def variant_key(self) -> str:
        prefix = f"{self.tier.lower()}-" if self.tier is not None else ""
        return f"{prefix}{self.variant.key}"

    @property
    def key(self) -> str:
        return f"{self.variant_key}-{self.method}"


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
            "checker_source_sha256": config["checker_source_sha256"],
            "pipeline_source_sha256": config["pipeline_source_sha256"],
            "lifting_tool_identity": config["lifting_tool_identity"],
            "images": config["worker_images"],
            "checker_images": config["checker_images"],
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
    model_ledger: LedgerIdentity | None = None,
) -> dict[str, object]:
    variant = task.variant
    result: dict[str, object] = {
        **asdict(variant),
        "method": task.method,
        "source_sha256": submission.source_sha256,
        "fully_successful": False,
        "model": asdict(bound_summary(workspace, run, task.key, model_ledger)),
        "reconstruction_seconds": submission.reconstruction_seconds,
    }
    if submission.source_sha256 is None:
        return {**result, "failure_category": submission.category}
    directory = run / "submissions" / task.key / "capture"
    snapshot = snapshot_project(directory / "project")
    files = dict(snapshot.files)
    if source_digest(files) != submission.source_sha256:
        raise ValueError("The submitted project changed before evaluation.")
    original = read_program(binary)
    if sha256(original).hexdigest() != variant.sha256:
        raise ValueError("The original bytes do not match the release manifest.")
    if submission.report_sha256 is None:
        raise ValueError("The submission has no bound package report.")
    record = read_package_report(directory / "report.json", submission.report_sha256)
    if record.get("sha256") != variant.sha256 or record.get("method") != task.method:
        raise ValueError("The project report does not match the input hash and method.")
    builds = directory.parent / f"build-{uuid4().hex}"
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


def _same_json(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _stable_m2_report(document: dict[str, object]) -> str:
    stable = {
        **{
            key: value
            for key, value in document.items()
            if key not in {"run_id", "replay_of", "reproduced", "results"}
        },
        "results": _stable_records(cast(list[dict[str, object]], document["results"])),
    }
    return json.dumps(stable, sort_keys=True, allow_nan=False)


def _m2_scope(workspace: Path) -> Scope:
    batches = []
    for tier in Tier:
        variants, digest = release_manifest(
            workspace / "sealed/release" / tier.lower(), tier
        )
        commitments = CHECKOUT / "docs/corpus_commitments.md"
        batches.append(
            Batch(
                tier,
                variants,
                digest,
                committed_hash(commitments, f"{tier.lower()}-source.tar.gz"),
                committed_hash(commitments, f"{tier.lower()}-inputs.tar.gz"),
            )
        )
    return Scope.parse(Scope(tuple(batches)).record())


@dataclass(frozen=True, slots=True)
class _ReplayLineage:
    origin_pipeline: str
    replay_pipelines: tuple[str, ...]


def _m2_replay_lineage(
    workspace: Path, replay: Path, keys: tuple[str, ...]
) -> _ReplayLineage:
    identity = read_identity(replay / "model-ledger.json")
    configuration = None
    stable = None
    visited: set[str] = set()
    replay_pipelines: list[str] = []
    while True:
        if replay.name in visited or recorded_kind(replay) != "m2":
            raise ValueError("The M2 replay lineage is invalid.")
        visited.add(replay.name)
        if open_binding(replay, keys) is None:
            raise ValueError("The M2 replay ancestor has no frozen capture binding.")
        record = json.loads((replay / "m2.json").read_text(encoding="utf-8"))
        if configuration is None:
            configuration = record["configuration"]
            stable = _stable_m2_report(record)
        if (
            not _same_json(record["configuration"], configuration)
            or not _same_json(record["model_ledger"], identity)
            or not _same_json(read_identity(replay / "model-ledger.json"), identity)
        ):
            raise ValueError("The M2 replay lineage changed its configuration or log.")
        source = record["replay_of"]
        if _stable_m2_report(record) != stable or (
            source is not None and record["reproduced"] is not True
        ):
            raise ValueError("The M2 replay lineage did not reproduce stable results.")
        if source is None:
            if identity["pipeline_run"] != f"{replay.name}-rebuild":
                raise ValueError("The M2 model log has a different origin.")
            return _ReplayLineage(identity["pipeline_run"], tuple(replay_pipelines))
        if not isinstance(source, str):
            raise ValueError("The M2 replay origin is invalid.")
        replay_pipelines.append(f"{replay.name}-rebuild")
        replay = _directory(workspace / "runs", source)


def _evaluate(
    workspace: Path, run: Path, replay: Path | None, kind: ReportKind = "m1"
) -> tuple[Path, bool]:
    release = workspace / "sealed/release/t0"
    scope = _m2_scope(workspace) if kind == "m2" else None
    if scope is None:
        variants, release_hash = t0_manifest(release)
    else:
        variants, release_hash = (
            scope.batches[0].variants,
            scope.batches[0].manifest_sha256,
        )
    config = _configuration(workspace, release_hash)
    if scope is not None:
        config.update({"schema": 2, "scope": scope.record()})
    config_file = run / "configuration.json"
    if (
        scope is not None
        and not config_file.is_file()
        and ((run / "model-ledger.json").exists() or (run / "submissions").exists())
    ):
        raise ValueError("The M2 capture has no recorded configuration.")
    plan = {
        "configuration": config,
        "replay_of": replay.name if replay is not None else None,
    }
    if config_file.exists() and not _same_json(
        json.loads(config_file.read_text(encoding="utf-8")), plan
    ):
        raise ValueError("The evaluation configuration changed after it was recorded.")
    prior = None
    if replay is not None:
        if scope is not None and recorded_kind(replay) != kind:
            raise ValueError("The replay report kind does not match the command.")
        prior = json.loads((replay / f"{kind}.json").read_text(encoding="utf-8"))
        if not _same_json(prior["configuration"], config):
            raise ValueError("Replay requires the same evaluation configuration.")
    tasks = tuple(
        Task(variant, method)
        for variant in variants
        if variant.flag == "-O0"
        for method in METHODS
    )
    if scope is not None:
        tasks = tuple(
            Task(variant, method, batch.tier)
            for batch in scope.batches
            for variant in batch.variants
            for method in METHODS
        )
    keys = tuple(task.key for task in tasks)
    capture_binding = open_binding(run, keys)
    write_report(config_file, plan)
    pipeline_run = f"{run.name}-rebuild"
    replay_pipeline = f"{replay.name}-rebuild" if replay is not None else None
    replay_pipelines: tuple[str, ...] = (pipeline_run,) if replay is not None else ()
    if scope is not None and replay is not None:
        lineage = _m2_replay_lineage(workspace, replay, keys)
        replay_pipeline = lineage.origin_pipeline
        replay_pipelines += lineage.replay_pipelines

    def check_replay_ledgers() -> None:
        for pipeline in replay_pipelines:
            require_no_replay_ledger(workspace, pipeline)

    identity_file = run / "model-ledger.json"
    if identity_file.exists() or identity_file.is_symlink():
        saved_identity = read_identity(identity_file)
        if saved_identity["pipeline_run"] != (replay_pipeline or pipeline_run):
            raise ValueError("The model ledger identity has a different pipeline run.")
        verify_identity(workspace, saved_identity)
    completed_report = run / f"{kind}.json"
    if completed_report.exists():
        if capture_binding is None:
            raise ValueError("The completed report has no frozen capture binding.")
        if scope is not None and recorded_kind(run) != kind:
            raise ValueError("The completed M2 report has a different scope.")
        completed = json.loads(completed_report.read_text(encoding="utf-8"))
        if not _same_json(completed.get("configuration"), config):
            raise ValueError(
                "The completed report has a different evaluation configuration."
            )
        completed_identity = read_identity(identity_file)
        if not _same_json(completed.get("model_ledger"), completed_identity):
            raise ValueError(
                "The completed report has a different model ledger identity."
            )
    if replay is not None:
        original_identity = read_identity(replay / "model-ledger.json")
        if (
            original_identity["pipeline_run"] != replay_pipeline
            or prior is None
            or not _same_json(prior.get("model_ledger"), original_identity)
        ):
            raise ValueError(
                "The replay model ledger identity does not match its origin."
            )
        verify_identity(workspace, original_identity)
        if open_binding(replay, keys) is None:
            raise ValueError("Replay requires a frozen capture binding at its origin.")
        check_replay_ledgers()
    if scope is not None:
        if identity_file.exists() and any(
            not (run / "submissions" / task.key / "capture/submission.json").is_file()
            for task in tasks
        ):
            raise ValueError("A frozen run cannot capture another submission.")
    releases = {
        task.key: workspace / "sealed/release" / task.tier.lower()
        if task.tier is not None
        else release
        for task in tasks
    }
    submissions = {
        task.key: submit(
            workspace,
            run / "submissions" / task.key,
            pipeline_run,
            task.key,
            task.variant.executable(releases[task.key]),
            task.method,
            replay_pipeline,
        )
        for task in tasks
    }
    if replay is not None:
        verify_identity(workspace, original_identity)
        check_replay_ledgers()
    model_ledger = freeze_identity(workspace, run, replay_pipeline or pipeline_run)
    model_summaries = bound_summaries(workspace, keys, model_ledger)
    capture_binding = freeze_binding(run, keys, capture_binding, submissions)
    current_config = _configuration(workspace, release_hash)
    if scope is not None:
        current_config.update({"schema": 2, "scope": _m2_scope(workspace).record()})
    if not _same_json(current_config, config):
        raise ValueError("The evaluation configuration changed before measurement.")
    if scope is None and t0_manifest(release) != (variants, release_hash):
        raise ValueError("The released binaries changed before measurement.")
    originals = {
        task.variant_key: _release_bytes(task.variant, releases[task.key])
        for task in tasks
        if task.method == "phoenix"
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
            origins[task.variant_key] = read_origin(
                run / "submissions" / task.key / "capture/origin.json",
                submission.origin_sha256,
            )
        if task.method == "phoenix" and submission.source_sha256 is not None:
            digest = submission.development_sha256
            if digest is None:
                raise DevelopmentError("The submission has no development evidence.")
            development[task.variant_key] = verify_development(
                originals[task.variant_key],
                run / "submissions" / task.key / "capture/development.json",
                digest,
                config["worker_images"],
            )
    verify_identity(workspace, model_ledger)
    check_replay_ledgers()
    verify_binding(run, keys, capture_binding)
    if scope is None:
        cases = heldout_cases(
            workspace / "holdout/t0-inputs.tar.gz",
            config["heldout_archive_sha256"],
            {task.variant.name for task in tasks},
        )
        task_cases = {task.key: cases[task.variant.name] for task in tasks}
    else:
        if prior is not None:
            previous_sources = {
                record["task_key"]: record["source_sha256"]
                for record in prior["results"]
            }
            if previous_sources != {
                key: submission.source_sha256 for key, submission in submissions.items()
            }:
                raise ValueError("Replay changed the frozen source snapshots.")
        task_cases = {}
        for batch in scope.batches:
            verify_binding(run, keys, capture_binding)
            verify_identity(workspace, model_ledger)
            check_replay_ledgers()
            cases = heldout_cases(
                workspace / "holdout" / f"{batch.tier.lower()}-inputs.tar.gz",
                batch.inputs_sha256,
                {variant.name for variant in batch.variants},
                tier=batch.tier,
            )
            task_cases.update(
                {
                    task.key: cases[task.variant.name]
                    for task in tasks
                    if task.tier == batch.tier
                }
            )
    records = [
        _measure(
            workspace,
            run,
            pipeline_run,
            task,
            submissions[task.key],
            originals[task.variant_key],
            task_cases[task.key],
            config,
            development.get(task.variant_key, frozenset()),
            origins.get(task.variant_key),
            model_ledger,
        )
        for task in tasks
    ]

    def verify_publication() -> None:
        verify_identity(workspace, model_ledger)
        if read_identity(identity_file) != model_ledger:
            raise ValueError("The model ledger identity changed during measurement.")
        verify_binding(run, keys, capture_binding)
        if bound_summaries(
            workspace, keys, model_ledger
        ) != model_summaries or not _same_json(
            [record.get("model") for record in records],
            [asdict(model_summaries[key]) for key in keys],
        ):
            raise ValueError(
                "The reported model summaries do not reconcile with the ledger."
            )
        check_replay_ledgers()

    if scope is not None:
        for task, record in zip(tasks, records, strict=True):
            record.update(
                tier=task.tier, variant_key=task.variant_key, task_key=task.key
            )
    scores = _scores(records)
    phoenix = scores["phoenix"]
    accepted = phoenix["variants"] == 20 and phoenix["fully_successful"] >= 16
    reproduced = (
        _stable_records(records)
        == _stable_records(cast(list[dict[str, object]], prior["results"]))
        if prior is not None
        else None
    )
    report = run / f"{kind}.json"
    document: dict[str, object] = {
        "run_id": run.name,
        "replay_of": replay.name if replay is not None else None,
        "reproduced": reproduced,
        "configuration": config,
        "corpus": "agent-sealed",
        "coverage_kind": "recovered_block_entries",
        "model_ledger": model_ledger,
        "scores": scores,
        "results": records,
        "accepted": accepted,
    }
    if scope is not None:
        summary = summarize(records, scope)
        accepted = summary["accepted"] is True
        document.update(
            report_kind="m2",
            scores=summary,
            accepted=accepted,
            source_adequacy="separate_author_evidence",
        )
        if prior is not None:
            reproduced = _stable_m2_report(document) == _stable_m2_report(prior)
            document["reproduced"] = reproduced
    write_report(report, document, before_publish=verify_publication)
    return report, accepted and reproduced is not False


def evaluate_t0(
    workspace: Path, run_id: str | None = None, replay_id: str | None = None
) -> tuple[Path, bool]:
    return _run_evaluation(workspace, run_id, replay_id, "m1")


def evaluate_m2(
    workspace: Path, run_id: str | None = None, replay_id: str | None = None
) -> tuple[Path, bool]:
    return _run_evaluation(workspace, run_id, replay_id, "m2")


def _run_evaluation(
    workspace: Path, run_id: str | None, replay_id: str | None, kind: ReportKind
) -> tuple[Path, bool]:
    workspace = workspace.resolve()
    runs = workspace / "runs"
    if runs.resolve() != runs:
        raise ValueError("The evaluation run directory cannot be a symbolic link.")
    run = _directory(runs, run_id or f"{kind}-{uuid4().hex}")
    replay = _directory(runs, replay_id) if replay_id is not None else None
    if run == replay:
        raise ValueError("Replay requires a new evaluation run ID.")
    run.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        run / "evaluation.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if kind == "m1":
            return _evaluate(workspace, run, replay)
        if any(re.fullmatch(r"m[0-9]+", path.stem) for path in run.glob("m*.json")):
            if recorded_kind(run) != kind:
                raise ValueError("The run directory has a different report kind.")
        return _evaluate(workspace, run, replay, kind)
