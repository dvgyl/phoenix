import fcntl
import hashlib
import json
import math
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, fields
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from phoenix_eval.artifacts import atomic_bytes
from phoenix_eval.build import PROJECT_CMAKE, project_files
from phoenix_eval.development import freeze_development
from phoenix_eval.docker import read_program
from phoenix_eval.jobs import file_lock
from phoenix_eval.model_ledger import _open_ledger, parse_event
from phoenix_eval.protection import (
    GUARD_ENV,
    GUARD_PROBE,
    MODEL_FD_ENV,
    REPLAY_ENV,
    guarded_command,
)
from phoenix_eval.provenance import CHECKOUT

type Method = Literal["phoenix", "ghidra-raw"]
_ORIGIN_LIMIT = 8 * 1024 * 1024
_CHECKPOINT_LIMIT = 64 * 1024


class EvaluationPending(RuntimeError):
    pass


class SubmissionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Submission:
    method: Method
    key: str
    source_sha256: str | None
    category: str | None
    replay_of: str | None = None
    development_sha256: str | None = None
    origin_sha256: str | None = None
    report_sha256: str | None = None
    reconstruction_seconds: float = 0.0


def write_report(
    path: Path, data: object, *, before_publish: Callable[[], None] | None = None
) -> None:
    atomic_bytes(
        path,
        (json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode(),
        before_publish=before_publish,
    )


def source_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def freeze_project(project: Path, snapshot: Path) -> str:
    files = project_files(project)
    if files.get("CMakeLists.txt") != PROJECT_CMAKE.encode("utf-8"):
        raise SubmissionError("The project must use the fixed build configuration.")
    if {name for name in files if name.endswith(".c")} != {"src/program.c"}:
        raise SubmissionError("The project must supply its fixed C translation unit.")
    digest = source_digest(files)
    if snapshot.is_dir():
        if source_digest(project_files(snapshot)) != digest:
            raise SubmissionError(
                "The existing source snapshot has different contents."
            )
        return digest
    with TemporaryDirectory(dir=snapshot.parent) as scratch:
        staging = Path(scratch) / "project"
        for name, data in files.items():
            file = staging / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        staging.replace(snapshot)
    return digest


def project_path(workspace: Path, pipeline_run: str, key: str) -> Path:
    return workspace / "runs" / pipeline_run / key / "package/out" / key


def _authorized_budget(
    directory: Path, cap: str | None, run_budget: int
) -> tuple[int, int]:
    authority = directory / "model-budget.json"
    requested = int(Decimal(cap or "5") * 1_000_000_000)
    with file_lock(authority.with_suffix(".lock")):
        if not authority.exists():
            write_report(authority, [requested, run_budget])
        binary_budget, total = json.loads(authority.read_bytes())
    if total != run_budget or (cap is not None and binary_budget != requested):
        raise SubmissionError("The authorized model budget changed.")
    return binary_budget, total


@contextmanager
def model_connection(
    workspace: Path,
    run: Path,
    key: str,
    binary_sha256: str,
    budget: tuple[int, int],
    cache_root: Path | None,
    env: dict[str, str],
) -> Iterator[int]:
    client, server = socket.socketpair()
    with client, server:
        broker = subprocess.Popen(
            (
                sys.executable,
                "-P",
                "-s",
                "-m",
                "phoenix.llm.ledger_channel",
                str(workspace),
                str(run),
                key,
                binary_sha256,
                *map(str, budget),
                str(cache_root or ""),
                str(server.fileno()),
            ),
            env={name: value for name, value in env.items() if name != GUARD_ENV},
            pass_fds=(server.fileno(),),
            start_new_session=True,
        )
        server.close()
        try:
            yield client.fileno()
        finally:
            client.close()
            try:
                broker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(broker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                broker.wait()


def stage_replay(
    source: Path,
    key: str,
    destination: Path,
    content: bytes | None,
) -> Path:
    if content is None:
        descriptor = _open_ledger(source / "llm.jsonl")
        content = b""
        if descriptor is not None:
            with os.fdopen(descriptor, "rb") as stream:
                fcntl.flock(stream, fcntl.LOCK_SH)
                content = stream.read()
    replay = destination / source.name
    (replay / key).mkdir(parents=True)
    (replay / "llm.jsonl").write_bytes(
        b"".join(
            line
            for line in content.splitlines(keepends=True)
            if parse_event(json.loads(line)).binary == key
        )
    )
    for name in (
        "run.json",
        "ingest/original.elf",
        "lift/lift.json",
        "lift/stage.json",
        "analyze/cases.json",
        "analyze/stage.json",
        "repair/budget-stop.json",
        f"package/out/{key}/phoenix_report.json",
    ):
        file = source / key / name
        if file.resolve() != file:
            raise SubmissionError("Use a physical replay artifact.")
        if file.is_file():
            target = replay / key / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file.read_bytes())
    return destination


def read_origin(path: Path, expected: str) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(_ORIGIN_LIMIT + 1)
    if not 0 < len(data) <= _ORIGIN_LIMIT:
        raise SubmissionError("The raw lift summary size is invalid.")
    if hashlib.sha256(data).hexdigest() != expected:
        raise SubmissionError("The raw lift summary changed after submission.")
    return data


def _seconds(value: object) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
        or value > sys.float_info.max
        or not math.isfinite(value)
    ):
        raise SubmissionError("The reconstruction time is invalid.")
    return float(value)


def _reconstruction_start(directory: Path) -> float:
    path = directory / "reconstruction-start.json"
    now = time.time()
    if path.exists():
        if path.resolve() != path or not path.is_file():
            raise SubmissionError("The reconstruction timer must be a regular file.")
        try:
            with path.open() as stream:
                data = stream.read(4097)
            if len(data) > 4096:
                raise ValueError
            started = _seconds(json.loads(data)["started"])
        except (KeyError, TypeError, ValueError):
            raise SubmissionError("The reconstruction timer is invalid.") from None
        if started > now:
            raise SubmissionError("The reconstruction start is in the future.")
        return started
    write_report(path, {"started": now})
    return now


def read_package_report(path: Path, expected: str) -> dict[str, object]:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise SubmissionError("The package report changed after submission.")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise SubmissionError("The package report is invalid.")
    _seconds(data.get("wall_seconds"))
    return data


def freeze_package_report(project: Path, directory: Path) -> str:
    content = (project / "phoenix_report.json").read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    target = directory / "report.json"
    if target.exists():
        read_package_report(target, digest)
    else:
        target.write_bytes(content)
        read_package_report(target, digest)
    return digest


def _checkpoint_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SubmissionError("The submission checkpoint has a repeated field.")
        result[key] = value
    return result


def read_submission(path: Path) -> tuple[Submission, str]:
    try:
        if os.path.realpath(path, strict=True) != str(path):
            raise ValueError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ValueError
        with os.fdopen(descriptor, "rb") as stream:
            content = stream.read(_CHECKPOINT_LIMIT + 1)
        if len(content) > _CHECKPOINT_LIMIT:
            raise ValueError
        data = json.loads(content, object_pairs_hook=_checkpoint_fields)
        if (
            not isinstance(data, dict)
            or set(data) != {field.name for field in fields(Submission)}
            or data["method"] not in ("phoenix", "ghidra-raw")
            or not isinstance(data["key"], str)
            or not data["key"]
            or (
                data["replay_of"] is not None
                and (not isinstance(data["replay_of"], str) or not data["replay_of"])
            )
        ):
            raise ValueError
        for name in (
            "source_sha256",
            "development_sha256",
            "origin_sha256",
            "report_sha256",
        ):
            value = data[name]
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            ):
                raise ValueError
        if data["source_sha256"] is None:
            if data["category"] not in ("pipeline-failed", "invalid-project"):
                raise ValueError
        elif data["category"] is not None:
            raise ValueError
        data["reconstruction_seconds"] = _seconds(data["reconstruction_seconds"])
        submission = Submission(**data)
    except (OSError, ValueError, TypeError, RecursionError):
        raise SubmissionError(
            "The capture submission checkpoint is invalid or missing."
        ) from None
    return submission, hashlib.sha256(content).hexdigest()


def _existing_submission(
    path: Path, snapshot: Path, method: Method, key: str, replay_of: str | None
) -> Submission:
    submission, _ = read_submission(path)
    if (
        submission.method != method
        or submission.key != key
        or submission.replay_of != replay_of
    ):
        raise SubmissionError("The submission checkpoint identity changed.")
    if submission.source_sha256 is not None and (
        source_digest(project_files(snapshot)) != submission.source_sha256
    ):
        raise SubmissionError("The source snapshot changed after submission.")
    if submission.origin_sha256 is not None:
        read_origin(snapshot.parent / "origin.json", submission.origin_sha256)
    if submission.source_sha256 is not None:
        if submission.report_sha256 is None:
            raise SubmissionError("The submission has no bound package report.")
        read_package_report(snapshot.parent / "report.json", submission.report_sha256)
    return submission


def submit(
    workspace: Path,
    directory: Path,
    pipeline_run: str,
    key: str,
    binary: Path,
    method: Method,
    replay_pipeline_run: str | None = None,
    *,
    cost_cap_usd: str | None = None,
    run_budget: int = 200_000_000_000,
    environment: dict[str, str] | None = None,
    cache_root: Path | None = None,
    recorded_ledger: bytes | None = None,
) -> Submission:
    if pipeline_run.startswith("m1-t0-"):
        raise SubmissionError("The pipeline run ID is reserved for sealed records.")
    if directory.resolve() != directory or not directory.is_relative_to(
        workspace / "runs"
    ):
        raise SubmissionError("Use the physical submission directory.")
    capture = directory / "capture"
    if capture.exists():
        if capture.resolve() != capture:
            raise SubmissionError("The capture path must be a regular directory.")
        return _existing_submission(
            capture / "submission.json",
            capture / "project",
            method,
            key,
            replay_pipeline_run,
        )
    if (directory / "submission.json").exists():
        raise SubmissionError("Use the recorded revision for this submission layout.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    pipeline_directory = workspace / "runs" / pipeline_run / key
    if pipeline_directory.resolve() != pipeline_directory:
        raise SubmissionError("Use a physical pipeline directory.")
    pipeline_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    probe = pipeline_directory / GUARD_PROBE
    probe.write_text("Synthetic file guard witness.\n", encoding="utf-8")
    cwd = pipeline_directory / "pipeline-cwd"
    cwd.mkdir(exist_ok=True, mode=0o700)
    base: tuple[str, ...] = (sys.executable, "-P", "-s", "-m", "phoenix", "run")
    base += ("--binary-id", key)
    exists = (pipeline_directory / "run.json").is_file()
    options: tuple[str, ...]
    binary_bytes = b"" if replay_pipeline_run is not None else read_program(binary)
    binary_sha256 = hashlib.sha256(binary_bytes).hexdigest()
    if replay_pipeline_run is not None:
        options = ("--replay", replay_pipeline_run, "--run-id", pipeline_run)
    elif exists:
        options = ("--resume", pipeline_run)
    else:
        copied_binary = pipeline_directory / "input.elf"
        copied_binary.write_bytes(binary_bytes)
        options = (str(copied_binary), "--run-id", pipeline_run, "--method", method)
    if cache_root is not None:
        options += ("--cache-root", str(cache_root))
    allow: tuple[Path, ...] = (pipeline_directory,)
    if cache_root is not None:
        allow += (cache_root,)
    elif replay_pipeline_run is None:
        allow += tuple(
            workspace / "cache/phoenix" / stage / binary_sha256
            for stage in ("lift", "devset")
        )
    if any(
        path.is_relative_to(directory) or directory.is_relative_to(path)
        for path in allow
    ):
        raise SubmissionError("The pipeline cannot have access to submission records.")
    started = _reconstruction_start(directory)
    budget = None
    if replay_pipeline_run is None:
        budget = _authorized_budget(directory, cost_cap_usd, run_budget)
        binary_cap, run_cap = (f"{Decimal(x) / 1_000_000_000:f}" for x in budget)
        base += ("--cost-cap-usd", binary_cap, "--budget-run", run_cap)
    elif cost_cap_usd is not None:
        base += ("--cost-cap-usd", cost_cap_usd)
    command = guarded_command(workspace, CHECKOUT, (*base, *options), "pipeline", allow)
    for path in allow[1:]:
        path.parent.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        **(environment or {}),
        GUARD_ENV: str(probe),
        "PYTHONPATH": str(CHECKOUT),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop(REPLAY_ENV, None)
    env.pop(MODEL_FD_ENV, None)
    with (
        ExitStack() as stack,
        (directory / "pipeline.stdout").open("ab") as output,
        (directory / "pipeline.stderr").open("ab") as errors,
    ):
        descriptors: tuple[int, ...] = ()
        if replay_pipeline_run is not None:
            if not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}", replay_pipeline_run
            ) or replay_pipeline_run.startswith("m1-t0-"):
                raise SubmissionError("Use a development replay ID.")
            temporary = stack.enter_context(
                TemporaryDirectory(dir=pipeline_directory, prefix=".replay-")
            )
            source = workspace / "runs" / replay_pipeline_run
            env[REPLAY_ENV] = str(
                stage_replay(source, key, Path(temporary), recorded_ledger)
            )
        else:
            assert budget is not None
            descriptor = stack.enter_context(
                model_connection(
                    workspace,
                    pipeline_directory.parent,
                    key,
                    binary_sha256,
                    budget,
                    cache_root,
                    env,
                )
            )
            env[MODEL_FD_ENV] = str(descriptor)
            descriptors = (descriptor,)
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            pass_fds=descriptors,
            stdout=output,
            stderr=errors,
            check=False,
            timeout=3600,
        )
    if result.returncode == 75:
        raise EvaluationPending(
            "The model service is unavailable. Resume the evaluation."
        )
    elapsed = _seconds(time.time() - started)
    with TemporaryDirectory(dir=directory, prefix=".capture-") as scratch:
        staging = Path(scratch) / "capture"
        staging.mkdir(mode=0o700)
        origin_sha = None
        if method in ("phoenix", "ghidra-raw"):
            lift = workspace / "runs" / pipeline_run / key / "recover"
            evidence = lift / "evidence.json"
            if evidence.is_file():
                try:
                    binding = json.loads(evidence.read_text(encoding="utf-8"))
                    original_sha, origin_sha = (
                        binding["binary_sha256"],
                        str(binding["sha256"]),
                    )
                except (KeyError, TypeError, ValueError):
                    raise SubmissionError("The raw lift identity is invalid.") from None
                if original_sha != hashlib.sha256(read_program(binary)).hexdigest():
                    raise SubmissionError(
                        "The raw lift summary has a different original hash."
                    )
                origin = read_origin(lift / "program.json", origin_sha)
                (staging / "origin.json").write_bytes(origin)
        if result.returncode not in (0, 1):
            submission = Submission(
                method,
                key,
                None,
                "pipeline-failed",
                replay_pipeline_run,
                origin_sha256=origin_sha,
                reconstruction_seconds=elapsed,
            )
        else:
            project = project_path(workspace, pipeline_run, key)
            try:
                digest = freeze_project(project, staging / "project")
                report_digest = freeze_package_report(project, staging)
                development_digest = None
                if method == "phoenix":
                    development = (
                        workspace / "runs" / pipeline_run / key / "analyze/cases.json"
                    )
                    development_digest = freeze_development(
                        development, staging / "development.json"
                    )
            except ValueError:
                submission = Submission(
                    method,
                    key,
                    None,
                    "invalid-project",
                    replay_pipeline_run,
                    origin_sha256=origin_sha,
                    reconstruction_seconds=elapsed,
                )
            else:
                submission = Submission(
                    method,
                    key,
                    digest,
                    None,
                    replay_pipeline_run,
                    development_digest,
                    origin_sha,
                    report_digest,
                    elapsed,
                )
        write_report(staging / "submission.json", asdict(submission))
        staging.replace(capture)
    return submission
