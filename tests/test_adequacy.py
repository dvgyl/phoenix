"""Check adequacy evidence, thresholds, and a synthetic Linux source proof."""

import json
import os
import subprocess
import sys
from base64 import b64encode
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from phoenix_eval.case import CaseFailure, FailureKind, Invocation
from phoenix_eval.outcome import (
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
)
from phoenix_eval.wire import encode_invocation, encode_result
from tools import adequacy as tool
from tools.adequacy_support import (
    Edit,
    apply,
    branches,
    classify,
    compiler_state,
    digest,
    sample,
)

ORIGINAL = Outcome(b"ok\n", b"", Exited(0), TreeSnapshot())
SOURCE = b"1234567890"


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    directory = Path(os.environ["PHOENIX_ROOT"]) / "tmp"
    directory.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="adequacy-test-", dir=directory) as name:
        yield Path(name)


def counts(**changes: int) -> dict[str, int]:
    return {**dict.fromkeys(tool.STATES, 0), **changes}


@pytest.mark.parametrize(
    "changed",
    [
        replace(ORIGINAL, stdout=b"ok"),
        replace(ORIGINAL, stdout=b"ok\r\n"),
        replace(ORIGINAL, stderr=b"\0"),
        replace(ORIGINAL, termination=Exited(1)),
        replace(ORIGINAL, termination=Signaled(15)),
        replace(ORIGINAL, tree=TreeSnapshot(0o700)),
        replace(
            ORIGINAL,
            tree=TreeSnapshot(entries=(TreeEntry("new", EntryKind.DIRECTORY, 0o755),)),
        ),
    ],
)
def test_each_observable_difference_kills(changed: Outcome) -> None:
    assert classify(ORIGINAL, changed) == "killed"
    assert classify(ORIGINAL, ORIGINAL) == "survived"


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "renamed"),
        ("mode", 0o600),
        ("data", b"changed"),
        ("kind", EntryKind.SYMLINK),
    ],
)
def test_tree_comparison_keeps_paths_kinds_modes_and_bytes(
    field: str, value: Any
) -> None:
    entry = TreeEntry("output", EntryKind.FILE, 0o777, b"data")
    baseline = replace(ORIGINAL, tree=TreeSnapshot(entries=(entry,)))
    mutant = replace(
        ORIGINAL, tree=TreeSnapshot(entries=(replace(entry, **{field: value}),))
    )
    assert classify(baseline, mutant) == "killed"


@pytest.mark.parametrize("kind", list(FailureKind))
def test_timeouts_kill_and_other_worker_failures_remain_unresolved(
    kind: FailureKind,
) -> None:
    assert classify(ORIGINAL, CaseFailure(kind, "test")) == (
        "timed_out" if kind is FailureKind.TIMEOUT else "unresolved"
    )


@pytest.mark.parametrize("tier", ["D0", "D1", "D2", "T0", "T1", "T2"])
def test_exact_ninety_percent_boundary(tier: str) -> None:
    assert tool.thresholds(
        tier, {"covered": 90, "total": 100}, counts(killed=90, survived=10)
    )
    assert not tool.thresholds(
        tier, {"covered": 899, "total": 1000}, counts(killed=90, survived=10)
    )
    assert not tool.thresholds(
        tier, {"covered": 90, "total": 100}, counts(killed=899, survived=101)
    )
    assert tool.thresholds(
        tier,
        {"covered": 9, "total": 10},
        counts(killed=8, timed_out=1, unresolved=1, uncompilable=20, equivalent=2),
    )
    assert not tool.thresholds(
        tier,
        {"covered": 9, "total": 10},
        counts(killed=8, unresolved=2, uncompilable=20),
    )


@pytest.mark.parametrize("tier", ["D3", "T3"])
def test_large_programs_have_seventy_percent_branch_gate_only(tier: str) -> None:
    assert tool.thresholds(tier, {"covered": 70, "total": 100}, counts(survived=10))
    assert not tool.thresholds(tier, {"covered": 699, "total": 1000}, counts(killed=10))


def test_empty_denominators_and_bad_counts_do_not_pass() -> None:
    assert not tool.thresholds("D0", {"covered": 0, "total": 0}, counts(killed=1))
    assert not tool.thresholds(
        "D0", {"covered": 9, "total": 10}, counts(uncompilable=1)
    )
    with pytest.raises(ValueError):
        tool.thresholds("unknown", {"covered": 1, "total": 1}, counts())
    with pytest.raises(ValueError):
        tool.thresholds("D0", {"covered": 2, "total": 1}, counts(killed=1))


def test_gcov_counts_never_executed_fallthrough_and_throw_branches() -> None:
    text = """branch  0 taken 0 (fallthrough)
branch  1 taken 104
branch  2 never executed
branch  3 taken 1 (throw)
branch  4 taken 0
call    0 returned 9
"""
    assert branches([text, "branch 0 taken 1\n"]) == {"covered": 3, "total": 6}


def test_sampling_is_uniform_over_candidates_and_independent_of_input_order() -> None:
    candidates = tuple(
        Edit("src/main.c", i, i + 1, "1", "0", family, 1, i + 1)
        for i in range(600)
        for family in (str(i % 9),)
    )
    chosen = sample(candidates, 1234)
    assert len(chosen) == 300
    assert chosen == sample(tuple(reversed(candidates)), 1234)
    assert chosen != sample(candidates, 1235)
    assert {x.operator for x in chosen} == {str(i) for i in range(9)}
    assert set(sample(candidates[:5], 1)) == set(candidates[:5])
    assert len({x.id for x in chosen}) == 300


def test_exact_edits_use_byte_offsets_and_reject_stale_source() -> None:
    edit = Edit("src/main.c", 2, 3, "+", "*", "arithmetic", 1, 3)
    assert apply({"src/main.c": b"\xc3\xa9+1;"}, edit)["src/main.c"] == b"\xc3\xa9*1;"
    with pytest.raises(ValueError, match="source bytes"):
        apply({"src/main.c": b"\xc3\xa9-1;"}, edit)


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[tool.ProgramInput, dict[str, Any], Path]:
    run_id = "a" * 32
    directory = tmp_path / "adequacy_runs" / run_id
    directory.mkdir(parents=True)
    program = tool.ProgramInput(
        "fixture",
        "D0",
        (("src/main.c", SOURCE),),
        (Invocation(),),
        (4,),
        {"gcc-O0": (0,)},
        {"source": "test"},
    )
    candidates = tuple(
        Edit("src/main.c", i, i + 1, chr(SOURCE[i]), "0", "integer_zero", 1, i + 1)
        for i in range(10)
    )
    ordered = sample(candidates, 8)
    baseline = {"result": json.loads(encode_result(ORIGINAL)), "runtime_ns": 100}
    rows = [
        {
            "id": edit.id,
            "status": "killed" if i < 9 else "survived",
            "compiler_returncode": 0,
            "cases": [
                {
                    "case": 0,
                    "limit_ns": 1000,
                    "result": json.loads(
                        encode_result(
                            replace(ORIGINAL, stdout=b"wrong") if i < 9 else ORIGINAL
                        )
                    ),
                }
            ],
        }
        for i, edit in enumerate(ordered)
    ]
    record = {
        "candidates": [{**asdict(x), "id": x.id} for x in candidates],
        "selected": [x.id for x in ordered],
        "baseline": [baseline],
        "results": rows,
        "gcov": {"main.c.gcov": "branch 0 taken 1\n"},
        "branches": {"covered": 1, "total": 1},
        "mutator": "fixture",
        "tools": {},
    }
    request = {
        "seed": 8,
        "bindings": program.bindings,
        "files": {"src/main.c": b64encode(SOURCE).decode()},
        "cases": [json.loads(encode_invocation(Invocation()))],
    }
    (directory / "request.json").write_text(json.dumps(request))
    (directory / "response.json").write_text(json.dumps(record))
    (directory / "diagnostics.txt").write_text("")
    report = json.loads(
        json.dumps(tool.make_report(program, 8, run_id, directory, record))
    )
    return program, report, tmp_path


def test_report_replays_counts_and_exact_threshold(
    evidence: tuple[Any, Any, Path],
) -> None:
    program, report, workspace = evidence
    assert tool.verify_report(program, report, workspace)
    assert report["counts"] == counts(killed=9, survived=1)
    assert report["survivors"][0]["file"] == "src/main.c"
    assert report["survivors"][0]["line"] == 1
    assert report["mutation_score"] == {"numerator": 9, "denominator": 10}


@pytest.mark.parametrize(
    "binding", ["source", "cases", "tools", "tool_code", "excluded", "manifest"]
)
def test_stale_bindings_fail(evidence: tuple[Any, Any, Path], binding: str) -> None:
    program, report, workspace = evidence
    program = replace(program, bindings={**program.bindings, binding: "changed"})
    with pytest.raises(ValueError, match="stale"):
        tool.verify_report(program, report, workspace)


def test_changed_artifact_fails(evidence: tuple[Any, Any, Path]) -> None:
    program, report, workspace = evidence
    path = workspace / "adequacy_runs" / report["run_id"] / "response.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash changed"):
        tool.verify_report(program, report, workspace)


def test_worker_transport_includes_the_pinned_runtime_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "phoenix_eval").mkdir()
    (repo / "tools/adequacy_support.py").write_text("fixture")
    (repo / "phoenix_eval/case.py").write_text("fixture")
    pins = b'qemu_cpu = "qemu64-v1"\nglibc_tunables = "fixture"\n'
    (repo / "tools.lock").write_bytes(pins)
    monkeypatch.setattr(tool, "REPO", repo)
    monkeypatch.setattr(
        tool, "worker_source_digest", lambda *_: "b" * 64, raising=False
    )
    requests = []

    def run(
        command: tuple[str, ...], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if "inspect" in command:
            fmt = (
                command[command.index("--format") + 1]
                if "--format" in command
                else next(x for x in command if x.startswith("--format="))
            )
            metadata = (
                "amd64 sha256:" + "a" * 64
                if ".Architecture" in fmt
                else "sha256:" + "a" * 64 + " " + "b" * 64
            )
            return subprocess.CompletedProcess(command, 0, metadata + "\n", "")
        if "input" in kwargs:
            requests.append(json.loads(kwargs["input"]))
            kwargs["stdout"].write(b"{}")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    directory = tmp_path / "run"
    directory.mkdir()
    assert tool.run_container({}, directory) == {}
    assert requests[0]["code"]["tools.lock"] == b64encode(pins).decode()


def test_a_compiler_signal_is_not_an_uncompilable_mutant(
    evidence: tuple[Any, Any, Path],
) -> None:
    _, report, workspace = evidence
    record = json.loads(
        (workspace / "adequacy_runs" / report["run_id"] / "response.json").read_text()
    )
    row = record["results"][0]
    row.update(
        compiler_returncode=-9,
        compiler_stderr="killed",
        status="uncompilable",
        cases=[],
    )
    with pytest.raises(ValueError, match="compiler|status"):
        tool.verify_observations(record, 1)


@pytest.mark.parametrize(
    "returncode,diagnostic,state",
    [
        (-9, "killed", "unresolved"),
        (1, "gcc: fatal error: Killed signal terminated program cc1", "unresolved"),
        (1, "error: invalid operands", "uncompilable"),
        (0, "warning: source text contains internal compiler error", "survived"),
    ],
)
def test_compiler_infrastructure_failures_stay_in_the_denominator(
    returncode: int, diagnostic: str, state: str
) -> None:
    assert compiler_state(returncode, diagnostic) == state


@pytest.mark.parametrize("change", ["status", "timeout", "incomplete"])
def test_observation_checks_reject_false_kills_or_incomplete_survivors(
    evidence: tuple[Any, Any, Path],
    change: str,
) -> None:
    _, report, workspace = evidence
    record = json.loads(
        (workspace / "adequacy_runs" / report["run_id"] / "response.json").read_text()
    )
    row = record["results"][-1]
    if change == "status":
        row["status"] = "killed"
    elif change == "timeout":
        row["cases"][0]["limit_ns"] = 999
    else:
        row["cases"] = []
    with pytest.raises(ValueError):
        tool.verify_observations(record, 1)


def install_helper(monkeypatch: pytest.MonkeyPatch, **attributes: Any) -> ModuleType:
    module = ModuleType("phoenix_eval.dev_corpus")
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def test_validation_helper_receives_manifest_and_all_binary_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "fixture"
    program = tmp_path / "corpus_dev" / name
    (program / "holdout").mkdir(parents=True)
    (program / "meta.json").write_text('{"tier":"D0"}')
    for relative in (
        "tools.lock",
        "tools/adequacy.py",
        "tools/adequacy_support.py",
        "containers/launch-target.c",
        "containers/Dockerfile",
        "phoenix_eval/__init__.py",
        "dev_bin/manifest.json",
        "corpus_dev/fixture/holdout/cases.jsonl",
        "corpus_dev/fixture/holdout/excluded.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    entries = tuple(
        SimpleNamespace(
            name=name,
            tier="D0",
            compiler=cc,
            level=level,
            key=f"{cc}-{level}",
            flags=("-std=c11", f"-{level}", "-lm"),
            sha256="a" * 64,
            category="fixture",
            twin_valid=True,
        )
        for cc in ("gcc", "clang")
        for level in ("O0", "O2", "Os", "O3")
    )
    observed = []

    def validate(corpus: Path, workspace: Path, binary: Any) -> Any:
        assert corpus == tmp_path / "corpus_dev"
        assert workspace == tmp_path
        observed.append(binary.key)
        selected = (1, 2) if binary.key == "gcc-O0" else (0, 2)
        return SimpleNamespace(
            indices=selected,
            cases=tuple(Invocation((str(i),)) for i in selected),
            excluded=tuple(i for i in range(3) if i not in selected),
        )

    helper = install_helper(
        monkeypatch,
        read_manifest=lambda path: entries,
        load_validated_cases=validate,
        _sources=lambda path: (("src/main.c", b"int main(void){return 0;}"),),
        _VALIDATION_PATHS=(
            "tools.lock",
            "containers/launch-target.c",
            "containers/Dockerfile",
        ),
    )
    loaded = tool.load_program(tmp_path, tmp_path, name)
    assert loaded.indices == (2,)
    assert loaded.cases == (Invocation(("2",)),)
    assert len(observed) == 8
    (tmp_path / "dev_bin/manifest.json").write_text("Another program changed.")
    (tmp_path / "phoenix_eval/unrelated_score.py").write_text("Unrelated scoring code.")
    assert tool.load_program(tmp_path, tmp_path, name).bindings == loaded.bindings
    (tmp_path / "containers/launch-target.c").write_text("Changed runtime source.")
    assert (
        tool.load_program(tmp_path, tmp_path, name).bindings["tool_code"]
        != loaded.bindings["tool_code"]
    )

    def stale(*args: Any) -> Any:
        raise ValueError("The held-out validation is stale.")

    monkeypatch.setattr(helper, "load_validated_cases", stale)
    with pytest.raises(ValueError, match="stale"):
        tool.load_program(tmp_path, tmp_path, name)


@pytest.mark.parametrize("fault", ["none", "missing", "below", "absent_manifest_entry"])
def test_summary_requires_twenty_two_current_programs(
    evidence: tuple[Any, Any, Path],
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    program, report, workspace = evidence
    if fault == "below":
        directory = workspace / "adequacy_runs" / report["run_id"]
        record = json.loads((directory / "response.json").read_text())
        record["gcov"] = {"main.c.gcov": "branch 0 taken 1\nbranch 1 taken 0\n"}
        record["branches"] = {"covered": 1, "total": 2}
        (directory / "response.json").write_text(json.dumps(record))
        report = json.loads(
            json.dumps(
                tool.make_report(program, 8, report["run_id"], directory, record)
            )
        )
    names = [f"program{i}" for i in range(22)]
    install_helper(
        monkeypatch,
        read_manifest=lambda path: tuple(SimpleNamespace(name=name) for name in names),
    )
    monkeypatch.setattr(
        tool, "load_program", lambda repo, root, name: replace(program, name=name)
    )
    for i, name in enumerate(names):
        path = workspace / "corpus_dev" / name
        path.mkdir(parents=True)
        if fault == "missing" and i == 0:
            continue
        record = {**report, "program": name}
        (path / "adequacy.json").write_text(json.dumps(record))
    if fault == "absent_manifest_entry":
        (workspace / "corpus_dev/extra").mkdir()
    assert tool.summary(workspace, workspace) == (0 if fault == "none" else 1)


def test_author_triage_needs_additional_cases_and_reason(
    evidence: tuple[Any, Any, Path],
) -> None:
    program, report, workspace = evidence
    directory = workspace / "adequacy_runs" / report["run_id"]
    record = json.loads((directory / "response.json").read_text())
    survivor = record["results"][-1]["id"]
    outcome = json.loads(encode_result(ORIGINAL))
    extra = [json.loads(encode_invocation(Invocation((str(i),)))) for i in range(1000)]
    data = {
        "bindings": program.bindings,
        "mutant_id": survivor,
        "seed": 9,
        "generator_sha256": "f" * 64,
        "cases": extra,
        "original": [outcome] * 1000,
        "mutant": [outcome] * 1000,
    }
    path = directory / "author.json"
    path.write_text(json.dumps(data))
    report["triage"] = [
        {
            "id": survivor,
            "author": "Synthetic author",
            "reason": "The unused function has no call site.",
            "evidence": path.name,
            "sha256": digest(path.read_bytes()),
        }
    ]
    assert tool.triaged_ids(report, directory, record, program.cases) == {survivor}
    report["triage"][0]["reason"] = ""
    with pytest.raises(ValueError, match="written reason"):
        tool.triaged_ids(report, directory, record, program.cases)
    report["triage"][0]["reason"] = "test"
    data["cases"] = extra[:999]
    path.write_text(json.dumps(data))
    report["triage"][0]["sha256"] = digest(path.read_bytes())
    with pytest.raises(ValueError, match="1000"):
        tool.triaged_ids(report, directory, record, program.cases)
    report["triage"] *= 21
    with pytest.raises(ValueError, match="20"):
        tool.triaged_ids(report, directory, record, program.cases)


SYNTHETIC = b"""#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include "inline.h"
#define STEP(n) ((n) + 1)
static int dormant(void) { return 17; }
static int negative(void) { return -3; }
static int characters(void) { int x = 'a'; x++; --x; return x; }
int main(int argc, char **argv) {
 int n = argc > 1 ? atoi(argv[1]) : 0;
 int i = 0; while (i < 2) i = STEP(i);
 int x = n + 3; x -= 1; x = x * 2; x = x / 2; x = x % 7;
 if ((n >= 0 && n <= 3) || n == 9) puts("yes"); else puts("no");
 switch (n) { case 0: puts("zero"); break; case 1: puts("one"); break; default: break; }
 FILE *f = fopen("result", "w"); if (!f) return 2;
 fprintf(f, "%d:%d\\n", x, i); fclose(f); chmod("result", 0600);
 mkdir("created", 0700);
 return n != 7 ? 0 : 1;
}
"""


def test_linux_container_proof(tmp_path: Path) -> None:
    if os.environ.get("PHOENIX_ADEQUACY_PROOF") != "1":
        pytest.skip("Set PHOENIX_ADEQUACY_PROOF=1 to run the Linux proof.")
    request = {
        "seed": 42,
        "bindings": {"fixture": "synthetic"},
        "files": {
            "src/main.c": b64encode(SYNTHETIC).decode(),
            "include/inline.h": b64encode(
                b"static int header_only(void){return 23;}\n"
            ).decode(),
        },
        "cases": [
            json.loads(encode_invocation(Invocation((str(n),))))
            for n in (-1, 0, 1, 3, 7, 9)
        ],
    }
    workspace = Path(os.environ["PHOENIX_ROOT"])
    directory = workspace / "adequacy_runs" / uuid4().hex
    directory.mkdir(parents=True)
    result = tool.run_container(request, directory)
    (tmp_path / "proof-location.txt").write_text(str(directory))
    candidates = {x["id"]: x for x in result["candidates"]}
    rows = {x["id"]: x for x in result["results"]}
    assert {x["operator"] for x in candidates.values()} == {
        "arithmetic",
        "relational",
        "logical",
        "integer_increment",
        "integer_zero",
        "condition_negate",
        "call_delete",
        "return_zero",
        "return_one",
    }
    assert len(result["selected"]) == len(candidates) < 300
    assert {x["status"] for x in rows.values()} >= {
        "killed",
        "survived",
        "timed_out",
        "uncompilable",
    }
    assert result["tools"]["mull_attempt"]["returncode"] != 0
    assert "18.1.3" in result["tools"]["clang"]
    assert any(x["file"] == "include/inline.h" for x in candidates.values())
    assert any(
        x["before"] == "-3" and x["after"] == "(-3 + 1)" for x in candidates.values()
    )
    assert any(x["before"] == "+" and x["line"] == 5 for x in candidates.values())
    assert any(
        x["before"] == "'a'" and x["after"] == "('a' + 1)" for x in candidates.values()
    )
    assert {
        x["before"] for x in candidates.values() if x["operator"] == "arithmetic"
    } >= {"++", "--"}
    for before in ('chmod("result", 0600)', 'mkdir("created", 0700)'):
        row = next(
            rows[identity]
            for identity, candidate in candidates.items()
            if candidate["operator"] == "call_delete" and candidate["before"] == before
        )
        assert row["status"] == "killed"
        assert (
            row["cases"][0]["result"]["stdout"]
            == result["baseline"][0]["result"]["stdout"]
        )
        assert (
            row["cases"][0]["result"]["tree"] != result["baseline"][0]["result"]["tree"]
        )
    survivors = [
        candidates[x["id"]] for x in rows.values() if x["status"] == "survived"
    ]
    assert any(
        x["before"] == "17" and x["operator"] == "return_zero" for x in survivors
    )
    assert any(x["file"] == "include/inline.h" for x in survivors)
    assert result["branches"]["total"] > 0
    assert 0 < result["branches"]["covered"] <= result["branches"]["total"]
    assert (
        sum(text.count("branch ") for text in result["gcov"].values())
        == result["branches"]["total"]
    )
    tool.verify_observations(result, 6)
    print(
        json.dumps(
            {
                "run_id": directory.name,
                "coverage": result["branches"],
                "counts": tool.counts_for(result["results"], set()),
            }
        )
    )
