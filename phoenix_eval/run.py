"""Run the development evaluation with a fixed roster and immutable results."""

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import cast

from phoenix_eval.dev_corpus import (
    DevBinary,
    load_validated_cases,
)
from phoenix_eval.docker import WorkerError
from phoenix_eval.integrity import IntegrityError
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
    digest,
    directory,
    evaluation_guard,
    immutable,
    ledger_snapshot,
    plan_record,
    read_json,
    record_result,
    verify_ledger,
)
from phoenix_eval.run_resources import Resources
from phoenix_eval.run_score import ledger_models, scoreboard, verify_scoreboard
from phoenix_eval.submission import EvaluationPending


def _pending(binary: DevBinary, plan: RunPlan) -> BinaryResult:
    key = task_key(binary)
    count = cast(dict[str, int], plan.configuration["case_counts"])[key]
    return BinaryResult(
        binary,
        False,
        ("pipeline_error",),
        (0, count * 4),
        True,
        {
            "task_key": key,
            "heldout_hash": cast(dict[str, str], plan.configuration["case_hashes"])[
                key
            ],
            "dev_passed": False,
        },
    )


def _read_results(
    run: Path, plan: RunPlan, refs: dict[str, object] | None = None
) -> tuple[BinaryResult, ...]:
    results = []
    for binary in plan.binaries:
        key = task_key(binary)
        path = run / "results" / f"{key}.json"
        if refs is not None and refs[key] is None:
            results.append(_pending(binary, plan))
            continue
        if path.exists():
            if refs is not None and digest(path.read_bytes()) != refs[key]:
                raise ValueError("A published terminal result changed.")
            result = BinaryResult.parse(read_json(path))
            if result.binary != binary or result.pending:
                raise ValueError("The terminal result differs from the fixed roster.")
            results.append(result)
        else:
            if refs is not None:
                raise ValueError("A published terminal result is missing.")
            results.append(_pending(binary, plan))
    return tuple(results)


def publish(
    workspace: Path,
    run: Path,
    plan: RunPlan,
    *,
    elapsed: float | None = None,
    resources: Resources | None = None,
) -> dict[str, object]:
    published = run / "scoreboard.json"
    if published.exists():
        saved = read_json(published)
        ledger = verify_ledger(workspace, run)
        records = _read_results(
            run, plan, cast(dict[str, object], saved["result_refs"])
        )
        verify_scoreboard(plan, records, ledger, saved, CHECKOUT)
        return saved
    records = _read_results(run, plan)
    replay_plan = (
        RunPlan.load(directory(workspace, plan.replay_of) / "plan.json")
        if plan.replay_of
        else None
    )
    prefix = (
        verify_ledger(workspace, directory(workspace, replay_plan.run_id))
        if replay_plan
        else None
    )
    source_pipeline = (
        str(
            read_json(
                directory(workspace, replay_plan.run_id) / "published-ledger.json"
            )["pipeline_run"]
        )
        if replay_plan
        else plan.pipeline
    )
    ledger, costs = ledger_snapshot(
        workspace,
        run,
        source_pipeline,
        prefix=prefix,
    )
    known = {task_key(binary) for binary in plan.binaries}
    if not set(costs) <= known:
        raise ValueError("The model ledger includes a binary outside the fixed roster.")
    storage = shutil.disk_usage(workspace)
    document = scoreboard(
        plan,
        records,
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
    document["models"] = ledger_models(ledger)
    document["row"] = plan.configuration.get("row")
    document["resource_scope"] = (
        "Evaluator descendants and all active Docker containers. "
        "Storage is workspace usage."
    )
    document["resource_samples"] = resources.samples if resources is not None else 0
    document["resource_sample_errors"] = (
        resources.failed_samples if resources is not None else 0
    )
    document["result_refs"] = {
        task_key(binary): digest(
            (run / "results" / f"{task_key(binary)}.json").read_bytes()
        )
        if (run / "results" / f"{task_key(binary)}.json").exists()
        else None
        for binary in plan.binaries
    }
    immutable(published, document)
    return document


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
                source = directory(workspace, replay_id)
                replay = RunPlan.load(source / "plan.json")
                prior = publish(workspace, source, replay)
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
                _read_results(
                    source, replay, cast(dict[str, object], prior["result_refs"])
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
                    **config,
                    **(metadata or {}),
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
            replay = RunPlan.load(directory(workspace, plan.replay_of) / "plan.json")
        if (run / "scoreboard.json").exists():
            publish(workspace, run, plan)
        stop = Event()
        prior_records = {}
        if replay is not None:
            prior_score = publish(
                workspace, directory(workspace, replay.run_id), replay
            )
            prior_records = {
                task_key(result.binary): result
                for result in _read_results(
                    directory(workspace, replay.run_id),
                    replay,
                    cast(dict[str, object], prior_score["result_refs"]),
                )
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
                    pending = _pending(binary, plan)
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
            document = publish(
                workspace,
                run,
                plan,
                elapsed=time.monotonic() - started,
                resources=resources,
            )
        current = _read_results(run, plan)
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
        if replay is not None:
            original = publish(workspace, directory(workspace, replay.run_id), replay)
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
