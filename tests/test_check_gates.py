"""Test mechanical gates with synthetic files and Git histories."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_gates as gates


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in ("phoenix", "phoenix_eval", "scripts", "tests", "corpus_dev"):
        (tmp_path / name).mkdir()
    write(tmp_path, "README.md", "Public instructions.\n")
    write(tmp_path, "docs/STATUS.md", "Measured state.\n")
    gates.git(tmp_path, "init", "-b", "main")
    gates.git(tmp_path, "config", "user.name", "Gate fixture")
    gates.git(tmp_path, "config", "user.email", "gate@example.invalid")
    commit(tmp_path)
    return tmp_path


def commit(repo: Path) -> str:
    gates.git(repo, "add", ".")
    gates.git(
        repo,
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--allow-empty",
        "-qm",
        "test: fixture",
    )
    return gates.git(repo, "rev-parse", "HEAD")


def row(commit: str, *, kind: str = "full", number: int = 1) -> list[str]:
    result = ["-"] * 23
    result[0:8] = [
        str(number),
        f"run-{number}",
        commit[:12],
        "corpus_dev",
        "a/b",
        kind,
        "warm",
        "R0",
    ]
    result[8] = f"{number}/3" if kind == "full" else "-"
    return result


def scoreboard(repo: Path, records: list[list[str]]) -> None:
    write(
        repo,
        "docs/SCOREBOARD.md",
        "\n".join("| " + " | ".join(record) + " |" for record in records) + "\n",
    )


def registry(
    repo: Path, revision: str | None, *, command: list[str] | None = None
) -> Path:
    return write(
        repo,
        "docs/plans/enabling.json",
        json.dumps(
            [
                {
                    "name": "bootstrap",
                    "paths": ["phoenix/"],
                    "acceptance": command or [sys.executable, "-c", "pass"],
                    "last_acceptance_commit": revision,
                }
            ]
        ),
    )


@pytest.mark.parametrize("kind", ["full", "quick"])
def test_stale_row_counts_staged_commit(repo: Path, kind: str) -> None:
    baseline = gates.git(repo, "rev-parse", "HEAD")
    scoreboard(repo, [row(baseline, kind=kind)])
    commit(repo)
    for _ in range(8):
        commit(repo)
    write(repo, "phoenix/new.py", "x = 1\n")
    gates.git(repo, "add", "phoenix/new.py")
    gates.stale(repo)  # Nine recorded commits and one staged commit.
    gates.git(repo, "reset", "-q")
    commit(repo)
    write(repo, "phoenix/new.py", "x = 2\n")
    gates.git(repo, "add", "phoenix/new.py")
    with pytest.raises(ValueError, match="10 commits"):
        gates.stale(repo)


def test_ci_counts_head_once_and_ignores_document_change(repo: Path) -> None:
    baseline = gates.git(repo, "rev-parse", "HEAD")
    scoreboard(repo, [row(baseline)])
    commit(repo)
    for _ in range(8):
        commit(repo)
    write(repo, "phoenix/new.py", "x = 1\n")
    commit(repo)
    gates.stale(repo)
    write(repo, "phoenix/new.py", "x = 2\n")
    commit(repo)
    with pytest.raises(ValueError, match="10 commits"):
        gates.stale(repo)
    write(repo, "README.md", "Updated instructions.\n")
    commit(repo)
    gates.stale(repo)


def test_probe_and_noise_do_not_reset_staleness(repo: Path) -> None:
    baseline = gates.git(repo, "rev-parse", "HEAD")
    for _ in range(11):
        commit(repo)
    recent = gates.git(repo, "rev-parse", "HEAD")
    scoreboard(
        repo,
        [
            row(baseline),
            row(recent, kind="probe", number=2),
            row(recent, kind="noise", number=3),
        ],
    )
    write(repo, "phoenix/new.py", "x = 1\n")
    gates.git(repo, "add", ".")
    with pytest.raises(ValueError, match="10 commits"):
        gates.stale(repo)


def test_missing_or_nonancestor_measurement_fails(repo: Path) -> None:
    write(repo, "phoenix/new.py", "x = 1\n")
    gates.git(repo, "add", ".")
    with pytest.raises(ValueError, match="needs a loop row"):
        gates.stale(repo)
    scoreboard(repo, [row("f" * 40)])
    with pytest.raises(ValueError, match="failed"):
        gates.stale(repo)


def test_staged_file_cannot_be_hidden_by_working_copy(repo: Path) -> None:
    registry(repo, commit(repo))
    write(repo, "phoenix/new.py", "x = 1\n")
    gates.git(repo, "add", ".")
    write(repo, "phoenix/new.py", "x = 2\n")
    with pytest.raises(ValueError, match="Staged files"):
        gates.stale(repo)


def test_enabling_acceptance_applies_only_to_one_complete_scope(repo: Path) -> None:
    baseline = gates.git(repo, "rev-parse", "HEAD")
    scoreboard(repo, [row(baseline)])
    for _ in range(11):
        commit(repo)
    registry(repo, commit(repo))
    commit(repo)
    write(repo, "phoenix/new.py", "x = 1\n")
    gates.git(repo, "add", "phoenix/new.py")
    gates.stale(repo)
    write(repo, "phoenix_eval/new.py", "x = 1\n")
    gates.git(repo, "add", "phoenix_eval/new.py")
    with pytest.raises(ValueError, match="10 commits"):
        gates.stale(repo)


@pytest.mark.parametrize("exit_code", [0, 1])
def test_acceptance_runs_command_and_records_only_a_pass(
    repo: Path, exit_code: int
) -> None:
    marker = repo / "accepted-marker"
    command = [
        sys.executable,
        "-c",
        (
            f"from pathlib import Path; Path({str(marker)!r}).touch(); "
            f"raise SystemExit({exit_code})"
        ),
    ]
    path = registry(repo, None, command=command)
    revision = commit(repo)
    if exit_code:
        with pytest.raises(ValueError, match="failed"):
            gates.accept_enabling(repo, "bootstrap")
    else:
        gates.accept_enabling(repo, "bootstrap")
    assert marker.exists()
    assert json.loads(path.read_text())[0]["last_acceptance_commit"] == (
        None if exit_code else revision
    )


def test_acceptance_rejects_dirty_or_changed_source(repo: Path) -> None:
    source = write(repo, "phoenix/new.py", "x = 1\n")
    registry(
        repo,
        None,
        command=[
            sys.executable,
            "-c",
            (f"from pathlib import Path; Path({str(source)!r}).write_text('changed')"),
        ],
    )
    commit(repo)
    with pytest.raises(ValueError, match="changed during acceptance"):
        gates.accept_enabling(repo, "bootstrap")
    with pytest.raises(ValueError, match="Commit the enabling item"):
        gates.accept_enabling(repo, "bootstrap")


def test_enabling_registry_rejects_excess_items_and_unsafe_paths(repo: Path) -> None:
    path = registry(repo, None)
    data = json.loads(path.read_text())
    path.write_text(json.dumps(data * 3))
    with pytest.raises(ValueError, match="two enabling"):
        gates.enabling(repo)
    data[0]["paths"] = ["../phoenix"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="relative enabling"):
        gates.enabling(repo)


@pytest.mark.parametrize("name,limit", list(gates.LIMITS.items()))
def test_file_limits_count_nonblank_lines(repo: Path, name: str, limit: int) -> None:
    path = write(repo, name, "\n# line\n" * limit)
    gates.code_size(repo)
    path.write_text(path.read_text() + "# extra\n")
    with pytest.raises(ValueError, match="exceeds"):
        gates.code_size(repo)


def test_source_limit_includes_all_pipeline_and_evaluator_files(repo: Path) -> None:
    write(repo, "phoenix/a.py", "# line\n" * 7499)
    path = write(repo, "phoenix_eval/nested/b.py", "# line\n" * 7500)
    write(repo, "tests/large.py", "# line\n" * 100)
    gates.code_size(repo)
    path.write_text(path.read_text() + "# extra\n")
    assert gates.source_lines(repo) == 15000
    with pytest.raises(ValueError, match="fewer than 15000"):
        gates.code_size(repo)


def test_status_limit_counts_blank_lines(repo: Path) -> None:
    path = write(repo, "docs/STATUS.md", "\n" * 60)
    gates.status_length(repo)
    path.write_text("\n" * 61)
    with pytest.raises(ValueError, match="60 lines"):
        gates.status_length(repo)


def test_banned_terms_use_required_case_and_word_boundaries(repo: Path) -> None:
    write(repo, "docs/example.md", "HOLDER hold Fresh complete review\n")
    gates.banned_terms(repo)
    for term in gates.PROCESS_TERMS:
        write(repo, "docs/example.md", term)
        with pytest.raises(ValueError, match="process term"):
            gates.banned_terms(repo)
    write(repo, "docs/example.md", "Measured state.")
    for term in gates.REPORT_TERMS:
        write(repo, "docs/REPORT.md", term.upper())
        with pytest.raises(ValueError, match="report term"):
            gates.banned_terms(repo)


@pytest.mark.parametrize(
    "leak",
    [
        "fixture_program",
        "long-string-value",
        "escaped-newline\nvalue",
        "joined-string-value",
    ],
)
def test_program_names_and_c_string_literals_are_rejected(
    repo: Path, leak: str
) -> None:
    write(
        repo,
        "corpus_dev/fixture_program/src/main.c",
        'char *a="long-string-value"; char *b="escaped-newline\\nvalue"; '
        'char *c="joined-" /* gap */ "string-value";',
    )
    write(repo, "phoenix/prompts/template.txt", leak)
    with pytest.raises(ValueError, match="Corpus program text"):
        gates.program_names(repo)


def test_short_literals_and_comments_are_allowed(repo: Path) -> None:
    write(
        repo,
        "corpus_dev/fixture_program/src/main.c",
        '// "comment-string-value"\nchar *x="short";',
    )
    write(repo, "phoenix/a.py", 'x = "short comment-string-value"')
    gates.program_names(repo)


@pytest.mark.parametrize(
    "path,source",
    [
        ("phoenix_eval/new.py", "import phoenix.pipeline"),
        ("phoenix_eval/new.py", "from phoenix import pipeline"),
        ("phoenix/new.py", "from tools.adequacy import summary"),
    ],
)
def test_import_direction(repo: Path, path: str, source: str) -> None:
    write(repo, path, source)
    with pytest.raises(ValueError, match="import direction"):
        gates.import_direction(repo)


@pytest.mark.parametrize(
    "path,source",
    [
        ("phoenix/a.py", "from phoenix.generate import switch_plan"),
        ("phoenix/generate/a.py", "from . import switch_binding"),
        ("phoenix_eval/a.py", "import phoenix_eval.m1"),
        (
            "phoenix_eval/a.py",
            "from importlib import import_module; "
            "import_module('phoenix_eval.' + 'm2')",
        ),
        ("tests/a.py", "import importlib; importlib.import_module('phoenix_eval.m1')"),
        ("scripts/old", "python -m phoenix_eval.m2"),
        ("phoenix/a.py", "loader = 'phoenix/lift/byte_model.py'"),
        ("scripts/old", "java ExportSwitchGraphs.java"),
    ],
)
def test_deleted_imports_loads_and_executables_fail(
    repo: Path, path: str, source: str
) -> None:
    write(repo, path, source)
    with pytest.raises(ValueError, match="Deleted"):
        gates.deleted_modules(repo)


def test_synthetic_fixture_strings_are_allowed_but_imports_are_not(repo: Path) -> None:
    path = write(repo, "tests/negative.py", "fixture = 'import phoenix_eval.m2'\n")
    gates.deleted_modules(repo)
    path.write_text("import phoenix_eval.m2\n")
    with pytest.raises(ValueError, match="Deleted import"):
        gates.deleted_modules(repo)


def provenance_fixture(repo: Path) -> tuple[str, dict[str, object]]:
    names = [
        ".dockerignore",
        "tools.lock",
        "scripts/build-worker",
        "containers/Dockerfile",
        "containers/a.c",
        "containers/c-integrity.cc",
        "containers/Dockerfile.integrity",
        "scripts/build-integrity",
        "schemas/lift.schema.json",
        "pyproject.toml",
        "phoenix/config.py",
        "phoenix_eval/example.py",
        "ghidra_scripts/example.java",
        "scripts/loop",
    ]
    for name in names:
        write(repo, name, "# source\n")
    revision = commit(repo)
    selected = {
        "worker_source_sha256": names[:5] + ["phoenix_eval/example.py"],
        "checker_source_sha256": ["tools.lock", *names[5:8]],
        "pipeline_source_sha256": names[8:11]
        + ["tools.lock", "ghidra_scripts/example.java"],
    }
    config: dict[str, object] = {"revision": revision}
    for key, paths in selected.items():
        digest = hashlib.sha256()
        for name in sorted(paths):
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(hashlib.sha256((repo / name).read_bytes()).digest())
        config[key] = digest.hexdigest()
    return revision, config


def test_provenance_checks_recorded_source_and_current_bytes(repo: Path) -> None:
    revision, config = provenance_fixture(repo)
    gate = gates.Gate(repo, repo)
    gate.provenance(config, revision, current=True)
    write(repo, "phoenix/config.py", "# changed\n")
    with pytest.raises(ValueError, match="stale source"):
        gate.provenance(config, revision, current=True)
    gate.provenance(config, revision, current=False)
    config["worker_source_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="provenance mismatch"):
        gate.provenance(config, revision, current=False)


def test_probe_requires_nonempty_denials(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = gates.Gate(repo, repo)
    for output in ("", "engineer sealed path denied=false\n"):
        monkeypatch.setattr(
            gates.Gate, "command", lambda *_args, _output=output, **_kwargs: _output
        )
        with pytest.raises(ValueError, match="probe"):
            gate.probe()
    monkeypatch.setattr(
        gates.Gate,
        "command",
        lambda *_args, **_kwargs: "engineer sealed path denied=true\n",
    )
    assert gate.probe() == "phoenix-eval probe: 1 checks, each denied=true"


def test_bootstrap_invokes_required_checks_and_fails_missing_smoke(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[str] = []
    for name in ("protection", "probe", "main_documents", "salvage", "corpus"):
        monkeypatch.setattr(
            gates.Gate, name, lambda _self, _name=name: called.append(_name)
        )
    monkeypatch.setattr(gates.Gate, "evidence", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(
        gates.Gate, "tests", lambda *_args, **_kwargs: called.append("tests")
    )
    scoreboard(repo, [row("a" * 40, kind="probe")])
    assert not gates.Gate(repo, repo).bootstrap()
    output = capsys.readouterr().out
    assert "[fail] M1 smoke run" in output
    assert output.endswith("R0-bootstrap: FAIL\n")
    assert called == [
        "protection",
        "probe",
        "main_documents",
        "salvage",
        "corpus",
        "tests",
    ]


def test_gate_reports_each_r0_condition_when_evidence_is_missing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gates.Gate, "command", lambda *_args, **_kwargs: "")
    assert not gates.Gate(repo, repo).r0()
    output = capsys.readouterr().out
    assert (
        len(
            [
                line
                for line in output.splitlines()
                if line.startswith(("[pass]", "[fail]"))
            ]
        )
        == 9
    )
    assert output.endswith("R0 gate: FAIL\n")


def test_read_rejects_symbolic_evidence(repo: Path) -> None:
    original = write(repo, "evidence.json", "{}")
    link = repo / "link.json"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="physical file"):
        gates.read(link)


@pytest.mark.parametrize("name", ["phoenix/new.py", "phoenix_eval/nested/new.py"])
def test_provenance_rejects_added_source_file(repo: Path, name: str) -> None:
    revision, config = provenance_fixture(repo)
    write(repo, name, "# new source\n")
    with pytest.raises(ValueError, match="source inventory"):
        gates.Gate(repo, repo).provenance(config, revision, current=True)


@pytest.mark.parametrize(
    "dynamic",
    [
        "import importlib; importlib.import_module('phoenix.pipeline')",
        "from importlib import import_module as load; load('phoenix.pipeline')",
    ],
)
def test_dynamic_import_direction(repo: Path, dynamic: str) -> None:
    write(repo, "phoenix_eval/new.py", dynamic)
    with pytest.raises(ValueError, match="import direction"):
        gates.import_direction(repo)


def test_deleted_dynamic_alias_in_test_code(repo: Path) -> None:
    write(
        repo,
        "tests/new.py",
        "from importlib import import_module as load\nload('phoenix_eval.m2')\n",
    )
    with pytest.raises(ValueError, match="Deleted"):
        gates.deleted_modules(repo)


@pytest.fixture
def evidence_repo(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[gates.Gate, list[str], dict[str, object], list[str]]:
    revision, config = provenance_fixture(repo)
    record = row(revision)
    binary = SimpleNamespace(name="fixture", sha256="a" * 64)
    document: dict[str, object] = {
        "commit": revision,
        "milestone": "R0",
        "loop": "full",
        "run_state": "complete",
        "corpus_hash": "b" * 64,
        "heldout_hash": "c" * 64,
    }
    plan = {"configuration": config, "binaries": [vars(binary)]}
    write(repo, "runs/run-1/scoreboard.json", json.dumps(document))
    write(repo, "runs/run-1/plan.json", json.dumps(plan))
    called: list[str] = []
    selection = SimpleNamespace(quick=False)
    modules = {
        "phoenix_eval.loop": SimpleNamespace(
            format_row=lambda _doc: "| " + " | ".join(record) + " |",
            validate_score=lambda *_args: called.append("validate_score"),
        ),
        "phoenix_eval.run_records": SimpleNamespace(
            directory=lambda workspace, run_id: workspace / "runs" / run_id,
            RunPlan=SimpleNamespace(
                load=lambda _path: SimpleNamespace(selection=selection)
            ),
        ),
        "phoenix_eval.run_plan": SimpleNamespace(
            _configuration=lambda _workspace: config,
            _selection=lambda *_args: ((binary,), "b" * 64, "c" * 64),
        ),
        "phoenix_eval.run": SimpleNamespace(
            publish=lambda *_args: called.append("publish")
        ),
    }
    original = importlib.import_module

    def module(name: str) -> object:
        return modules[name] if name in modules else original(name)

    monkeypatch.setattr(importlib, "import_module", module)
    return gates.Gate(repo, repo), record, document, called


@pytest.mark.parametrize("state", ["complete", "stopped"])
def test_evidence_checks_actual_artifact_and_invokes_validators(
    evidence_repo: tuple[gates.Gate, list[str], dict[str, object], list[str]],
    state: str,
) -> None:
    gate, record, document, called = evidence_repo
    document["run_state"] = state
    write(gate.root, "runs/run-1/scoreboard.json", json.dumps(document))
    assert gate.evidence(record)[0] == document
    assert called == ["validate_score", "publish"]


def test_rows_accept_the_loop_table_format(repo: Path) -> None:
    from phoenix_eval.loop import HEADER, format_row

    document: dict[str, object] = {
        "row": 1,
        "run_id": "fixture",
        "commit": "a" * 40,
        "corpus": "corpus_dev",
        "corpus_hash": "b" * 64,
        "heldout_hash": "c" * 64,
        "loop": "probe",
        "cache": "warm",
        "milestone": "R0",
        "experiment": None,
        "success": {"D0": {"O0": [1, 2]}},
    }
    write(repo, "docs/SCOREBOARD.md", HEADER + format_row(document))
    records = gates.rows(repo)
    assert len(records) == 1
    assert len(records[0]) == 23
    assert records[0][1] == "fixture"


@pytest.mark.parametrize(
    "field,value",
    [
        ("corpus_hash", "d" * 64),
        ("heldout_hash", "e" * 64),
        ("run_state", "unknown"),
        ("milestone", "R1"),
    ],
)
def test_evidence_rejects_changed_identity(
    evidence_repo: tuple[gates.Gate, list[str], dict[str, object], list[str]],
    field: str,
    value: object,
) -> None:
    gate, record, document, _ = evidence_repo
    document[field] = value
    write(gate.root, "runs/run-1/scoreboard.json", json.dumps(document))
    with pytest.raises(ValueError):
        gate.evidence(record)


def test_evidence_rejects_changed_selection(
    evidence_repo: tuple[gates.Gate, list[str], dict[str, object], list[str]],
) -> None:
    gate, record, _, _ = evidence_repo
    path = gate.root / "runs/run-1/plan.json"
    plan = json.loads(path.read_text())
    plan["binaries"] = []
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="selection is stale"):
        gate.evidence(record)


@pytest.mark.parametrize(
    "failed",
    [
        None,
        "coverage",
        "noise",
        "check",
        "performance",
        "tests",
        "storage",
        "size",
        "corpus",
    ],
)
def test_budget_exception_keeps_other_conditions_strict(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failed: str | None,
) -> None:
    revision = gates.git(repo, "rev-parse", "HEAD")
    write(repo, "phoenix/config.py", "# settings\n")
    revision = commit(repo)
    records = [row(revision, number=n) for n in range(1, 4)]
    records.extend(
        [
            row(revision, kind="noise", number=4),
            row(revision, kind="probe", number=5),
            row(revision, kind="probe", number=6),
        ]
    )
    scoreboard(repo, records)
    for record in records[-2:]:
        quick = record[0] == "6"
        write(
            repo,
            f"runs/{record[1]}/plan.json",
            json.dumps(
                {
                    "selection": {
                        "quick": quick,
                        "tiers": ["D0", "D1"] if quick else ["D0"],
                        "levels": ["O0", "O2", "Os"] if quick else ["O0"],
                    }
                }
            ),
        )
    write(
        repo,
        "runs/r0-resize.json",
        json.dumps({"status": "bad" if failed == "storage" else "dry_run_ok"}),
    )

    def evidence(
        _self: gates.Gate, record: list[str], *, current: bool = True
    ) -> tuple[dict[str, object], dict[str, object]]:
        kind = record[5]
        cells = {
            tier: {level: [7, 10] for level in ("O0", "O2", "Os")}
            for tier in ("D0", "D1")
        }
        if failed == "coverage":
            del cells["D1"]["Os"]
        document: dict[str, object] = {
            "commit": revision,
            "experiment": [int(record[0]), 3],
            "success": cells,
            "quick_set": 2 if failed == "noise" else 1,
            "cache": "cold" if kind == "noise" else "warm",
            "noise": {"D0": [0, 12]},
            "loop_minutes": 31 if failed == "performance" else 1,
            "run_state": "complete",
        }
        return document, {}

    def command(_self: gates.Gate, *args: str, **kwargs: object) -> str:
        if failed == "check" and args == ("./scripts/check",):
            raise ValueError("Synthetic check failure.")
        if failed == "tests" and "tests/test_integrity.py" in args:
            raise ValueError("Synthetic fixture failure.")
        return ""

    def corpus(_self: gates.Gate) -> str:
        if failed == "corpus":
            raise ValueError("Synthetic corpus failure.")
        return (
            "corpus_dev 22 programs: meta, held-out validation, "
            "8 builds, twins (0 invalid), adequacy"
        )

    monkeypatch.setattr(gates.Gate, "evidence", evidence)
    monkeypatch.setattr(gates.Gate, "command", command)
    monkeypatch.setattr(gates.Gate, "corpus", corpus)
    monkeypatch.setattr(
        gates, "source_lines", lambda _root: 9000 if failed == "size" else 100
    )
    original_import = importlib.import_module
    fake_records = SimpleNamespace(
        directory=lambda workspace, run_id: workspace / "runs" / run_id
    )
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: (
            fake_records
            if name == "phoenix_eval.run_records"
            else original_import(name)
        ),
    )
    assert gates.Gate(repo, repo).r0() is (failed is None)
    output = capsys.readouterr().out
    assert "budget 3/3 used, gap 10.00 points" in output
    assert output.endswith("R0 gate: PASS\n" if failed is None else "R0 gate: FAIL\n")
    assert (
        len(
            [
                line
                for line in output.splitlines()
                if line.startswith(("[pass]", "[fail]"))
            ]
        )
        == 9
    )


@pytest.mark.parametrize("tamper", [False, True])
def test_smoke_checks_project_bytes_and_four_builds(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tamper: bool
) -> None:
    revision, config = provenance_fixture(repo)
    report = {
        "development_behavior_passed": True,
        "development_integrity": {"passed": True},
        "dev_cases": 2,
        "dev_cases_matched_on_all_builds": 2,
        "builds": [
            {
                "architecture": arch,
                "compiler": cc,
                "built": True,
                "dev_cases_matched": 2,
                "dev_differences": [],
            }
            for arch in ("amd64", "arm64")
            for cc in ("gcc", "clang")
        ],
    }
    data = json.dumps(report)
    for run_id in ("original", "replay"):
        write(repo, f"runs/{run_id}/target/run.json", json.dumps(config))
        write(
            repo, f"runs/{run_id}/target/package/out/target/phoenix_report.json", data
        )
    write(
        repo,
        "runs/r0-smoke.json",
        json.dumps(
            {
                "run_id": "original",
                "replay_id": "replay",
                "commit": revision,
                "dev_pass_rate": 1.0,
                "replay_identical": True,
                "integrity_passed": True,
                "project_files": {
                    "phoenix_report.json": hashlib.sha256(data.encode()).hexdigest()
                },
            }
        ),
    )
    original_import = importlib.import_module
    module = SimpleNamespace(
        directory=lambda workspace, run_id: workspace / "runs" / run_id
    )
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: (
            module if name == "phoenix_eval.run_records" else original_import(name)
        ),
    )
    gate = gates.Gate(repo, repo)
    if tamper:
        write(repo, "runs/replay/target/package/out/target/extra.c", "changed")
        with pytest.raises(ValueError, match="replay bytes changed"):
            gate.smoke()
    else:
        gate.smoke()


def test_gate_shell_runs_synthetic_enabling_acceptance(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(gates.__file__).resolve().parent
    write(repo, "scripts/check_gates.py", (source / "check_gates.py").read_text())
    wrapper = write(repo, "scripts/gate", (source / "gate").read_text())
    wrapper.chmod(0o755)
    marker = repo / "accepted-marker"
    registry(
        repo,
        None,
        command=[
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        ],
    )
    revision = commit(repo)
    uv = write(
        repo,
        "bin/uv",
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[sys.argv.index('python') + 1:]\n"
        "os.execv(sys.executable, [sys.executable, *args])\n",
    )
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", str(uv.parent) + os.pathsep + os.environ["PATH"])
    assert (
        gates.run(repo, [str(wrapper), "--enabling", "bootstrap"])
        == "[pass] enabling bootstrap\n"
    )
    assert marker.exists()
    assert (
        json.loads((repo / "docs/plans/enabling.json").read_text())[0][
            "last_acceptance_commit"
        ]
        == revision
    )


def test_deleted_test_executable_is_rejected(repo: Path) -> None:
    write(repo, "scripts/old", "pytest tests/test_m2.py")
    with pytest.raises(ValueError, match="Deleted executable"):
        gates.deleted_modules(repo)


def test_registry_and_synthetic_fixtures_do_not_hide_imports(repo: Path) -> None:
    write(repo, "scripts/check_gates.py", Path(gates.__file__).read_text())
    write(repo, "tests/test_check_gates.py", Path(__file__).read_text())
    gates.deleted_modules(repo)


@pytest.mark.parametrize(
    "missing", [None, "accepted", "twin", "validation", "adequacy"]
)
def test_corpus_checks_actual_inventory_and_invokes_validation(
    repo: Path, monkeypatch: pytest.MonkeyPatch, missing: str | None
) -> None:
    binaries = []
    for index in range(22):
        name = f"fixture_{index}"
        tier = "D0" if index < 10 else "D1"
        write(
            repo,
            f"corpus_dev/{name}/meta.json",
            json.dumps({"name": name, "tier": tier}),
        )
        for cc in ("gcc", "clang"):
            for level in ("O0", "O2", "Os", "O3"):
                key = f"{cc}-{level}"
                binaries.append(
                    SimpleNamespace(
                        name=name,
                        tier=tier,
                        compiler=cc,
                        level=level,
                        key=key,
                        twin_valid=index != 0,
                    )
                )
                write(repo, f"dev_bin/{name}/{key}/{name}", "text")
                write(
                    repo,
                    f"dev_bin/{name}/{key}/{name}.twin",
                    "changed" if index == 0 else "text",
                )
    if missing != "accepted":
        write(repo, "corpus_dev/accepted.json", "{}")
    if missing == "twin":
        (repo / "dev_bin/fixture_0/gcc-O0/fixture_0.twin").unlink()
    checked: list[str] = []

    def validate(*args: object) -> None:
        if missing == "validation":
            raise ValueError("Synthetic validation failure.")
        checked.append("validated")

    def command(*args: object, **kwargs: object) -> str:
        assert args[-2:] == ("tools/adequacy.py", "--summary")
        if missing == "adequacy":
            raise ValueError("Synthetic adequacy failure.")
        checked.append("adequacy")
        return ""

    modules = {
        "phoenix_eval.dev_corpus": SimpleNamespace(
            read_manifest=lambda _path: binaries,
            load_validated_cases=validate,
            binary_path=lambda workspace, binary: (
                workspace / "dev_bin" / binary.name / binary.key / binary.name
            ),
        ),
        "phoenix_eval.run_plan": SimpleNamespace(
            _selection=lambda *_args: checked.append("selection")
        ),
        "phoenix_eval.run_records": SimpleNamespace(Selection=lambda: None),
        "phoenix_eval.elf": SimpleNamespace(
            elf_sections=lambda data, _name: {".text": SimpleNamespace(data=data)}
        ),
    }
    monkeypatch.setattr(importlib, "import_module", lambda name: modules[name])
    monkeypatch.setattr(gates.Gate, "command", command)
    gate = gates.Gate(repo, repo)
    if missing:
        with pytest.raises((ValueError, FileNotFoundError)):
            gate.corpus()
    else:
        assert gate.corpus() == (
            "corpus_dev 22 programs: meta, held-out validation, "
            "8 builds, twins (8 invalid), adequacy"
        )
        assert checked.count("validated") == 176
        assert checked[-2:] == ["selection", "adequacy"]
