"""Compare one original executable with four independent project builds."""

import platform
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from itertools import batched
from pathlib import Path

from phoenix_eval.build import BuildResult, build_project
from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.coverage import BlockInventory, inspect_x86
from phoenix_eval.docker import MAX_BATCH, Engine, run_cases
from phoenix_eval.outcome import Outcome, compare
from phoenix_eval.toolchain import Compiler
from phoenix_eval.trace import CodeTrace


@dataclass(frozen=True)
class BuildReport:
    architecture: str
    compiler: Compiler
    compiled: bool
    warnings: int
    matched_cases: int
    evaluation_errors: int
    failure_categories: dict[str, int]


@dataclass(frozen=True)
class PairReport:
    total_cases: int
    eligible_cases: int
    emulator_disagreements: int
    evaluation_errors: int
    original_error_categories: dict[str, int]
    recovered_blocks: int
    covered_blocks: int
    builds: tuple[BuildReport, ...]
    behavior_passed: bool


class _RunError(StrEnum):
    WORKER = "worker_error"
    MALFORMED = "malformed_result"


def _run(
    binary: Path,
    cases: tuple[Invocation, ...],
    engine: Engine,
    image: str,
    *,
    trace: bool = False,
) -> Iterator[CaseResult | _RunError]:
    results: tuple[CaseResult, ...] | None
    for batch in batched(cases, MAX_BATCH):
        try:
            results = run_cases(binary, batch, engine, image=image, trace=trace)
        except Exception:
            # Worker exceptions can contain private data.
            results = None
        if results is None:
            yield from (_RunError.WORKER,) * len(batch)
            continue
        if not isinstance(results, tuple) or len(results) != len(batch):
            yield from (_RunError.MALFORMED,) * len(batch)
            continue
        for result in results:
            if isinstance(result, Outcome) and (
                result.trace is None or (trace and isinstance(result.trace, CodeTrace))
            ):
                yield result
            elif (
                isinstance(result, CaseFailure)
                and isinstance(result.kind, FailureKind)
                and (trace or result.kind is not FailureKind.TRACE)
            ):
                yield result
            else:
                yield _RunError.MALFORMED


def _failure(result: CaseFailure | _RunError) -> str:
    if isinstance(result, CaseFailure):
        return f"sandbox_{result.kind.value}"
    return result.value


def _originals(
    original: Path,
    cases: tuple[Invocation, ...],
    engine: Engine,
    images: dict[str, str],
    inventory: BlockInventory | None,
) -> tuple[list[tuple[Invocation, Outcome]], int, Counter[str], int]:
    eligible = []
    covered: set[int] = set()
    disagreements = 0
    errors: Counter[str] = Counter()
    for batch in batched(cases, MAX_BATCH):
        baseline = _run(original, batch, engine, images["amd64"])
        independent = (
            _run(original, batch, Engine.QEMU_X86_64, images["arm64"])
            if engine is Engine.ROSETTA
            else None
        )
        agreed = []
        for case, first in zip(batch, baseline, strict=True):
            second = next(independent) if independent is not None else first
            if not isinstance(first, Outcome):
                errors[_failure(first)] += 1
            elif not isinstance(second, Outcome):
                errors[_failure(second)] += 1
            elif compare(first, second):
                disagreements += 1
            elif inventory is None:
                errors["coverage_inspection_error"] += 1
            else:
                agreed.append((case, first))

        if not agreed or inventory is None:
            continue
        traced = _run(
            original,
            tuple(case for case, _ in agreed),
            Engine.QEMU_X86_64,
            images["arm64"],
            trace=True,
        )
        for (case, expected), observed in zip(agreed, traced, strict=True):
            if not isinstance(observed, Outcome):
                errors[_failure(observed)] += 1
            elif observed.trace is None:
                errors["missing_trace"] += 1
            elif compare(expected, observed):
                errors["traced_behavior_changed"] += 1
            else:
                hits = inventory.hits(observed.trace)
                if inventory.entry not in hits:
                    errors["trace_missed_entry"] += 1
                else:
                    covered.update(hits)
                    eligible.append((case, expected))
    return eligible, disagreements, errors, len(covered)


def _evaluate_build(
    project: Path,
    build_directory: Path,
    engine: Engine,
    compiler: Compiler,
    image: str,
    eligible: list[tuple[Invocation, Outcome]],
) -> BuildReport:
    architecture = engine.platform
    destination = build_directory / f"{architecture}-{compiler.value}.elf"
    try:
        build = (
            None
            if destination.exists(follow_symlinks=False)
            else build_project(project, destination, engine, compiler, image=image)
        )
    except Exception:
        # Build diagnostics can contain private paths.
        build = None
    if (
        not isinstance(build, BuildResult)
        or build.engine is not engine
        or build.compiler is not compiler
        or build.executable not in (None, destination)
    ):
        return BuildReport(architecture, compiler, False, 0, 0, 1, {"build_error": 1})
    if build.executable is None:
        return BuildReport(
            architecture, compiler, False, build.warnings, 0, 0, {"build_failed": 1}
        )
    matched = 0
    errors = 0
    failures: Counter[str] = Counter()
    rebuilt = _run(destination, tuple(case for case, _ in eligible), engine, image)
    for (_, expected), observed in zip(eligible, rebuilt, strict=True):
        if isinstance(observed, Outcome):
            differences = compare(expected, observed)
            if differences:
                failures.update(differences)
            else:
                matched += 1
        else:
            failures[_failure(observed)] += 1
            errors += isinstance(observed, _RunError)
    return BuildReport(
        architecture, compiler, True, build.warnings, matched, errors, dict(failures)
    )


def evaluate_pair(
    original: Path,
    project: Path,
    cases: tuple[Invocation, ...],
    build_directory: Path,
    images: dict[str, str],
) -> PairReport:
    """Evaluate behavior with pinned worker images.

    The caller must verify the Docker runtime, including Rosetta on Apple
    Silicon, and supply a private build directory with unused artifact names.
    Each original case contributes to at most one error category. A rebuild
    case can contribute to several difference categories. Coverage counts
    recovered block entries reached by eligible original cases.
    """
    image_ids = {arch: images.get(arch, "") for arch in ("amd64", "arm64")}
    if not all(re.fullmatch(r"sha256:[a-f0-9]{64}", id_) for id_ in image_ids.values()):
        raise ValueError("Pair evaluation requires pinned amd64 and arm64 worker IDs.")
    engine = (
        Engine.ROSETTA
        if platform.system() == "Darwin" and platform.machine() == "arm64"
        else Engine.AMD64
    )
    inventory = None
    if cases:
        try:
            inspected = inspect_x86(original, image_ids["amd64"])
            if isinstance(inspected, BlockInventory):
                inventory = inspected
        except Exception:
            # The inspection error can include private paths or binary data.
            pass
    eligible, disagreements, original_errors, covered = _originals(
        original, cases, engine, image_ids, inventory
    )
    builds = tuple(
        _evaluate_build(
            project,
            build_directory,
            target,
            compiler,
            image_ids[target.platform],
            eligible,
        )
        for target in (engine, Engine.ARM64)
        for compiler in (Compiler.GCC, Compiler.CLANG)
    )
    errors = original_errors.total() + sum(build.evaluation_errors for build in builds)
    return PairReport(
        total_cases=len(cases),
        eligible_cases=len(eligible),
        emulator_disagreements=disagreements,
        evaluation_errors=errors,
        original_error_categories=dict(original_errors),
        recovered_blocks=len(inventory.blocks) if inventory is not None else 0,
        covered_blocks=covered,
        builds=builds,
        behavior_passed=bool(eligible)
        and errors == 0
        and all(
            build.compiled and build.matched_cases == len(eligible) for build in builds
        ),
    )
