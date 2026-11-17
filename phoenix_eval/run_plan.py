"""Freeze tool identities and select accepted development binaries."""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from phoenix_eval.dev_corpus import (
    DevBinary,
    ValidatedCases,
    corpus_hash,
    heldout_hash,
    read_manifest,
)
from phoenix_eval.docker import Engine, freeze_images
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import (
    CHECKER_SOURCE_LABEL,
    CHECKOUT,
    checker_source_digest,
    evaluator_build,
    lifting_tool_identity,
    pinned_lifting_tools,
    pipeline_source_digest,
)
from phoenix_eval.run_records import Selection, digest, read_json


def model_identity(root: Path = CHECKOUT) -> dict[str, object]:
    return {"config_sha256": digest((root / "phoenix/config.py").read_bytes())}


def _configuration(workspace: Path) -> dict[str, object]:
    status = subprocess.run(
        (
            "git",
            "-C",
            str(CHECKOUT),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "phoenix",
            "phoenix_eval",
        ),
        capture_output=True,
        check=True,
        text=True,
        timeout=15,
    )
    if status.stdout:
        raise ValueError("Commit pipeline and evaluator changes before a loop.")
    runtime = verify_runtime("apple-silicon")
    build = evaluator_build()
    checker = checker_source_digest()
    ghidra, java = pinned_lifting_tools(workspace)
    return {
        "revision": build.commit,
        "configuration_identity": model_identity(),
        "worker_source_sha256": build.worker_source_sha256,
        "checker_source_sha256": checker,
        "pipeline_source_sha256": pipeline_source_digest(),
        "worker_images": freeze_images(
            (Engine.ROSETTA, Engine.ARM64), build.worker_source_sha256
        ),
        "checker_images": freeze_images(
            (Engine.ROSETTA, Engine.ARM64),
            checker,
            repository="phoenix-c-integrity",
            source_label=CHECKER_SOURCE_LABEL,
        ),
        "lifting_tool_identity": lifting_tool_identity(ghidra, java),
        "pipeline_settings": {
            "seed": 0x70686F656E6978,
            "repair_limit": 20,
            "strongest_repair": False,
            "budget_run": 200_000_000_000,
            "ghidra": str(ghidra),
            "java_home": str(java),
        },
        "runtime": asdict(runtime),
    }


def quick_set(binaries: tuple[DevBinary, ...]) -> tuple[DevBinary, ...]:
    return tuple(
        binary
        for tier in ("D0", "D1")
        for level in ("O0", "O2", "Os")
        for compiler in ("gcc", "clang")
        for binary in sorted(
            (
                item
                for item in binaries
                if (item.tier, item.level, item.compiler) == (tier, level, compiler)
            ),
            key=lambda item: item.sha256,
        )[:2]
    )


def _selection(
    workspace: Path, selection: Selection
) -> tuple[tuple[DevBinary, ...], str, str]:
    corpus = CHECKOUT / "corpus_dev"
    binaries = read_manifest(workspace / "dev_bin/manifest.json")
    acceptance = corpus / "accepted.json"
    accepted = read_json(acceptance) if acceptance.exists() else None
    binary_hash = corpus_hash(workspace, binaries)
    case_hash = heldout_hash(corpus, workspace, binaries)
    if accepted is None and not selection.probe:
        raise ValueError("Accept the current corpus before an evaluation.")
    if accepted is not None and (
        accepted.get("corpus_hash") != binary_hash
        or accepted.get("heldout_hash") != case_hash
    ):
        raise ValueError("The corpus differs from its acceptance record.")
    if selection.quick:
        expected = quick_set(binaries)
        lines = (corpus / "quick.txt").read_text().splitlines()
        wanted = [
            f"{item.name} {item.compiler} {item.level} {item.sha256}"
            for item in expected
        ]
        if lines != ["# version 1", *wanted] or len(expected) != 24:
            raise ValueError("The quick set differs from version 1.")
        binaries = expected
    chosen = tuple(
        item
        for item in binaries
        if item.tier in selection.tiers and item.level in selection.levels
    )
    if not chosen:
        raise ValueError("The selected cells contain no binaries.")
    return chosen, binary_hash, case_hash


def case_identity(
    corpus: Path, binary: DevBinary, valid: ValidatedCases
) -> tuple[int, str]:
    return len(valid.cases), digest(
        json.dumps(
            [
                valid.indices,
                digest((corpus / binary.name / "holdout/cases.jsonl").read_bytes()),
            ]
        ).encode()
    )


def adequacy_snapshot(
    corpus: Path, binaries: tuple[DevBinary, ...], probe: bool
) -> dict[str, object]:
    result: dict[str, object] = {}
    for name in sorted({binary.name for binary in binaries}):
        path = corpus / name / "adequacy.json"
        if not path.exists() and probe:
            result[name] = None
            continue
        report = read_json(path)
        coverage = report.get("coverage")
        if (
            not isinstance(coverage, dict)
            or any(type(coverage.get(key)) is not int for key in ("covered", "total"))
            or not 0 <= coverage["covered"] <= coverage["total"]
            or coverage["total"] < 1
        ):
            raise ValueError("The source branch coverage is invalid.")
        result[name] = {
            "coverage": coverage,
            "report_sha256": digest(path.read_bytes()),
        }
    return result
