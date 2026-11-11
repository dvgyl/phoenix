import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Literal

from phoenix_eval.build import PROJECT_CMAKE, project_files
from phoenix_eval.development import freeze_development
from phoenix_eval.docker import read_program
from phoenix_eval.protection import GUARD_ENV, GUARD_PROBE, guarded_command
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", delete_on_close=False
    ) as stream:
        json.dump(data, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")
        stream.close()
        if before_publish is not None:
            before_publish()
        Path(stream.name).replace(path)


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
) -> Submission:
    if directory.resolve() != directory:
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
    probe = directory / GUARD_PROBE
    probe.write_text("Synthetic file guard witness.\n", encoding="utf-8")
    cwd = directory / "pipeline-cwd"
    cwd.mkdir(exist_ok=True, mode=0o700)
    base = (sys.executable, "-P", "-s", "-m", "phoenix", "run", "--binary-id", key)
    exists = (workspace / "runs" / pipeline_run / key / "run.json").is_file()
    options: tuple[str, ...]
    if replay_pipeline_run is not None:
        options = ("--replay", replay_pipeline_run, "--run-id", pipeline_run)
    elif exists:
        options = ("--resume", pipeline_run)
    else:
        options = (str(binary), "--run-id", pipeline_run, "--method", method)
    command = guarded_command(workspace, (*base, *options), release=True, probe=probe)
    started = _reconstruction_start(directory)
    with (
        (directory / "pipeline.stdout").open("ab") as output,
        (directory / "pipeline.stderr").open("ab") as errors,
    ):
        result = subprocess.run(
            command,
            cwd=cwd,
            env={
                **os.environ,
                GUARD_ENV: str(probe),
                "PYTHONPATH": str(CHECKOUT),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
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
        if method == "ghidra-raw":
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
