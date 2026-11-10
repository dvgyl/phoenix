import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import TypedDict, cast

from phoenix_eval.submission import write_report


class LedgerIdentity(TypedDict):
    schema: int
    pipeline_run: str
    sha256: str | None


def ledger_digest(path: Path) -> str | None:
    if path.resolve() != path:
        raise ValueError("The model ledger path cannot contain symbolic links.")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("The model ledger must be a regular file.")
    with os.fdopen(descriptor, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_identity(path: Path) -> LedgerIdentity:
    try:
        if path.resolve() != path:
            raise ValueError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ValueError
        with os.fdopen(descriptor, "rb") as stream:
            content = stream.read(4097)
            if len(content) > 4096:
                raise ValueError
            data = json.loads(content)
        if (
            not isinstance(data, dict)
            or set(data) != {"schema", "pipeline_run", "sha256"}
            or type(data["schema"]) is not int
            or data["schema"] != 1
            or not isinstance(data["pipeline_run"], str)
            or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,71}", data["pipeline_run"]
            )
            or (
                data["sha256"] is not None
                and (
                    not isinstance(data["sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
                )
            )
        ):
            raise ValueError
        return cast(LedgerIdentity, data)
    except (OSError, ValueError, TypeError):
        raise ValueError(
            "The model ledger identity record is invalid or missing."
        ) from None


def verify_identity(workspace: Path, identity: LedgerIdentity) -> None:
    path = workspace / "runs" / identity["pipeline_run"] / "llm.jsonl"
    if ledger_digest(path) != identity["sha256"]:
        raise ValueError("The model ledger changed after submission.")


def freeze_identity(workspace: Path, run: Path, pipeline_run: str) -> LedgerIdentity:
    identity = LedgerIdentity(
        schema=1,
        pipeline_run=pipeline_run,
        sha256=ledger_digest(workspace / "runs" / pipeline_run / "llm.jsonl"),
    )
    record = run / "model-ledger.json"
    if record.exists() or record.is_symlink():
        if read_identity(record) != identity:
            raise ValueError("The model ledger changed after submission.")
    else:
        write_report(record, identity)
    return identity


def require_no_replay_ledger(workspace: Path, pipeline_run: str) -> None:
    if ledger_digest(workspace / "runs" / pipeline_run / "llm.jsonl") is not None:
        raise ValueError("Replay must not create a fresh model ledger.")
