import json
import re
import shutil
import subprocess
from hashlib import sha256
from pathlib import Path
from time import time
from unittest.mock import Mock

import pytest

from phoenix import pipeline, verify
from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.generate import Candidate, Definition, write_project
from phoenix.ingest import BinaryMetadata
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Model, Usage
from phoenix.package import package_project
from phoenix.recover import Function, Program
from phoenix.verify import BUILD_CONFIGURATIONS, Check, Verification
from phoenix.verify.integrity import IntegrityInputs
from phoenix_eval.build import BuildResult, ProjectSnapshot, snapshot_project
from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine
from phoenix_eval.integrity import IntegrityReport
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.toolchain import Compiler
from phoenix_eval.trace import CodeTrace


def preprocess(source: bytes) -> bytes:
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("This source regression needs the installed C preprocessor.")
    return subprocess.run(
        (compiler, "-E", "-P", "-x", "c", "-"),
        input=source,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout


@pytest.mark.parametrize(("expected_exit", "repairs"), [(9, 0), (10, 0), (10, 1)])
def test_delivered_line_sensitive_source_is_the_tested_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_exit: int,
    repairs: int,
) -> None:
    binary = tmp_path / "original.elf"
    binary.write_bytes(b"synthetic original")
    metadata = BinaryMetadata(sha256(binary.read_bytes()).hexdigest(), 0, ())
    expected = (
        Outcome(b"", b"", Exited(expected_exit), TreeSnapshot(), CodeTrace(0, 2, (0,))),
        Outcome(b"", b"", Exited(0), TreeSnapshot(), CodeTrace(0, 2, (1,))),
    )
    cases = (Invocation(), Invocation(("other",)))
    analysis = Analysis(
        tuple(DevelopmentCase(case, result) for case, result in zip(cases, expected)),
        2,
        2,
        2,
        0,
        0,
    )
    program = Program(
        0,
        0,
        0,
        0,
        (
            Function(0, "main", "main", ((0, 0),), "", "int main(void)"),
            Function(1, "other", "other", ((1, 1),), "", "int other(void)"),
        ),
        (),
        (),
    )
    monkeypatch.setattr(pipeline, "analyze", lambda *_: analysis)
    monkeypatch.setattr(pipeline, "lift_binary", lambda *_: None)
    monkeypatch.setattr(pipeline, "recover", lambda *_: program)

    def reached(
        _binary: Path, _program: Program, outcomes: tuple[Outcome, ...]
    ) -> frozenset[int]:
        return frozenset(
            hit
            for outcome in outcomes
            if outcome.trace is not None
            for hit in outcome.trace.hits
        )

    monkeypatch.setattr(pipeline, "reached_functions", reached)
    snapshots: list[ProjectSnapshot] = []
    checked: list[ProjectSnapshot] = []

    def build(
        snapshot: ProjectSnapshot,
        destination: Path,
        engine: Engine,
        compiler: Compiler,
        *,
        image: str,
    ) -> BuildResult:
        source = dict(snapshot.files)["src/program.c"]
        compiled = preprocess(source)
        snapshots.append(snapshot)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(compiled)
        return BuildResult(engine, compiler, destination, 0, "")

    def observations(
        compiled: bytes,
        _cases: tuple[Invocation, ...],
        engine: Engine,
        *,
        image: str,
    ) -> tuple[Outcome, ...]:
        match = re.search(rb"return (\d+)( \+ 1)?;", compiled)
        assert match is not None
        value = int(match[1]) + bool(match[2])
        return (Outcome(b"", b"", Exited(value), TreeSnapshot()), expected[1])

    def integrity_check(
        _inputs: IntegrityInputs,
        snapshot: ProjectSnapshot,
        result: Verification,
    ) -> IntegrityReport:
        checked.append(snapshot)
        assert snapshot in snapshots
        assert all(
            check.tested_executable == preprocess(dict(snapshot.files)["src/program.c"])
            for check in result.checks
        )
        return IntegrityReport(True, {}, 0, 4, (), (), ())

    feedback_calls = []

    def feedback(
        _binary: Path,
        _program: Program,
        result: Verification,
        _cases: tuple[Invocation, ...],
        _expected: tuple[Outcome, ...],
        _images: dict[str, str],
    ) -> str:
        feedback_calls.append(result)
        assert result.passed_cases == frozenset({1})
        assert all(check.differences[0] == ("termination",) for check in result.checks)
        return "The line-sensitive return value differs."

    monkeypatch.setattr(verify, "build_project", build)
    monkeypatch.setattr(verify, "run_cases", observations)
    monkeypatch.setattr(IntegrityInputs, "check", integrity_check)
    monkeypatch.setattr(pipeline, "feedback", feedback)
    usage = Usage(1, 0, 1)
    provider = Mock()
    provider.name = "synthetic"
    provider.maximum_usage.return_value = usage
    provider.complete.side_effect = [
        Completion(
            json.dumps(
                {
                    "declarations": "",
                    "functions": {
                        "0x0": {
                            "signature": "int main(void)",
                            "body": body,
                            "evidence": "Fixture",
                        },
                        "0x1": {
                            "signature": "int other(void)",
                            "body": "return 0;",
                            "evidence": "Fixture",
                        },
                    },
                }
            ),
            usage,
            Model.SOL,
        )
        for body in ("return __LINE__;", "return __LINE__ + 1;")
    ]
    settings = pipeline.Settings(
        {"amd64": "synthetic", "arm64": "synthetic"},
        0,
        tmp_path,
        tmp_path,
        repairs,
        False,
        {},
    )
    run = tmp_path / "original"
    ledger = Ledger(run)
    args = ("fixture", binary, metadata, settings, ledger, provider)
    result = pipeline.reconstruct(run, *args, started=time())
    delivered = snapshot_project(result.project)
    report = json.loads((result.project / "phoenix_report.json").read_text())
    passed = expected_exit == 9 or repairs == 1
    assert result.development_passed is passed
    assert report["development_behavior_passed"] is passed
    assert report["dev_cases_matched_on_all_builds"] == (2 if passed else 1)
    assert [item["confidence"] for item in report["functions"]] == [
        "tested" if passed else "unverified",
        "tested",
    ]
    assert delivered == snapshots[-1] == checked[-1]
    assert report["project_sha256"] == sha256(delivered.archive).hexdigest()
    source = dict(delivered.files)["src/program.c"]
    assert source.count(b"PHOENIX-UNVERIFIED") == 2
    assert b"return 9" in preprocess(source)
    assert provider.complete.call_count == 1 + repairs
    assert len(feedback_calls) == repairs
    if repairs:
        assert "line-sensitive" in provider.complete.call_args.args[0].prompt
        feedback_path = run / "fixture/repair/round-00/feedback.json"
        feedback_path.write_text(json.dumps("Stale feedback must not be used."))

    calls = len(snapshots)
    resumed = pipeline.reconstruct(run, *args, started=time())
    assert snapshot_project(resumed.project) == delivered
    assert len(snapshots) == calls
    assert provider.complete.call_count == 1 + repairs
    replayed = pipeline.reconstruct(
        tmp_path / "replay", *args, started=time(), replay=True
    )
    assert snapshot_project(replayed.project) == delivered
    assert replayed.development_passed is passed
    assert provider.complete.call_count == 1 + repairs


def test_package_keeps_return_line_eight(tmp_path: Path) -> None:
    candidate = Candidate(
        "", (Definition(0, "int main(void)", "return __LINE__;", "Fixture"),)
    )
    tested = tmp_path / "tested"
    write_project(tested, candidate)
    snapshot = snapshot_project(tested)
    compiled = preprocess(dict(snapshot.files)["src/program.c"])
    assert b"return 8;" in compiled
    program = Program(
        0,
        0,
        0,
        0,
        (Function(0, "main", "main", ((0, 1),), "", "int main(void)"),),
        (),
        (),
    )
    outcome = Outcome(b"", b"", Exited(8), TreeSnapshot())
    checks = tuple(
        Check(
            BuildResult(engine, compiler, tmp_path / f"{engine}-{compiler}.elf", 0, ""),
            (outcome,),
            ((),),
            compiled,
        )
        for engine, compiler in BUILD_CONFIGURATIONS
    )
    packaged = tmp_path / "packaged"
    package_project(
        packaged,
        program,
        candidate,
        snapshot,
        frozenset({0}),
        Verification(checks, 1),
        None,
        {"run_id": "synthetic"},
    )
    assert snapshot_project(packaged) == snapshot
    assert b"return 8;" in preprocess((packaged / "src/program.c").read_bytes())
    report = json.loads((packaged / "phoenix_report.json").read_text())
    assert report["functions"][0]["confidence"] == "tested"
    assert all(
        build["executable_sha256"] == sha256(compiled).hexdigest()
        for build in report["builds"]
    )
