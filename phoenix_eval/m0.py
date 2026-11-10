import hashlib
import json
import random
import subprocess
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path
from uuid import uuid4

from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.coverage import measure_public
from phoenix_eval.docker import Engine, WorkerError, freeze_images, run_batch
from phoenix_eval.outcome import (
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
    compare,
)
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import evaluator_build
from phoenix_eval.toolchain import Compiler, build_public
from phoenix_eval.wire import encode_result

TRIALS = 3
SEED = 0x70686F656E6978


class Mode(StrEnum):
    APPLE_SILICON = "apple-silicon"
    NATIVE_AMD64 = "native-amd64"
    NATIVE_ARM64 = "native-arm64"

    @property
    def engines(self) -> tuple[Engine, ...]:
        if self is Mode.APPLE_SILICON:
            return Engine.ROSETTA, Engine.ARM64, Engine.QEMU_X86_64
        if self is Mode.NATIVE_AMD64:
            return (Engine.AMD64,)
        return (Engine.ARM64,)


@dataclass(frozen=True)
class Program:
    name: str
    cases: tuple[Invocation, ...]
    expected: tuple[Outcome, ...]
    mutants: int = 5


def _output(stdout: bytes = b"", stderr: bytes = b"", code: int = 0) -> Outcome:
    return Outcome(stdout, stderr, Exited(code), TreeSnapshot())


def _number(value: int) -> bytes:
    return f"{value}\n".encode("ascii")


def public_programs(seed: int) -> tuple[Program, ...]:
    rng = random.Random(seed)
    data = tuple(rng.randbytes(size) for size in (1, 7, 20))
    stats = Program(
        "bitstats",
        (
            Invocation(),
            Invocation(("other",)),
            Invocation(("sum",)),
            Invocation(("count",), b"\0\xff", overlay=(("PHOENIX_TAG", "test"),)),
            *(
                Invocation((operation,), sample)
                for operation in ("sum", "count")
                for sample in data
            ),
        ),
        (
            _output(stderr=b"use sum or count\n", code=3),
            _output(stderr=b"use sum or count\n", code=3),
            _output(b"0\n"),
            _output(b"2\ntest\n"),
            *(_output(_number(sum(sample))) for sample in data),
            *(_output(_number(len(sample))) for sample in data),
        ),
    )
    files = Program(
        "filemarks",
        (
            Invocation(),
            Invocation(("write",)),
            *(
                Invocation(
                    ("write",),
                    tree=TreeSnapshot(
                        entries=(TreeEntry("input", EntryKind.FILE, 0o644, sample),)
                    ),
                )
                for sample in (b"", *data)
            ),
        ),
        (
            _output(code=2),
            _output(stderr=b"missing input\n", code=5),
            *(
                Outcome(
                    _number(len(sample)),
                    b"",
                    Exited(0),
                    TreeSnapshot(
                        entries=(
                            TreeEntry("input", EntryKind.FILE, 0o644, sample),
                            TreeEntry("output", EntryKind.DIRECTORY, 0o700),
                            TreeEntry(
                                "output/result",
                                EntryKind.FILE,
                                0o600,
                                bytes(value ^ 0xA5 for value in sample),
                            ),
                        )
                    ),
                )
                for sample in (b"", *data)
            ),
        ),
    )
    return stats, files


def _fingerprint(outcomes: tuple[CaseResult, ...]) -> str:
    return hashlib.sha256(
        "\n".join(encode_result(result) for result in outcomes).encode("ascii")
    ).hexdigest()


def _mismatch(original: CaseResult, rebuild: CaseResult) -> bool:
    return (
        isinstance(original, Outcome)
        and isinstance(rebuild, Outcome)
        and bool(compare(original, rebuild))
    )


def _probe(work: Path, executable: Path, engine: Engine, image: str) -> bool:
    cases = tuple(
        Invocation(args)
        for args in (
            (),
            ("escape",),
            ("signal",),
            ("exit",),
            ("fifo",),
            ("wait",),
            ("policy",),
        )
    )
    result = run_batch(executable, cases, engine, image=image)
    (work / f"probe-{engine.value}.jsonl").write_text(
        "".join(encode_result(outcome) + "\n" for outcome in result), encoding="ascii"
    )
    return (
        result[:4]
        == (
            Outcome(b"/program\n", b"", Exited(0), TreeSnapshot()),
            Outcome(b"", b"", Exited(0), TreeSnapshot()),
            Outcome(b"", b"", Signaled(15), TreeSnapshot()),
            Outcome(b"", b"", Exited(143), TreeSnapshot()),
        )
        and isinstance(result[4], CaseFailure)
        and result[4].kind is FailureKind.SNAPSHOT
        and isinstance(result[5], CaseFailure)
        and result[5].kind is FailureKind.TIMEOUT
        and result[6] == _output()
    )


def evaluate(
    corpus: Path, runs: Path, mode: Mode, seed: int = SEED
) -> tuple[Path, bool]:
    runtime = verify_runtime(mode)
    provenance = evaluator_build()
    images = freeze_images(mode.engines, provenance.worker_source_sha256)
    run_id = f"m0-{uuid4().hex}"
    work = runs / run_id
    work.mkdir(parents=True)
    report_path = work / "m0.json"
    native_engines = tuple(
        engine for engine in mode.engines if engine is not Engine.QEMU_X86_64
    )
    probe_binaries = {}
    for engine in native_engines:
        executable = work / f"runprobe-{engine.value}.elf"
        build_public(
            corpus / "runprobe.c",
            executable,
            engine,
            Compiler.GCC,
            image=images[engine.platform],
        )
        probe_binaries[engine.platform] = executable
    probes = {
        engine: _probe(
            work,
            probe_binaries[
                "amd64" if engine is Engine.QEMU_X86_64 else engine.platform
            ],
            engine,
            images[engine.platform],
        )
        for engine in mode.engines
    }

    def run(
        binary: Path, cases: tuple[Invocation, ...], engine: Engine
    ) -> tuple[CaseResult, ...]:
        return run_batch(binary, cases, engine, image=images[engine.platform])

    summaries = []
    all_passed = all(probes.values())
    for program in public_programs(seed):
        source = corpus / f"{program.name}.c"
        baseline_engine = native_engines[0]
        original = work / f"{program.name}-original.elf"
        build_public(
            source,
            original,
            baseline_engine,
            Compiler.GCC,
            image=images[baseline_engine.platform],
        )
        baseline = run(original, program.cases, baseline_engine)
        expected_ok = baseline == program.expected
        stable = all(isinstance(outcome, Outcome) for outcome in baseline)
        for _ in range(TRIALS):
            stable &= baseline == run(original, program.cases, baseline_engine)

        excluded: set[int] = set()
        oracle_ok = True
        if Engine.QEMU_X86_64 in mode.engines:
            independent = run(original, program.cases, Engine.QEMU_X86_64)
            oracle_ok = all(isinstance(outcome, Outcome) for outcome in independent)
            for _ in range(TRIALS):
                oracle_ok &= independent == run(
                    original, program.cases, Engine.QEMU_X86_64
                )
            excluded = {
                index
                for index, (first, second) in enumerate(
                    zip(baseline, independent, strict=True)
                )
                if _mismatch(first, second)
            }
        eligible = tuple(
            index for index in range(len(program.cases)) if index not in excluded
        )
        coverage = None
        coverage_failure = None
        if (
            Engine.QEMU_X86_64 in mode.engines
            and stable
            and oracle_ok
            and expected_ok
            and eligible
        ):
            try:
                coverage = asdict(
                    measure_public(
                        original,
                        tuple(program.cases[index] for index in eligible),
                        tuple(baseline[index] for index in eligible),
                        work / f"{program.name}-dev.jsonl",
                        seed,
                        images,
                    )
                )
            except (
                ValueError,
                OSError,
                WorkerError,
                subprocess.SubprocessError,
            ) as error:
                coverage_failure = str(error)
        portable = {}
        mutations = {}
        for engine in native_engines:
            build = partial(build_public, image=images[engine.platform])
            control: tuple[CaseResult, ...] = ()
            for compiler in Compiler:
                rebuild = work / f"{program.name}-{engine.value}-{compiler}.elf"
                build(source, rebuild, engine, compiler)
                candidate = run(rebuild, program.cases, engine)
                if compiler is Compiler.GCC:
                    control = candidate
                portable[f"{engine.value}-{compiler}"] = bool(eligible) and all(
                    isinstance(candidate[index], Outcome)
                    and candidate[index] == baseline[index]
                    for index in eligible
                )
            killed = 0
            valid = (
                expected_ok and oracle_ok and portable[f"{engine.value}-{Compiler.GCC}"]
            )
            for mutant in range(1, program.mutants + 1):
                rebuild = work / f"{program.name}-{engine.value}-mutant-{mutant}.elf"
                build(source, rebuild, engine, Compiler.GCC, mutant)
                changed = run(rebuild, program.cases, engine)
                valid &= all(isinstance(changed[index], Outcome) for index in eligible)
                killed += any(
                    _mismatch(control[index], changed[index]) for index in eligible
                )
            mutations[engine] = {
                "killed": killed if valid else 0,
                "total": program.mutants,
                "valid": valid,
            }

        passed = (
            stable
            and oracle_ok
            and expected_ok
            and (Engine.QEMU_X86_64 not in mode.engines or coverage is not None)
            and all(portable.values())
            and all(
                bool(result["valid"]) and 10 * result["killed"] >= 9 * result["total"]
                for result in mutations.values()
            )
        )
        all_passed &= passed
        summaries.append(
            {
                "program": program.name,
                "cases": len(program.cases),
                "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                "outcome_sha256": _fingerprint(baseline),
                "self_match": stable,
                "matches_expected_public_behavior": expected_ok,
                "coverage": coverage,
                "coverage_failure": coverage_failure,
                "independent_oracle_healthy": oracle_ok,
                "emulator_sensitive_cases": len(excluded),
                "portability": portable,
                "mutations": mutations,
            }
        )

    report_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "mode": mode,
                "runtime": asdict(runtime),
                "worker_images": images,
                "evaluator": asdict(provenance),
                "seed": seed,
                "self_trials": TRIALS,
                "sandbox_probes": probes,
                "programs": summaries,
                "behavior_checks_passed": all_passed,
            },
            indent=2,
        )
        + "\n"
    )
    return report_path, all_passed
