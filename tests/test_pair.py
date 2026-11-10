import json
import platform
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from phoenix_eval import pair
from phoenix_eval.build import BuildResult, ProjectSnapshot, snapshot_project
from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.coverage import BlockInventory
from phoenix_eval.docker import MAX_BATCH, Engine, WorkerError
from phoenix_eval.outcome import EntryKind, Exited, Outcome, TreeEntry, TreeSnapshot
from phoenix_eval.toolchain import Compiler
from phoenix_eval.trace import CodeTrace
from phoenix_eval.worker import MAX_PROGRAM_BYTES

IMAGES = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
MARKER = "private-synthetic-marker"
BASELINE = Outcome(
    b"expected output", b"expected diagnostic", Exited(3), TreeSnapshot()
)
TRACE = CodeTrace(0x5000, 0x5100, (0x5010, 0x5020, 0x5028))
ARTIFACTS = ("amd64-gcc.elf", "amd64-clang.elf", "arm64-gcc.elf", "arm64-clang.elf")


class FakeWorker:
    def __init__(self, tmp_path: Path) -> None:
        self.original = tmp_path / f"{MARKER}-original"
        self.project = tmp_path / f"{MARKER}-project"
        self.build_directory = tmp_path / f"{MARKER}-builds"
        self.original_bytes = self.original.name.encode()
        self.original.write_bytes(self.original_bytes)
        (self.project / "src").mkdir(parents=True)
        (self.project / "CMakeLists.txt").write_bytes(
            b"add_executable(program src/main.c)"
        )
        self.source = self.project / "src/main.c"
        self.source.write_bytes(b"int main(void) { return 0; }")
        self.snapshot = snapshot_project(self.project)
        self.cases = tuple(
            Invocation(
                (f"{MARKER}-arg-{index}",),
                stdin=f"{MARKER}-stdin-{index}".encode(),
                tree=TreeSnapshot(
                    entries=(TreeEntry(MARKER, EntryKind.FILE, 0o600, MARKER.encode()),)
                ),
                overlay=(("TEST_LABEL", MARKER),),
            )
            for index in range(4)
        )
        self.outcomes: dict[tuple[str, Engine, bool, Invocation], CaseResult] = {}
        self.calls: list[tuple[str, Engine, bool, tuple[Invocation, ...]]] = []
        self.failed_builds: set[str] = set()
        self.worker_errors: set[str] = set()
        self.truncated_results: set[str] = set()
        self.built: list[tuple[str, Engine, Compiler]] = []

    def inspect_x86(self, binary: bytes, image: str) -> BlockInventory:
        assert binary == self.original_bytes
        assert image == IMAGES["amd64"]
        return BlockInventory(
            entry=0x1010,
            link_start=0x1000,
            sites=frozenset({0x1010, 0x1020, 0x1028, 0x1030}),
            blocks=frozenset({0x1010, 0x1020, 0x1030}),
        )

    def run_cases(
        self,
        binary: bytes,
        cases: tuple[Invocation, ...],
        engine: Engine,
        *,
        trace: bool,
        image: str,
    ) -> tuple[CaseResult, ...]:
        assert image == IMAGES[engine.platform]
        name = binary.decode("ascii")
        if trace:
            assert binary == self.original_bytes and engine is Engine.QEMU_X86_64
        self.calls.append((name, engine, trace, cases))
        if name in self.worker_errors:
            raise WorkerError(f"{MARKER}: {cases!r}")
        if name in self.truncated_results:
            return ()
        default = replace(BASELINE, trace=TRACE) if trace else BASELINE
        return tuple(
            self.outcomes.get((name, engine, trace, case), default) for case in cases
        )

    def build_project(
        self,
        project: ProjectSnapshot,
        destination: Path,
        engine: Engine,
        compiler: Compiler,
        *,
        image: str,
    ) -> BuildResult:
        assert project == self.snapshot
        assert image == IMAGES[engine.platform]
        self.built.append((destination.name, engine, compiler))
        if destination.name in self.failed_builds:
            return BuildResult(engine, compiler, None, 2, MARKER)
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(destination.name.encode())
        return BuildResult(engine, compiler, destination, 1, MARKER)

    def evaluate(self, cases: tuple[Invocation, ...] | None = None) -> pair.PairReport:
        return pair.evaluate_pair(
            self.original,
            self.project,
            self.cases if cases is None else cases,
            self.build_directory,
            IMAGES,
        )


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeWorker:
    fake = FakeWorker(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setattr(pair, "run_cases", fake.run_cases)
    monkeypatch.setattr(pair, "inspect_x86", fake.inspect_x86)
    monkeypatch.setattr(pair, "build_project", fake.build_project)
    return fake


def test_excludes_emulator_disagreement_and_counts_block_entries(
    worker: FakeWorker,
) -> None:
    excluded, *eligible = worker.cases
    original = worker.original.name
    worker.outcomes[original, Engine.QEMU_X86_64, False, excluded] = replace(
        BASELINE, stdout=b"different emulator output"
    )
    report = worker.evaluate()
    assert report.behavior_passed
    assert report.total_cases == 4
    assert report.eligible_cases == 3
    assert report.emulator_disagreements == 1
    assert report.evaluation_errors == 0
    assert (report.covered_blocks, report.recovered_blocks) == (2, 3)
    assert (original, Engine.ROSETTA, False, worker.cases) in worker.calls
    assert (original, Engine.QEMU_X86_64, False, worker.cases) in worker.calls
    assert (original, Engine.QEMU_X86_64, True, tuple(eligible)) in worker.calls
    assert [build.matched_cases for build in report.builds] == [3] * 4
    assert {item.name for item in worker.build_directory.iterdir()} == set(ARTIFACTS)
    assert all(
        cases == tuple(eligible)
        for name, _, _, cases in worker.calls
        if name != original
    )


@pytest.mark.parametrize(
    ("observation", "category"),
    [
        (BASELINE, "missing_trace"),
        (
            replace(BASELINE, trace=CodeTrace(0x5000, 0x5100, (0x5030,))),
            "trace_missed_entry",
        ),
        (replace(BASELINE, stderr=b"changed", trace=TRACE), "traced_behavior_changed"),
        (CaseFailure(FailureKind.TRACE, MARKER), "sandbox_trace"),
        (cast(CaseResult, {"private": MARKER}), "malformed_result"),
    ],
)
def test_trace_error_excludes_case_and_fails_pair(
    worker: FakeWorker, observation: CaseResult, category: str
) -> None:
    worker.outcomes[worker.original.name, Engine.QEMU_X86_64, True, worker.cases[0]] = (
        observation
    )
    report = worker.evaluate()
    assert not report.behavior_passed
    assert report.eligible_cases == 3
    assert report.emulator_disagreements == 0
    assert report.evaluation_errors == 1
    assert report.original_error_categories == {category: 1}
    assert report.covered_blocks == 2
    assert [build.matched_cases for build in report.builds] == [3] * 4


@pytest.mark.parametrize("empty", [True, False])
def test_no_eligible_cases_cannot_pass(worker: FakeWorker, empty: bool) -> None:
    cases = () if empty else worker.cases
    for case in cases:
        for engine in (Engine.ROSETTA, Engine.QEMU_X86_64):
            worker.outcomes[worker.original.name, engine, False, case] = CaseFailure(
                FailureKind.LIMIT, MARKER
            )
    report = worker.evaluate(cases)
    assert not report.behavior_passed
    assert report.eligible_cases == report.emulator_disagreements == 0
    assert report.evaluation_errors == len(cases)
    assert report.original_error_categories == ({} if empty else {"sandbox_limit": 4})
    assert all(
        name == worker.original.name and not traced
        for name, _, traced, _ in worker.calls
    )


def test_qemu_failure_is_not_an_emulator_disagreement(worker: FakeWorker) -> None:
    worker.outcomes[
        worker.original.name, Engine.QEMU_X86_64, False, worker.cases[0]
    ] = CaseFailure(FailureKind.LAUNCH, MARKER)
    report = worker.evaluate()
    assert not report.behavior_passed
    assert report.eligible_cases == 3
    assert report.emulator_disagreements == 0
    assert report.evaluation_errors == 1
    assert report.original_error_categories == {"sandbox_launch": 1}


def test_duplicate_invocations_count_across_batches(worker: FakeWorker) -> None:
    cases = (worker.cases[0],) * 17
    report = worker.evaluate(cases)
    assert report.behavior_passed
    assert report.eligible_cases == 17
    assert [build.matched_cases for build in report.builds] == [17] * 4
    assert (report.covered_blocks, report.recovered_blocks) == (2, 3)


@pytest.mark.parametrize("from_paths", [True, False])
def test_pair_uses_captured_inputs_across_all_builds_and_batches(
    worker: FakeWorker, monkeypatch: pytest.MonkeyPatch, from_paths: bool
) -> None:
    def inspect(binary: bytes, image: str) -> BlockInventory:
        worker.original.write_bytes(b"edited before the first worker")
        return worker.inspect_x86(binary, image)

    def build(
        project: ProjectSnapshot,
        destination: Path,
        engine: Engine,
        compiler: Compiler,
        *,
        image: str,
    ) -> BuildResult:
        worker.source.write_bytes(b"edited before a later build")
        return worker.build_project(project, destination, engine, compiler, image=image)

    observed: dict[str, list[bytes]] = {name: [] for name in ARTIFACTS}

    def run(
        binary: bytes,
        cases: tuple[Invocation, ...],
        engine: Engine,
        *,
        trace: bool,
        image: str,
    ) -> tuple[CaseResult, ...]:
        if binary == worker.original_bytes:
            worker.original.write_bytes(b"edited between workers")
        else:
            name = binary.decode("ascii")
            observed[name].append(binary)
            (worker.build_directory / name).write_bytes(b"edited between batches")
        return worker.run_cases(binary, cases, engine, trace=trace, image=image)

    monkeypatch.setattr(pair, "inspect_x86", inspect)
    monkeypatch.setattr(pair, "build_project", build)
    monkeypatch.setattr(pair, "run_cases", run)
    if not from_paths:
        worker.original.unlink()
        worker.source.unlink()

    cases = (worker.cases[0],) * (MAX_BATCH + 1)
    report = pair.evaluate_pair(
        worker.original if from_paths else worker.original_bytes,
        worker.project if from_paths else worker.snapshot,
        cases,
        worker.build_directory,
        IMAGES,
    )

    assert report.behavior_passed
    assert report.eligible_cases == len(cases)
    original_calls = [call for call in worker.calls if call[0] == worker.original.name]
    assert len(original_calls) == 6
    for artifact, report_build in zip(ARTIFACTS, report.builds, strict=True):
        first, second = observed[artifact]
        assert first == second == artifact.encode()
        assert report_build.executable_sha256 == sha256(first).hexdigest()
        assert (worker.build_directory / artifact).read_bytes() != first


def test_pair_rejects_an_oversize_original_path(worker: FakeWorker) -> None:
    with worker.original.open("wb") as stream:
        stream.truncate(MAX_PROGRAM_BYTES + 1)

    report = worker.evaluate()

    assert not report.behavior_passed
    assert report.original_error_categories == {"worker_error": len(worker.cases)}
    assert worker.calls == []
    assert all(build.executable_sha256 is None for build in report.builds)


def test_pair_reports_a_source_capture_failure(worker: FakeWorker) -> None:
    worker.source.unlink()

    report = worker.evaluate()

    assert not report.behavior_passed
    assert report.eligible_cases == len(worker.cases)
    assert report.evaluation_errors == 4
    assert worker.built == []
    assert all(
        not build.compiled
        and build.executable_sha256 is None
        and build.failure_categories == {"build_error": 1}
        for build in report.builds
    )


def test_pair_reports_an_artifact_capture_failure(
    worker: FakeWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def build(
        project: ProjectSnapshot,
        destination: Path,
        engine: Engine,
        compiler: Compiler,
        *,
        image: str,
    ) -> BuildResult:
        result = worker.build_project(
            project, destination, engine, compiler, image=image
        )
        if destination.name == ARTIFACTS[0]:
            destination.unlink()
        return result

    monkeypatch.setattr(pair, "build_project", build)

    report = worker.evaluate()

    assert not report.behavior_passed
    assert report.evaluation_errors == 1
    first, *_ = report.builds
    assert first.compiled and first.executable_sha256 is None
    assert first.failure_categories == {"build_error": 1}
    assert all(name != ARTIFACTS[0] for name, _, _, _ in worker.calls)


def test_native_original_still_requires_trace(
    worker: FakeWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    report = worker.evaluate()
    assert report.behavior_passed
    calls = [call for call in worker.calls if call[0] == worker.original.name]
    assert {(engine, trace) for _, engine, trace, _ in calls} == {
        (Engine.AMD64, False),
        (Engine.QEMU_X86_64, True),
    }


def test_rejects_stale_artifact(worker: FakeWorker) -> None:
    worker.build_directory.mkdir()
    stale = worker.build_directory / ARTIFACTS[0]
    stale.write_bytes(b"stale")
    report = worker.evaluate()
    assert not report.behavior_passed
    assert not report.builds[0].compiled
    assert report.builds[0].failure_categories == {"build_error": 1}
    assert report.evaluation_errors == 1
    assert stale.read_bytes() == b"stale"
    assert all(name != stale.name for name, _, _, _ in worker.calls)


def test_counts_build_failure_and_sandbox_failure(worker: FakeWorker) -> None:
    worker.failed_builds.add("amd64-clang.elf")
    worker.outcomes["arm64-gcc.elf", Engine.ARM64, False, worker.cases[0]] = (
        CaseFailure(FailureKind.TIMEOUT, MARKER)
    )
    report = worker.evaluate()
    assert not report.behavior_passed
    assert report.evaluation_errors == 0
    _, failed, sandbox, _ = report.builds
    assert not failed.compiled
    assert failed.warnings == 2
    assert failed.matched_cases == 0
    assert failed.failure_categories == {"build_failed": 1}
    assert sandbox.compiled
    assert sandbox.matched_cases == 3
    assert sandbox.failure_categories == {"sandbox_timeout": 1}
    assert {name for name, _, _ in worker.built} == set(ARTIFACTS)
    assert {name for name, _, _, _ in worker.calls}.isdisjoint(worker.failed_builds)


def test_compares_all_outcome_fields_across_four_builds(worker: FakeWorker) -> None:
    diffs = (
        replace(BASELINE, stdout=b"stdout mismatch", stderr=b"stderr mismatch"),
        replace(BASELINE, stderr=b"stderr mismatch"),
        replace(BASELINE, termination=Exited(4)),
        replace(BASELINE, tree=TreeSnapshot(root_mode=0o700)),
    )
    engines = (Engine.ROSETTA, Engine.ROSETTA, Engine.ARM64, Engine.ARM64)
    for artifact, engine, observed in zip(ARTIFACTS, engines, diffs, strict=True):
        worker.outcomes[artifact, engine, False, worker.cases[0]] = observed
    report = worker.evaluate()
    assert not report.behavior_passed
    assert all(build.compiled and build.matched_cases == 3 for build in report.builds)
    assert [build.failure_categories for build in report.builds] == [
        {"stdout": 1, "stderr": 1},
        {"stderr": 1},
        {"termination": 1},
        {"tree": 1},
    ]


def test_worker_errors_and_malformed_batches_do_not_leak(
    worker: FakeWorker, capsys: pytest.CaptureFixture[str]
) -> None:
    worker.worker_errors.add("amd64-gcc.elf")
    worker.truncated_results.add("arm64-gcc.elf")
    worker.outcomes["arm64-clang.elf", Engine.ARM64, False, worker.cases[1]] = replace(
        BASELINE, stdout=MARKER.encode()
    )
    report = worker.evaluate()
    assert not report.behavior_passed
    assert report.evaluation_errors == 8
    assert report.builds[0].failure_categories == {"worker_error": 4}
    assert report.builds[2].failure_categories == {"malformed_result": 4}
    assert report.builds[3].failure_categories == {"stdout": 1}
    serialized = json.dumps(asdict(report))
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")
    assert set(asdict(report)) == {
        "total_cases",
        "eligible_cases",
        "emulator_disagreements",
        "evaluation_errors",
        "original_error_categories",
        "recovered_blocks",
        "covered_blocks",
        "builds",
        "behavior_passed",
    }
    assert set(asdict(report.builds[0])) == {
        "architecture",
        "compiler",
        "compiled",
        "warnings",
        "matched_cases",
        "evaluation_errors",
        "failure_categories",
        "executable_sha256",
    }
    for private in (MARKER, str(worker.build_directory), "expected output", *ARTIFACTS):
        assert private not in serialized
    assert {path.name for path in worker.build_directory.iterdir()} == set(ARTIFACTS)
