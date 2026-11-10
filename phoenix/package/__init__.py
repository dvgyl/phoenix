import json
from bisect import bisect_left
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from phoenix.generate import Candidate
from phoenix.recover import Program
from phoenix.verify import Verification
from phoenix_eval.build import ProjectSnapshot, snapshot_project
from phoenix_eval.coverage import read_executable_bounds
from phoenix_eval.integrity import IntegrityReport
from phoenix_eval.outcome import Outcome


def reached_functions(
    binary: Path, program: Program, outcomes: tuple[Outcome, ...]
) -> frozenset[int]:
    entry, code = read_executable_bounds(binary.read_bytes())
    ghidra_bias = program.startup - entry
    hits = sorted(
        {
            hit - outcome.trace.start + code + ghidra_bias
            for outcome in outcomes
            if outcome.trace is not None
            for hit in outcome.trace.hits
        }
    )
    reached = set()
    for function in program.functions:
        for start, end in function.ranges:
            index = bisect_left(hits, start)
            if index < len(hits) and hits[index] <= end:
                reached.add(function.entry)
                break
    return frozenset(reached)


def package_project(
    project: Path,
    program: Program,
    candidate: Candidate,
    snapshot: ProjectSnapshot,
    tested: frozenset[int],
    verification: Verification,
    integrity: IntegrityReport | None,
    evidence: dict[str, object],
) -> None:
    for directory in (project, project / "src", project / "include"):
        if directory.is_symlink():
            raise ValueError("The package directory must not be a symbolic link.")
        directory.mkdir(parents=True, exist_ok=True)
    for name, data in snapshot.files:
        path = project / name
        if path.is_symlink():
            raise ValueError("A package source file must not be a symbolic link.")
        path.write_bytes(data)
    definitions = {item.entry: item for item in candidate.functions}
    functions = [
        {
            "address": hex(function.entry),
            "ranges": [(hex(start), hex(end)) for start, end in function.ranges],
            "name": function.name,
            "signature": definitions[function.entry].signature,
            "evidence": definitions[function.entry].evidence,
            "ghidra_signature": function.ghidra_signature,
            "confidence": "tested" if function.entry in tested else "unverified",
        }
        for function in program.functions
    ]
    builds = [
        {
            "architecture": check.build.engine.platform,
            "engine": check.build.engine,
            "compiler": check.build.compiler,
            "built": check.build.executable is not None,
            "warnings": check.build.warnings,
            "executable_sha256": sha256(check.tested_executable).hexdigest()
            if check.tested_executable is not None
            else None,
            "dev_cases_matched": sum(not result for result in check.differences),
            "dev_differences": [
                {"case": index, "categories": categories}
                for index, categories in enumerate(check.differences)
                if categories
            ],
        }
        for check in verification.checks
    ]
    report = {
        **evidence,
        "project_sha256": sha256(snapshot.archive).hexdigest(),
        "builds": builds,
        "dev_cases": verification.case_count,
        "dev_cases_matched_on_all_builds": len(verification.passed_cases),
        "development_behavior_passed": verification.passed,
        "development_integrity": asdict(integrity) if integrity is not None else None,
        "functions": functions,
    }
    (project / "phoenix_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    if integrity is None:
        integrity_status = "No build was available for the development integrity check."
    elif integrity.passed:
        integrity_status = "The development integrity check passed."
    else:
        categories = ", ".join(
            f"`{name}` ({count})"
            for name, count in sorted(integrity.categories.items())
        )
        integrity_status = f"The development integrity check failed. {categories}."
    lines = [
        "# Phoenix reconstruction report",
        "",
        f"Run `{evidence['run_id']}`.",
        "",
        f"{len(verification.passed_cases)} of {verification.case_count} development "
        "cases matched on all four builds.",
        "",
        integrity_status,
        "",
        "The test runner measures original instruction hits. Function labels use "
        "passing tests and those hits. Branch coverage is unmeasured.",
        "",
        "The package contains the tested source snapshot. Source comments record "
        "confidence at generation. Read the function records in phoenix_report.json "
        "for final test confidence.",
        "",
        "| Architecture | Compiler | Build passed | Warnings | Matching cases |",
        "| --- | --- | --- | --- | --- |",
        *(
            f"| {build['architecture']} | {build['compiler']} | {build['built']} | "
            f"{build['warnings']} | {build['dev_cases_matched']} |"
            for build in builds
        ),
        "",
        "See `phoenix_report.json` for function signatures, evidence, and differences.",
        "",
    ]
    (project / "PHOENIX_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    if snapshot_project(project) != snapshot:
        raise ValueError(
            "The delivered project differs from the tested source snapshot."
        )
