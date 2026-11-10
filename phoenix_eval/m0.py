import hashlib
import json
import random
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.docker import Engine, run_batch
from phoenix_eval.outcome import (
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
    compare,
)
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
            return Engine.AMD64, Engine.ARM64, Engine.QEMU_X86_64
        if self is Mode.NATIVE_AMD64:
            return (Engine.AMD64,)
        return (Engine.ARM64,)


@dataclass(frozen=True)
class Program:
    name: str
    cases: tuple[Invocation, ...]
    mutants: int = 5


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


def _probe(corpus: Path, work: Path, engine: Engine) -> bool:
    executable = work / f"runprobe-{engine.value}.elf"
    build_public(corpus / "runprobe.c", executable, engine, Compiler.GCC)
    cases = tuple(
        Invocation(args)
        for args in ((), ("escape",), ("signal",), ("exit",), ("fifo",))
    )
    result = run_batch(executable, cases, engine)
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
    )


def evaluate(
    corpus: Path, runs: Path, mode: Mode, seed: int = SEED
) -> tuple[Path, bool]:
    run_id = f"m0-{uuid4().hex}"
    work = runs / run_id
    work.mkdir(parents=True)
    report_path = work / "m0.json"
    native_engines = tuple(
        engine for engine in mode.engines if engine is not Engine.QEMU_X86_64
    )
    probes = {engine: _probe(corpus, work, engine) for engine in native_engines}
    summaries = []
    all_passed = all(probes.values())
    for program in public_programs(seed):
        source = corpus / f"{program.name}.c"
        baseline_engine = native_engines[0]
        original = work / f"{program.name}-original.elf"
        build_public(source, original, baseline_engine, Compiler.GCC)
        baseline = run_batch(original, program.cases, baseline_engine)
        stable = all(isinstance(outcome, Outcome) for outcome in baseline)
        for _ in range(TRIALS):
            stable &= baseline == run_batch(original, program.cases, baseline_engine)

        excluded: set[int] = set()
        oracle_ok = True
        if Engine.QEMU_X86_64 in mode.engines:
            independent = run_batch(original, program.cases, Engine.QEMU_X86_64)
            oracle_ok = all(isinstance(outcome, Outcome) for outcome in independent)
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
        portable = {}
        mutations = {}
        for engine in native_engines:
            for compiler in Compiler:
                rebuild = work / f"{program.name}-{engine.value}-{compiler}.elf"
                build_public(source, rebuild, engine, compiler)
                candidate = run_batch(rebuild, program.cases, engine)
                portable[f"{engine.value}-{compiler}"] = bool(eligible) and all(
                    isinstance(candidate[index], Outcome)
                    and candidate[index] == baseline[index]
                    for index in eligible
                )
            killed = 0
            valid = True
            for mutant in range(1, program.mutants + 1):
                rebuild = work / f"{program.name}-{engine.value}-mutant-{mutant}.elf"
                build_public(source, rebuild, engine, Compiler.GCC, mutant)
                changed = run_batch(rebuild, program.cases, engine)
                valid &= all(isinstance(changed[index], Outcome) for index in eligible)
                killed += any(
                    _mismatch(baseline[index], changed[index]) for index in eligible
                )
            mutations[engine] = {
                "killed": killed,
                "total": program.mutants,
                "valid": valid,
            }

        passed = (
            stable
            and oracle_ok
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
