"""Capture and independently score one development binary."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import uuid4

from phoenix_eval.build import snapshot_project
from phoenix_eval.dev_corpus import DevBinary, binary_path, load_validated_cases
from phoenix_eval.development import verify_development
from phoenix_eval.docker import read_program
from phoenix_eval.integrity import check_integrity, inspect_project, original_shapes
from phoenix_eval.model_ledger import read_events, require_no_replay_ledger, summarize
from phoenix_eval.pair import evaluate_pair
from phoenix_eval.provenance import CHECKOUT
from phoenix_eval.quality import goto_density, register_named_locals
from phoenix_eval.run_plan import case_identity
from phoenix_eval.run_records import BinaryResult, RunPlan, read_json
from phoenix_eval.submission import (
    project_path,
    read_origin,
    read_package_report,
    source_digest,
    submit,
)

CAPS = {"D0": "3", "D1": "10", "D2": "30", "D3": "60"}


def task_key(binary: DevBinary) -> str:
    return f"{binary.name}-{binary.key}"


def package_files(path: Path) -> dict[str, str]:
    result = {}
    total = 0
    for file in sorted(path.rglob("*")):
        if file.resolve() != file:
            raise ValueError("The package contains a symbolic link.")
        if file.is_dir():
            continue
        if not file.is_file():
            raise ValueError("The package contains a special file.")
        data = file.read_bytes()
        total += len(data)
        if total > 16 * 1024 * 1024:
            raise ValueError("The package exceeds its size limit.")
        result[file.relative_to(path).as_posix()] = sha256(data).hexdigest()
    if not result:
        raise ValueError("The package is empty.")
    return result


def validate_checkpoint(
    directory: Path, binary: DevBinary, plan: RunPlan, replay_from: str | None
) -> None:
    record = read_json(directory / "run.json")
    config = plan.configuration
    expected = {
        "version": 1,
        "binary_sha256": binary.sha256,
        "revision": config["revision"],
        "worker_source_sha256": config["worker_source_sha256"],
        "checker_source_sha256": config["checker_source_sha256"],
        "pipeline_source_sha256": config["pipeline_source_sha256"],
        "images": config["worker_images"],
        "checker_images": config["checker_images"],
        "lifting_tool_identity": config["lifting_tool_identity"],
        "protection": {"profile": "pipeline", "probe_denied": True},
        "method": "phoenix",
        "replay_from": replay_from,
        "budget_binary": int(CAPS[binary.tier]) * 1_000_000_000,
        **cast(dict[str, object], config["pipeline_settings"]),
    }
    if any(record.get(name) != value for name, value in expected.items()):
        raise ValueError("The pipeline checkpoint differs from the fixed run plan.")


def measure(
    workspace: Path,
    run: Path,
    binary: DevBinary,
    plan: RunPlan,
    replay: RunPlan | None = None,
) -> BinaryResult:
    key = task_key(binary)
    original_path = binary_path(workspace, binary)
    valid = load_validated_cases(CHECKOUT / "corpus_dev", workspace, binary)
    count, heldout = case_identity(CHECKOUT / "corpus_dev", binary, valid)
    if (
        count != cast(dict[str, int], plan.configuration["case_counts"])[key]
        or heldout != cast(dict[str, str], plan.configuration["case_hashes"])[key]
    ):
        raise ValueError("The held-out cases differ from the fixed run plan.")
    source_pipeline = (
        str(
            read_json(workspace / "runs" / replay.run_id / "published-ledger.json")[
                "pipeline_run"
            ]
        )
        if replay
        else None
    )
    submission = submit(
        workspace,
        run / "submissions" / key,
        plan.pipeline,
        key,
        original_path,
        "phoenix",
        source_pipeline,
        cost_cap_usd=CAPS[binary.tier],
        environment={"PHOENIX_LLM_CACHE": "on" if plan.llm_cache else "off"},
        cache_root=(run / "cold-cache" / key)
        if not plan.llm_cache and not replay
        else None,
    )
    result: dict[str, object] = {
        **asdict(binary),
        "task_key": key,
        "fully_successful": False,
        "categories": [],
        "held_out_cases": [0, 4 * len(valid.cases)],
        "heldout_hash": heldout,
        "reconstruction_seconds": submission.reconstruction_seconds,
        "source_sha256": submission.source_sha256,
        "dev_passed": False,
        "dev_set_hash": submission.development_sha256,
        "replay_identical": False,
        "integrity_categories": {},
        "register_named_locals": None,
        "goto_per_100_lines": None,
    }
    if submission.source_sha256 is None:
        result["categories"] = ["pipeline_error"]
        return BinaryResult.parse(result)
    validate_checkpoint(
        workspace / "runs" / plan.pipeline / key, binary, plan, source_pipeline
    )
    capture = run / "submissions" / key / "capture"
    snapshot = snapshot_project(capture / "project")
    files = dict(snapshot.files)
    if (
        source_digest(files) != submission.source_sha256
        or submission.report_sha256 is None
        or submission.origin_sha256 is None
        or submission.development_sha256 is None
    ):
        raise ValueError("The capture has incomplete or changed evidence.")
    report = read_package_report(capture / "report.json", submission.report_sha256)
    if (
        report.get("sha256") != binary.sha256
        or report.get("method") != "phoenix"
        or report.get("project_sha256") != sha256(snapshot.archive).hexdigest()
    ):
        raise ValueError("The package report differs from the tested source.")
    original = read_program(original_path)
    images = cast(dict[str, str], plan.configuration["worker_images"])
    outputs = verify_development(
        original, capture / "development.json", submission.development_sha256, images
    )
    fingerprint = package_files(project_path(workspace, plan.pipeline, key))
    if replay is None:
        check_pipeline = f"{plan.run_id}-check"
        replayed = submit(
            workspace,
            run / "replay-check" / key,
            check_pipeline,
            key,
            original_path,
            "phoenix",
            plan.pipeline,
        )
        identical = (
            replayed.source_sha256 == submission.source_sha256
            and package_files(project_path(workspace, check_pipeline, key))
            == fingerprint
        )
        require_no_replay_ledger(workspace, check_pipeline)
    else:
        prior = read_json(
            workspace / "runs" / replay.run_id / "results" / f"{key}.json"
        )
        identical = fingerprint == prior.get("package_files")
        require_no_replay_ledger(workspace, plan.pipeline)
    builds = run / "builds" / key / uuid4().hex
    builds.mkdir(parents=True)
    pair = evaluate_pair(original, snapshot, valid.cases, builds, images)
    evidence = inspect_project(
        snapshot, cast(dict[str, str], plan.configuration["checker_images"])
    )
    origin = original_shapes(
        read_origin(capture / "origin.json", submission.origin_sha256), raw=False
    )
    executables = []
    for build in pair.builds:
        if build.executable_sha256 is not None:
            executable = read_program(
                builds / f"{build.architecture}-{build.compiler}.elf"
            )
            if sha256(executable).hexdigest() != build.executable_sha256:
                raise ValueError("A tested executable changed.")
            executables.append(executable)
    integrity = check_integrity(
        original, files, tuple(executables), evidence, outputs, origin
    )
    categories = set()
    x86, arm = pair.builds[:2], pair.builds[2:]
    if any(not build.compiled for build in x86):
        categories.add("build_x86")
    if any(not build.compiled for build in arm):
        categories.add("build_arm")
    x86_passed = all(
        build.compiled
        and build.matched_cases == len(valid.cases)
        and not build.evaluation_errors
        for build in x86
    )
    arm_passed = all(
        build.compiled
        and build.matched_cases == len(valid.cases)
        and not build.evaluation_errors
        for build in arm
    )
    if (
        not pair.behavior_passed
        or pair.eligible_cases != len(valid.cases)
        or pair.emulator_disagreements
    ):
        if not x86_passed:
            categories.add("behavior_x86")
        elif not arm_passed:
            categories.add("behavior_arm_only")
        else:
            categories.add("pipeline_error")
    if not integrity.passed:
        categories.add("integrity")
    if not identical:
        categories.add("pipeline_error")
    if report.get("unsupported_behavior") or report.get("unsupported_behaviors"):
        categories.add("pipeline_error")
    if report.get("stop") == "budget-limit":
        categories.add("budget")
    registers = register_named_locals(evidence)
    ledger = workspace / "runs" / (source_pipeline or plan.pipeline) / "llm.jsonl"
    events = read_events(ledger.read_text().splitlines()) if ledger.exists() else ()
    cost = summarize(events, key)
    if package_files(project_path(workspace, plan.pipeline, key)) != fingerprint:
        raise ValueError("The package changed during measurement.")
    result.update(
        fully_successful=not categories,
        categories=sorted(categories),
        held_out_cases=[
            sum(build.matched_cases for build in pair.builds),
            4 * len(valid.cases),
        ],
        behavior=asdict(pair),
        integrity_categories=integrity.categories,
        dev_passed=report.get("development_behavior_passed") is True,
        replay_identical=identical,
        package_files=fingerprint,
        register_named_locals=registers,
        goto_per_100_lines=goto_density(files),
        cost_nanodollars=cost.cost_nanodollars + cost.unknown_cost_reservations,
        model=asdict(cost),
    )
    return BinaryResult.parse(result)
