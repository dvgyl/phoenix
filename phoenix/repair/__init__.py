from dataclasses import replace
from pathlib import Path

from phoenix.package import reached_functions
from phoenix.recover import Program
from phoenix.verify import Check, Verification, mismatch
from phoenix_eval.case import CaseFailure, CaseResult, Invocation
from phoenix_eval.docker import Engine, run_cases
from phoenix_eval.outcome import Outcome
from phoenix_eval.wire import encode_invocation


def _smaller(case: Invocation) -> tuple[Invocation, ...]:
    candidates = [
        Invocation(),
        replace(case, args=()),
        replace(case, stdin=b""),
        replace(case, stdin=case.stdin[: len(case.stdin) // 2]),
        replace(case, overlay=()),
        replace(case, tree=Invocation().tree),
    ]
    return tuple(item for item in dict.fromkeys(candidates) if item != case)


def _minimize(
    binary: Path,
    check: Check,
    case: Invocation,
    expected: Outcome,
    index: int,
    images: dict[str, str],
) -> tuple[Invocation, Outcome, CaseResult]:
    assert check.build.executable is not None
    actual = check.outcomes[index]
    candidates = _smaller(case)
    if not candidates:
        return case, expected, actual
    rosetta = run_cases(binary, candidates, Engine.ROSETTA, image=images["amd64"])
    qemu = run_cases(binary, candidates, Engine.QEMU_X86_64, image=images["arm64"])
    engine = check.build.engine
    rebuilt = run_cases(
        check.build.executable, candidates, engine, image=images[engine.platform]
    )
    for candidate, left, right, result in zip(
        candidates, rosetta, qemu, rebuilt, strict=True
    ):
        if (
            isinstance(left, Outcome)
            and left == right
            and mismatch(left, result) == check.differences[index]
        ):
            return candidate, left, result
    return case, expected, actual


def _output_differences(expected: Outcome, actual: CaseResult) -> str:
    if isinstance(actual, CaseFailure):
        return f"The rebuild reported sandbox category {actual.kind}."
    lines = []
    for stream, left, right in (
        ("stdout", expected.stdout, actual.stdout),
        ("stderr", expected.stderr, actual.stderr),
    ):
        if left == right:
            continue
        index = next(
            (index for index, (a, b) in enumerate(zip(left, right)) if a != b),
            min(len(left), len(right)),
        )
        lines.append(
            f"{stream} first differs at byte {index}. The original has {len(left)} "
            f"bytes. The rebuild has {len(right)} bytes."
        )
    return "\n".join(lines)


def feedback(
    binary: Path,
    program: Program,
    verification: Verification,
    cases: tuple[Invocation, ...],
    expected: tuple[Outcome, ...],
    images: dict[str, str],
) -> str:
    for check in verification.checks:
        if check.build.executable is None:
            return (
                f"The {check.build.engine} {check.build.compiler} build failed.\n"
                + check.build.diagnostics[-4_000:]
            )
    for check in verification.checks:
        for index, kinds in enumerate(check.differences):
            if not kinds:
                continue
            case, outcome, actual = _minimize(
                binary, check, cases[index], expected[index], index, images
            )
            reached = reached_functions(binary, program, (expected[index],))
            functions = ", ".join(hex(entry) for entry in sorted(reached))
            details = (
                f"The {check.build.engine} {check.build.compiler} run differs.\n"
                f"Categories {', '.join(kinds)}\n"
                f"Functions reached by the original dev case {functions}\n"
                f"Development input {encode_invocation(case)}\n"
                f"{_output_differences(outcome, actual)}"
            )
            return details[:8_000]
    raise ValueError("No development failure is available for repair.")
