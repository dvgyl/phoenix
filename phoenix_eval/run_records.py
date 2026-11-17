"""Store fixed run plans, terminal results, and published ledger snapshots."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

from phoenix_eval.dev_corpus import DevBinary
from phoenix_eval.model_ledger import ModelSummary, _open_ledger, read_events, summarize
from phoenix_eval.submission import write_report


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def directory(workspace: Path, run_id: str) -> Path:
    if not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}", run_id
    ) or run_id.startswith("m1-t0-"):
        raise ValueError("Use a development evaluation run ID.")
    path = workspace / "runs" / run_id
    if path.resolve() != path:
        raise ValueError("Use a physical run directory.")
    return path


@contextmanager
def evaluation_guard(
    workspace: Path, run: Path, replay_id: str | None = None
) -> Iterator[None]:
    descriptors = []
    marker = run / ".active"
    active = False
    try:
        for path, operation in (
            (workspace / "runs/.archive.lock", fcntl.LOCK_SH),
            (run / "evaluation.lock", fcntl.LOCK_EX | fcntl.LOCK_NB),
        ):
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Use regular evaluation lock files.")
            fcntl.flock(descriptor, operation)
            if path.name == ".archive.lock" and replay_id is not None:
                while not directory(workspace, replay_id).exists():
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                    from phoenix_eval.run_archive import restore_run

                    restore_run(workspace, replay_id)
                    fcntl.flock(descriptor, fcntl.LOCK_SH)
        if marker.resolve() != marker:
            raise ValueError("Use a regular active marker path.")
        with os.fdopen(
            os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), "w"
        ) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Use a regular active marker.")
            os.ftruncate(stream.fileno(), 0)
            stream.write(str(os.getpid()))
        active = True
        yield
    finally:
        if active:
            marker.unlink(missing_ok=True)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_json(path: Path) -> dict[str, object]:
    if path.resolve() != path or not path.is_file():
        raise ValueError("Use a regular run record.")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("The run record must be a JSON object.")
    return cast(dict[str, object], value)


def immutable(path: Path, value: object) -> None:
    encoded = json.dumps(value, sort_keys=True, allow_nan=False)
    if path.exists():
        if json.dumps(read_json(path), sort_keys=True, allow_nan=False) != encoded:
            raise ValueError(f"An immutable record changed: {path.name}")
        return
    write_report(path, value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("The record needs a string.")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("The record needs a string sequence.")
    return tuple(_string(item) for item in value)


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("The record needs a boolean.")
    return value


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("The record needs an object.")
    return cast(dict[str, object], value)


def _binary(value: dict[str, object]) -> DevBinary:
    return DevBinary(
        _string(value["name"]),
        _string(value["tier"]),
        _string(value["compiler"]),
        _strings(value["flags"]),
        _string(value["sha256"]),
        _string(value["category"]),
        _boolean(value["twin_valid"]),
    )


@dataclass(frozen=True)
class Selection:
    corpus: str = "corpus_dev"
    tiers: tuple[str, ...] = ("D0", "D1")
    levels: tuple[str, ...] = ("O0", "O2", "Os")
    quick: bool = False
    probe: bool = False

    def __post_init__(self) -> None:
        if (
            self.corpus != "corpus_dev"
            or not self.tiers
            or not self.levels
            or not set(self.tiers) <= {"D0", "D1", "D2", "D3"}
            or not set(self.levels) <= {"O0", "O2", "Os", "O3"}
        ):
            raise ValueError("Use development tiers and supported optimization levels.")


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    selection: Selection
    binaries: tuple[DevBinary, ...]
    configuration: dict[str, object]
    corpus_hash: str
    heldout_hash: str
    llm_cache: bool
    started: float
    dependencies: tuple[str, ...]
    replay_of: str | None = None

    @property
    def pipeline(self) -> str:
        return f"{self.run_id}-p"

    @classmethod
    def load(cls, path: Path) -> RunPlan:
        data = read_json(path)
        if set(data) != set(cls.__dataclass_fields__):
            raise ValueError("The fixed run plan has invalid fields.")
        selection = _mapping(data["selection"])
        binaries = data["binaries"]
        if (
            not isinstance(binaries, list)
            or not isinstance(data["started"], (float, int))
            or isinstance(data["started"], bool)
        ):
            raise ValueError("The fixed run plan has invalid binaries or start time.")
        parsed = tuple(_binary(_mapping(item)) for item in binaries)
        return cls(
            _string(data["run_id"]),
            Selection(
                _string(selection["corpus"]),
                _strings(selection["tiers"]),
                _strings(selection["levels"]),
                _boolean(selection["quick"]),
                _boolean(selection["probe"]),
            ),
            parsed,
            _mapping(data["configuration"]),
            _string(data["corpus_hash"]),
            _string(data["heldout_hash"]),
            _boolean(data["llm_cache"]),
            float(data["started"]),
            _strings(data["dependencies"]),
            _string(data["replay_of"]) if data["replay_of"] is not None else None,
        )


def ledger_snapshot(
    workspace: Path,
    run: Path,
    pipeline: str,
    *,
    name: str = "published-ledger",
    prefix: bytes | None = None,
) -> tuple[bytes, dict[str, ModelSummary]]:
    live = directory(workspace, pipeline) / "llm.jsonl"
    content = b""
    descriptor = _open_ledger(live)
    if descriptor is not None:
        with os.fdopen(descriptor, "rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            content = stream.read()
    if prefix is not None:
        if not content.startswith(prefix):
            raise ValueError("The replay ledger lost its published prefix.")
        content = prefix
    events = read_events(content.decode("utf-8").splitlines())
    snapshot = run / f"{name}.jsonl"
    if (run / f"{name}.json").exists():
        content = verify_ledger(workspace, run, name=name)
        events = read_events(content.decode("utf-8").splitlines())
    else:
        if snapshot.resolve() != snapshot:
            raise ValueError("Use a regular ledger snapshot path.")
        with NamedTemporaryFile(dir=run, delete_on_close=False) as staged:
            staged.write(content)
            staged.close()
            Path(staged.name).replace(snapshot)
    immutable(
        run / f"{name}.json",
        {"pipeline_run": pipeline, "bytes": len(content), "sha256": digest(content)},
    )
    return content, {
        key: summarize(events, key) for key in {event.binary for event in events}
    }


def verify_ledger(
    workspace: Path, run: Path, *, name: str = "published-ledger"
) -> bytes:
    record = read_json(run / f"{name}.json")
    path = run / f"{name}.jsonl"
    descriptor = _open_ledger(path)
    if descriptor is None:
        raise ValueError("The published ledger snapshot is missing.")
    with os.fdopen(descriptor, "rb") as stream:
        content = stream.read()
    if len(content) != record["bytes"] or digest(content) != record["sha256"]:
        raise ValueError("The published model ledger changed.")
    live = directory(workspace, str(record["pipeline_run"])) / "llm.jsonl"
    descriptor = _open_ledger(live)
    if descriptor is not None:
        with os.fdopen(descriptor, "rb") as stream:
            if stream.read(len(content)) != content:
                raise ValueError("The live model ledger lost its published prefix.")
    elif content:
        raise ValueError("The original model ledger is missing.")
    read_events(content.decode("utf-8").splitlines())
    return content


@dataclass(frozen=True)
class BinaryResult:
    binary: DevBinary
    fully_successful: bool
    categories: tuple[str, ...]
    held_out_cases: tuple[int, int]
    pending: bool
    details: dict[str, object]

    @classmethod
    def parse(cls, value: dict[str, object]) -> BinaryResult:
        binary = _binary(value)
        success, pending = (
            _boolean(value["fully_successful"]),
            _boolean(value.get("pending", False)),
        )
        categories, cases = _strings(value["categories"]), value["held_out_cases"]
        if (
            not isinstance(cases, (tuple, list))
            or len(cases) != 2
            or any(type(item) is not int or item < 0 for item in cases)
            or cases[0] > cases[1]
            or (
                success
                and (pending or categories or cases[0] != cases[1] or cases[1] == 0)
            )
        ):
            raise ValueError("Invalid binary result fields.")
        fields = {
            *DevBinary.__dataclass_fields__,
            "fully_successful",
            "pending",
            "categories",
            "held_out_cases",
        }
        return cls(
            binary,
            success,
            tuple(categories),
            (cases[0], cases[1]),
            pending,
            {name: item for name, item in value.items() if name not in fields},
        )

    def record(self) -> dict[str, object]:
        value = {
            **asdict(self.binary),
            **self.details,
            "fully_successful": self.fully_successful,
            "categories": list(self.categories),
            "held_out_cases": list(self.held_out_cases),
            "pending": self.pending,
        }
        return cast(dict[str, object], json.loads(json.dumps(value, allow_nan=False)))


def record_result(run: Path, key: str, result: BinaryResult) -> None:
    immutable(run / "results" / f"{key}.json", result.record())


def plan_record(plan: RunPlan) -> dict[str, object]:
    return cast(dict[str, object], asdict(plan))
