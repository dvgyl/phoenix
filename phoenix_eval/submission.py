import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
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


def write_report(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", delete_on_close=False
    ) as stream:
        json.dump(data, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")
        stream.close()
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


def _existing_submission(
    path: Path, snapshot: Path, method: Method, key: str, replay_of: str | None
) -> Submission:
    data = json.loads(path.read_text(encoding="utf-8"))
    submission = Submission(
        method,
        key,
        data["source_sha256"],
        data["category"],
        replay_of,
        data.get("development_sha256"),
        data.get("origin_sha256"),
    )
    if (
        data["method"] != method
        or data["key"] != key
        or data.get("replay_of") != replay_of
    ):
        raise SubmissionError("The submission checkpoint identity changed.")
    if submission.source_sha256 is not None and (
        source_digest(project_files(snapshot)) != submission.source_sha256
    ):
        raise SubmissionError("The source snapshot changed after submission.")
    if submission.origin_sha256 is not None:
        read_origin(snapshot.parent / "origin.json", submission.origin_sha256)
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
    record = directory / "submission.json"
    snapshot = directory / "project"
    if record.is_file():
        return _existing_submission(record, snapshot, method, key, replay_pipeline_run)
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
            (directory / "origin.json").write_bytes(origin)
    if result.returncode not in (0, 1):
        submission = Submission(
            method,
            key,
            None,
            "pipeline-failed",
            replay_pipeline_run,
            origin_sha256=origin_sha,
        )
    else:
        project = project_path(workspace, pipeline_run, key)
        try:
            digest = freeze_project(project, snapshot)
            development_digest = None
            if method == "phoenix":
                development = (
                    workspace / "runs" / pipeline_run / key / "analyze/cases.json"
                )
                development_digest = freeze_development(
                    development, directory / "development.json"
                )
        except (OSError, ValueError):
            submission = Submission(
                method,
                key,
                None,
                "invalid-project",
                replay_pipeline_run,
                origin_sha256=origin_sha,
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
            )
    write_report(record, asdict(submission))
    return submission
