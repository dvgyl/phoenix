import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict, cast

from phoenix.analyze import Analysis, DevelopmentCase, analyze
from phoenix.generate import (
    Candidate,
    InvalidCandidate,
    parse_candidate,
    request_candidate,
    write_project,
)
from phoenix.ingest import BinaryMetadata
from phoenix.lift import lift_binary
from phoenix.llm.ledger import BudgetExceeded, Ledger
from phoenix.llm.provider import Model, Provider, Request, RetryLater
from phoenix.package import package_project, reached_functions
from phoenix.recover import recover
from phoenix.repair import feedback
from phoenix.verify import Check, Verification, verify_project
from phoenix_eval.build import BuildResult
from phoenix_eval.docker import Engine
from phoenix_eval.outcome import Outcome
from phoenix_eval.toolchain import Compiler
from phoenix_eval.wire import (
    decode_invocation,
    decode_result,
    encode_invocation,
    encode_result,
)


class _SavedAnalysis(TypedDict):
    cases: list[tuple[str, str]]
    covered_blocks: int
    recovered_blocks: int
    candidate_count: int
    emulator_sensitive: int
    invalid_candidates: int


class _SavedBuild(TypedDict):
    engine: str
    compiler: str
    executable: str | None
    warnings: int
    diagnostics: str


class _SavedCheck(TypedDict):
    build: _SavedBuild
    outcomes: list[str]
    differences: list[list[str]]


@dataclass(frozen=True, slots=True)
class Settings:
    images: dict[str, str]
    seed: int
    ghidra: Path
    java_home: Path
    repair_limit: int
    astra_repair: bool

    def __post_init__(self) -> None:
        if not 0 <= self.repair_limit <= 20:
            raise ValueError("Use a repair limit from 0 to 20.")


@dataclass(frozen=True, slots=True)
class Reconstruction:
    project: Path
    development_passed: bool


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete_on_close=False
    ) as staged:
        json.dump(value, staged, ensure_ascii=True, indent=2)
        staged.write("\n")
        staged.close()
        Path(staged.name).replace(path)


def _read_analysis(path: Path) -> Analysis:
    saved = cast(_SavedAnalysis, json.loads(path.read_text(encoding="utf-8")))
    cases = []
    for invocation, result in saved["cases"]:
        outcome = decode_result(result)
        if not isinstance(outcome, Outcome) or outcome.trace is None:
            raise ValueError("The saved development case has no traced outcome.")
        cases.append(DevelopmentCase(decode_invocation(invocation), outcome))
    return Analysis(
        tuple(cases),
        saved["covered_blocks"],
        saved["recovered_blocks"],
        saved["candidate_count"],
        saved["emulator_sensitive"],
        saved["invalid_candidates"],
    )


def _analyze(binary: Path, path: Path, settings: Settings) -> Analysis:
    if path.is_file():
        return _read_analysis(path)
    result = analyze(binary, settings.images, settings.seed)
    write_json(
        path,
        {
            "cases": [
                (encode_invocation(case.invocation), encode_result(case.expected))
                for case in result.cases
            ],
            "covered_blocks": result.covered_blocks,
            "recovered_blocks": result.recovered_blocks,
            "candidate_count": result.candidate_count,
            "emulator_sensitive": result.emulator_sensitive,
            "invalid_candidates": result.invalid_candidates,
        },
    )
    return result


def _load_verification(path: Path, build_dir: Path, count: int) -> Verification:
    saved = cast(list[_SavedCheck], json.loads(path.read_text(encoding="utf-8")))
    checks = []
    for record in saved:
        build = record["build"]
        executable = build["executable"]
        checks.append(
            Check(
                BuildResult(
                    Engine(build["engine"]),
                    Compiler(build["compiler"]),
                    build_dir / executable if executable else None,
                    build["warnings"],
                    build["diagnostics"],
                ),
                tuple(decode_result(item) for item in record["outcomes"]),
                tuple(tuple(item) for item in record["differences"]),
            )
        )
    return Verification(tuple(checks), count)


def _verify(
    project: Path, build_dir: Path, path: Path, analysis: Analysis, settings: Settings
) -> Verification:
    if path.is_file():
        result = _load_verification(path, build_dir, len(analysis.cases))
        if all(
            check.build.executable is None or check.build.executable.is_file()
            for check in result.checks
        ):
            return result
    result = verify_project(
        project,
        build_dir,
        tuple(case.invocation for case in analysis.cases),
        tuple(case.expected for case in analysis.cases),
        settings.images,
    )
    write_json(
        path,
        [
            {
                "build": {
                    "engine": check.build.engine,
                    "compiler": check.build.compiler,
                    "warnings": check.build.warnings,
                    "diagnostics": check.build.diagnostics,
                    "executable": check.build.executable.name
                    if check.build.executable is not None
                    else None,
                },
                "outcomes": [encode_result(item) for item in check.outcomes],
                "differences": check.differences,
            }
            for check in result.checks
        ],
    )
    return result


def _completion(
    request: Request,
    provider: Provider,
    ledger: Ledger,
    run: Path,
    key: str,
    replay: bool,
) -> str:
    for attempt in range(4):
        try:
            return ledger.call(key, request, provider, replay=replay).text
        except RetryLater as error:
            if attempt == 3:
                raise
            delay = min(3600, max(error.delay_seconds, 30) * 2**attempt)
            print(
                json.dumps(
                    {"run_id": run.name, "stage": "model", "retry_seconds": delay}
                ),
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
    raise AssertionError("The model retry loop has no result.")


def reconstruct(
    run: Path,
    key: str,
    binary: Path,
    metadata: BinaryMetadata,
    settings: Settings,
    ledger: Ledger,
    provider: Provider,
    *,
    started: float,
    replay: bool = False,
) -> Reconstruction:
    directory = run / key
    analysis = _analyze(binary, directory / "analyze/cases.json", settings)
    export = directory / "lift/lift.json"
    if not export.is_file():
        lift_binary(binary, export, settings.ghidra, settings.java_home)
    program = recover(export)
    write_json(directory / "recover/program.json", asdict(program))

    previous: Candidate | None = None
    difference = ""
    best: tuple[Candidate, Verification] | None = None
    stop = "repair-limit"
    budget_stop = ledger.path.parent / key / "repair/budget-stop.json"
    for index in range(settings.repair_limit + 1):
        if replay and budget_stop.is_file():
            saved_stop = json.loads(budget_stop.read_text(encoding="utf-8"))
            if index == saved_stop:
                stop = "budget-limit"
                break
        stage = "generate" if index == 0 else f"repair/round-{index:02}"
        model = Model.ASTRA if index >= 2 and settings.astra_repair else Model.SOL
        request = request_candidate(
            program,
            previous=previous,
            difference=difference,
            round_number=index,
            model=model,
        )
        try:
            response = _completion(request, provider, ledger, run, key, replay)
        except BudgetExceeded:
            if best is None:
                raise
            stop = "budget-limit"
            write_json(budget_stop, index)
            break
        try:
            candidate = parse_candidate(response, program)
        except InvalidCandidate as error:
            if index == settings.repair_limit:
                if best is None:
                    raise
                stop = "invalid-repair"
                break
            difference = f"The prior model response was invalid. {error}"
            continue
        project = directory / stage / "project"
        write_project(project, candidate)
        round_name = f"round-{index:02}"
        verification = _verify(
            project,
            directory / "build" / round_name,
            directory / "verify" / round_name / "result.json",
            analysis,
            settings,
        )
        if best is None or verification.quality >= best[1].quality:
            best = candidate, verification
        if verification.passed:
            stop = "development-passed"
            break
        if index == settings.repair_limit:
            break
        previous = candidate
        feedback_path = directory / "repair" / round_name / "feedback.json"
        if feedback_path.is_file():
            difference = cast(
                str, json.loads(feedback_path.read_text(encoding="utf-8"))
            )
        else:
            difference = feedback(
                binary,
                program,
                verification,
                tuple(case.invocation for case in analysis.cases),
                tuple(case.expected for case in analysis.cases),
                settings.images,
            )
            write_json(feedback_path, difference)
    if best is None:
        raise InvalidCandidate("The model did not emit a usable project.")
    candidate, verification = best
    passed = verification.passed_cases
    reached = reached_functions(
        binary,
        program,
        tuple(analysis.cases[index].expected for index in sorted(passed)),
    )
    output = directory / "package" / "out" / key
    package_project(
        output,
        program,
        candidate,
        reached,
        verification,
        {
            "run_id": run.name,
            "sha256": metadata.sha256,
            "seed": settings.seed,
            "images": settings.images,
            "replayed": replay,
            "stop": stop,
            "wall_seconds": round(time.time() - started, 3),
            "llm": asdict(ledger.summary(key)),
            "coverage": {
                "kind": "recovered_block_entries",
                "covered": analysis.covered_blocks,
                "total": analysis.recovered_blocks,
            },
            "analysis_candidates": analysis.candidate_count,
            "emulator_sensitive_candidates": analysis.emulator_sensitive,
            "invalid_candidates": analysis.invalid_candidates,
        },
    )
    write_json(
        output / "tests/dev.json",
        json.loads((directory / "analyze/cases.json").read_text(encoding="utf-8")),
    )
    return Reconstruction(output, verification.passed)
