import hashlib
import json
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval import dev_corpus as dc
from phoenix_eval.case import CaseFailure, FailureKind, Invocation
from phoenix_eval.docker import Engine, WorkerError
from phoenix_eval.outcome import Exited, Outcome, Signaled, TreeSnapshot
from phoenix_eval.wire import encode_invocation, encode_result


def outcome(*, stdout: bytes = b"ok", stderr: bytes = b"", code: int = 0) -> Outcome:
    return Outcome(stdout, stderr, Exited(code), TreeSnapshot())


def observation(label: str, cases: tuple[Outcome | CaseFailure, ...]) -> dc.Observation:
    return dc.Observation(label, "a" * 64, (cases, cases, cases))


@pytest.mark.parametrize(
    "excluded,passed", [(0, True), (5, True), (6, False), (100, False)]
)
def test_exact_exclusion_boundary(excluded: int, passed: bool) -> None:
    base = (outcome(),) * 100
    changed = (outcome(stdout=b"changed"),) * excluded + base[excluded:]
    result = dc.assess((observation("base", base), observation("other", changed)), 100)
    assert result["excluded"] == list(range(excluded))
    assert result["excluded_count"] == excluded
    assert result["passed"] is passed
    assert len(result["failures"]) == excluded  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changed",
    [
        outcome(stdout=b"ok\n"),
        outcome(stderr=b"error"),
        outcome(code=2),
        replace(outcome(), termination=Signaled(11)),
        replace(outcome(), tree=TreeSnapshot(0o700)),
    ],
)
def test_each_outcome_field_and_each_repeat_must_match(changed: Outcome) -> None:
    base = (outcome(),) * 100
    third = (changed, *base[1:])
    runs = (dc.Observation("run", "a" * 64, (base, base, third)),)
    result = dc.assess(runs, 100)
    assert result["excluded"] == [0]
    failure = result["failures"]["0"]  # type: ignore[index]
    assert failure["reasons"] == ["outcome_difference"]
    assert failure["observations"][2]["repeat"] == 2


@pytest.mark.parametrize(
    "message",
    [
        b"AddressSanitizer: heap-buffer-overflow",
        b"UndefinedBehaviorSanitizer: error",
        b"file.c:10: runtime error: signed integer overflow",
        b"LeakSanitizer: error",
    ],
)
def test_identical_sanitizer_errors_are_excluded(message: bytes) -> None:
    cases = (outcome(stderr=message),) + (outcome(),) * 99
    result = dc.assess((observation("sanitizer", cases),), 100)
    assert result["excluded"] == [0]
    assert result["passed"] is True


def test_program_diagnostic_is_not_a_sanitizer_report() -> None:
    for message in (
        b"runtime error: invalid record",
        b"failed to allocate 999999999999 bytes",
    ):
        cases = (outcome(stderr=message, code=1),) * 100
        result = dc.assess(
            tuple(observation(label, cases) for label in sorted(dc._REQUIRED_RUNS)), 100
        )
        assert result["excluded"] == []
        assert result["passed"] is True


def test_worker_failure_is_not_a_successful_case_exclusion() -> None:
    cases = (CaseFailure(FailureKind.LAUNCH, "denied"),) + (outcome(),) * 99
    result = dc.assess((observation("worker", cases),), 100)
    assert result["excluded"] == [0]
    assert result["passed"] is False
    assert result["errors"] == ["worker: launch: denied"]


def test_missing_sanitizer_runtime_is_preserved() -> None:
    failure = outcome(
        stderr=b"/program: error while loading shared libraries: libasan.so.8", code=127
    )
    result = dc.assess((observation("sanitizer", (failure,) * 100),), 100)
    assert result["excluded_count"] == 100
    assert result["passed"] is False
    assert "libasan.so.8" in str(result["errors"])


def test_missing_repeats_cannot_validate() -> None:
    with pytest.raises(ValueError, match="three complete repeats"):
        dc.assess((dc.Observation("missing", "a" * 64, ((outcome(),),)),), 1)


@pytest.fixture
def program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    target = repo / "corpus_dev/checksample"
    (target / "src").mkdir(parents=True)
    (target / "holdout").mkdir()
    (target / "src/main.c").write_text("int main(void) { return 0; }\n")
    (target / "meta.json").write_text(
        json.dumps(
            {
                "name": "checksample",
                "tier": "D0",
                "category": "synthetic",
            }
        )
    )
    (target / "holdout/cases.jsonl").write_text(
        (encode_invocation(Invocation()) + "\n") * 100
    )
    (repo / "tools.lock").write_text("source_date_epoch = 1794268800\n")
    (repo / "phoenix_eval").mkdir()
    (repo / "phoenix_eval/worker.py").write_text("# Synthetic worker identity.\n")
    for name in dc._VALIDATION_PATHS:
        path = repo / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic dependency\n")
    monkeypatch.setattr(dc, "REPO", repo)
    monkeypatch.setattr(dc, "_oracle_errors", Mock(return_value=[]))
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    return target


def binary_file(program: Path) -> dc.DevBinary:
    data = b"synthetic binary; never execute on the host"
    binary = dc.DevBinary(
        "checksample",
        "D0",
        "gcc",
        ("-std=c11", "-O0", "-lm"),
        hashlib.sha256(data).hexdigest(),
        "synthetic",
        False,
    )
    destination = program.parents[2] / "dev_bin/checksample/gcc-O0/checksample"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    return binary


def validate_mock(program: Path, monkeypatch: pytest.MonkeyPatch) -> dc.DevBinary:
    binary = binary_file(program)
    monkeypatch.setattr(dc, "compile_source", Mock(return_value={"program": b"build"}))
    monkeypatch.setattr(
        dc, "run_cases", Mock(side_effect=lambda b, c, e, **kw: (outcome(),) * len(c))
    )
    assert dc.validate_program(
        program,
        program.parents[2],
        (binary,),
        1,
        {"amd64": "image-amd64", "arm64": "image-arm64"},
    )
    return binary


def test_validation_uses_all_builds_runners_and_repeats(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = validate_mock(program, monkeypatch)
    builds = dc.compile_source.call_args_list  # type: ignore[attr-defined]
    assert len(builds) == 5
    assert {(call.args[1], call.args[3].platform) for call in builds[:4]} == {
        (cc, arch) for cc in dc.COMPILERS for arch in ("amd64", "arm64")
    }
    assert all(
        call.args[2][: len(dc.CANONICAL_FLAGS)] == dc.CANONICAL_FLAGS for call in builds
    )
    assert builds[-1].args[2][-1] == "-fsanitize=address,undefined"
    assert dc.run_cases.call_count == 27  # type: ignore[attr-defined]
    loaded = dc.load_validated_cases(program.parent, program.parents[2], binary)
    assert loaded.total == len(loaded.cases) == 100
    assert loaded.excluded == ()


def test_heldout_hash_requires_current_validation(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = validate_mock(program, monkeypatch)
    digest = dc.heldout_hash(program.parent, program.parents[2], (binary,))
    assert len(digest) == 64
    assert digest == dc.heldout_hash(program.parent, program.parents[2], (binary,))
    (program / "src/main.c").write_text("int main(void) { return 1; }\n")
    with pytest.raises(ValueError, match="stale"):
        dc.heldout_hash(program.parent, program.parents[2], (binary,))


def test_other_tiers_need_200_cases(program: Path) -> None:
    path = program / "meta.json"
    meta = json.loads(path.read_text())
    meta["tier"] = "D1"
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="at least 200"):
        dc._cases(program)


@pytest.mark.parametrize(
    "changed", ["source", "cases", "binary", "tools", "validator", "metadata"]
)
def test_stale_records_cannot_pass(
    program: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    binary = validate_mock(program, monkeypatch)
    path = {
        "source": program / "src/main.c",
        "cases": program / "holdout/cases.jsonl",
        "binary": dc.binary_path(program.parents[2], binary),
        "tools": dc.REPO / "tools.lock",
        "validator": dc.REPO / "phoenix_eval/worker.py",
        "metadata": program / "meta.json",
    }[changed]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="stale|changed"):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


def test_failed_build_is_recorded_and_cannot_pass(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = binary_file(program)
    monkeypatch.setattr(
        dc, "compile_source", Mock(side_effect=WorkerError("compiler error"))
    )
    monkeypatch.setattr(
        dc, "run_cases", Mock(side_effect=lambda b, c, e, **kw: (outcome(),) * len(c))
    )
    assert not dc.validate_program(
        program,
        program.parents[2],
        (binary,),
        1,
        {"amd64": "image-amd64", "arm64": "image-arm64"},
    )
    record = json.loads((program / "holdout/excluded.json").read_text())["binaries"][
        binary.key
    ]
    assert len(record["errors"]) == 5
    assert record["excluded_count"] == 0
    with pytest.raises(ValueError, match="validation failed"):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


@pytest.mark.parametrize(
    "field,value",
    [
        ("excluded", [100]),
        ("excluded", [False]),
        ("excluded", [0, 0]),
        ("excluded", list(range(6))),
        ("excluded_count", 1),
        ("runs", []),
        ("passed", False),
    ],
)
def test_loader_rejects_invalid_validation(
    program: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    binary = validate_mock(program, monkeypatch)
    path = program / "holdout/excluded.json"
    record = json.loads(path.read_text())
    record["binaries"][binary.key][field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


def test_loader_rejects_summary_that_keeps_hidden_failure_records(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = validate_mock(program, monkeypatch)
    path = program / "holdout/excluded.json"
    record = json.loads(path.read_text())
    entry = record["binaries"][binary.key]
    entry["failures"] = {
        str(i): {"reasons": ["outcome_difference"], "observations": []}
        for i in range(6)
    }
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="contradicts"):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


def test_loader_rechecks_excluded_observations(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = validate_mock(program, monkeypatch)
    path = program / "holdout/excluded.json"
    record = json.loads(path.read_text())
    entry = record["binaries"][binary.key]
    entry.update(
        excluded=[0],
        excluded_count=1,
        failures={
            "0": {
                "reasons": ["outcome_difference"],
                "observations": [
                    {
                        "run": run["label"],
                        "repeat": repeat,
                        "result": json.loads(encode_result(outcome())),
                    }
                    for run in entry["runs"]
                    for repeat in range(3)
                ],
            }
        },
    )
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="contradict"):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


def test_valid_exclusion_record_returns_only_valid_cases(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = binary_file(program)
    monkeypatch.setattr(dc, "compile_source", Mock(return_value={"program": b"build"}))

    def run(
        binary: bytes, cases: tuple[Invocation, ...], engine: Engine, **_: object
    ) -> tuple[Outcome, ...]:
        return (
            outcome(stdout=b"different" if engine is Engine.QEMU_X86_64 else b"ok"),
        ) + (outcome(),) * (len(cases) - 1)

    monkeypatch.setattr(dc, "run_cases", run)
    assert dc.validate_program(
        program,
        program.parents[2],
        (binary,),
        1,
        {"amd64": "image-amd64", "arm64": "image-arm64"},
    )
    loaded = dc.load_validated_cases(program.parent, program.parents[2], binary)
    assert loaded.excluded == (0,)
    assert loaded.indices == tuple(range(1, 100))
    assert len(loaded.cases) == 99


def test_worker_error_cannot_become_an_accepted_exclusion(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = validate_mock(program, monkeypatch)
    path = program / "holdout/excluded.json"
    record = json.loads(path.read_text())
    entry = record["binaries"][binary.key]
    samples = tuple(
        dc.Observation(
            run["label"],
            run["sha256"],
            tuple(
                (
                    (
                        CaseFailure(FailureKind.LAUNCH, "denied")
                        if index == 0 and repeat == 0
                        else outcome()
                    ),
                )
                + (outcome(),) * 99
                for repeat in range(3)
            ),
        )
        for index, run in enumerate(entry["runs"])
    )
    assessed = dc.assess(samples, 100)
    assert assessed["passed"] is False
    assert assessed["errors"]
    entry.update(assessed, passed=True, errors=[])
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="contradict"):
        dc.load_validated_cases(program.parent, program.parents[2], binary)


def test_stale_worker_image_cannot_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    def inspect(
        command: tuple[str, ...], **_: object
    ) -> subprocess.CompletedProcess[str]:
        fmt = next(item for item in command if ".Id" in item)
        lines = [
            f"sha256:{char * 64} {'0' * 64}"
            if "org.phoenix.worker-source-sha256" in fmt
            else f"{arch} sha256:{char * 64}"
            for arch, char in (("amd64", "a"), ("arm64", "b"))
        ]
        return subprocess.CompletedProcess(command, 0, "\n".join(lines) + "\n", "")

    monkeypatch.setattr(subprocess, "run", inspect)
    with pytest.raises(WorkerError, match="Rebuild"):
        dc._images(True)


def test_manifest_keeps_invalid_twins_and_checks_binary_hash(program: Path) -> None:
    binary = binary_file(program)
    workspace = program.parents[2]
    manifest = workspace / "dev_bin/manifest.json"
    manifest.write_text(json.dumps({"binaries": [asdict(binary)]}))
    assert dc.read_manifest(manifest) == (binary,)
    assert len(dc.corpus_hash(workspace, (binary,))) == 64
    assert dc.binary_path(workspace, binary).read_bytes()
    with pytest.raises(ValueError):
        dc.binary_path(workspace, replace(binary, sha256="0" * 64))
    manifest.write_text(json.dumps({"binaries": [asdict(binary), asdict(binary)]}))
    with pytest.raises(ValueError, match="repeats"):
        dc.read_manifest(manifest)


def test_worker_errors_retry_once_and_preserve_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Mock(side_effect=WorkerError("worker unavailable"))
    monkeypatch.setattr(dc, "run_cases", runner)
    observed = dc._observe(
        "unavailable", b"binary", (Invocation(),), Engine.ARM64, "image"
    )
    assert runner.call_count == 6
    assert dc.assess((observed,), 1)["passed"] is False


def test_matrix_keeps_invalid_twin_and_compiler_error_is_fatal(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dc, "_images", Mock(return_value={"amd64": "image-amd64"}))
    outputs = {
        "program": b"binary",
        "program.twin": b"twin",
        "text": b"a",
        "text.twin": b"b",
    }
    build = Mock(return_value=outputs)
    monkeypatch.setattr(dc, "compile_source", build)
    assert dc.main(["checksample"]) == 0
    manifest = program.parents[2] / "dev_bin/manifest.json"
    entries = dc.read_manifest(manifest)
    assert len(entries) == 8
    assert not any(entry.twin_valid for entry in entries)
    assert {(entry.compiler, entry.level) for entry in entries} == {
        (cc, level) for cc in dc.COMPILERS for level in dc.LEVELS
    }
    assert all(call.kwargs["twin"] for call in build.call_args_list)
    build.side_effect = WorkerError("compiler error")
    assert dc.main(["checksample"]) == 1
    assert dc.read_manifest(manifest) == ()


def test_incomplete_corpus_and_failed_validation_cannot_pass(
    program: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dc, "_images", Mock(return_value={"amd64": "image"}))
    monkeypatch.setattr(dc, "verify_runtime", Mock())
    monkeypatch.setattr(
        dc,
        "compile_source",
        Mock(
            return_value={
                "program": b"binary",
                "program.twin": b"twin",
                "text": b"x",
                "text.twin": b"x",
            }
        ),
    )
    validate = Mock(return_value=False)
    monkeypatch.setattr(dc, "validate_program", validate)
    assert dc.main(["--check", "checksample"]) == 1
    assert len(dc.read_manifest(program.parents[2] / "dev_bin/manifest.json")) == 8
    validate.assert_called_once()
    assert dc.main([]) == 1


def test_compiler_failure_cannot_emit_an_old_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Mock(
        return_value=subprocess.CompletedProcess((), 1, b"", b"compile failed")
    )
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(WorkerError, match="compile failed"):
        dc.compile_source(
            (("src/main.c", b"bad C"),),
            "gcc",
            ("-std=c11", "-O0"),
            Engine.ROSETTA,
            1794268800,
            "pinned-image",
            twin=True,
        )
    command = runner.call_args.args[0]
    assert "--platform=linux/amd64" in command
    assert "--network=none" in command
    assert "--env=SOURCE_DATE_EPOCH=1794268800" in command
    assert "--entrypoint=/bin/sh" in command
    assert "pinned-image" in command
