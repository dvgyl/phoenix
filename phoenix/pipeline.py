import json
import sys
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
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
from phoenix.generate.raw import write_raw_project
from phoenix.generate.switch_plan import SwitchPlan, plan_switches
from phoenix.ingest import BinaryMetadata
from phoenix.lift import lift_binary
from phoenix.lift.mapping import read_selected_generation
from phoenix.llm.ledger import BudgetExceeded, Ledger
from phoenix.llm.provider import Model, Provider, Request, RetryLater
from phoenix.package import package_project, reached_functions
from phoenix.recover import recover, recover_bytes
from phoenix.repair import feedback
from phoenix.verify import (
    BUILD_CONFIGURATIONS,
    Check,
    Verification,
    mismatch,
    verify_project,
)
from phoenix.verify.integrity import IntegrityInputs
from phoenix_eval.build import BuildResult, ProjectSnapshot, snapshot_project
from phoenix_eval.docker import Engine, read_program
from phoenix_eval.integrity import IntegrityReport, original_shapes
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
    executable_sha256: str | None
    warnings: int
    diagnostics: str


class _SavedCheck(TypedDict):
    build: _SavedBuild
    outcomes: list[str]


class _SavedVerification(TypedDict):
    project_sha256: str
    development_sha256: str
    checks: list[_SavedCheck]


class Method(StrEnum):
    PHOENIX = "phoenix"
    GHIDRA_RAW = "ghidra-raw"


@dataclass(frozen=True, slots=True)
class Settings:
    images: dict[str, str]
    seed: int
    ghidra: Path
    java_home: Path
    repair_limit: int
    astra_repair: bool
    checker_images: dict[str, str]
    method: Method = Method.PHOENIX
    checked_switches: bool = False

    def __post_init__(self) -> None:
        if self.checked_switches and self.method is not Method.PHOENIX:
            raise ValueError("Checked switches require the Phoenix method.")
        if not 0 <= self.repair_limit <= 20:
            raise ValueError("Use a repair limit from 0 to 20.")


@dataclass(frozen=True, slots=True)
class Reconstruction:
    project: Path
    development_passed: bool


@dataclass(frozen=True, slots=True)
class Trial:
    candidate: Candidate
    project: ProjectSnapshot
    verification: Verification
    integrity: IntegrityReport | None

    @property
    def passed(self) -> bool:
        return (
            self.verification.passed
            and self.integrity is not None
            and self.integrity.passed
        )


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


def _analysis_record(result: Analysis) -> _SavedAnalysis:
    return {
        "cases": [
            (encode_invocation(case.invocation), encode_result(case.expected))
            for case in result.cases
        ],
        "covered_blocks": result.covered_blocks,
        "recovered_blocks": result.recovered_blocks,
        "candidate_count": result.candidate_count,
        "emulator_sensitive": result.emulator_sensitive,
        "invalid_candidates": result.invalid_candidates,
    }


def _analyze(binary: Path, path: Path, settings: Settings) -> Analysis:
    if path.is_file():
        return _read_analysis(path)
    result = analyze(binary, settings.images, settings.seed)
    write_json(path, _analysis_record(result))
    return result


def _load_verification(
    records: list[_SavedCheck], build_dir: Path, expected: tuple[Outcome, ...]
) -> Verification:
    configurations = [
        (record["build"]["engine"], record["build"]["compiler"]) for record in records
    ]
    if len(configurations) != len(BUILD_CONFIGURATIONS) or set(configurations) != set(
        BUILD_CONFIGURATIONS
    ):
        raise ValueError(
            "Saved verification requires four distinct build configurations."
        )
    checks = []
    for record in records:
        build = record["build"]
        engine, compiler = Engine(build["engine"]), Compiler(build["compiler"])
        executable = None
        tested = None
        outcomes = tuple(decode_result(item) for item in record["outcomes"])
        if len(outcomes) != (len(expected) if build["executable"] is not None else 0):
            raise ValueError(
                "The saved build result count does not match the development cases."
            )
        if build["executable"] is not None:
            name = f"{engine.value}-{compiler}.elf"
            executable = build_dir / name
            if build["executable"] != name or executable.resolve() != executable:
                raise ValueError("The saved executable path has changed.")
            tested = read_program(executable)
            if sha256(tested).hexdigest() != build["executable_sha256"]:
                raise ValueError("The tested executable has changed.")
        elif build["executable_sha256"] is not None:
            raise ValueError("A failed build cannot have a tested executable identity.")
        checks.append(
            Check(
                BuildResult(
                    engine,
                    compiler,
                    executable,
                    build["warnings"],
                    build["diagnostics"],
                ),
                outcomes,
                tuple(
                    mismatch(original, actual)
                    for original, actual in zip(expected, outcomes)
                ),
                tested,
            )
        )
    return Verification(tuple(checks), len(expected))


def _verify(
    project: ProjectSnapshot,
    build_dir: Path,
    path: Path,
    analysis: Analysis,
    settings: Settings,
) -> Verification:
    project_digest = sha256(project.archive).hexdigest()
    development_digest = sha256(
        json.dumps(_analysis_record(analysis)["cases"], ensure_ascii=True).encode()
    ).hexdigest()
    expected = tuple(case.expected for case in analysis.cases)
    if path.is_file():
        saved = cast(_SavedVerification, json.loads(path.read_text(encoding="utf-8")))
        if saved["project_sha256"] != project_digest:
            raise ValueError("The source used for the saved builds has changed.")
        if saved.get("development_sha256") != development_digest:
            raise ValueError(
                "The saved development inputs or expected outcomes have changed."
            )
        return _load_verification(saved["checks"], build_dir, expected)
    result = verify_project(
        project,
        build_dir,
        tuple(case.invocation for case in analysis.cases),
        expected,
        settings.images,
    )
    write_json(
        path,
        {
            "project_sha256": project_digest,
            "development_sha256": development_digest,
            "checks": [
                {
                    "build": {
                        "engine": check.build.engine,
                        "compiler": check.build.compiler,
                        "warnings": check.build.warnings,
                        "diagnostics": check.build.diagnostics,
                        "executable": check.build.executable.name
                        if check.build.executable is not None
                        else None,
                        "executable_sha256": sha256(check.tested_executable).hexdigest()
                        if check.tested_executable is not None
                        else None,
                    },
                    "outcomes": [encode_result(item) for item in check.outcomes],
                }
                for check in result.checks
            ],
        },
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
    analysis = (
        _analyze(binary, directory / "analyze/cases.json", settings)
        if settings.method is Method.PHOENIX
        else None
    )
    export = directory / "lift/lift.json"
    switch_plan: SwitchPlan | None = None
    if settings.checked_switches:
        original = read_program(binary)
        publication = export.parent
        selection = publication / "evidence-current"
        if not selection.exists() and not selection.is_symlink():
            lift_binary(
                binary,
                export,
                settings.ghidra,
                settings.java_home,
                max_heap_mib=256,
                mapping_companion=True,
                switch_graphs=True,
                switch_source=True,
            )
        _, generation = read_selected_generation(publication, original)
        program = recover_bytes(generation.lift, binary)
        switch_plan = plan_switches(original, generation, program)
        write_json(directory / "recover/switches.json", switch_plan.record())
    else:
        if not export.is_file():
            lift_binary(binary, export, settings.ghidra, settings.java_home)
        program = recover(export, binary)
    protected = switch_plan.protected if switch_plan is not None else ()
    recovered = directory / "recover/program.json"
    write_json(recovered, asdict(program))
    output = directory / "package" / "out" / key
    if analysis is None:
        write_json(
            directory / "recover/evidence.json",
            {
                "sha256": sha256(recovered.read_bytes()).hexdigest(),
                "binary_sha256": metadata.sha256,
            },
        )
        write_raw_project(output, program, binary)
        write_json(
            output / "phoenix_report.json",
            {
                "run_id": run.name,
                "sha256": metadata.sha256,
                "method": settings.method,
                "wall_seconds": round(time.time() - started, 3),
                "llm": asdict(ledger.summary(key)),
            },
        )
        return Reconstruction(output, True)

    original = read_program(binary)
    if sha256(original).hexdigest() != metadata.sha256:
        raise ValueError("The saved input binary SHA-256 has changed.")
    integrity_inputs = IntegrityInputs(
        original,
        original_shapes(recovered.read_bytes(), raw=False),
        frozenset(
            value
            for case in analysis.cases
            for value in (case.expected.stdout, case.expected.stderr)
        ),
        settings.checker_images,
    )
    previous: Candidate | None = None
    difference = ""
    best: Trial | None = None
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
            protected=protected,
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
            candidate = parse_candidate(response, program, protected=protected)
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
        snapshot = snapshot_project(project)
        round_name = f"round-{index:02}"
        verification = _verify(
            snapshot,
            directory / "build" / round_name,
            directory / "verify" / round_name / "result.json",
            analysis,
            settings,
        )
        integrity = integrity_inputs.check(snapshot, verification)
        trial = Trial(candidate, snapshot, verification, integrity)
        if trial.passed:
            best = trial
            stop = "development-passed"
            break
        if best is None or verification.quality >= best.verification.quality:
            best = trial
        if index == settings.repair_limit:
            break
        previous = candidate
        feedback_path = directory / "repair" / round_name / "feedback.json"
        if integrity is not None and integrity.categories.keys() - {"missing_build"}:
            difference = integrity_inputs.repair_feedback(integrity)
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
    verification = best.verification
    passed = verification.passed_cases
    reached = reached_functions(
        binary,
        program,
        tuple(analysis.cases[index].expected for index in sorted(passed)),
    )
    package_project(
        output,
        program,
        best.candidate,
        best.project,
        reached,
        verification,
        best.integrity,
        {
            "run_id": run.name,
            "sha256": metadata.sha256,
            "seed": settings.seed,
            "method": settings.method,
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
            **(
                {"checked_switches": switch_plan.record()}
                if switch_plan is not None
                else {}
            ),
        },
    )
    write_json(
        output / "tests/dev.json",
        _analysis_record(analysis),
    )
    if snapshot_project(output) != best.project:
        raise ValueError("The final package differs from the tested source snapshot.")
    return Reconstruction(output, best.passed)
