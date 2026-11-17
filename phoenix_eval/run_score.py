"""Compute aggregate fields from the fixed binary roster."""

from collections import Counter
from pathlib import Path
from statistics import median, quantiles
from typing import cast

from phoenix_eval.model_ledger import ModelSummary
from phoenix_eval.run_records import BinaryResult, RunPlan


def _distribution(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    quartiles = (
        quantiles(values, n=4, method="inclusive") if len(values) > 1 else values * 3
    )
    return {"median": median(values), "q1": quartiles[0], "q3": quartiles[2]}


def _lines(root: Path, directories: tuple[str, ...]) -> int:
    return sum(
        sum(bool(line.strip()) for line in path.read_text().splitlines())
        for directory in directories
        for path in (root / directory).rglob("*.py")
    )


def scoreboard(
    plan: RunPlan,
    results: tuple[BinaryResult, ...],
    costs: dict[str, ModelSummary],
    *,
    elapsed: float,
    free_gib: float,
    peak_memory_gib: float | None,
    peak_storage_gib: float,
    root: Path,
) -> dict[str, object]:
    records = [result.record() for result in results]
    tiers = sorted({str(record["tier"]) for record in records})
    failures: Counter[str] = Counter()
    for record in records:
        failures.update(cast(list[str], record["categories"]))
    success = {}
    programs: dict[str, object] = {}
    escape = {}
    arm_gap = {}
    cost_usd = {}
    minutes = {}
    gotos = {}
    for tier in tiers:
        selected = [record for record in records if record["tier"] == tier]
        success[tier] = {
            level: [
                sum(
                    record["fully_successful"] is True
                    for record in selected
                    if cast(tuple[str, ...], record["flags"])[1] == f"-{level}"
                ),
                sum(
                    cast(tuple[str, ...], record["flags"])[1] == f"-{level}"
                    for record in selected
                ),
            ]
            for level in plan.selection.levels
        }
        names = {str(record["name"]) for record in selected}
        complete_programs = all(
            {
                (record["compiler"], cast(tuple[str, ...], record["flags"])[1])
                for record in selected
                if record["name"] == name
            }
            >= {
                (compiler, f"-{level}")
                for compiler in ("gcc", "clang")
                for level in ("O0", "O2", "Os")
            }
            for name in names
        )
        programs[tier] = (
            [
                sum(
                    all(
                        record["fully_successful"] is True
                        for record in selected
                        if record["name"] == name
                        and cast(tuple[str, ...], record["flags"])[1] != "-O3"
                    )
                    for name in names
                ),
                len(names),
            ]
            if complete_programs
            else None
        )
        dev = [record for record in selected if record.get("dev_passed") is True]
        escape[tier] = [
            sum(
                "behavior_x86" in cast(list[str], record["categories"])
                or "behavior_arm_only" in cast(list[str], record["categories"])
                for record in dev
            ),
            len(dev),
        ]
        x86 = arm = 0
        for record in selected:
            behavior = cast(dict[str, object], record.get("behavior", {}))
            builds = cast(list[dict[str, object]], behavior.get("builds", []))
            total = cast(int, behavior.get("total_cases", 0))
            if len(builds) == 4 and total:
                passes = [
                    build["compiled"] is True
                    and build["matched_cases"] == total
                    and build["evaluation_errors"] == 0
                    for build in builds
                ]
                x86 += all(passes[:2])
                arm += all(passes[2:])
        arm_gap[tier] = 100 * (x86 - arm) / len(selected)
        cost_usd[tier] = _distribution(
            [
                float(
                    costs[str(record["task_key"])].cost_nanodollars
                    + costs[str(record["task_key"])].unknown_cost_reservations
                )
                / 1e9
                if str(record["task_key"]) in costs
                else float(cast(int, record.get("cost_nanodollars", 0))) / 1e9
                for record in selected
            ]
        )
        minutes[tier] = _distribution(
            [
                float(cast(float, record.get("reconstruction_seconds", 0))) / 60
                for record in selected
            ]
        )
        density = [
            float(cast(float, record["goto_per_100_lines"]))
            for record in selected
            if record.get("goto_per_100_lines") is not None
        ]
        gotos[tier] = median(density) if density else None
    pending = any(record.get("pending") is True for record in records)
    totals = [cast(list[int], record["held_out_cases"]) for record in records]
    config = plan.configuration
    return {
        "row": None,
        "run_id": plan.run_id,
        "commit": config["revision"],
        "tag": None,
        "corpus": "corpus_dev",
        "loop": config.get("loop", "probe"),
        "run_state": "stopped" if pending else "complete",
        "corpus_hash": plan.corpus_hash,
        "heldout_hash": plan.heldout_hash,
        "cache": "warm" if plan.llm_cache else "cold",
        "milestone": config.get("milestone", "R0"),
        "experiment": config.get("experiment"),
        "quick_set": 1 if plan.selection.quick else None,
        "noise_ref": config.get("noise_ref"),
        "mode": "m1",
        "models": config.get("models", {}),
        "configuration_identity": config.get("configuration_identity"),
        "success": success,
        "source_branch_coverage": config.get("source_branch_coverage"),
        "program_success": programs,
        "maintainable": None,
        "held_out_cases": [
            sum(value[0] for value in totals),
            sum(value[1] for value in totals),
        ],
        "failure_categories": dict(failures),
        "integrity_failures": sum(
            "integrity" in cast(list[str], record["categories"]) for record in records
        ),
        "glibc_internal_symbols": None,
        "register_named_locals": sum(
            cast(int, record.get("register_named_locals") or 0) for record in records
        ),
        "arm_gap_points": arm_gap,
        "dev_edge_coverage_median": None,
        "function_reachability_median": None,
        "dev_mutation_score_median": None,
        "escape_rate": escape,
        "truth_transplant_rate": None,
        "transformed_interface_rate": None,
        "theseus_fraction_median": None,
        "function_status": None,
        "literal_mode_byte_share": None,
        "nondefault_type_share": None,
        "goto_per_100_lines": gotos,
        "edit_task": None,
        "cost_usd": cost_usd,
        "binary_minutes": minutes,
        "loop_minutes": elapsed / 60,
        "peak_memory_gib": peak_memory_gib,
        "peak_storage_gib": peak_storage_gib,
        "free_storage_gib": free_gib,
        "source_lines": _lines(root, ("phoenix", "phoenix_eval")),
        "test_lines": _lines(root, ("tests",)),
        "noise": None,
        "dev_set_hashes": {
            str(record["task_key"]): record.get("dev_set_hash") for record in records
        },
        "binaries": records,
    }
