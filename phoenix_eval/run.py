"""Run the development evaluation with a fixed roster and immutable results."""

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from typing import cast

from phoenix_eval.dev_corpus import (
    DevBinary,
    load_validated_cases,
)
from phoenix_eval.docker import WorkerError
from phoenix_eval.integrity import IntegrityError
from phoenix_eval.model_ledger import summarize
from phoenix_eval.provenance import (
    CHECKOUT,
)
from phoenix_eval.run_binary import measure, task_key
from phoenix_eval.run_plan import (
    _configuration,
    _selection,
    adequacy_snapshot,
    case_identity,
)
from phoenix_eval.run_records import (
    BinaryResult,
    RunPlan,
    Selection,
    capture_ledger,
    digest,
    directory,
    evaluation_guard,
    immutable,
    parse_json,
    pending_result,
    plan_record,
    read_ledger,
    read_results,
    record_bytes,
    record_result,
)
from phoenix_eval.run_resources import Resources
from phoenix_eval.run_score import scoreboard
from phoenix_eval.submission import EvaluationPending


@dataclass(frozen=True)
class Publication:
    plan: RunPlan
    results: tuple[BinaryResult, ...]
    document: dict[str, object]
    sha256: str


def publish(
    workspace: Path, run_id: str, *, require_existing: bool = False
) -> Publication:
    run = directory(workspace, run_id)
    try:
        with evaluation_guard(workspace, run):
            return _publish_locked(workspace, run, require_existing=require_existing)
    except BlockingIOError as error:
        raise ValueError(f"Evaluation run {run_id} is still active.") from error


def _publish_locked(
    workspace: Path,
    run: Path,
    *,
    require_existing: bool = False,
    elapsed: float | None = None,
    resources: Resources | None = None,
) -> Publication:
    plan = RunPlan.load(run / "plan.json")
    published = run / "scoreboard.json"
    if require_existing and not published.exists():
        raise ValueError("The published scoreboard is missing.")
    content = record_bytes(published) if published.exists() else None
    saved = parse_json(content) if content is not None else None
    refs = saved["result_refs"] if saved is not None else None
    if saved is not None and not isinstance(refs, dict):
        raise ValueError("The result references must be an object.")
    records = read_results(run, plan, cast(dict[str, object] | None, refs))
    source, prefix = plan, None
    seen = {plan.run_id}
    source_ledgers = []
    while source.replay_of is not None:
        if source.replay_of in seen:
            raise ValueError("The replay plan dependencies contain a cycle.")
        seen.add(source.replay_of)
        source_run = directory(workspace, source.replay_of)
        source = RunPlan.load(source_run / "plan.json")
        source_ledgers.append(read_ledger(workspace, source_run))
    for snapshot in source_ledgers:
        if snapshot.pipeline != source.pipeline or (
            prefix is not None and prefix != snapshot.content
        ):
            raise ValueError("The original replay ledger identity changed.")
        prefix = snapshot.content
    ledger = (
        read_ledger(workspace, run)
        if saved is not None
        else capture_ledger(workspace, run, source.pipeline, prefix=prefix)
    )
    if ledger.pipeline != source.pipeline or (
        prefix is not None and prefix != ledger.content
    ):
        raise ValueError("The published model ledger identity changed.")
    keys = records.refs.keys()
    if any(event.binary not in keys for event in ledger.events):
        raise ValueError("The model ledger includes a binary outside the fixed roster.")
    costs = {key: summarize(ledger.events, key) for key in keys}
    storage = shutil.disk_usage(workspace)
    document = scoreboard(
        plan,
        records.results,
        costs,
        elapsed=elapsed if elapsed is not None else time.time() - plan.started,
        free_gib=storage.free / 2**30,
        peak_memory_gib=resources.peak_memory_gib
        if resources is not None and resources.samples
        else None,
        peak_storage_gib=resources.peak_storage_gib
        if resources is not None
        else storage.used / 2**30,
        root=CHECKOUT,
    )
    document["models"] = {
        "runtime": sorted({str(event.request["model"]) for event in ledger.events})
    }
    document["row"] = plan.configuration.get("row")
    document["result_refs"] = records.refs
    document["resource_scope"] = (
        "Evaluator descendants and all active Docker containers. "
        "Storage is workspace usage."
    )
    if saved is None:
        document["resource_samples"] = resources.samples if resources is not None else 0
        document["resource_sample_errors"] = (
            resources.failed_samples if resources is not None else 0
        )
        immutable(published, document)
        content = record_bytes(published)
        saved = parse_json(content)
    measured = {
        "loop_minutes",
        "peak_memory_gib",
        "peak_storage_gib",
        "free_storage_gib",
        "source_lines",
        "test_lines",
    }
    expected = {key: value for key, value in document.items() if key not in measured}
    actual = {key: saved[key] for key in expected if key in saved}
    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(
        expected, sort_keys=True, allow_nan=False
    ):
        raise ValueError("The published score differs from its fixed evidence.")
    assert content is not None
    return Publication(plan, records.results, saved, digest(content))


def evaluate(
    workspace: Path,
    run_id: str,
    selection: Selection,
    llm_cache: bool,
    *,
    resume: bool = False,
    replay_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    run = directory(workspace, run_id)
    run.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    guard_source = replay_id
    if resume and (run / "plan.json").exists():
        guard_source = RunPlan.load(run / "plan.json").replay_of
    with evaluation_guard(workspace, run, guard_source):
        config = _configuration(workspace)
        path = run / "plan.json"
        replay = None
        prior = None
        if path.exists():
            if not resume:
                raise ValueError("Resume an existing evaluation run.")
            plan = RunPlan.load(path)
            if any(
                plan.configuration.get(name) != value for name, value in config.items()
            ):
                raise ValueError(
                    "Resume requires the recorded evaluation configuration."
                )
        else:
            if resume:
                raise ValueError("The evaluation has no fixed run plan.")
            if replay_id is not None:
                prior = publish(workspace, replay_id)
                replay = prior.plan
                if any(
                    replay.configuration.get(name) != value
                    for name, value in config.items()
                ):
                    raise ValueError(
                        "Replay requires the recorded evaluation configuration."
                    )
                selection = replay.selection
                binaries, binary_hash, case_hash = (
                    replay.binaries,
                    replay.corpus_hash,
                    replay.heldout_hash,
                )
            else:
                binaries, binary_hash, case_hash = _selection(workspace, selection)
            cases = {
                task_key(binary): case_identity(
                    CHECKOUT / "corpus_dev",
                    binary,
                    load_validated_cases(CHECKOUT / "corpus_dev", workspace, binary),
                )
                for binary in binaries
            }
            if replay is not None and (
                {key: value[0] for key, value in cases.items()}
                != replay.configuration["case_counts"]
                or {key: value[1] for key, value in cases.items()}
                != replay.configuration["case_hashes"]
            ):
                raise ValueError("The held-out cases differ from the source run plan.")
            plan = RunPlan(
                run_id,
                selection,
                binaries,
                {
                    **(metadata or {}),
                    **config,
                    "case_counts": {key: value[0] for key, value in cases.items()},
                    "case_hashes": {key: value[1] for key, value in cases.items()},
                    "source_branch_coverage": adequacy_snapshot(
                        CHECKOUT / "corpus_dev", binaries, selection.probe
                    )
                    if replay is None
                    else replay.configuration["source_branch_coverage"],
                },
                binary_hash,
                case_hash,
                llm_cache,
                time.time(),
                (
                    f"{run_id}-p",
                    f"{run_id}-check",
                    *((replay_id,) if replay_id else ()),
                ),
                replay_id,
            )
            immutable(path, plan_record(plan))
        for dependency in (plan.pipeline, f"{plan.run_id}-check"):
            directory(workspace, dependency).mkdir(exist_ok=True)
        if plan.replay_of is not None:
            if prior is None:
                prior = publish(workspace, plan.replay_of)
            replay = prior.plan
        if (run / "scoreboard.json").exists():
            _publish_locked(workspace, run)
        stop = Event()
        prior_records = {}
        if prior is not None:
            prior_records = {
                task_key(result.binary): result for result in prior.results
            }
        resources = Resources(workspace)
        resources.start()

        def execute(binary: DevBinary) -> None:
            key = task_key(binary)
            if stop.is_set() or (run / "results" / f"{key}.json").exists():
                return
            if key in prior_records and (
                prior_records[key].pending
                or prior_records[key].details.get("source_sha256") is None
            ):
                if not prior_records[key].pending:
                    record_result(run, key, prior_records[key])
                return
            for attempt in range(2):
                try:
                    result = measure(workspace, run, binary, plan, replay)
                    record_result(run, key, result)
                    resources.sample()
                    return
                except EvaluationPending:
                    return
                except (
                    OSError,
                    WorkerError,
                    subprocess.SubprocessError,
                    ValueError,
                ) as error:
                    if not attempt and not isinstance(error, ValueError):
                        continue
                    category = (
                        "integrity"
                        if isinstance(error, IntegrityError)
                        else "timeout"
                        if isinstance(error, subprocess.TimeoutExpired)
                        else "pipeline_error"
                    )
                    pending = pending_result(binary, plan)
                    result = replace(
                        pending,
                        pending=False,
                        categories=(category,),
                        details={**pending.details, "error": str(error)},
                    )
                record_result(run, key, result)
                resources.sample()
                return

        try:
            jobs = max(
                1,
                int(
                    os.environ.get(
                        "PHOENIX_JOBS", str(max(1, (os.cpu_count() or 2) // 2))
                    )
                ),
            )
            pool = ThreadPoolExecutor(max_workers=min(16, jobs))
            try:
                list(pool.map(execute, plan.binaries))
            except KeyboardInterrupt:
                stop.set()
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
        except KeyboardInterrupt:
            stop.set()
        finally:
            resources.finish()
            document = _publish_locked(
                workspace,
                run,
                elapsed=time.monotonic() - started,
                resources=resources,
            ).document
        current = read_results(run, plan).results
        if [result.record() for result in current] != document["binaries"]:
            continuation = digest(
                json.dumps(
                    [result.record() for result in current], sort_keys=True
                ).encode()
            )[:12]
            immutable(
                run / f"continuation-{continuation}.json",
                {
                    "published_run": plan.run_id,
                    "binaries": [result.record() for result in current],
                },
            )
        if prior is not None:
            original = prior.document
            stable = (
                "success",
                "program_success",
                "held_out_cases",
                "integrity_failures",
                "failure_categories",
            )
            document = {
                **document,
                "reproduced": all(document[name] == original[name] for name in stable),
            }
            immutable(run / "replay-result.json", document)
        return document
