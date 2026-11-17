from hashlib import sha256
from pathlib import Path

from phoenix import checkpoints
from phoenix.config import ROLE_MODELS
from phoenix.generate import (
    Candidate,
    InvalidCandidate,
    parse_candidate,
    request_candidate,
    write_project,
)
from phoenix.generate.raw import write_raw_project
from phoenix.ingest import BinaryMetadata
from phoenix.llm.ledger import BudgetExceeded, Ledger
from phoenix.llm.provider import Provider
from phoenix.package import package_project, reached_functions
from phoenix.pipeline_types import Reconstruction, Settings, Trial
from phoenix.recover import recover
from phoenix.repair import feedback
from phoenix.verify.integrity import IntegrityInputs
from phoenix_eval.build import snapshot_project
from phoenix_eval.docker import read_program
from phoenix_eval.integrity import original_shapes


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
    export, analysis = checkpoints.prepare_stages(
        binary,
        metadata.sha256,
        directory,
        settings,
        recorded=ledger.path.parent / key if replay else None,
    )
    program = recover(export, binary)
    recovered = checkpoints.save_recovery(directory, program, metadata.sha256)
    output = directory / "package" / "out" / key
    if analysis is None:
        write_raw_project(output, program, binary)
        checkpoints.write_json(
            output / "phoenix_report.json",
            checkpoints.report(
                run, key, ledger, started, replay, metadata.sha256, settings
            ),
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
        if checkpoints.budget_stopped(budget_stop, index, replay):
            stop = "budget-limit"
            break
        stage = "generate" if index == 0 else f"repair/round-{index:02}"
        model = ROLE_MODELS[
            "strongest" if index >= 2 and settings.strongest_repair else "runtime"
        ]
        request = request_candidate(
            program,
            previous=previous,
            difference=difference,
            round_number=index,
            model=model,
        )
        try:
            response = checkpoints.completion(
                request, provider, ledger, run, key, replay
            )
        except BudgetExceeded:
            if best is None:
                raise
            stop = "budget-limit"
            checkpoints.write_json(budget_stop, index)
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
        snapshot = snapshot_project(project)
        round_name = f"round-{index:02}"
        verification = checkpoints.verification(
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
        checkpoints.write_json(feedback_path, difference)
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
        checkpoints.report(
            run, key, ledger, started, replay, metadata.sha256, settings, analysis, stop
        ),
    )
    checkpoints.write_json(
        output / "tests/dev.json",
        checkpoints.analysis_record(analysis),
    )
    if snapshot_project(output) != best.project:
        raise ValueError("The final package differs from the tested source snapshot.")
    return Reconstruction(output, best.passed)
