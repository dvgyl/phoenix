import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import time
from uuid import uuid4

from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.generate.switch_plan import plan_switches
from phoenix.generate.switch_source import parse_flat_switch
from phoenix.ingest import inspect_binary
from phoenix.lift import LiftError
from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import read_selected_generation
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, ProviderError, Request, Usage
from phoenix.pipeline import Settings, _analysis_record, reconstruct, write_json
from phoenix.public_checks.switch_manifest import SwitchSuite, load_suite
from phoenix.public_checks.switch_response import (
    FixedPublicProvider,
    PublicResponse,
    prepare_response,
)
from phoenix.recover import recover_bytes
from phoenix.recover.addresses import prove_addresses
from phoenix_eval.build import snapshot_project
from phoenix_eval.coverage import inspect_x86
from phoenix_eval.docker import Engine, WorkerError, freeze_images, run_cases
from phoenix_eval.outcome import Outcome, compare
from phoenix_eval.pair import PairReport, evaluate_pair
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import (
    CHECKER_SOURCE_LABEL,
    checker_source_digest,
    evaluator_build,
    lifting_tool_identity,
    pinned_lifting_tools,
    pipeline_source_digest,
)
from phoenix_eval.toolchain import Compiler, build_public
from phoenix_eval.wire import encode_result


class _ReplayOnly:
    name = FixedPublicProvider.name

    def maximum_usage(self, request: Request) -> Usage:
        raise AssertionError("The public replay cannot reserve model use.")

    def complete(self, request: Request) -> Completion:
        raise AssertionError("The public replay cannot call a provider.")


def _prepared(binary: Path, publication: Path) -> PublicResponse:
    original = binary.read_bytes()
    _, generation = read_selected_generation(publication, original)
    program = recover_bytes(generation.lift, binary)
    lift = parse_lift(generation.lift, original)
    proof = prove_addresses(original, lift, generation.mapping)
    (protected,) = plan_switches(original, generation, program).protected
    return prepare_response(program, original, lift, proof, protected)


def _development(
    binary: Path, suite: SwitchSuite, images: dict[str, str], directory: Path
) -> Analysis:
    cases = tuple(case.invocation for case in suite.cases)
    left = run_cases(binary, cases, Engine.ROSETTA, image=images["amd64"])
    right = run_cases(binary, cases, Engine.QEMU_X86_64, image=images["arm64"])
    write_json(
        directory / "oracles.json",
        [
            {
                "case": case.identifier,
                "rosetta": encode_result(first),
                "qemu": encode_result(second),
            }
            for case, first, second in zip(suite.cases, left, right, strict=True)
        ],
    )
    if any(
        not isinstance(first, Outcome)
        or not isinstance(second, Outcome)
        or compare(first, second)
        for first, second in zip(left, right, strict=True)
    ):
        raise ValueError("The public oracle results do not all agree.")
    selected = tuple(case for case in suite.cases if case.development)
    traced = run_cases(
        binary,
        tuple(case.invocation for case in selected),
        Engine.QEMU_X86_64,
        trace=True,
        image=images["arm64"],
    )
    write_json(
        directory / "development-traces.json",
        [
            {"case": case.identifier, "result": encode_result(result)}
            for case, result in zip(selected, traced, strict=True)
        ],
    )
    expected = {
        case.identifier: result for case, result in zip(suite.cases, left, strict=True)
    }
    inventory = inspect_x86(binary, image=images["amd64"])
    development = []
    covered: set[int] = set()
    for case, result in zip(selected, traced, strict=True):
        baseline = expected[case.identifier]
        if (
            not isinstance(baseline, Outcome)
            or not isinstance(result, Outcome)
            or result.trace is None
            or compare(baseline, result)
        ):
            raise ValueError("The public development trace changed its outcome.")
        covered.update(inventory.hits(result.trace))
        development.append(DevelopmentCase(case.invocation, result))
    return Analysis(
        tuple(development), len(covered), len(inventory.blocks), len(selected), 0, 0
    )


def check_source(source: bytes, prepared: PublicResponse) -> None:
    fragment = prepared.protected_source.encode("utf-8")
    parsed = parse_flat_switch(fragment)
    labels = tuple(label.value for arm in parsed.arms for label in arm.labels)
    if (
        sha256(fragment).hexdigest() != prepared.protected_source_sha256
        or source.count(fragment) != 1
        or parsed.mask != 15
        or labels != (*range(12), None)
    ):
        raise ValueError("The public project lost its protected source contract.")


def disabled_source(source: bytes, prepared: PublicResponse) -> bytes:
    check_source(source, prepared)
    stub = (prepared.protected_signature + "\n{\n    return 0;\n}\n").encode("utf-8")
    return source.replace(prepared.protected_source.encode("utf-8"), stub, 1)


def _passed(report: PairReport, case_count: int) -> bool:
    return (
        report.behavior_passed
        and report.total_cases == report.eligible_cases == case_count
        and report.emulator_disagreements == report.evaluation_errors == 0
        and _four_builds(report)
        and all(
            build.compiled
            and build.matched_cases == case_count
            and build.evaluation_errors == 0
            and not build.failure_categories
            for build in report.builds
        )
    )


def _four_builds(report: PairReport) -> bool:
    return len(report.builds) == 4 and {
        (build.architecture, build.compiler) for build in report.builds
    } == {
        (architecture, compiler)
        for architecture in ("amd64", "arm64")
        for compiler in (Compiler.GCC, Compiler.CLANG)
    }


def run_gate(workspace: Path, repository: Path, identifier: str) -> Path:
    if os.environ.get("PHOENIX_VM_LEASE") != "public-u2":
        raise ValueError("Wait for the public switch Linux window.")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", identifier) is None:
        raise ValueError("The public run ID is invalid.")
    dirty = subprocess.check_output(
        ("git", "-C", str(repository), "status", "--porcelain"), text=True
    )
    if dirty.strip():
        raise ValueError("Commit the public control before Linux execution.")
    suite = load_suite(repository / "corpus_public/mechanisms/switch")
    provenance = evaluator_build(repository)
    runtime = verify_runtime("apple-silicon")
    images = freeze_images(
        (Engine.ROSETTA, Engine.ARM64), provenance.worker_source_sha256
    )
    checker_digest = checker_source_digest(repository)
    checkers = freeze_images(
        (Engine.ROSETTA, Engine.ARM64),
        checker_digest,
        repository="phoenix-c-integrity",
        source_label=CHECKER_SOURCE_LABEL,
    )
    ghidra, java = pinned_lifting_tools(workspace, repository)
    tools = lifting_tool_identity(ghidra, java)
    directory = workspace / "audit/public-gates" / identifier
    if directory.resolve() != directory:
        raise ValueError("The public output directory must have no symbolic links.")
    directory.mkdir(parents=True, mode=0o700)
    settings = Settings(
        images, 0, ghidra, java, 0, False, checkers, checked_switches=True
    )
    write_json(
        directory / "preflight.json",
        {
            "kind": "public-U2-production-caller",
            "run_id": identifier,
            "evaluator": asdict(provenance),
            "pipeline_source_sha256": pipeline_source_digest(repository),
            "runtime": asdict(runtime),
            "worker_images": images,
            "checker_images": checkers,
            "lifting_tools": tools,
            "source_sha256": suite.source_sha256,
            "manifest_sha256": suite.manifest_sha256,
            "cases_sha256": suite.cases_sha256,
            "uses_live_model_provider": False,
            "unvisited_selector": suite.unvisited_selector,
        },
    )
    results: list[dict[str, object]] = []
    write_json(
        directory / "report.json",
        {
            "kind": "public-U2-production-caller",
            "run_id": identifier,
            "results": results,
            "complete": False,
            "passed": False,
        },
    )
    cases = tuple(case.invocation for case in suite.cases)
    for compiler in (Compiler.GCC, Compiler.CLANG):
        control = directory / compiler.value
        control.mkdir(mode=0o700)
        binary = control / "original.elf"
        build_public(
            suite.source, binary, Engine.ROSETTA, compiler, image=images["amd64"]
        )
        analysis = _development(binary, suite, images, control)
        run = control / "reconstruction"
        key = "public-switch"
        write_json(run / key / "analyze/cases.json", _analysis_record(analysis))
        provider = FixedPublicProvider(lambda: _prepared(binary, run / key / "lift"))
        ledger = Ledger(run)
        result = reconstruct(
            run,
            key,
            binary,
            inspect_binary(binary),
            settings,
            ledger,
            provider,
            started=time(),
        )
        if provider.prepared is None or provider.calls != 1:
            raise ValueError(
                "The public caller did not use exactly one fixed response."
            )
        prepared = provider.prepared
        write_json(control / "fixed-response.json", asdict(prepared))
        original_snapshot = snapshot_project(result.project)
        source = dict(original_snapshot.files)["src/program.c"]
        check_source(source, prepared)
        written = json.loads((result.project / "phoenix_report.json").read_bytes())
        (protected,) = written["checked_switches"]["protected"]
        if protected["selectors"] != list(range(12)):
            raise ValueError("The public project lost a checked selector.")
        replay = control / "replay"
        write_json(replay / key / "analyze/cases.json", _analysis_record(analysis))
        replayed = reconstruct(
            replay,
            key,
            binary,
            inspect_binary(binary),
            settings,
            ledger,
            _ReplayOnly(),
            started=time(),
            replay=True,
        )
        if snapshot_project(replayed.project) != original_snapshot:
            raise ValueError("The public replay changed its source project.")
        pair_directory = control / "verification"
        pair_directory.mkdir()
        positive = evaluate_pair(binary, result.project, cases, pair_directory, images)
        negative_project = control / "disabled-emitter"
        shutil.copytree(result.project, negative_project)
        altered = disabled_source(source, prepared)
        (negative_project / "src/program.c").write_bytes(altered)
        source_rejected = False
        try:
            check_source(altered, prepared)
        except ValueError:
            source_rejected = True
        negative_directory = control / "negative-verification"
        negative_directory.mkdir()
        unvisited = tuple(
            case.invocation for case in suite.cases if not case.development
        )
        negative = evaluate_pair(
            binary, negative_project, unvisited, negative_directory, images
        )
        negative_passed = (
            source_rejected
            and _four_builds(negative)
            and negative.total_cases == negative.eligible_cases == len(unvisited)
            and negative.emulator_disagreements == negative.evaluation_errors == 0
            and all(
                build.compiled
                and build.matched_cases == 0
                and build.evaluation_errors == 0
                and build.failure_categories == {"stdout": len(unvisited)}
                for build in negative.builds
            )
        )
        rows = {
            "compiler": compiler.value,
            "binary_sha256": sha256(binary.read_bytes()).hexdigest(),
            "project_sha256": sha256(original_snapshot.archive).hexdigest(),
            "protected_source_sha256": prepared.protected_source_sha256,
            "development_cases": len(analysis.cases),
            "verification_cases": len(cases),
            "source_bytes": len(source),
            "replay_source_equal": True,
            "development_passed": result.development_passed,
            "replay_development_passed": replayed.development_passed,
            "measured": asdict(positive),
            "negative_source_control": {
                "source_contract_rejected": source_rejected,
                "stale_metadata_retained": True,
                "measured": asdict(negative),
                "expected_failure_observed": negative_passed,
            },
            "passed": (
                _passed(positive, len(cases))
                and negative_passed
                and result.development_passed
                and replayed.development_passed
            ),
        }
        results.append(rows)
        write_json(
            directory / "report.json",
            {
                "kind": "public-U2-production-caller",
                "run_id": identifier,
                "results": results,
                "complete": len(results) == 2,
                "passed": len(results) == 2 and all(row["passed"] for row in results),
            },
        )
    return directory / "report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a public Phoenix mechanism.")
    parser.add_argument("unit", choices=("U2",))
    parser.add_argument("--run-id", default=f"public-u2-{uuid4().hex}")
    args = parser.parse_args()
    workspace = os.environ.get("PHOENIX_ROOT")
    if workspace is None:
        parser.error("Source the Phoenix workspace environment.")
    try:
        report = run_gate(
            Path(workspace), Path(__file__).resolve().parents[2], args.run_id
        )
    except (
        OSError,
        ValueError,
        LiftError,
        ProviderError,
        WorkerError,
        subprocess.SubprocessError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(report)
    record = json.loads(report.read_bytes())
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
