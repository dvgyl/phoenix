import json
import sys
import time
from dataclasses import asdict
from hashlib import sha256
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict, cast

from phoenix.analyze import Analysis, DevelopmentCase, analyze
from phoenix.cache import StageCache, StageIdentity
from phoenix.config import LLM_RETRY_ATTEMPTS, LLM_RETRY_BASE_DELAY
from phoenix.jobs import Slots
from phoenix.lift import lift_binary
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Provider, Request, RetryLater
from phoenix.pipeline_types import Method, PackageMetadata, Settings
from phoenix.recover import Program
from phoenix.verify import (
    Check,
    Verification,
    mismatch,
    verify_project,
)
from phoenix_eval.build import BuildResult, ProjectSnapshot
from phoenix_eval.docker import Engine, read_program
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


def _package_metadata(
    run: Path, key: str, ledger: Ledger, started: float, replay: bool
) -> PackageMetadata:
    if not replay:
        return PackageMetadata(run.name, False, round(time.time() - started, 3))
    report = ledger.path.parent / key / "package/out" / key / "phoenix_report.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The recorded package metadata is invalid.")
    run_id = data.get("run_id")
    replayed = data.get("replayed", False)
    elapsed = data.get("wall_seconds")
    if (
        not isinstance(run_id, str)
        or not run_id
        or type(replayed) is not bool
        or not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("The recorded package metadata is invalid.")
    return PackageMetadata(run_id, replayed, float(elapsed))


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


def analysis_record(result: Analysis) -> _SavedAnalysis:
    return cast(
        _SavedAnalysis,
        {
            **vars(result),
            "cases": [
                (encode_invocation(case.invocation), encode_result(case.expected))
                for case in result.cases
            ],
        },
    )


def _analyze(binary: Path, path: Path, settings: Settings) -> Analysis:
    if path.is_file():
        return _read_analysis(path)
    result = analyze(binary, settings.images, settings.seed)
    write_json(path, analysis_record(result))
    return result


def prepare_stages(
    binary: Path,
    binary_sha256: str,
    directory: Path,
    settings: Settings,
    *,
    recorded: Path | None = None,
) -> tuple[Path, Analysis | None]:
    if sha256(binary.read_bytes()).hexdigest() != binary_sha256:
        raise ValueError("The saved input binary SHA-256 has changed.")
    export = directory / "lift/lift.json"

    def lift(output: Path) -> None:
        with Slots.from_environment().acquire("compile"):
            lift_binary(binary, output, settings.ghidra, settings.java_home)
        if sha256(binary.read_bytes()).hexdigest() != binary_sha256:
            raise ValueError("The input binary changed during the lift stage.")

    def analysis_file(output: Path) -> None:
        _analyze(binary, output, settings)
        if sha256(binary.read_bytes()).hexdigest() != binary_sha256:
            raise ValueError("The input binary changed during the devset stage.")

    if settings.cache_root is None:
        analysis = (
            _analyze(binary, directory / "analyze/cases.json", settings)
            if settings.method is Method.PHOENIX
            else None
        )
        if not export.is_file():
            lift(export)
        return export, analysis
    if settings.stage_versions is None:
        raise ValueError("Cached stages require recorded stage versions.")
    cache = StageCache(settings.cache_root)
    cache.materialize(
        "lift",
        StageIdentity(binary_sha256, settings.stage_versions["lift"]),
        export,
        lift,
        recorded=recorded / "lift/lift.json" if recorded is not None else None,
    )
    analysis = None
    if settings.method is Method.PHOENIX:
        path = directory / "analyze/cases.json"
        cache.materialize(
            "devset",
            StageIdentity(
                binary_sha256, settings.stage_versions["devset"], settings.seed
            ),
            path,
            analysis_file,
            recorded=recorded / "analyze/cases.json" if recorded is not None else None,
        )
        analysis = _read_analysis(path)
    return export, analysis


def _load_verification(
    records: list[_SavedCheck], build_dir: Path, expected: tuple[Outcome, ...]
) -> Verification:
    checks = []
    for record in records:
        build = record["build"]
        engine, compiler = Engine(build["engine"]), Compiler(build["compiler"])
        executable = None
        tested = None
        outcomes = tuple(decode_result(item) for item in record["outcomes"])
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


def verification(
    project: ProjectSnapshot,
    build_dir: Path,
    path: Path,
    analysis: Analysis,
    settings: Settings,
) -> Verification:
    project_digest = sha256(project.archive).hexdigest()
    development_digest = sha256(
        json.dumps(analysis_record(analysis)["cases"], ensure_ascii=True).encode()
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


def completion(
    request: Request,
    provider: Provider,
    ledger: Ledger,
    run: Path,
    key: str,
    replay: bool,
) -> str:
    for attempt in range(LLM_RETRY_ATTEMPTS):
        try:
            return ledger.call(key, request, provider, replay=replay).text
        except RetryLater as error:
            if attempt == LLM_RETRY_ATTEMPTS - 1:
                raise
            delay = min(
                3600, max(error.delay_seconds, LLM_RETRY_BASE_DELAY) * 2**attempt
            )
            print(
                json.dumps(
                    {"run_id": run.name, "stage": "model", "retry_seconds": delay}
                ),
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
    raise AssertionError("The model retry loop has no result.")


def report(
    run: Path,
    key: str,
    ledger: Ledger,
    started: float,
    replay: bool,
    binary_sha256: str,
    settings: Settings,
    analysis: Analysis | None = None,
    stop: str = "",
) -> dict[str, object]:
    metadata: dict[str, object] = asdict(
        _package_metadata(run, key, ledger, started, replay)
    )
    metadata["sha256"] = binary_sha256
    summary = asdict(ledger.summary(key))
    if analysis is None:
        return {**metadata, "method": settings.method, "llm": summary}
    return {
        **metadata,
        "seed": settings.seed,
        "method": settings.method,
        "images": settings.images,
        "stop": stop,
        "llm": summary,
        "coverage": {
            "kind": "recovered_block_entries",
            "covered": analysis.covered_blocks,
            "total": analysis.recovered_blocks,
        },
        "analysis_candidates": analysis.candidate_count,
        "emulator_sensitive_candidates": analysis.emulator_sensitive,
        "invalid_candidates": analysis.invalid_candidates,
    }


def save_recovery(directory: Path, program: Program, binary_sha256: str) -> Path:
    recovered = directory / "recover/program.json"
    write_json(recovered, asdict(program))
    write_json(
        directory / "recover/evidence.json",
        {
            "sha256": sha256(recovered.read_bytes()).hexdigest(),
            "binary_sha256": binary_sha256,
        },
    )
    return recovered


def budget_stopped(path: Path, index: int, replay: bool) -> bool:
    return (
        replay
        and path.is_file()
        and index == json.loads(path.read_text(encoding="utf-8"))
    )
