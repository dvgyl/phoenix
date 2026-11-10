from dataclasses import dataclass
from pathlib import Path

from phoenix_eval.build import BuildResult, build_project
from phoenix_eval.case import CaseFailure, CaseResult, Invocation
from phoenix_eval.docker import Engine, run_cases
from phoenix_eval.outcome import Outcome, compare
from phoenix_eval.toolchain import Compiler


@dataclass(frozen=True, slots=True)
class Check:
    build: BuildResult
    outcomes: tuple[CaseResult, ...]
    differences: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class Verification:
    checks: tuple[Check, ...]
    case_count: int

    @property
    def passed_cases(self) -> frozenset[int]:
        if any(check.build.executable is None for check in self.checks):
            return frozenset()
        return frozenset(
            index
            for index in range(self.case_count)
            if all(not check.differences[index] for check in self.checks)
        )

    @property
    def passed(self) -> bool:
        return len(self.passed_cases) == self.case_count

    @property
    def quality(self) -> tuple[int, int, int]:
        return (
            len(self.passed_cases),
            sum(check.build.executable is not None for check in self.checks),
            sum(
                not differences
                for check in self.checks
                for differences in check.differences
            ),
        )


def mismatch(expected: Outcome, actual: CaseResult) -> tuple[str, ...]:
    if isinstance(actual, CaseFailure):
        return (f"sandbox-{actual.kind}",)
    return tuple(compare(expected, actual))


def verify_project(
    project: Path,
    directory: Path,
    cases: tuple[Invocation, ...],
    expected: tuple[Outcome, ...],
    images: dict[str, str],
) -> Verification:
    if not cases or len(cases) != len(expected):
        raise ValueError("The development inputs and outcomes must match in number.")
    checks = []
    for engine in (Engine.ROSETTA, Engine.ARM64):
        for compiler in Compiler:
            image = images[engine.platform]
            executable = directory / f"{engine.value}-{compiler}.elf"
            build = build_project(project, executable, engine, compiler, image=image)
            outcomes = (
                run_cases(build.executable, cases, engine, image=image)
                if build.executable is not None
                else ()
            )
            differences = tuple(
                mismatch(original, candidate)
                for original, candidate in zip(expected, outcomes)
            )
            checks.append(Check(build, outcomes, differences))
    return Verification(tuple(checks), len(cases))
