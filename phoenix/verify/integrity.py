import subprocess
from dataclasses import dataclass, replace

from phoenix.verify import Verification
from phoenix_eval.build import ProjectSnapshot
from phoenix_eval.integrity import (
    CompilerEvidence,
    FunctionShape,
    IntegrityError,
    IntegrityReport,
    check_integrity,
    inspect_project,
)


@dataclass(frozen=True, slots=True)
class IntegrityInputs:
    original: bytes
    shapes: tuple[FunctionShape, ...]
    outputs: frozenset[bytes]
    images: dict[str, str]

    def check(
        self, project: ProjectSnapshot, verification: Verification
    ) -> IntegrityReport | None:
        executables = tuple(
            check.tested_executable
            for check in verification.checks
            if check.tested_executable is not None
        )
        if not executables:
            return None
        evidence: tuple[CompilerEvidence, ...] = ()
        rejection = None
        try:
            evidence = inspect_project(project, self.images)
        except IntegrityError as error:
            if not error.category.startswith("compiler_") or error.category in {
                "compiler_arguments",
                "compiler_incomplete",
                "compiler_target",
            }:
                raise
            rejection = error.category
        except (OSError, subprocess.SubprocessError):
            raise IntegrityError(
                "The development source checker is unavailable."
            ) from None
        report = check_integrity(
            self.original,
            dict(project.files),
            executables,
            evidence,
            self.outputs,
            self.shapes,
        )
        if rejection is not None:
            report = replace(
                report, passed=False, categories={**report.categories, rejection: 1}
            )
        return report

    def repair_feedback(self, report: IntegrityReport) -> str:
        lines = [
            "The development integrity check failed.",
            *(f"{name} {count}" for name, count in sorted(report.categories.items())),
        ]
        if "unproven_control_flow" in report.categories:
            lines.extend(
                f"{shape.name} allows {shape.branches} branches, "
                f"{shape.loops} loops, and {shape.switches} switches."
                for shape in self.shapes
            )
        return "\n".join(lines)
