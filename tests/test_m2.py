import json
import subprocess
import sys
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix.llm.ledger import Budget, BudgetExceeded, Ledger
from phoenix.llm.provider import Completion, Request, Usage
from phoenix_eval import __main__ as cli
from phoenix_eval import m1, m2
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import Tier, Variant
from phoenix_eval.model_ledger import bound_summary, read_identity
from phoenix_eval.submission import EvaluationPending, Method, Submission
from phoenix_eval.toolchain import Compiler


def scope_fixture(category: str = "synthetic") -> m2.Scope:
    return m2.Scope(
        tuple(
            m2.Batch(
                tier,
                tuple(
                    sorted(
                        (
                            Variant(f"case-{index}", compiler, flag, "a" * 64, category)
                            for index in range(tier.programs)
                            for compiler in Compiler
                            for flag in tier.flags
                        ),
                        key=lambda v: v.key,
                    )
                ),
                "b" * 64,
                "c" * 64,
                "d" * 64,
            )
            for tier in Tier
        )
    )


def results_fixture(scope: m2.Scope) -> list[dict[str, Any]]:
    return [
        {
            **asdict(v),
            "tier": batch.tier,
            "method": method,
            "variant_key": f"{batch.tier.lower()}-{v.key}",
            "task_key": f"{batch.tier.lower()}-{v.key}-{method}",
            "source_sha256": "e" * 64,
            "model": {
                "calls": 0,
                "usage": {
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                },
                "cost_nanodollars": 0,
                "unknown_cost_reservations": 0,
            },
            "reconstruction_seconds": 1.0,
            "fully_successful": True,
            "integrity": {
                "passed": True,
                "categories": {},
                "checked_storage_records": 0,
                "checked_executables": 4,
                "targets": ["x86_64-linux-gnu", "aarch64-linux-gnu"],
                "clang_versions": ["synthetic", "synthetic"],
                "justifications": [],
            },
            "behavior": {
                "eligible_cases": 2,
                "total_cases": 3,
                "emulator_disagreements": 1,
                "evaluation_errors": 0,
                "original_error_categories": {},
                "recovered_blocks": 5,
                "covered_blocks": 3,
                "behavior_passed": True,
                "builds": [
                    {
                        "architecture": arch,
                        "compiler": compiler,
                        "compiled": True,
                        "matched_cases": 2,
                        "evaluation_errors": 0,
                        "failure_categories": {},
                        "warnings": 0,
                        "executable_sha256": "f" * 64,
                    }
                    for arch in ("amd64", "arm64")
                    for compiler in Compiler
                ],
            },
        }
        for batch in scope.batches
        for v in batch.variants
        for method in m2.METHODS
    ]


@given(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 -", min_size=1, max_size=128)
)
def test_scope_round_trip(category: str) -> None:
    scope = scope_fixture(category)
    assert m2.Scope.parse(json.loads(json.dumps(scope.record()))) == scope
    keys = scope.record()["task_keys"]
    assert isinstance(keys, list)
    assert len(keys) == len(set(keys)) == 260
    assert sum(len(b.variants) for b in scope.batches) == 130
    rebuilds = scope.record()["rebuilds"]
    assert isinstance(rebuilds, list) and len(rebuilds) == 4


@pytest.mark.parametrize(
    "field", ["schema", "batches", "methods", "task_keys", "rebuilds", "project_cmake"]
)
@given(value=st.sampled_from([None, True, "changed", [], {}]))
def test_scope_rejects_changed_fields(value: object, field: str) -> None:
    data = scope_fixture().record()
    data[field] = value
    with pytest.raises(ValueError, match="scope"):
        m2.Scope.parse(data)


@pytest.mark.parametrize(
    "field",
    [
        "tier",
        "flags",
        "manifest_sha256",
        "source_archive_sha256",
        "heldout_archive_sha256",
        "variants",
    ],
)
def test_scope_rejects_changed_batch(field: str) -> None:
    data = json.loads(json.dumps(scope_fixture().record()))
    data["batches"][1][field] = "changed"
    with pytest.raises(ValueError, match="scope"):
        m2.Scope.parse(data)


def test_scope_rejects_unknown_fields_and_duplicate_variants() -> None:
    data = json.loads(json.dumps(scope_fixture().record()))
    for target in (data, data["batches"][0], data["batches"][1]["variants"][0]):
        target["extra"] = 1
        with pytest.raises(ValueError):
            m2.Scope.parse(data)
        del target["extra"]
    data["batches"][1]["variants"][1] = data["batches"][1]["variants"][0]
    with pytest.raises(ValueError):
        m2.Scope.parse(data)


@pytest.mark.parametrize(
    "tier,flag,threshold",
    [("T0", "-O0", 16), ("T0", "-O2", 16), ("T1", "-O0", 18), ("T1", "-O2", 12)],
)
def test_exact_numerical_thresholds(tier: str, flag: str, threshold: int) -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    selected = [
        r
        for r in records
        if (r["tier"], r["flag"], r["method"]) == (tier, flag, "phoenix")
    ]
    for record in selected[threshold:]:
        record["fully_successful"] = False
        record["integrity"]["passed"] = False
    assert m2.summarize(records, scope)["numerical_thresholds_met"] is True
    selected[threshold - 1]["fully_successful"] = False
    selected[threshold - 1]["integrity"]["passed"] = False
    assert m2.summarize(records, scope)["numerical_thresholds_met"] is False


@pytest.mark.parametrize("tier", list(Tier))
@pytest.mark.parametrize("failures,within", [(1, True), (2, False)])
def test_portability_uses_integer_bound_and_requires_root_cause(
    tier: Tier, failures: int, within: bool
) -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    selected = [
        r
        for r in records
        if (r["tier"], r["flag"], r["method"]) == (tier, "-O0", "phoenix")
    ]
    for record in selected[:failures]:
        record["fully_successful"] = False
        record["behavior"]["behavior_passed"] = False
        record["behavior"]["evaluation_errors"] = 1
        record["behavior"]["builds"][2].update(matched_cases=0, evaluation_errors=1)
    summary = m2.summarize(records, scope)
    assert summary["portability_bound_met"] is within
    assert summary["root_cause_gate"] == "required"
    assert summary["accepted"] is False
    assert summary["arm_only_failure_categories"] == {
        r["variant_key"]: "arm_only_behavior_failure" for r in selected[:failures]
    }


def test_os_has_no_threshold_and_architecture_requires_both_compilers() -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    for record in records:
        if record["flag"] == "-Os":
            record.update(fully_successful=False)
            record.pop("behavior")
    summary = m2.summarize(records, scope)
    assert summary["accepted"] is True
    groups = summary["groups"]
    assert isinstance(groups, list)
    assert all(
        g["required_fully_successful"] is None
        for g in groups
        if g["flag"] == "-Os" and g["method"] == "phoenix"
    )
    one = results_fixture(scope)[0]
    one["behavior"]["builds"][1]["compiler"] = "gcc"
    assert not m2.architecture_passed(one, "amd64")
    one["behavior"]["original_error_categories"] = {"worker_error": 1}
    assert not m2.architecture_passed(one, "arm64")
    one["behavior"]["eligible_cases"] = 0
    assert not m2.architecture_passed(one, "amd64")


@pytest.mark.parametrize("change", ["duplicate", "missing", "tier", "extra"])
def test_result_roster_is_exact(change: str) -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    if change == "duplicate":
        records[1] = records[0]
    elif change == "missing":
        records.pop()
    elif change == "extra":
        records.append(records[0])
    else:
        records[0]["tier"] = "T1"
    with pytest.raises(ValueError, match="roster"):
        m2.summarize(records, scope)


class Provider:
    name = "synthetic"

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: Request) -> Completion:
        return Completion("opaque response", Usage(5, 0, 3), request.model)


@pytest.fixture
def synthetic_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    scope = scope_fixture()
    state: dict[str, Any] = {
        "scope": scope,
        "submitted": [],
        "opened": [],
        "pending": None,
    }
    monkeypatch.setattr(m1, "_m2_scope", lambda _: state["scope"])
    monkeypatch.setattr(
        m1,
        "_configuration",
        lambda *_: {
            "schema": 1,
            "heldout_archive_sha256": "d" * 64,
            "worker_images": {},
            "checker_images": {},
            "pipeline_settings": {
                "budget_binary": 5_000_000_000,
                "budget_run": 200_000_000_000,
            },
        },
    )
    monkeypatch.setattr(m1, "_release_bytes", lambda v, release: release.name.encode())
    monkeypatch.setattr(m1, "_validate_pipeline_record", lambda *_: None)
    monkeypatch.setattr(
        m1, "verify_development", lambda original, *_: frozenset({original})
    )
    monkeypatch.setattr(
        m1, "read_origin", lambda path, _: path.parents[1].name[:2].encode()
    )

    def submit(
        workspace: Path,
        directory: Path,
        pipeline: str,
        key: str,
        binary: Path,
        method: Method,
        replay: str | None,
    ) -> Submission:
        assert binary.parents[2].name == key[:2]
        if state["pending"] == key:
            raise EvaluationPending("Synthetic interruption.")
        capture = directory / "capture/submission.json"
        if capture.exists():
            return Submission(**json.loads(capture.read_text()))
        ledger = Ledger(workspace / "runs" / (replay or pipeline))
        if method == "phoenix":
            provider = Provider()
            if replay:

                def forbidden(_: Request) -> Completion:
                    pytest.fail("Replay called a fresh model provider.")

                monkeypatch.setattr(provider, "complete", forbidden)
            ledger.call(
                key, Request("synthetic request"), provider, replay=replay is not None
            )
        result = Submission(
            method,
            key,
            "e" * 64,
            None,
            replay,
            "d" * 64,
            "f" * 64,
            "a" * 64,
            1.0 if replay is None else 2.0,
        )
        capture.parent.mkdir(parents=True)
        capture.write_text(json.dumps(asdict(result)))
        state["submitted"].append((pipeline, key, replay))
        return result

    def cases(
        path: Path, digest: str, names: set[str], *, tier: Tier
    ) -> dict[str, tuple[Invocation, ...]]:
        pipeline = state["submitted"][-1][0]
        run = workspace_run = tmp_path / "runs" / pipeline.removesuffix("-rebuild")
        assert read_identity(run / "model-ledger.json")["sha256"] is not None
        assert (
            len(list((workspace_run / "submissions").glob("*/capture/submission.json")))
            == 260
        )
        state["opened"].append(tier)
        return {name: (Invocation(stdin=tier.encode()),) for name in names}

    fixtures = {r["task_key"]: r for r in results_fixture(scope)}

    def measure(
        workspace: Path,
        run: Path,
        pipeline: str,
        task: m1.Task,
        submission: Submission,
        binary: bytes,
        cases: tuple[Invocation, ...],
        config: m1._Configuration,
        dev: frozenset[bytes],
        origin: bytes,
        identity: Any,
    ) -> dict[str, object]:
        assert len(state["opened"]) % 2 == 0
        assert task.tier is not None
        assert binary == task.tier.lower().encode()
        assert cases[0].stdin == task.tier.encode()
        assert dev == frozenset({binary})
        assert origin == binary
        return {
            **fixtures[task.key],
            "model": asdict(bound_summary(workspace, run, task.key, identity)),
            "reconstruction_seconds": submission.reconstruction_seconds,
        }

    monkeypatch.setattr(m1, "submit", submit)
    monkeypatch.setattr(m1, "heldout_cases", cases)
    monkeypatch.setattr(m1, "_measure", measure)
    return state


@pytest.mark.parametrize("source", ["origin", "first", "resume"])
def test_replay_rejects_changed_configuration_json_type(
    tmp_path: Path, synthetic_engine: dict[str, Any], source: str
) -> None:
    report, _ = m1.evaluate_m2(tmp_path, "origin")
    if source == "first":
        m1.evaluate_m2(tmp_path, "first", "origin")
    document = json.loads(report.read_text())
    document["configuration"]["pipeline_settings"]["budget_binary"] = 5_000_000_000.0
    report.write_text(json.dumps(document))
    before = report.read_bytes()
    submitted = len(synthetic_engine["submitted"])
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError):
        if source == "resume":
            m1.evaluate_m2(tmp_path, "origin")
        else:
            m1.evaluate_m2(tmp_path, "copy", source)
    assert synthetic_engine["opened"] == []
    assert len(synthetic_engine["submitted"]) == submitted
    assert report.read_bytes() == before


def test_full_matrix_freeze_replay_and_replay_lineage(
    tmp_path: Path, synthetic_engine: dict[str, Any]
) -> None:
    report, passed = m1.evaluate_m2(tmp_path, "origin")
    assert passed
    original = json.loads(report.read_text())
    assert original["coverage_kind"] == "recovered_block_entries"
    assert len(original["results"]) == 260
    assert len(synthetic_engine["submitted"]) == 260
    assert synthetic_engine["opened"] == [Tier.T0, Tier.T1]
    ledger = tmp_path / "runs/origin-rebuild/llm.jsonl"
    digest = sha256(ledger.read_bytes()).hexdigest()
    assert original["model_ledger"]["sha256"] == digest
    assert len(ledger.read_text().splitlines()) == 260
    for name, source in (("replay", "origin"), ("again", "replay")):
        replay, passed = m1.evaluate_m2(tmp_path, name, source)
        assert passed
        data = json.loads(replay.read_text())
        assert data["reproduced"] is True
        assert data["model_ledger"] == original["model_ledger"]
        assert not (tmp_path / f"runs/{name}-rebuild/llm.jsonl").exists()
    assert sha256(ledger.read_bytes()).hexdigest() == digest


def test_interrupted_matrix_resumes_across_colliding_tier_names(
    tmp_path: Path, synthetic_engine: dict[str, Any]
) -> None:
    synthetic_engine["pending"] = "t1-case-0-clang-O0-phoenix"
    with pytest.raises(EvaluationPending):
        m1.evaluate_m2(tmp_path, "origin")
    assert len(synthetic_engine["submitted"]) == 80
    assert synthetic_engine["opened"] == []
    synthetic_engine["pending"] = None
    assert m1.evaluate_m2(tmp_path, "origin")[1]
    assert len(synthetic_engine["submitted"]) == 260
    assert len(set(key for _, key, _ in synthetic_engine["submitted"])) == 260
    assert m1.evaluate_m2(tmp_path, "origin")[1]
    assert len(synthetic_engine["submitted"]) == 260


@pytest.mark.parametrize("change", ["scope", "ledger", "capture", "identity"])
def test_frozen_resume_rejects_tampering_before_input(
    tmp_path: Path, synthetic_engine: dict[str, Any], change: str
) -> None:
    m1.evaluate_m2(tmp_path, "origin")
    synthetic_engine["opened"].clear()
    if change == "scope":
        scope = synthetic_engine["scope"]
        synthetic_engine["scope"] = replace(
            scope,
            batches=(
                replace(scope.batches[0], source_sha256="0" * 64),
                scope.batches[1],
            ),
        )
    elif change == "ledger":
        with (tmp_path / "runs/origin-rebuild/llm.jsonl").open("ab") as stream:
            stream.write(b"changed")
    elif change == "capture":
        (
            tmp_path
            / "runs/origin/submissions/t1-case-0-clang-O0-phoenix"
            / "capture/submission.json"
        ).unlink()
    else:
        (tmp_path / "runs/origin/model-ledger.json").unlink()
    with pytest.raises(ValueError):
        m1.evaluate_m2(tmp_path, "origin")
    assert synthetic_engine["opened"] == []


@pytest.mark.parametrize(
    "field", ["coverage_kind", "model", "source_sha256", "configuration"]
)
def test_replay_binds_stable_fields(
    tmp_path: Path, synthetic_engine: dict[str, Any], field: str
) -> None:
    report, _ = m1.evaluate_m2(tmp_path, "origin")
    data = json.loads(report.read_text())
    if field in ("model", "source_sha256"):
        if field == "model":
            data["results"][0][field]["calls"] = 999
        else:
            data["results"][0][field] = "0" * 64
    elif field == "configuration":
        data[field]["worker_images"] = {"amd64": "changed"}
    else:
        data[field] = "changed"
    report.write_text(json.dumps(data))
    if field in ("source_sha256", "configuration", "coverage_kind"):
        with pytest.raises(ValueError):
            m1.evaluate_m2(tmp_path, "replay", "origin")
    else:
        replay, passed = m1.evaluate_m2(tmp_path, "replay", "origin")
        assert not passed
        assert json.loads(replay.read_text())["reproduced"] is False


def test_m2_cli_and_root_replay_dispatch(
    tmp_path: Path, synthetic_engine: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["phoenix-eval", "m2", "--run-id", "origin"])
    assert cli.main() == 0
    monkeypatch.setattr(sys, "argv", ["phoenix-eval", "--replay", "origin"])
    assert cli.main() == 0
    monkeypatch.setattr(sys, "argv", ["phoenix-eval", "m1", "--replay", "origin"])
    assert cli.main() == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "mixed",
        "unsupported",
        "malformed",
        "kind",
        "schema",
        "scope",
        "roster",
        "scores",
        "duplicate_json",
    ],
)
def test_replay_dispatch_rejects_bad_reports(tmp_path: Path, mutation: str) -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    scores = m2.summarize(records, scope)
    data = {
        "run_id": tmp_path.name,
        "replay_of": None,
        "reproduced": None,
        "configuration": {"schema": 2, "scope": scope.record()},
        "results": records,
        "scores": scores,
        "accepted": True,
        "report_kind": "m2",
        "source_adequacy": "separate_author_evidence",
        "coverage_kind": "recovered_block_entries",
        "corpus": "agent-sealed",
        "model_ledger": {
            "schema": 1,
            "pipeline_run": "synthetic-rebuild",
            "sha256": None,
        },
    }
    (tmp_path / "model-ledger.json").write_text(json.dumps(data["model_ledger"]))
    path = tmp_path / "m2.json"
    path.write_text(json.dumps(data))
    assert m2.recorded_kind(tmp_path) == "m2"
    if mutation == "missing":
        path.unlink()
    elif mutation in ("mixed", "unsupported"):
        (tmp_path / ("m1.json" if mutation == "mixed" else "m3.json")).write_text("{}")
    elif mutation == "malformed":
        path.write_text("[]")
    elif mutation == "duplicate_json":
        path.write_text(
            path.read_text().replace(
                '"report_kind": "m2"', '"report_kind": "m1", "report_kind": "m2"'
            )
        )
    else:
        modified = json.loads(path.read_text())
        if mutation == "kind":
            modified["report_kind"] = "m1"
        elif mutation == "schema":
            modified["configuration"]["schema"] = True
        elif mutation == "scope":
            modified["configuration"]["scope"]["methods"] = ["phoenix"]
        elif mutation == "roster":
            modified["results"][1] = modified["results"][0]
        else:
            modified["scores"]["accepted"] = False
        path.write_text(json.dumps(modified))
    with pytest.raises(ValueError):
        m2.recorded_kind(tmp_path)


def test_shared_budget_and_tier_keys(tmp_path: Path) -> None:
    assert Budget() == Budget(5_000_000_000, 200_000_000_000)
    ledger = Ledger(tmp_path, Budget(120_000, 160_000))
    provider = Provider()
    request = Request("same request")
    ledger.call("t0-case-0-gcc-O0-phoenix", request, provider)
    ledger.call("t1-case-0-gcc-O0-phoenix", request, provider)
    assert ledger.summary("t0-case-0-gcc-O0-phoenix").calls == 1
    assert ledger.summary("t1-case-0-gcc-O0-phoenix").calls == 1
    with pytest.raises(BudgetExceeded):
        ledger.call("t1-case-1-gcc-O0-phoenix", request, provider)


def test_scope_load_binds_both_commitments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = scope_fixture()
    commitments = tmp_path / "docs/corpus_commitments.md"
    commitments.parent.mkdir()
    commitments.write_text(
        "".join(
            f"| `{batch.tier.lower()}-{kind}.tar.gz` | `{digest}` |\n"
            for batch in scope.batches
            for kind, digest in (
                ("source", batch.source_sha256),
                ("inputs", batch.inputs_sha256),
            )
        )
    )
    monkeypatch.setattr(m1, "CHECKOUT", tmp_path)

    def release(path: Path, tier: Tier) -> tuple[tuple[Variant, ...], str]:
        assert path == tmp_path / "sealed/release" / tier.lower()
        batch = next(b for b in scope.batches if b.tier == tier)
        return batch.variants, batch.manifest_sha256

    monkeypatch.setattr(m1, "release_manifest", release)
    assert m1._m2_scope(tmp_path) == scope
    commitments.write_text(commitments.read_text().replace("t1-source", "missing"))
    with pytest.raises(ValueError, match="commitment"):
        m1._m2_scope(tmp_path)


@pytest.mark.parametrize("phase", ["submit", "cases", "measure"])
def test_m2_replay_rejects_a_fresh_model_log(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    m1.evaluate_m2(tmp_path, "origin")
    name = {"submit": "submit", "cases": "heldout_cases", "measure": "_measure"}[phase]
    original = getattr(m1, name)

    def changed(*args: Any, **kwargs: Any) -> Any:
        ledger = tmp_path / "runs/replay-rebuild/llm.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(b"fresh synthetic log")
        return original(*args, **kwargs)

    monkeypatch.setattr(m1, name, changed)
    with pytest.raises(ValueError, match="fresh model ledger"):
        m1.evaluate_m2(tmp_path, "replay", "origin")
    assert not (tmp_path / "runs/replay/m2.json").exists()


@pytest.mark.parametrize(
    ("ancestor", "phase", "opened"),
    [
        ("first", "before", []),
        ("second", "before", []),
        ("first", "submit", []),
        ("first", "cases", [Tier.T0]),
        ("second", "measure", [Tier.T0, Tier.T1]),
    ],
)
def test_m2_replay_rejects_model_logs_in_its_lineage(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    ancestor: str,
    phase: str,
    opened: list[Tier],
) -> None:
    prior = [
        m1.evaluate_m2(tmp_path, "origin")[0],
        m1.evaluate_m2(tmp_path, "first", "origin")[0],
        m1.evaluate_m2(tmp_path, "second", "first")[0],
    ]
    original = tmp_path / "runs/origin-rebuild/llm.jsonl"
    saved = {path: path.read_bytes() for path in [*prior, original]}
    synthetic_engine["opened"].clear()
    submitted = len(synthetic_engine["submitted"])
    ledger = tmp_path / "runs" / f"{ancestor}-rebuild" / "llm.jsonl"

    def add_ledger() -> None:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(saved[original])

    if phase == "before":
        add_ledger()
    else:
        name = {"submit": "submit", "cases": "heldout_cases", "measure": "_measure"}[
            phase
        ]
        operation = getattr(m1, name)

        def changed(*args: Any, **kwargs: Any) -> Any:
            result = operation(*args, **kwargs)
            if not ledger.exists():
                add_ledger()
            return result

        monkeypatch.setattr(m1, name, changed)
    with pytest.raises(ValueError, match="fresh model ledger"):
        m1.evaluate_m2(tmp_path, "next", "second")
    if phase == "before":
        assert len(synthetic_engine["submitted"]) == submitted
    assert synthetic_engine["opened"] == opened
    assert not (tmp_path / "runs/next/m2.json").exists()
    assert ledger.read_bytes() == saved[original]
    assert all(path.read_bytes() == data for path, data in saved.items())


@pytest.mark.parametrize(
    ("phase", "pipeline"), [("compare", "first"), ("write", "next")]
)
def test_m2_replay_rechecks_model_logs_after_rendering(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    pipeline: str,
) -> None:
    origin = m1.evaluate_m2(tmp_path, "origin")[0]
    first = m1.evaluate_m2(tmp_path, "first", "origin")[0]
    saved = {p: p.read_bytes() for p in (origin, first)}
    synthetic_engine["opened"].clear()
    log = tmp_path / "runs" / f"{pipeline}-rebuild" / "llm.jsonl"

    def introduce_log(document: object) -> None:
        if isinstance(document, dict) and document.get("run_id") == "next":
            log.parent.mkdir(exist_ok=True)
            log.write_bytes(b"")

    if phase == "compare":
        project = m1._stable_m2_report

        def compare(document: dict[str, object]) -> str:
            result = project(document)
            introduce_log(document)
            return result

        monkeypatch.setattr(m1, "_stable_m2_report", compare)
    else:
        serialize = json.dump

        def dump(data: object, *args: Any, **kwargs: Any) -> None:
            serialize(data, *args, **kwargs)
            introduce_log(data)

        monkeypatch.setattr(json, "dump", dump)

    with pytest.raises(ValueError, match="fresh model ledger"):
        m1.evaluate_m2(tmp_path, "next", "first")
    assert log.is_file()
    assert synthetic_engine["opened"] == [Tier.T0, Tier.T1]
    assert not (tmp_path / "runs/next/m2.json").exists()
    assert all(p.read_bytes() == data for p, data in saved.items())


@pytest.mark.parametrize("pipeline", ["first", "next"])
def test_m2_replay_cyclic_model_log_reports_controlled_error(
    tmp_path: Path,
    synthetic_engine: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pipeline: str,
) -> None:
    m1.evaluate_m2(tmp_path, "origin")
    m1.evaluate_m2(tmp_path, "first", "origin")
    synthetic_engine["opened"].clear()
    submitted = len(synthetic_engine["submitted"])
    log = tmp_path / "runs" / f"{pipeline}-rebuild" / "llm.jsonl"
    log.parent.mkdir(exist_ok=True)
    log.symlink_to(log.name)
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(
        sys, "argv", ["phoenix-eval", "m2", "--run-id", "next", "--replay", "first"]
    )
    assert cli.main() == 2
    assert "model ledger" in capsys.readouterr().err
    assert synthetic_engine["opened"] == []
    assert len(synthetic_engine["submitted"]) == submitted
    assert not (tmp_path / "runs/next/m2.json").exists()


@pytest.mark.parametrize(
    "change", ["cycle", "log_origin", "config_missing", "report_scope"]
)
def test_m2_rejects_conflicting_lineage(
    tmp_path: Path, synthetic_engine: dict[str, Any], change: str
) -> None:
    report, _ = m1.evaluate_m2(tmp_path, "origin")
    data = json.loads(report.read_text())
    if change == "cycle":
        data["replay_of"] = "origin"
    elif change == "log_origin":
        data["model_ledger"]["pipeline_run"] = "other-rebuild"
        (report.parent / "model-ledger.json").write_text(
            json.dumps(data["model_ledger"])
        )
    elif change == "config_missing":
        (report.parent / "configuration.json").unlink()
    else:
        data["configuration"]["scope"]["batches"][1]["source_archive_sha256"] = "0" * 64
    report.write_text(json.dumps(data))
    synthetic_engine["opened"].clear()
    with pytest.raises(ValueError):
        if change in ("config_missing", "report_scope"):
            m1.evaluate_m2(tmp_path, "origin")
        else:
            m1.evaluate_m2(tmp_path, "replay", "origin")
    assert synthetic_engine["opened"] == []


@pytest.mark.parametrize("point", ["record", "publish"])
def test_atomic_capture_keeps_tier_keys_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    from phoenix_eval import submission as capture

    calls: list[tuple[str, ...]] = []

    def execute(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 2)

    monkeypatch.setattr(subprocess, "run", execute)
    monkeypatch.setattr(
        capture, "guarded_command", lambda _, command, **kwargs: command
    )
    first = "t0-case-0-gcc-O0-phoenix"
    second = "t1-case-0-gcc-O0-phoenix"

    def submit(key: str) -> Submission:
        return capture.submit(
            tmp_path,
            tmp_path / "captures" / key,
            "matrix",
            key,
            tmp_path / "opaque.elf",
            "phoenix",
        )

    with monkeypatch.context() as patch:
        write = capture.write_report
        replace_path = Path.replace

        def interrupt_record(path: Path, data: object) -> None:
            write(path, data)
            if path.name == "submission.json":
                raise KeyboardInterrupt

        def interrupt_publish(path: Path, destination: Path) -> Path:
            result = replace_path(path, destination)
            if destination.name == "capture":
                raise KeyboardInterrupt
            return result

        if point == "record":
            patch.setattr(capture, "write_report", interrupt_record)
        else:
            patch.setattr(Path, "replace", interrupt_publish)
        with pytest.raises(KeyboardInterrupt):
            submit(first)
    t1 = submit(second)
    t0 = submit(first)
    assert t0.key == first and t1.key == second
    assert submit(first) == t0
    assert submit(second) == t1
    keys = [command[command.index("--binary-id") + 1] for command in calls]
    assert keys.count(first) == (2 if point == "record" else 1)
    assert keys.count(second) == 1


def test_every_m2_task_uses_four_existing_pair_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import cast

    from test_pair import IMAGES, FakeWorker

    from phoenix_eval import pair
    from phoenix_eval.build import PROJECT_CMAKE, snapshot_project
    from phoenix_eval.integrity import IntegrityReport
    from phoenix_eval.model_ledger import freeze_identity
    from phoenix_eval.submission import freeze_package_report, freeze_project

    worker = FakeWorker(tmp_path)
    worker.source.rename(worker.source.with_name("program.c"))
    (worker.project / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    worker.snapshot = snapshot_project(worker.project)
    monkeypatch.setattr(pair, "run_cases", worker.run_cases)
    monkeypatch.setattr(pair, "inspect_x86", worker.inspect_x86)
    monkeypatch.setattr(pair, "build_project", worker.build_project)
    monkeypatch.setattr(m1, "inspect_project", lambda *_: ())
    monkeypatch.setattr(m1, "original_shapes", lambda *_, **kwargs: ())
    monkeypatch.setattr(
        m1, "check_integrity", lambda *_: IntegrityReport(True, {}, 0, 4, (), (), ())
    )
    run = tmp_path / "evaluation"
    identity = freeze_identity(tmp_path, run, "synthetic")
    scope = scope_fixture()
    records = []
    for batch in scope.batches:
        for variant in batch.variants:
            variant = replace(variant, sha256=sha256(worker.original_bytes).hexdigest())
            for method in m2.METHODS:
                task = m1.Task(variant, method, batch.tier)
                directory = run / "submissions" / task.key / "capture"
                directory.mkdir(parents=True)
                (worker.project / "phoenix_report.json").write_text(
                    json.dumps(
                        {
                            "sha256": variant.sha256,
                            "method": method,
                            "wall_seconds": 1,
                        }
                    )
                )
                submission = Submission(
                    method,
                    task.key,
                    freeze_project(worker.project, directory / "project"),
                    None,
                    report_sha256=freeze_package_report(worker.project, directory),
                )
                records.append(
                    m1._measure(
                        tmp_path,
                        run,
                        "synthetic",
                        task,
                        submission,
                        worker.original_bytes,
                        worker.cases,
                        cast(
                            m1._Configuration,
                            {"worker_images": IMAGES, "checker_images": {}},
                        ),
                        origin_bytes=b"opaque origin",
                        model_ledger=identity,
                    )
                )
    assert len(records) == 260
    assert all(r["fully_successful"] is True for r in records)
    assert len(worker.built) == 1040
    assert all(
        sum(arch.platform == name for _, arch, _ in worker.built) == 520
        for name in ("amd64", "arm64")
    )


@pytest.mark.parametrize("missing", ["source_sha256", "integrity", "behavior"])
def test_success_cannot_omit_required_evidence(missing: str) -> None:
    scope = scope_fixture()
    records = results_fixture(scope)
    records[0].pop(missing)
    with pytest.raises(ValueError):
        m2.summarize(records, scope)


@pytest.mark.parametrize("kind", ["m0", "m1", "m3"])
def test_m2_new_run_rejects_another_report_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    directory = tmp_path / "runs/origin"
    directory.mkdir(parents=True)
    (directory / f"{kind}.json").write_text(
        json.dumps(
            {
                "run_id": "origin",
                "configuration": {"schema": 1},
                "results": [],
                "scores": {},
                "accepted": False,
            }
        )
    )

    def forbidden(_: Path) -> m2.Scope:
        pytest.fail("The command read a release before rejecting the report kind.")

    monkeypatch.setattr(m1, "_m2_scope", forbidden)
    with pytest.raises(ValueError):
        m1.evaluate_m2(tmp_path, "origin")
