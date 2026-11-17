"""Build development binaries and validate development held-out cases."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import uuid4

from phoenix_eval.case import (
    CaseFailure,
    CaseResult,
    FailureKind,
    Invocation,
    WorkerRuntime,
)
from phoenix_eval.corpus import _case
from phoenix_eval.docker import (
    Engine,
    WorkerError,
    docker_cli,
    freeze_images,
    run_cases,
)
from phoenix_eval.elf import elf_sections
from phoenix_eval.jobs import limited
from phoenix_eval.outcome import Outcome
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import worker_source_digest
from phoenix_eval.wire import decode_result, encode_result
from phoenix_eval.worker import worker_args

REPO = Path(__file__).resolve().parents[1]
LEVELS = ("O0", "O2", "Os", "O3")
COMPILERS = ("gcc", "clang")
CANONICAL_FLAGS = (
    "-std=c11",
    "-O2",
    "-Wall",
    "-Wextra",
    "-Iinclude",
    "-ffp-contract=off",
    "-fno-strict-aliasing",
    "-fwrapv",
    "-fsigned-char",
    "-fstack-protector-all",
    "-Wl,-z,relro,-z,now",
)
_COMPILE = r"""
tar -xf -
cc=$1
twin=$2
output=$3
shift 3
"$cc" "$@" -o "$output" src/*.c -lm >&2
if [ "$twin" = yes ]; then
    strip --strip-all "$output"
    "$cc" "$@" -g -o "$output.twin" src/*.c -lm >&2
    objcopy -O binary --only-section=.text "$output" .phoenix-text
    objcopy -O binary --only-section=.text "$output.twin" .phoenix-text.twin
    tar -cf - "$output" "$output.twin" .phoenix-text .phoenix-text.twin
else
    tar -cf - "$output"
fi
"""
_REQUIRED_RUNS = frozenset(
    (
        *(
            f"canonical/amd64/{cc}/{runner}"
            for cc in COMPILERS
            for runner in (Engine.ROSETTA, Engine.QEMU_X86_64)
        ),
        *(f"canonical/arm64/{cc}/arm64" for cc in COMPILERS),
        "sanitizer/arm64/gcc",
        "original/rosetta",
        "original/qemu-x86-64",
    )
)
_VALIDATION_PATHS = (
    "tools.lock",
    "scripts/build-worker",
    "containers/Dockerfile",
    "containers/prepare-runtime.sh",
    "containers/launch-target.c",
    *(
        f"phoenix_eval/{module}.py"
        for module in (
            "dev_corpus",
            "case",
            "corpus",
            "docker",
            "elf",
            "jobs",
            "outcome",
            "platforms",
            "provenance",
            "trace",
            "tree",
            "wire",
            "worker",
        )
    ),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as name:
        temporary = Path(name) / "record.json"
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)


def _regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    return path.read_bytes()


@dataclass(frozen=True)
class DevBinary:
    name: str
    tier: str
    compiler: str
    flags: tuple[str, ...]
    sha256: str
    category: str
    twin_valid: bool

    def __post_init__(self) -> None:
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]*", self.name)
            or self.tier not in ("D0", "D1", "D2", "D3")
            or self.compiler not in COMPILERS
            or self.flags not in tuple(("-std=c11", f"-{x}", "-lm") for x in LEVELS)
            or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)
            or not self.category
            or not isinstance(self.twin_valid, bool)
        ):
            raise ValueError("Invalid development binary entry.")

    @property
    def level(self) -> str:
        return self.flags[1][1:]

    @property
    def key(self) -> str:
        return f"{self.compiler}-{self.level}"


@dataclass(frozen=True)
class ValidatedCases:
    cases: tuple[Invocation, ...]
    indices: tuple[int, ...]
    excluded: tuple[int, ...]
    total: int


@dataclass(frozen=True)
class Observation:
    label: str
    sha256: str
    repeats: tuple[tuple[CaseResult, ...], ...]


def read_manifest(path: Path) -> tuple[DevBinary, ...]:
    """Read all entries, including entries with an invalid twin."""
    rows = _json(path).get("binaries")
    if not isinstance(rows, list):
        raise ValueError("The manifest needs a binaries list.")
    result = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(DevBinary.__dataclass_fields__):
            raise ValueError("Invalid manifest fields.")
        if (
            any(
                not isinstance(row[k], str)
                for k in ("name", "tier", "compiler", "sha256", "category")
            )
            or not isinstance(row["flags"], list)
            or any(not isinstance(flag, str) for flag in row["flags"])
        ):
            raise ValueError("Invalid manifest field types.")
        result.append(DevBinary(**{**row, "flags": tuple(row["flags"])}))
    if len({(item.name, item.key) for item in result}) != len(result):
        raise ValueError("The manifest repeats a binary.")
    return tuple(result)


def binary_path(workspace: Path, binary: DevBinary) -> Path:
    """Resolve a binary and verify its recorded hash."""
    root = (workspace / "dev_bin").resolve()
    path = root / binary.name / binary.key / binary.name
    if not path.resolve().is_relative_to(root) or _sha(_regular(path)) != binary.sha256:
        raise ValueError(f"The binary hash or path changed: {binary.name}/{binary.key}")
    return path


def _sources(program: Path) -> tuple[tuple[str, bytes], ...]:
    files = []
    for directory in (program / "src", program / "include"):
        if directory.is_symlink():
            raise ValueError("Source directories must not be symbolic links.")
        if not directory.exists():
            continue
        for parent, dirs, names in directory.walk():
            if any((parent / name).is_symlink() for name in dirs):
                raise ValueError("Source directories must not contain symbolic links.")
            for name in names:
                path = parent / name
                files.append((path.relative_to(program).as_posix(), _regular(path)))
    if not any(re.fullmatch(r"src/[^/]+\.c", name) for name, _ in files):
        raise ValueError("A program needs src/*.c files.")
    return tuple(sorted(files))


def _file_hash(files: tuple[tuple[str, bytes], ...]) -> str:
    return _sha(json.dumps([(name, _sha(data)) for name, data in files]).encode())


def _bindings(program: Path) -> dict[str, str]:
    return {
        "source_sha256": _file_hash(_sources(program)),
        "cases_sha256": _sha(_regular(program / "holdout/cases.jsonl")),
        "meta_sha256": _sha(_regular(program / "meta.json")),
        "tools_sha256": _sha(_regular(REPO / "tools.lock")),
        "validator_sha256": _file_hash(
            tuple((name, _regular(REPO / name)) for name in _VALIDATION_PATHS)
        ),
    }


def _cases(program: Path) -> tuple[Invocation, ...]:
    cases = tuple(
        _case(line)
        for line in _regular(program / "holdout/cases.jsonl")
        .decode("ascii")
        .splitlines()
    )
    minimum = 100 if _json(program / "meta.json")["tier"] == "D0" else 200
    if len(cases) < minimum:
        raise ValueError(f"The held-out set needs at least {minimum} cases.")
    return cases


def load_validated_cases(
    corpus: Path, workspace: Path, binary: DevBinary
) -> ValidatedCases:
    """Reject stale or failed records before returning cases to the evaluator."""
    binary_path(workspace, binary)
    program = corpus / binary.name
    record = _json(program / "holdout/excluded.json")
    if record.get("version") != 1 or record.get("bindings") != _bindings(program):
        raise ValueError("The held-out validation is stale.")
    binaries = record.get("binaries")
    if not isinstance(binaries, dict):
        raise ValueError("The validation has no binary records.")
    entry = binaries.get(binary.key)
    cases = _cases(program)
    if not isinstance(entry, dict) or (
        entry.get("sha256") != binary.sha256
        or entry.get("total") != len(cases)
        or entry.get("errors") != []
        or entry.get("passed") is not True
    ):
        raise ValueError("The held-out validation failed or has a stale binary hash.")
    runs = entry.get("runs")
    if (
        not isinstance(runs, list)
        or len(runs) != len(_REQUIRED_RUNS)
        or any(
            not isinstance(run, dict)
            or not isinstance(run.get("label"), str)
            or run.get("repeats") != 3
            or run.get("cases_per_repeat") != len(cases)
            or not isinstance(run.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", run["sha256"])
            for run in runs
        )
        or {run["label"] for run in runs} != _REQUIRED_RUNS
        or any(
            run["sha256"] != binary.sha256
            for run in runs
            if run["label"].startswith("original/")
        )
    ):
        raise ValueError("The validation omits required builds or repeats.")
    excluded = entry.get("excluded")
    if (
        not isinstance(excluded, list)
        or any(type(i) is not int or not 0 <= i < len(cases) for i in excluded)
        or excluded != sorted(set(excluded))
        or len(excluded) * 20 > len(cases)
        or entry.get("excluded_count") != len(excluded)
    ):
        raise ValueError("Invalid excluded case indices or count.")
    failures = entry.get("failures")
    if not isinstance(failures, dict) or set(failures) != {str(i) for i in excluded}:
        raise ValueError("The validation summary contradicts its failure records.")
    for failure in failures.values():
        if not isinstance(failure, dict) or not isinstance(
            failure.get("observations"), list
        ):
            raise ValueError("Invalid validation failure observations.")
        observations = failure["observations"]
        expected = {(run["label"], repeat) for run in runs for repeat in range(3)}
        if (
            len(observations) != len(expected)
            or any(
                not isinstance(item, dict)
                or (item.get("run"), item.get("repeat")) not in expected
                for item in observations
            )
            or {(item["run"], item["repeat"]) for item in observations} != expected
        ):
            raise ValueError("The failure record omits a required observation.")
        checked = assess(
            tuple(
                Observation(
                    run["label"],
                    run["sha256"],
                    tuple(
                        (
                            decode_result(
                                json.dumps(
                                    next(
                                        item["result"]
                                        for item in observations
                                        if item["run"] == run["label"]
                                        and item["repeat"] == repeat
                                    )
                                )
                            ),
                        )
                        for repeat in range(3)
                    ),
                )
                for run in runs
            ),
            1,
        )
        found = cast(dict[str, dict[str, object]], checked["failures"])
        if (
            checked["errors"]
            or checked["excluded"] != [0]
            or found["0"]["reasons"] != failure.get("reasons")
        ):
            raise ValueError("The failure reasons contradict the recorded outcomes.")
    indices = tuple(i for i in range(len(cases)) if i not in excluded)
    return ValidatedCases(
        tuple(cases[i] for i in indices), indices, tuple(excluded), len(cases)
    )


def corpus_hash(workspace: Path, binaries: tuple[DevBinary, ...]) -> str:
    """Hash the selected manifest entries and verify all binary bytes."""
    for binary in binaries:
        binary_path(workspace, binary)
    return _sha(
        json.dumps(
            [asdict(x) for x in sorted(binaries, key=lambda x: (x.name, x.key))],
            sort_keys=True,
        ).encode()
    )


def heldout_hash(corpus: Path, workspace: Path, binaries: tuple[DevBinary, ...]) -> str:
    """Hash validated held-out inputs and their exclusion records."""
    for binary in binaries:
        load_validated_cases(corpus, workspace, binary)
    return _file_hash(
        tuple(
            (f"{name}/{filename}", _regular(corpus / name / "holdout" / filename))
            for name in sorted({x.name for x in binaries})
            for filename in ("cases.jsonl", "excluded.json")
        )
    )


@limited("compile")
def compile_source(
    files: tuple[tuple[str, bytes], ...],
    compiler: str,
    flags: tuple[str, ...],
    engine: Engine,
    epoch: int,
    image: str,
    *,
    twin: bool = False,
    output_name: str = "program",
) -> dict[str, bytes]:
    """Compile source in Linux. Return files without executing target code."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", output_name):
        raise ValueError("Use a valid compiler output name.")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for name, data in files:
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(data), 0o644, epoch
            archive.addfile(member, io.BytesIO(data))
    name = f"phoenix-dev-build-{uuid4().hex}"
    command = (
        *docker_cli(),
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        f"--platform=linux/{engine.platform}",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--memory=1536m",
        "--memory-swap=1536m",
        "--user=19704:19704",
        "--tmpfs=/work:rw,exec,nosuid,nodev,size=256m,uid=19704,gid=19704,mode=0700",
        "--workdir=/work",
        "--env=TMPDIR=/work",
        "--env=HOME=/nonexistent",
        f"--env=SOURCE_DATE_EPOCH={epoch}",
        "--entrypoint=/bin/sh",
        f"--name={name}",
        image,
        "-ec",
        _COMPILE,
        "build-dev",
        compiler,
        "yes" if twin else "no",
        output_name,
        *flags,
    )
    try:
        result = subprocess.run(
            command,
            input=payload.getvalue(),
            capture_output=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            (*docker_cli(), "rm", "-f", name),
            capture_output=True,
            timeout=10,
            check=False,
        )
        raise WorkerError("The development build exceeded its time limit.") from None
    if result.returncode:
        raise WorkerError(result.stderr.decode("utf-8", errors="replace"))
    expected = {output_name: "program"}
    if twin:
        expected.update(
            {
                f"{output_name}.twin": "program.twin",
                ".phoenix-text": "text",
                ".phoenix-text.twin": "text.twin",
            }
        )
    outputs = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        for member in archive:
            if (
                member.name not in expected
                or expected[member.name] in outputs
                or not member.isfile()
                or not 0 < member.size <= 16 * 1024 * 1024
            ):
                raise WorkerError("The compiler returned an invalid file.")
            stream = archive.extractfile(member)
            assert stream is not None
            outputs[expected[member.name]] = stream.read()
    if set(outputs) != set(expected.values()):
        raise WorkerError("The compiler omitted a required file.")
    for key in ("program", "program.twin") if twin else ("program",):
        data = outputs[key]
        if not data.startswith(b"\x7fELF\x02\x01") or int.from_bytes(
            data[18:20], "little"
        ) != (62 if engine.platform == "amd64" else 183):
            raise WorkerError("The compiler returned the wrong ELF architecture.")
    if twin:
        for key, text in (("program", "text"), ("program.twin", "text.twin")):
            if elf_sections(outputs[key], ".text")[".text"].data != outputs[text]:
                raise WorkerError("The extracted .text bytes do not match the ELF.")
    return outputs


def _observe(
    label: str, binary: bytes, cases: tuple[Invocation, ...], engine: Engine, image: str
) -> Observation:
    repeats = []
    for _ in range(3):
        for attempt in range(2):
            try:
                results = run_cases(binary, cases, engine, image=image)
                if len(results) != len(cases):
                    raise WorkerError("The worker returned the wrong result count.")
                break
            except (OSError, subprocess.SubprocessError, WorkerError) as exc:
                if attempt:
                    results = tuple(
                        CaseFailure(FailureKind.LAUNCH, str(exc)) for _ in cases
                    )
        repeats.append(results)
    return Observation(label, _sha(binary), tuple(repeats))


def assess(observations: tuple[Observation, ...], total: int) -> dict[str, object]:
    """Preserve all failed case observations. Apply the exact 5 percent boundary."""
    if (
        not observations
        or total <= 0
        or any(
            len(item.repeats) != 3 or any(len(run) != total for run in item.repeats)
            for item in observations
        )
    ):
        raise ValueError("Validation requires three complete repeats of each build.")
    failures: dict[str, object] = {}
    errors: set[str] = set()
    for index in range(total):
        samples = [
            (item.label, repeat, run[index])
            for item in observations
            for repeat, run in enumerate(item.repeats)
        ]
        baseline = samples[0][2]
        ordinary_stderr = {
            outcome.stderr
            for label, _, outcome in samples
            if label.split("/")[0] != "sanitizer" and isinstance(outcome, Outcome)
        }
        reasons = set()
        for label, _, outcome in samples:
            if isinstance(outcome, CaseFailure):
                reasons.add("worker_failure")
                errors.add(f"{label}: {outcome.kind}: {outcome.detail}")
            elif (
                label.split("/")[0] == "sanitizer"
                and outcome.stderr not in ordinary_stderr
                and any(
                    marker in outcome.stderr
                    for marker in (
                        b"AddressSanitizer",
                        b"UndefinedBehaviorSanitizer",
                        b"LeakSanitizer",
                        b"runtime error:",
                    )
                )
            ):
                reasons.add("sanitizer")
            if outcome != baseline:
                reasons.add("outcome_difference")
            if isinstance(outcome, Outcome) and (
                outcome.stderr.startswith(
                    b"/program: error while loading shared libraries:"
                )
                or b"ERROR: AddressSanitizer failed to allocate" in outcome.stderr
            ):
                reasons.add("runtime_failure")
                errors.add(f"{label}: {outcome.stderr.decode(errors='replace')}")
        if reasons:
            failures[str(index)] = {
                "reasons": sorted(reasons),
                "observations": [
                    {
                        "run": label,
                        "repeat": repeat,
                        "result": json.loads(encode_result(outcome)),
                    }
                    for label, repeat, outcome in samples
                ],
            }
    excluded = sorted(int(index) for index in failures)
    return {
        "total": total,
        "excluded": excluded,
        "excluded_count": len(excluded),
        "passed": len(excluded) * 20 <= total and not errors,
        "errors": sorted(errors),
        "failures": failures,
        "runs": [
            {
                "label": x.label,
                "sha256": x.sha256,
                "repeats": 3,
                "cases_per_repeat": total,
            }
            for x in observations
        ],
    }


def _oracle_errors() -> list[str]:
    with (REPO / "tools.lock").open("rb") as stream:
        pins = tomllib.load(stream)
    args = worker_args(WorkerRuntime.QEMU, ())
    environment = Invocation().environment()
    errors = []
    cpu = pins.get("qemu_cpu")
    mask = pins.get("glibc_tunables")
    if not isinstance(cpu, str) or not cpu:
        errors.append("tools.lock has no qemu_cpu pin.")
    elif ("-cpu", cpu) not in tuple(zip(args, args[1:])):
        errors.append("The evaluator worker does not apply the qemu_cpu pin.")
    if not isinstance(mask, str) or not mask:
        errors.append("tools.lock has no glibc_tunables pin.")
    elif environment.get("GLIBC_TUNABLES") != mask:
        errors.append("The evaluator worker does not apply the glibc_tunables pin.")
    return errors


def validate_program(
    program: Path,
    workspace: Path,
    binaries: tuple[DevBinary, ...],
    epoch: int,
    images: dict[str, str],
) -> bool:
    bindings = _bindings(program)
    files, cases = _sources(program), _cases(program)
    common = []
    errors = _oracle_errors()
    for engine in (Engine.ROSETTA, Engine.ARM64):
        for compiler in COMPILERS:
            label = f"canonical/{engine.platform}/{compiler}"
            try:
                built = compile_source(
                    files,
                    compiler,
                    CANONICAL_FLAGS,
                    engine,
                    epoch,
                    images[engine.platform],
                )["program"]
            except (
                OSError,
                ValueError,
                tarfile.TarError,
                subprocess.SubprocessError,
                WorkerError,
            ) as exc:
                errors.append(f"{label}: {exc}")
                continue
            runners = (
                (Engine.ROSETTA, Engine.QEMU_X86_64)
                if engine is Engine.ROSETTA
                else (engine,)
            )
            for runner in runners:
                common.append(
                    _observe(
                        f"{label}/{runner}",
                        built,
                        cases,
                        runner,
                        images[runner.platform],
                    )
                )
    try:
        built = compile_source(
            files,
            "gcc",
            (*CANONICAL_FLAGS, "-fsanitize=address,undefined"),
            Engine.ARM64,
            epoch,
            images["arm64"],
        )["program"]
        common.append(
            _observe(
                "sanitizer/arm64/gcc",
                built,
                cases,
                Engine.TRUE_SOURCE_ARM64,
                images["arm64"],
            )
        )
    except (
        OSError,
        ValueError,
        tarfile.TarError,
        subprocess.SubprocessError,
        WorkerError,
    ) as exc:
        errors.append(f"sanitizer/arm64/gcc: {exc}")
    records = {}
    for binary in binaries:
        original = _regular(binary_path(workspace, binary))
        observations = (
            *common,
            *(
                _observe(
                    f"original/{engine}",
                    original,
                    cases,
                    engine,
                    images[engine.platform],
                )
                for engine in (Engine.ROSETTA, Engine.QEMU_X86_64)
            ),
        )
        record = assess(observations, len(cases))
        record["sha256"] = binary.sha256
        record["errors"] = [*cast(list[str], record["errors"]), *errors]
        record["passed"] = record["passed"] and not errors
        records[binary.key] = record
        print(
            f"{binary.name}/{binary.key}: "
            f"excluded {record['excluded_count']}/{len(cases)}; "
            f"{'pass' if record['passed'] else 'FAIL'}",
            flush=True,
        )
    if bindings != _bindings(program):
        raise ValueError("The program changed during validation.")
    _write_json(
        program / "holdout/excluded.json",
        {
            "version": 1,
            "bindings": bindings,
            "images": images,
            "binaries": records,
        },
    )
    for error in sorted(
        {
            error
            for record in records.values()
            for error in cast(list[str], record["errors"])
        }
    ):
        print(f"{program.name}: {error}", file=sys.stderr)
    return all(record["passed"] for record in records.values())


def _images(check: bool) -> dict[str, str]:
    platforms = ("amd64", "arm64") if check else ("amd64",)
    images = freeze_images(
        (Engine.ROSETTA, Engine.ARM64) if check else (Engine.ROSETTA,),
        worker_source_digest(REPO),
    )
    result = subprocess.run(
        (
            *docker_cli(),
            "image",
            "inspect",
            "--format",
            "{{.Architecture}} {{.Id}}",
            *(f"phoenix-worker:{x}" for x in platforms),
        ),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    for platform, line in zip(platforms, result.stdout.splitlines(), strict=True):
        architecture, digest = line.split()
        if architecture != platform or images[platform] != digest:
            raise ValueError("The worker image has the wrong architecture or ID.")
    return images


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("programs", nargs="*")
    args = parser.parse_args(argv)
    try:
        workspace = Path(os.environ["PHOENIX_ROOT"]).resolve()
        corpus = REPO / "corpus_dev"
        names = args.programs or sorted(
            path.name for path in corpus.iterdir() if path.is_dir()
        )
        if (
            not names
            or len(set(names)) != len(names)
            or any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in names)
        ):
            raise ValueError("Select distinct development program names.")
        with (REPO / "tools.lock").open("rb") as stream:
            epoch = tomllib.load(stream)["source_date_epoch"]
        images = _images(args.check)
        if args.check:
            verify_runtime("apple-silicon")
        manifest = workspace / "dev_bin/manifest.json"
        entries = (
            [x for x in read_manifest(manifest) if x.name not in names]
            if args.programs and manifest.exists()
            else []
        )
        _write_json(manifest, {"binaries": [asdict(x) for x in entries]})
        passed = True
        for name in names:
            program = corpus / name
            if program.is_symlink() or program.resolve().parent != corpus.resolve():
                raise ValueError("Use a development corpus program directory.")
            meta, files = _json(program / "meta.json"), _sources(program)
            if meta.get("name") != name:
                raise ValueError(
                    "The metadata name differs from the program directory."
                )
            selected = []
            for compiler in COMPILERS:
                for level in LEVELS:
                    output = compile_source(
                        files,
                        compiler,
                        ("-std=c11", f"-{level}"),
                        Engine.ROSETTA,
                        epoch,
                        images["amd64"],
                        twin=True,
                        output_name=name,
                    )
                    binary = DevBinary(
                        name,
                        str(meta["tier"]),
                        compiler,
                        ("-std=c11", f"-{level}", "-lm"),
                        _sha(output["program"]),
                        str(meta["category"]),
                        output["text"] == output["text.twin"],
                    )
                    destination = workspace / "dev_bin" / name / binary.key
                    destination.mkdir(parents=True, exist_ok=True)
                    for filename, key in (
                        (name, "program"),
                        (f"{name}.twin", "program.twin"),
                    ):
                        path = destination / filename
                        path.write_bytes(output[key])
                        path.chmod(0o600)
                    selected.append(binary)
                    entries.append(binary)
                    _write_json(manifest, {"binaries": [asdict(x) for x in entries]})
            if files != _sources(program) or meta != _json(program / "meta.json"):
                raise ValueError("The program changed during the build.")
            if args.check:
                passed = (
                    validate_program(program, workspace, tuple(selected), epoch, images)
                    and passed
                )
        print(
            f"Built {len(names)} programs; manifest: {len(entries)} binaries; "
            f"invalid twins: {sum(not x.twin_valid for x in entries)}."
        )
        if not args.programs and len(names) != 22:
            raise ValueError("Corpus acceptance needs 22 programs and 176 binaries.")
        return 0 if passed else 1
    except (
        OSError,
        ValueError,
        KeyError,
        WorkerError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ) as exc:
        print(f"build-dev-corpus: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
