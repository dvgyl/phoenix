from dataclasses import replace
from pathlib import Path

import pytest

import phoenix.analyze as stage
from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.coverage import BlockInventory
from phoenix_eval.docker import Engine, WorkerError
from phoenix_eval.outcome import EntryKind, Exited, Outcome, TreeEntry, TreeSnapshot
from phoenix_eval.trace import CodeTrace

IMAGES = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
BLOCKS = frozenset((0x1000, 0x1004, 0x1008))
INVENTORY = BlockInventory(0x1000, 0x1000, BLOCKS, BLOCKS)
BASE_TRACE = CodeTrace(0x2000, 0x2010, (0x2000,))
BASE_OUTCOME = Outcome(b"stdout", b"stderr", Exited(3), TreeSnapshot())


def test_analysis_selects_matched_inputs_and_mutation_gains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "program"
    binary.write_bytes(b"\0--extra\0Usage: program [--mode]\0")
    calls: list[tuple[Engine, bool, Invocation]] = []
    original_file = b"alpha,1\nbeta,2\n"
    output = TreeEntry("result", EntryKind.FILE, 0o600, b"bytes")
    tree = TreeSnapshot(entries=(output,))

    def inspect(path: Path, image: str) -> BlockInventory:
        assert path == binary and image == IMAGES["amd64"]
        return INVENTORY

    def run(
        path: Path,
        cases: tuple[Invocation, ...],
        engine: Engine,
        *,
        trace: bool,
        image: str,
    ) -> tuple[CaseResult, ...]:
        assert path == binary and image == IMAGES[engine.platform]
        assert 0 < len(cases) <= 3
        results: list[CaseResult] = []
        for case in cases:
            calls.append((engine, trace, case))
            outcome = replace(BASE_OUTCOME, tree=tree)
            if case.args == ("--version",):
                results.append(CaseFailure(FailureKind.TIMEOUT, "Timeout."))
                continue
            if case.args == ("0",) and engine is Engine.QEMU_X86_64:
                other = replace(output, mode=0o644)
                outcome = replace(outcome, tree=TreeSnapshot(entries=(other,)))
            if trace:
                hits = BASE_TRACE.hits
                if case.args == ("sample", "1"):
                    outcome = replace(outcome, stderr=b"Trace changed stderr.")
                if case.args == ("--extra",):
                    hits = (0x2004,)
                if case.args == ("--mode",):
                    hits = (0x2000, 0x2004)
                if case.tree.entries and case.tree.entries[0].data != original_file:
                    hits = (0x2000, 0x2008)
                outcome = replace(outcome, trace=replace(BASE_TRACE, hits=hits))
            results.append(outcome)
        return tuple(results)

    monkeypatch.setattr(stage, "inspect_x86", inspect)
    monkeypatch.setattr(stage, "run_batch", run)
    monkeypatch.setattr(stage, "MAX_BATCH", 3)

    result = stage.analyze(binary, IMAGES, seed=42)
    replay_calls = calls.copy()
    calls.clear()
    replay = stage.analyze(binary, IMAGES, seed=42)
    assert calls == replay_calls
    assert result == replay
    assert [case.expected.trace for case in result.cases] == [
        case.expected.trace for case in replay.cases
    ]

    empty, argv, text, raw, file, mode, mutated_file = result.cases
    assert empty.invocation == Invocation()
    assert argv.invocation.args == ("--help",)
    assert text.invocation.stdin == original_file
    assert b"\0" in raw.invocation.stdin
    (entry,) = file.invocation.tree.entries
    (mutated_entry,) = mutated_file.invocation.tree.entries
    assert file.invocation.args == mutated_file.invocation.args == (entry.path,)
    assert entry.data != mutated_entry.data
    assert replace(mutated_entry, data=entry.data) == entry
    assert mode.invocation.args == ("--mode",)
    probed = {case for _, _, case in calls}
    assert any(
        case != text.invocation
        and replace(case, stdin=original_file) == text.invocation
        and len(case.stdin) == len(original_file)
        for case in probed
    )
    assert all(
        case.expected == replace(BASE_OUTCOME, tree=tree) for case in result.cases
    )
    assert empty.expected.trace == BASE_TRACE
    assert mutated_file.expected.trace == replace(BASE_TRACE, hits=(0x2000, 0x2008))
    assert result.covered_blocks == 3
    assert result.recovered_blocks == 3
    assert result.candidate_count == len(probed) == 16
    assert result.emulator_sensitive == 1
    assert result.invalid_candidates == 3


@pytest.mark.parametrize(
    ("problem", "error", "message"),
    (
        ("timeout", ValueError, "no valid"),
        ("missing-trace", WorkerError, "trace state"),
        ("worker-error", WorkerError, "protocol failed"),
        ("late-worker-error", WorkerError, "protocol failed"),
        ("short-response", WorkerError, "wrong result count"),
    ),
)
def test_analysis_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
    error: type[Exception],
    message: str,
) -> None:
    binary = tmp_path / "program"
    binary.touch()

    def run(
        _binary: Path,
        cases: tuple[Invocation, ...],
        _engine: Engine,
        *,
        trace: bool,
        image: str,
    ) -> tuple[CaseResult, ...]:
        if problem == "timeout":
            return (CaseFailure(FailureKind.TIMEOUT, "Timeout."),) * len(cases)
        if trace and problem == "worker-error":
            raise WorkerError("The worker protocol failed.")
        if trace and problem == "short-response":
            return ()
        if problem == "late-worker-error":
            if trace and any(case.args == ("--help",) and case.stdin for case in cases):
                raise WorkerError("The worker protocol failed.")
            outcome = replace(BASE_OUTCOME, trace=BASE_TRACE) if trace else BASE_OUTCOME
            return (outcome,) * len(cases)
        return (BASE_OUTCOME,) * len(cases)

    monkeypatch.setattr(stage, "inspect_x86", lambda *_: INVENTORY)
    monkeypatch.setattr(stage, "run_batch", run)
    with pytest.raises(error, match=message):
        stage.analyze(binary, IMAGES, seed=0)


@pytest.mark.parametrize("images", ({}, {**IMAGES, "amd64": "phoenix-worker:amd64"}))
def test_analysis_requires_pinned_images(
    tmp_path: Path, images: dict[str, str]
) -> None:
    with pytest.raises(ValueError, match="pinned amd64"):
        stage.analyze(tmp_path / "unused", images, seed=0)
