"""Measure development held-out adequacy under SPEC.md section 10.6."""

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine, docker_args, docker_cli, freeze_images
from phoenix_eval.outcome import Outcome
from phoenix_eval.provenance import worker_source_digest
from phoenix_eval.wire import decode_invocation, decode_result, encode_invocation
from tools.adequacy_support import (
    Edit,
    branches,
    classify,
    compiler_state,
    digest,
    sample,
)

REPO = Path(__file__).resolve().parents[1]
STATES = ("killed", "survived", "timed_out", "uncompilable", "unresolved", "equivalent")
BOOTSTRAP = """
import base64, json, pathlib, sys
request = json.load(sys.stdin)
code = pathlib.Path('/scratch/code')
for name, data in request.pop('code').items():
    path = code / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(data))
sys.path.insert(0, str(code))
from adequacy_support import driver
print(json.dumps(driver(request)))
"""


@dataclass(frozen=True)
class ProgramInput:
    name: str
    tier: str
    files: tuple[tuple[str, bytes], ...]
    cases: tuple[Invocation, ...]
    indices: tuple[int, ...]
    exclusions: dict[str, tuple[int, ...]]
    bindings: dict[str, str]


def hash_files(files: tuple[tuple[str, bytes], ...]) -> str:
    return digest(
        json.dumps(
            [(name, digest(data)) for name, data in sorted(files)], sort_keys=True
        ).encode()
    )


def load_program(repo: Path, workspace: Path, name: str) -> ProgramInput:
    # The corpus builder supplies these interfaces when its branch merges.
    helper = importlib.import_module("phoenix_eval.dev_corpus")

    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("Use a development program name.")
    corpus = repo / "corpus_dev"
    program = corpus / name
    if corpus.is_symlink() or (workspace / "dev_bin").is_symlink():
        raise ValueError("Corpus and binary directories must not be symbolic links.")
    if (
        program.is_symlink()
        or program.resolve().parent != (repo / "corpus_dev").resolve()
    ):
        raise ValueError("The program path must stay in corpus_dev.")
    if (program / "holdout").is_symlink():
        raise ValueError(
            "The development held-out directory must not be a symbolic link."
        )
    manifest = workspace / "dev_bin/manifest.json"
    entries = tuple(x for x in helper.read_manifest(manifest) if x.name == name)
    if {(x.compiler, x.level) for x in entries} != {
        (cc, level) for cc in ("gcc", "clang") for level in ("O0", "O2", "Os", "O3")
    } or len(entries) != 8:
        raise ValueError("A program needs all eight validated manifest entries.")
    validated = [
        (x, helper.load_validated_cases(repo / "corpus_dev", workspace, x))
        for x in entries
    ]
    exclusions = {binary.key: cases.excluded for binary, cases in validated}
    common = set(validated[0][1].indices)
    cases_by_index: dict[int, Invocation] = {}
    for _, valid in validated:
        common.intersection_update(valid.indices)
        for index, case in zip(valid.indices, valid.cases, strict=True):
            if index in cases_by_index and case != cases_by_index[index]:
                raise ValueError("The validation returned inconsistent case inputs.")
            cases_by_index[index] = case
    indices = tuple(sorted(common))
    if not indices:
        raise ValueError("There are no cases valid for all binaries.")
    files = helper._sources(program)
    paths = {
        "tools": repo / "tools.lock",
        "cases": program / "holdout/cases.jsonl",
        "excluded": program / "holdout/excluded.json",
        "meta": program / "meta.json",
    }
    bindings = {name: digest(path.read_bytes()) for name, path in paths.items()}
    fields = ("name", "tier", "compiler", "flags", "sha256", "category", "twin_valid")
    bindings["manifest"] = digest(
        json.dumps(
            [
                {field: getattr(entry, field) for field in fields}
                for entry in sorted(entries, key=lambda entry: entry.key)
            ],
            sort_keys=True,
        ).encode()
    )
    bindings["source"] = hash_files(files)
    bindings["tool_code"] = hash_files(
        tuple(
            (name, (repo / name).read_bytes())
            for name in sorted(
                {
                    "tools/adequacy.py",
                    "tools/adequacy_support.py",
                    "phoenix_eval/__init__.py",
                    *helper._VALIDATION_PATHS,
                }
            )
        )
    )
    tier = json.loads((program / "meta.json").read_text())["tier"]
    if {x.tier for x in entries} != {tier} or tier not in ("D0", "D1", "D2", "D3"):
        raise ValueError("The manifest and metadata tiers differ.")
    return ProgramInput(
        name,
        tier,
        files,
        tuple(cases_by_index[i] for i in indices),
        indices,
        exclusions,
        bindings,
    )


def thresholds(tier: str, coverage: dict[str, int], counts: dict[str, int]) -> bool:
    if tier not in ("D0", "D1", "D2", "D3", "T0", "T1", "T2", "T3"):
        raise ValueError("Unknown adequacy tier.")
    if (
        set(coverage) != {"covered", "total"}
        or any(
            type(x) is not int or x < 0 for x in (*coverage.values(), *counts.values())
        )
        or set(counts) != set(STATES)
        or coverage["covered"] > coverage["total"]
    ):
        raise ValueError("Invalid adequacy counts.")
    numerator = counts["killed"] + counts["timed_out"]
    denominator = sum(counts.values()) - counts["uncompilable"] - counts["equivalent"]
    large = tier in ("D3", "T3")
    return (
        coverage["total"] > 0
        and coverage["covered"] * 10 >= coverage["total"] * (7 if large else 9)
        and (large or (denominator > 0 and numerator * 10 >= denominator * 9))
    )


def counts_for(results: list[dict[str, Any]], equivalent: set[str]) -> dict[str, int]:
    counts = dict.fromkeys(STATES, 0)
    if len({row["id"] for row in results}) != len(results) or len(equivalent) > 20:
        raise ValueError("Duplicate mutants or excessive author triage.")
    for row in results:
        status = row["status"]
        if status not in STATES[:-1] or (
            row["id"] in equivalent and status != "survived"
        ):
            raise ValueError("Invalid mutant classification.")
        counts["equivalent" if row["id"] in equivalent else status] += 1
    if equivalent - {row["id"] for row in results}:
        raise ValueError("The triage names an unsampled mutant.")
    return counts


def verify_observations(evidence: dict[str, Any], case_count: int) -> None:
    baseline = evidence["baseline"]
    if len(baseline) != case_count or case_count == 0:
        raise ValueError("The original observations are incomplete.")
    originals = [decode_result(json.dumps(x["result"])) for x in baseline]
    if any(not isinstance(x, Outcome) for x in originals) or any(
        type(x["runtime_ns"]) is not int or x["runtime_ns"] <= 0 for x in baseline
    ):
        raise ValueError("The original observations failed or lack runtimes.")
    for row in evidence["results"]:
        status = compiler_state(
            row["compiler_returncode"], row.get("compiler_stderr", "")
        )
        if row["compiler_returncode"]:
            if row["cases"] or row["status"] != status:
                raise ValueError("The mutant status contradicts its compiler result.")
            continue
        for index, observation in enumerate(row["cases"]):
            if (
                index >= case_count
                or observation["case"] != index
                or observation["limit_ns"] != baseline[index]["runtime_ns"] * 10
            ):
                raise ValueError("The case index or time limit changed.")
            original = originals[index]
            assert isinstance(original, Outcome)
            state = classify(original, decode_result(json.dumps(observation["result"])))
            if state in ("killed", "timed_out"):
                status = state
                if index != len(row["cases"]) - 1:
                    raise ValueError("A mutant has cases after its kill witness.")
            elif state == "unresolved":
                status = state
        if status in ("survived", "unresolved") and len(row["cases"]) != case_count:
            raise ValueError("A survivor has incomplete case observations.")
        if row["status"] != status:
            raise ValueError("The mutant status differs from its observations.")


def run_container(request: dict[str, Any], directory: Path) -> dict[str, Any]:
    images = freeze_images((Engine.ROSETTA,), worker_source_digest(REPO))
    image = subprocess.run(
        (
            *docker_cli(),
            "image",
            "inspect",
            images["amd64"],
            "--format",
            "{{.Architecture}} {{.Id}}",
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.split()
    if (
        len(image) != 2
        or image[0] != "amd64"
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", image[1])
        or image[1] != images["amd64"]
    ):
        raise ValueError("The worker image has the wrong architecture or ID.")
    request["image"] = image[1]
    request["code"] = {
        "tools.lock": b64encode((REPO / "tools.lock").read_bytes()).decode(),
        "adequacy_support.py": b64encode(
            (REPO / "tools/adequacy_support.py").read_bytes()
        ).decode(),
        **{
            f"phoenix_eval/{path.name}": b64encode(path.read_bytes()).decode()
            for path in sorted((REPO / "phoenix_eval").glob("*.py"))
        },
    }
    payload = json.dumps(request).encode()
    (directory / "request.json").write_bytes(payload)
    name = f"phoenix-adequacy-{uuid4().hex}"
    args = docker_args(Engine.ROSETTA, name, image[1])
    try:
        with (
            (directory / "response.json").open("wb") as stdout,
            (directory / "diagnostics.txt").open("wb") as stderr,
        ):
            completed = subprocess.run(
                (
                    *args[:-1],
                    "--entrypoint=/usr/bin/python3",
                    args[-1],
                    "-B",
                    "-c",
                    BOOTSTRAP,
                ),
                input=payload,
                stdout=stdout,
                stderr=stderr,
                timeout=172800,
            )
        if completed.returncode:
            raise RuntimeError((directory / "diagnostics.txt").read_text()[-4096:])
    finally:
        subprocess.run(
            (*docker_cli(), "rm", "-f", name), capture_output=True, timeout=15
        )
    return json.loads((directory / "response.json").read_bytes())  # type: ignore[no-any-return]


def triaged_ids(
    report: dict[str, Any],
    directory: Path,
    evidence: dict[str, Any],
    cases: tuple[Invocation, ...],
) -> set[str]:
    triage = report.get("triage", [])
    if not isinstance(triage, list) or len(triage) > 20:
        raise ValueError("The author can triage at most 20 survivors.")
    ids = set()
    heldout = {encode_invocation(x) for x in cases}
    for item in triage:
        if not item.get("author", "").strip() or not item.get("reason", "").strip():
            raise ValueError("Author triage needs an author and a written reason.")
        path = directory / item["evidence"]
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("Triage evidence must stay in the run directory.")
        data = path.read_bytes()
        if digest(data) != item["sha256"]:
            raise ValueError("The triage evidence hash changed.")
        record = json.loads(data)
        extra = record["cases"]
        encoded = {encode_invocation(decode_invocation(json.dumps(x))) for x in extra}
        if (
            record["bindings"] != report["bindings"]
            or record["mutant_id"] != item["id"]
            or not re.fullmatch(r"[a-f0-9]{64}", record["generator_sha256"])
            or type(record["seed"]) is not int
            or len(encoded - heldout) < 1000
            or len(extra) != len(record["original"])
            or len(extra) != len(record["mutant"])
        ):
            raise ValueError(
                "Triage needs 1000 additional generated cases and current bindings."
            )
        for original, mutant in zip(record["original"], record["mutant"], strict=True):
            outcome = decode_result(json.dumps(original))
            if (
                not isinstance(outcome, Outcome)
                or classify(outcome, decode_result(json.dumps(mutant))) != "survived"
            ):
                raise ValueError("Additional cases did not preserve the survivor.")
        if item["id"] in ids:
            raise ValueError("The author triaged one mutant more than once.")
        ids.add(item["id"])
    counts_for(evidence["results"], ids)
    return ids


def make_report(
    program: ProgramInput,
    seed: int,
    run_id: str,
    directory: Path,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    counts = counts_for(evidence["results"], set())
    candidates = {x["id"]: x for x in evidence["candidates"]}
    return {
        "version": 1,
        "program": program.name,
        "tier": program.tier,
        "seed": seed,
        "run_id": run_id,
        "bindings": program.bindings,
        "artifacts": {
            name: digest((directory / name).read_bytes())
            for name in ("request.json", "response.json", "diagnostics.txt")
        },
        "valid_indices": program.indices,
        "excluded": program.exclusions,
        "mutator": evidence["mutator"],
        "tools": evidence["tools"],
        "coverage": evidence["branches"],
        "counts": counts,
        "mutation_score": {
            "numerator": counts["killed"] + counts["timed_out"],
            "denominator": sum(counts.values()) - counts["uncompilable"],
        },
        "survivors": [
            {**candidates[x["id"]], "status": x["status"]}
            for x in evidence["results"]
            if x["status"] in ("survived", "unresolved")
        ],
        "triage": [],
        "passed": thresholds(program.tier, evidence["branches"], counts),
    }


def verify_report(
    program: ProgramInput, report: dict[str, Any], workspace: Path
) -> bool:
    if (
        report.get("version") != 1
        or report.get("program") != program.name
        or report.get("tier") != program.tier
        or report.get("bindings") != program.bindings
        or report.get("valid_indices") != list(program.indices)
        or report.get("excluded") != {k: list(v) for k, v in program.exclusions.items()}
        or not re.fullmatch(r"[a-f0-9]{32}", report.get("run_id", ""))
    ):
        raise ValueError("The adequacy evidence is stale or incomplete.")
    directory = workspace / "adequacy_runs" / report["run_id"]
    if (
        directory.is_symlink()
        or directory.resolve().parent != (workspace / "adequacy_runs").resolve()
    ):
        raise ValueError("The run path must stay in adequacy_runs.")
    if set(report["artifacts"]) != {"request.json", "response.json", "diagnostics.txt"}:
        raise ValueError("The report omits required evidence files.")
    for name, expected in report["artifacts"].items():
        path = directory / name
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError("The adequacy artifact hash changed.")
    evidence = json.loads((directory / "response.json").read_bytes())
    request = json.loads((directory / "request.json").read_bytes())
    edits = tuple(
        Edit(**{k: v for k, v in x.items() if k != "id"})
        for x in evidence["candidates"]
    )
    if (
        request["seed"] != report["seed"]
        or request["bindings"] != program.bindings
        or request["files"] != {k: b64encode(v).decode() for k, v in program.files}
        or request["cases"] != [json.loads(encode_invocation(x)) for x in program.cases]
        or any(
            edit.id != raw["id"]
            for edit, raw in zip(edits, evidence["candidates"], strict=True)
        )
        or evidence["selected"] != [x.id for x in sample(edits, report["seed"])]
        or evidence["selected"] != [x["id"] for x in evidence["results"]]
        or evidence["branches"] != branches(list(evidence["gcov"].values()))
        or report["coverage"] != evidence["branches"]
    ):
        raise ValueError("The selected mutants or coverage evidence changed.")
    verify_observations(evidence, len(program.cases))
    equivalents = triaged_ids(report, directory, evidence, program.cases)
    counts = counts_for(evidence["results"], equivalents)
    score = {
        "numerator": counts["killed"] + counts["timed_out"],
        "denominator": sum(counts.values())
        - counts["uncompilable"]
        - counts["equivalent"],
    }
    if (
        counts != report["counts"]
        or report["mutation_score"] != score
        or report["tools"] != evidence["tools"]
        or report["mutator"] != evidence["mutator"]
    ):
        raise ValueError("The report counts differ from the mutant evidence.")
    return thresholds(program.tier, evidence["branches"], counts)


def summary(repo: Path, workspace: Path) -> int:
    helper = importlib.import_module("phoenix_eval.dev_corpus")

    corpus = repo / "corpus_dev"
    if corpus.is_symlink() or (workspace / "dev_bin").is_symlink():
        raise ValueError("Corpus and binary directories must not be symbolic links.")
    names = {x.name for x in helper.read_manifest(workspace / "dev_bin/manifest.json")}
    names.update(x.name for x in corpus.iterdir() if x.is_dir())
    passed = 0
    for name in sorted(names):
        try:
            program = load_program(repo, workspace, name)
            report = json.loads((corpus / name / "adequacy.json").read_text())
            ok = verify_report(program, report, workspace)
            passed += ok
            print(
                f"{name}: {'PASS' if ok else 'FAIL'}; "
                f"branches {report['coverage']}; mutants {report['counts']}"
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"{name}: FAIL; {exc}")
    print(f"{passed}/{len(names)} programs meet the adequacy thresholds. Required: 22.")
    return 0 if passed == len(names) == 22 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", nargs="?")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    if args.summary == bool(args.program):
        parser.error("Select a program or --summary.")
    try:
        workspace = Path(os.environ["PHOENIX_ROOT"]).resolve()
        if not REPO.resolve().is_relative_to(workspace):
            raise ValueError(
                "Keep the repository and adequacy data under PHOENIX_ROOT."
            )
        if args.summary:
            return summary(REPO, workspace)
        program = load_program(REPO, workspace, args.program)
        run_id = uuid4().hex
        directory = workspace / "adequacy_runs" / run_id
        directory.mkdir(parents=True)
        evidence = run_container(
            {
                "seed": args.seed,
                "bindings": program.bindings,
                "files": {k: b64encode(v).decode() for k, v in program.files},
                "cases": [json.loads(encode_invocation(x)) for x in program.cases],
            },
            directory,
        )
        if load_program(REPO, workspace, program.name) != program:
            raise ValueError("The program changed during adequacy measurement.")
        report = make_report(program, args.seed, run_id, directory, evidence)
        path = REPO / "corpus_dev" / program.name / "adequacy.json"
        temporary = directory / "adequacy.json"
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        path.write_bytes(temporary.read_bytes())
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        ImportError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"adequacy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
