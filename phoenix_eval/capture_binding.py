import json
import os
from collections.abc import Mapping
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from phoenix_eval.model_ledger import ledger_digest
from phoenix_eval.submission import Submission, read_submission, write_report

_REJECTION = "capture-rejected.json"


class _CaptureContradiction(ValueError):
    def __init__(self, key: str, digest: str, returned: Submission) -> None:
        super().__init__("The capture checkpoint differs from the returned submission.")
        self.record = {
            "schema": 1,
            "phase": "rejected",
            "reason": "checkpoint-mismatch",
            "task_key_sha256": sha256(key.encode("utf-8")).hexdigest(),
            "checkpoint_sha256": digest,
            "returned_submission_sha256": sha256(
                json.dumps(asdict(returned), sort_keys=True, allow_nan=False).encode(
                    "utf-8"
                )
            ).hexdigest(),
        }


def _reject(run: Path, error: _CaptureContradiction) -> None:
    if json.loads(_read(run)) != {"schema": 1, "phase": "capturing"}:
        raise ValueError("The capture binding changed before rejection.")
    directory = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(
            _REJECTION,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            # The marker blocks retry even if its details are incomplete.
            os.fsync(directory)
            json.dump(error.record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(directory)


def _digest(path: Path) -> str:
    digest = ledger_digest(path)
    if digest is None:
        raise ValueError("The frozen capture evidence is invalid or missing.")
    return digest


def _physical(path: Path) -> bool:
    try:
        return os.path.realpath(path, strict=True) == str(path)
    except OSError:
        return False


def _record(
    run: Path,
    keys: tuple[str, ...],
    submissions: Mapping[str, Submission] | None = None,
) -> dict[str, object]:
    captures = []
    if len(keys) != len(set(keys)):
        raise ValueError("The capture roster contains duplicate task keys.")
    for key in keys:
        directory = run / "submissions" / key / "capture"
        if not directory.is_dir() or not _physical(directory):
            raise ValueError("The frozen capture directory is invalid or missing.")
        files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or not _physical(path):
                raise ValueError("The frozen capture cannot contain symbolic links.")
            if not path.is_dir():
                name = path.relative_to(directory).as_posix()
                if name == "submission.json":
                    saved, digest = read_submission(path)
                    if submissions is not None and (
                        saved.key != key or saved != submissions[key]
                    ):
                        raise _CaptureContradiction(key, digest, submissions[key])
                    if saved.key != key:
                        raise ValueError(
                            "The capture checkpoint differs from "
                            "the returned submission."
                        )
                    files[name] = digest
                else:
                    files[name] = _digest(path)
        if "submission.json" not in files:
            raise ValueError("The frozen capture checkpoint is missing.")
        captures.append({"key": key, "files": files})
    return {
        "schema": 1,
        "phase": "frozen",
        "configuration_sha256": _digest(run / "configuration.json"),
        "model_ledger_sha256": _digest(run / "model-ledger.json"),
        "captures": captures,
    }


def _fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("The capture binding contains a repeated JSON field.")
        result[key] = value
    return result


def _read(run: Path) -> bytes:
    try:
        (run / _REJECTION).lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError(
            "The capture was rejected after a checkpoint contradiction. "
            "Preserve this run and use a new evaluation run ID."
        )
    path = run / "capture-binding.json"
    _digest(path)
    content = path.read_bytes()
    record = json.loads(content, object_pairs_hook=_fields)
    if (
        not isinstance(record, dict)
        or type(record.get("schema")) is not int
        or record["schema"] != 1
    ):
        raise ValueError("The capture binding schema is invalid.")
    return content


def open_binding(run: Path, keys: tuple[str, ...]) -> bytes | None:
    path = run / "capture-binding.json"
    if not path.exists() and not path.is_symlink():
        if any(item.name != "evaluation.lock" for item in run.iterdir()):
            raise ValueError(
                "The capture binding is missing. Use the recorded evaluation revision."
            )
        write_report(path, {"schema": 1, "phase": "capturing"})
    content = _read(run)
    if json.loads(content) == {"schema": 1, "phase": "capturing"}:
        return None
    verify_binding(run, keys, content)
    return content


def freeze_binding(
    run: Path,
    keys: tuple[str, ...],
    bound: bytes | None,
    submissions: Mapping[str, Submission],
) -> bytes:
    if set(submissions) != set(keys):
        raise ValueError("The returned submissions do not match the capture roster.")
    try:
        record = _record(run, keys, submissions)
    except _CaptureContradiction as error:
        if bound is None:
            _reject(run, error)
        raise
    if bound is None:
        if json.loads(_read(run)) != {"schema": 1, "phase": "capturing"}:
            raise ValueError("The capture binding changed before publication.")
        write_report(run / "capture-binding.json", record)
        bound = _read(run)
    if _read(run) != bound or json.loads(bound) != record:
        raise ValueError("The frozen capture binding changed after submission.")
    return bound


def verify_binding(run: Path, keys: tuple[str, ...], bound: bytes) -> None:
    if _read(run) != bound or json.loads(bound) != _record(run, keys):
        raise ValueError("The frozen capture binding changed after submission.")
