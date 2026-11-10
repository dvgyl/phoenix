import json
from pathlib import Path

import pytest

from phoenix_eval import m0
from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.docker import Engine
from phoenix_eval.outcome import Exited, Outcome, Signaled, TreeSnapshot
from phoenix_eval.toolchain import Compiler

EMPTY = Outcome(b"", b"", Exited(0), TreeSnapshot())


@pytest.mark.parametrize("mode", list(m0.Mode))
@pytest.mark.parametrize("mutants_detected", [True, False])
def test_m0_requires_valid_mutant_differences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: m0.Mode,
    mutants_detected: bool,
) -> None:
    def build(
        source: Path, output: Path, engine: Engine, compiler: Compiler, mutant: int = 0
    ) -> None:
        output.write_bytes(b"public test executable")

    def run(
        binary: Path, cases: tuple[Invocation, ...], engine: Engine
    ) -> tuple[CaseResult, ...]:
        if binary.name.startswith("runprobe-"):
            return (
                Outcome(b"/program\n", b"", Exited(0), TreeSnapshot()),
                EMPTY,
                Outcome(b"", b"", Signaled(15), TreeSnapshot()),
                Outcome(b"", b"", Exited(143), TreeSnapshot()),
                CaseFailure(FailureKind.SNAPSHOT, "FIFO"),
            )
        if "-mutant-" in binary.name:
            if mutants_detected:
                return tuple(
                    Outcome(b"different", b"", Exited(0), TreeSnapshot()) for _ in cases
                )
            return tuple(CaseFailure(FailureKind.LAUNCH, "Exec failed.") for _ in cases)
        return (EMPTY,) * len(cases)

    monkeypatch.setattr(m0, "build_public", build)
    monkeypatch.setattr(m0, "run_batch", run)
    path, passed = m0.evaluate(tmp_path, tmp_path, mode)
    report = json.loads(path.read_text())
    assert passed == mutants_detected == report["behavior_checks_passed"]
    assert report["run_id"] == path.parent.name
    assert report["self_trials"] == 3
    assert report["programs"][0]["self_match"]
    for mutation in report["programs"][0]["mutations"].values():
        assert mutation["killed"] == (5 if mutants_detected else 0)


def test_public_case_seed_is_reproducible() -> None:
    assert m0.public_programs(123) == m0.public_programs(123)
    assert m0.public_programs(123) != m0.public_programs(456)
