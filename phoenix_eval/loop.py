"""Publish development loop rows without changing evaluation records."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib
import json
import math
import os
import re
import subprocess
import sys
import uuid
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from tempfile import NamedTemporaryFile
from typing import Protocol, cast

from phoenix_eval.docker import WorkerError

HEADER = (
    "| row | run_id | commit | corpus | data hash | loop | cache | milestone | exp | "
    "main metric | tier 0 | tier 1 | tier 2 | tier 3 | maintainable | "
    "held-out passed | "
    "integrity | edge cov | escape | literal % | goto/100 | cost median | free GiB |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    "---|---|---|---|---|\n"
)
TIERS = ("D0", "D1", "D2", "D3")
LEVELS = ("O0", "O2", "Os", "O3")


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object.")
    return cast(dict[str, object], value)


def _records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("Expected a list of records.")
    return [_object(item) for item in value]


def _physical(path: Path) -> Path:
    if path.resolve() != path:
        raise ValueError(f"Use a physical path: {path}")
    return path


def _read(path: Path) -> dict[str, object]:
    return _object(json.loads(_physical(path).read_bytes()))


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, allow_nan=False).encode() + b"\n"


def _atomic(path: Path, content: bytes) -> None:
    _physical(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            staged.replace(path)
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            staged.unlink(missing_ok=True)


def _immutable(path: Path, value: object) -> None:
    if path.exists():
        if _encode(_read(path)) != _encode(value):
            raise ValueError(f"An immutable loop record changed: {path.name}")
    else:
        _atomic(path, _encode(value))


def _hash(value: object, length: int = 64) -> str:
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        raise ValueError("Invalid recorded hash.")
    return value


def _run(workspace: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", run_id):
        raise ValueError("Invalid development run ID.")
    if run_id.startswith("m1-t0-"):
        raise ValueError("Use a development run ID.")
    return _physical(workspace / "runs" / run_id)


def revision(checkout: Path, *, clean: bool = True) -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ("git", "-C", str(checkout), *args),
            check=True,
            text=True,
            capture_output=True,
            timeout=15,
            env={
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            },
        ).stdout.strip()

    if clean and git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "phoenix/",
        "phoenix_eval/",
    ):
        raise ValueError("Commit tracked and untracked pipeline and evaluator changes.")
    return _hash(git("rev-parse", "HEAD"), 40)


def _pair(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int or item < 0 for item in value)
        or value[0] > value[1]
    ):
        raise ValueError("Invalid count or denominator.")
    return value[0], value[1]


def _identity(record: dict[str, object]) -> tuple[str, ...]:
    flags = record.get("flags")
    if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
        raise ValueError("Invalid binary flags.")
    levels = [level for level in LEVELS if f"-{level}" in flags]
    if len(levels) != 1 or record.get("tier") not in TIERS:
        raise ValueError("Invalid binary cell.")
    return (
        str(record["name"]),
        str(record["tier"]),
        str(record["compiler"]),
        *flags,
        _hash(record["sha256"]),
    )


def validate_score(
    document: dict[str, object], plan: dict[str, object], run: Path
) -> None:
    """Check identities and fixed denominators against the recorded plan."""
    config = _object(plan["configuration"])
    for key in ("run_id", "corpus_hash", "heldout_hash"):
        if document.get(key) != plan.get(key):
            raise ValueError(f"The scoreboard differs from the plan: {key}")
    for key in ("corpus_hash", "heldout_hash"):
        _hash(document[key])
    _hash(document["commit"], 40)
    if (
        document["commit"] != config["revision"]
        or document.get("corpus") != "corpus_dev"
    ):
        raise ValueError("The scoreboard has a different commit or corpus.")
    for key in ("row", "loop", "milestone", "experiment", "noise_ref"):
        if document.get(key) != config.get(key):
            raise ValueError(f"The scoreboard metadata differs: {key}")
    if document.get("cache") != ("warm" if plan["llm_cache"] else "cold"):
        raise ValueError("The scoreboard cache setting differs.")
    selected = _records(plan["binaries"])
    records = _records(document["binaries"])
    roster = {_identity(item) for item in selected}
    if len(roster) != len(selected) or len(records) != len(selected):
        raise ValueError("The fixed denominator changed.")
    if {_identity(item) for item in records} != roster:
        raise ValueError("The binary identities changed.")
    hashes, counts = _object(config["case_hashes"]), _object(config["case_counts"])
    refs = _object(document["result_refs"])
    keys = [str(record["task_key"]) for record in records]
    if (
        len(set(keys)) != len(keys)
        or set(keys) != set(refs)
        or set(keys) != set(hashes)
        or set(keys) != set(counts)
    ):
        raise ValueError("The result references differ from the fixed denominator.")
    cells: dict[str, dict[str, list[int]]] = {}
    selection = _object(plan["selection"])
    levels = cast(list[str], selection["levels"])
    totals = [0, 0]
    failures: Counter[str] = Counter()
    stopped = False
    for record, key in zip(records, keys, strict=True):
        if not re.fullmatch(r"[A-Za-z0-9._-]+", key) or key in (".", ".."):
            raise ValueError("Invalid result reference.")
        if _hash(record["heldout_hash"]) != _hash(hashes[key]):
            raise ValueError("The held-out identity changed.")
        n, total = _pair(record["held_out_cases"])
        if type(counts[key]) is not int or total != cast(int, counts[key]) * 4:
            raise ValueError("The held-out denominator changed.")
        success, pending = record.get("fully_successful"), record.get("pending", False)
        categories = record.get("categories")
        if (
            type(success) is not bool
            or type(pending) is not bool
            or not isinstance(categories, list)
            or any(not isinstance(item, str) for item in categories)
        ):
            raise ValueError("Invalid binary outcome.")
        if success and (pending or categories or n != total or total == 0):
            raise ValueError("An unfinished or failed binary cannot pass.")
        if pending:
            if refs[key] is not None or n != 0:
                raise ValueError("An unfinished binary has a terminal result.")
        else:
            path = _physical(run / "results" / f"{key}.json")
            if (
                hashlib.sha256(path.read_bytes()).hexdigest() != _hash(refs[key])
                or _read(path) != record
            ):
                raise ValueError("A terminal result changed.")
        stopped |= bool(pending)
        failures.update(categories)
        totals[0] += n
        totals[1] += total
        tier = str(record["tier"])
        cell = cells.setdefault(tier, {level: [0, 0] for level in levels})
        level = next(
            level for level in LEVELS if f"-{level}" in cast(list[str], record["flags"])
        )
        if level not in cell or tier not in cast(list[str], selection["tiers"]):
            raise ValueError("A binary is outside the selected cells.")
        cell[level][0] += success is True
        cell[level][1] += 1
    if document.get("success") != cells or document.get("held_out_cases") != totals:
        raise ValueError("The aggregate counts differ from the fixed denominator.")
    if document.get("failure_categories") != dict(failures) or document.get(
        "integrity_failures"
    ) != sum("integrity" in cast(list[str], item["categories"]) for item in records):
        raise ValueError("The aggregate failure counts differ.")
    if document.get("run_state") != ("stopped" if stopped else "complete"):
        raise ValueError("The run state differs from its results.")


def _number(value: object) -> str:
    if value is None:
        return "-"
    if type(value) not in (int, float) or not math.isfinite(cast(float, value)):
        raise ValueError("Expected a finite measurement.")
    return f"{value:.6g}"


def _ratio(value: object) -> str:
    return "-" if value is None else "/".join(map(str, _pair(value)))


def format_row(document: dict[str, object]) -> str:
    """Format the ROADMAP section 6.3 cells. Missing measurements stay null."""

    def tier_values(
        key: str, *, distribution: bool = False, ratio: bool = False
    ) -> str:
        values = document.get(key)
        if values is None:
            return "-"
        parts = []
        for tier, value in _object(values).items():
            if distribution and value is not None:
                value = _object(value).get("median")
            if value is not None:
                parts.append(f"{tier} {_ratio(value) if ratio else _number(value)}")
        return "; ".join(parts) or "-"

    def overall(key: str) -> str:
        value = document.get(key)
        if not isinstance(value, dict):
            return _number(value)
        values = [
            item.get(key)
            for item in _records(document.get("binaries", []))
            if item.get(key) is not None
        ]
        if values and key == "goto_per_100_lines":
            return _number(median(cast(list[float], values)))
        measured = [item for item in value.values() if item is not None]
        if len(measured) > 1:
            raise ValueError(f"An overall measurement is required: {key}")
        return _number(measured[0] if measured else None)

    success = _object(document.get("success") or {})
    noise = document.get("noise")
    tiers = []
    for tier in TIERS:
        cells = _object(success.get(tier) or {})
        tiers.append(
            _ratio(_object(noise).get(tier))
            if noise is not None
            else "; ".join(
                f"{level} {_ratio(cells[level])}" for level in LEVELS if level in cells
            )
            or "-"
        )
    metric = "-"
    d0 = _object(success.get("D0") or {}).get("O0")
    if d0 is not None and _pair(d0)[1]:
        n, total = _pair(d0)
        metric = f"D0 -O0 binary success rate = {_number(100 * n / total)}% (gate 80%)"
    maintainable = _object(document.get("maintainable") or {})
    maintain = (
        "; ".join(
            f"{index}: {_ratio(maintainable[tier])}"
            for index, tier in ((1, "D1"), (2, "D2"))
            if maintainable.get(tier) is not None
        )
        or "-"
    )
    row_cells = [
        str(document["row"]),
        str(document["run_id"]),
        str(document["commit"])[:12],
        str(document["corpus"]),
        f"{str(document['corpus_hash'])[:8]}/{str(document['heldout_hash'])[:8]}",
        str(document["loop"]),
        str(document["cache"]),
        str(document["milestone"]),
        _ratio(document.get("experiment")),
        metric,
        *tiers,
        maintain,
        _ratio(document.get("held_out_cases")),
        _number(document.get("integrity_failures")),
        tier_values("dev_edge_coverage_median"),
        tier_values("escape_rate", ratio=True),
        overall("literal_mode_byte_share"),
        overall("goto_per_100_lines"),
        tier_values("cost_usd", distribution=True),
        _number(document.get("free_storage_gib")),
    ]
    if any("|" in cell or "\n" in cell or "\r" in cell for cell in row_cells):
        raise ValueError("A scoreboard cell contains a table separator.")
    return "| " + " | ".join(row_cells) + " |\n"


def table(path: Path) -> tuple[str, list[list[str]]]:
    if not path.exists():
        return HEADER, []
    text = _physical(path).read_text()
    if text.count(HEADER) != 1:
        raise ValueError("The scoreboard header is missing or changed.")
    rows: list[list[str]] = []
    for line in text.split(HEADER, 1)[1].splitlines():
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if (
            not line.startswith("|")
            or not line.endswith("|")
            or len(cells) != 23
            or cells[0] != str(len(rows) + 1)
        ):
            raise ValueError("Invalid scoreboard row sequence.")
        _run(path.parent.parent, cells[1])
        if any(row[1] == cells[1] for row in rows):
            raise ValueError("Duplicate scoreboard run ID.")
        rows.append(cells)
    return text, rows


def append_row(path: Path, document: dict[str, object]) -> None:
    text, rows = table(path)
    line = format_row(document)
    cells = [cell.strip() for cell in line.split("|")[1:-1]]
    existing = [row for row in rows if row[1] == document["run_id"]]
    if existing:
        if existing != [cells]:
            raise ValueError("A published run ID has a conflicting row.")
        return
    if document["row"] != len(rows) + 1:
        raise ValueError("The row number is already used or is out of sequence.")
    _atomic(path, (text.rstrip() + "\n" + line).encode())


@dataclass(frozen=True)
class Request:
    kind: str = "full"
    tiers: tuple[str, ...] = ("D0", "D1")
    levels: tuple[str, ...] = ("O0", "O2", "Os")
    llm_cache: bool = True
    label: str | None = None
    quick: bool = False

    def __post_init__(self) -> None:
        if (
            self.kind not in ("full", "quick", "probe", "noise")
            or not self.tiers
            or not self.levels
            or len(set(self.tiers)) != len(self.tiers)
            or len(set(self.levels)) != len(self.levels)
            or not set(self.tiers) <= set(TIERS)
            or not set(self.levels) <= set(LEVELS[:3])
        ):
            raise ValueError(
                "Use R0 loop kinds, development tiers, and optimization levels."
            )
        if self.kind == "noise" and (
            self.llm_cache or self.tiers != ("D0", "D1") or self.levels != LEVELS[:3]
        ):
            raise ValueError("Noise requires the complete cold quick set.")
        if self.quick and self.kind != "probe":
            raise ValueError("Use the quick flag with a probe request.")

    @property
    def quick_selection(self) -> bool:
        return self.quick or self.kind in ("quick", "noise")

    def record(self) -> dict[str, object]:
        return _object(json.loads(_encode(asdict(self))))


class Backend(Protocol):
    def evaluate(
        self,
        workspace: Path,
        run_id: str,
        request: Request,
        metadata: dict[str, object],
    ) -> None: ...
    def publish(self, workspace: Path, run_id: str) -> dict[str, object]: ...
    def noise_identity(self, workspace: Path) -> tuple[str, str]: ...
    def configuration_identity(self) -> dict[str, object]: ...


def noise_document(
    run_id: str,
    children: list[dict[str, object]],
    configuration_identity: dict[str, object],
) -> dict[str, object]:
    """Count tier flips on identical binaries and held-out cases."""
    left, right = children
    for field in (
        "commit",
        "corpus_hash",
        "heldout_hash",
        "quick_set",
        "row",
        "milestone",
    ):
        if left.get(field) != right.get(field):
            raise ValueError(f"Noise identities changed: {field}")
    if left.get("quick_set") != 1 or any(
        child.get("cache") != "cold" for child in children
    ):
        raise ValueError("Noise requires quick set 1 and the cold cache.")

    def indexed(child: dict[str, object]) -> dict[tuple[str, ...], dict[str, object]]:
        return {
            (*_identity(item), _hash(item["heldout_hash"])): item
            for item in _records(child["binaries"])
        }

    before, after = indexed(left), indexed(right)
    if before.keys() != after.keys() or not before:
        raise ValueError("Noise binary or held-out identities changed.")
    counts: dict[str, list[int]] = {}
    audit = []
    for identity, old in before.items():
        new = after[identity]
        outcomes = [old["fully_successful"], new["fully_successful"]]
        count = counts.setdefault(str(old["tier"]), [0, 0])
        count[0] += outcomes[0] != outcomes[1]
        count[1] += 1
        audit.append({**new, "noise_outcomes": outcomes})
    return {
        **right,
        "run_id": run_id,
        "loop": "noise",
        "experiment": None,
        "noise": counts,
        "noise_rate": {
            tier: (n + 0.5) / (total + 1) for tier, (n, total) in counts.items()
        },
        "binaries": audit,
        "dependencies": [child["run_id"] for child in children],
        "configuration_identity": configuration_identity,
        "child_models": {str(child["run_id"]): child["models"] for child in children},
        "run_state": "stopped"
        if any(child["run_state"] == "stopped" for child in children)
        else "complete",
        "cost_usd": None,
        "child_cost_usd": {
            str(child["run_id"]): child.get("cost_usd") for child in children
        },
        "loop_minutes": sum(cast(float, child["loop_minutes"]) for child in children),
        "peak_memory_gib": max(
            (
                cast(float, child["peak_memory_gib"])
                for child in children
                if child.get("peak_memory_gib") is not None
            ),
            default=None,
        ),
        "peak_storage_gib": max(
            cast(float, child["peak_storage_gib"]) for child in children
        ),
        "free_storage_gib": right.get("free_storage_gib"),
    }


class Loop:
    def __init__(self, workspace: Path, checkout: Path, backend: Backend):
        self.workspace = _physical(workspace)
        self.checkout = _physical(checkout)
        self.backend = backend
        self.scoreboard = checkout / "docs/SCOREBOARD.md"
        self.active = workspace / "runs/.active-loop.json"

    @contextmanager
    def _unselected(self, claim: dict[str, object]) -> Iterator[bool]:
        run_id = str(claim["run_id"])
        dependencies = (
            [f"{run_id}-a", f"{run_id}-b"]
            if _object(claim["request"])["kind"] == "noise"
            else []
        )
        if claim["dependencies"] != dependencies:
            yield False
            return
        with ExitStack() as locks:
            for identifier in [run_id, *dependencies]:
                run = _run(self.workspace, identifier)
                if run.exists():
                    lock = locks.enter_context(
                        _physical(run / "evaluation.lock").open("a+b")
                    )
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    allowed = {"evaluation.lock"}
                    if identifier == run_id:
                        allowed |= {
                            "loop.json",
                            "noise-identity.json",
                            "preselection-failure.json",
                        }
                    if any(
                        path.name not in allowed or not _physical(path).is_file()
                        for path in run.iterdir()
                    ):
                        yield False
                        return
                if any(
                    _run(self.workspace, f"{identifier}{suffix}").exists()
                    for suffix in ("-p", "-check")
                ):
                    yield False
                    return
            yield True

    def _preselection_failed(self, claim: dict[str, object]) -> bool:
        path = _run(self.workspace, str(claim["run_id"])) / "preselection-failure.json"
        if not path.exists():
            return False
        record = _read(path)
        error = _object(record.get("error"))
        if (
            set(record)
            != {
                "schema",
                "run_id",
                "state",
                "claim_sha256",
                "error",
                "experiment",
                "selection_fixed",
                "paid_pipeline_work",
            }
            or record["schema"] != 1
            or record["run_id"] != claim["run_id"]
            or record["state"] != "preselection_failed"
            or record["claim_sha256"] != hashlib.sha256(_encode(claim)).hexdigest()
            or record["experiment"] is not None
            or record["selection_fixed"] is not False
            or record["paid_pipeline_work"] is not False
            or set(error) != {"type", "message"}
            or any(not isinstance(value, str) for value in error.values())
        ):
            raise ValueError("Unknown preselection failure state. Preserve it.")
        return True

    def _record_preselection_failure(
        self, claim: dict[str, object], error: Exception
    ) -> None:
        try:
            with self._unselected(claim) as safe:
                if not safe:
                    return
                _immutable(
                    _run(self.workspace, str(claim["run_id"]))
                    / "preselection-failure.json",
                    {
                        "schema": 1,
                        "run_id": claim["run_id"],
                        "state": "preselection_failed",
                        "claim_sha256": hashlib.sha256(_encode(claim)).hexdigest(),
                        "error": {"type": type(error).__name__, "message": str(error)},
                        "experiment": None,
                        "selection_fixed": False,
                        "paid_pipeline_work": False,
                    },
                )
                self.active.unlink()
        except (OSError, ValueError):
            return

    def _noise_reference(
        self, rows: list[list[str]], configuration_identity: dict[str, object]
    ) -> int | None:
        noise_rows = [row for row in reversed(rows) if row[5] == "noise"]
        if not noise_rows:
            return None
        try:
            corpus, heldout = self.backend.noise_identity(self.workspace)
        except (ValueError, OSError, KeyError, WorkerError, subprocess.SubprocessError):
            return None
        for row in noise_rows:
            path = _run(self.workspace, row[1]) / "scoreboard.json"
            if not path.exists():
                continue
            noise = _read(path)
            if (
                noise.get("run_id") == row[1]
                and noise.get("row") == int(row[0])
                and noise.get("loop") == "noise"
                and noise.get("corpus") == "corpus_dev"
                and noise.get("corpus_hash") == corpus
                and noise.get("heldout_hash") == heldout
                and noise.get("quick_set") == 1
                and noise.get("configuration_identity") == configuration_identity
            ):
                return int(row[0])
        return None

    def _claim(self, run_id: str) -> dict[str, object]:
        claim = _read(_run(self.workspace, run_id) / "loop.json")
        if (
            set(claim)
            != {
                "schema",
                "run_id",
                "checkout",
                "commit",
                "request",
                "metadata",
                "dependencies",
            }
            or claim.get("schema") != 1
            or claim.get("run_id") != run_id
        ):
            raise ValueError("Unknown active-loop record. Preserve it for recovery.")
        if claim.get("checkout") != str(self.checkout):
            raise ValueError("Recover the active loop from its recorded checkout.")
        request = _object(claim["request"])
        metadata = _object(claim["metadata"])
        if (
            request.get("kind") not in ("full", "quick", "probe", "noise")
            or metadata.get("loop") != request["kind"]
        ):
            raise ValueError("Unknown loop request state.")
        return claim

    def _child(self, run_id: str, claim: dict[str, object]) -> dict[str, object]:
        run = _run(self.workspace, run_id)
        if not (run / "plan.json").exists():
            raise ValueError(
                f"Run {run_id} has no fixed plan. Preserve the active-loop record."
            )
        plan = _read(run / "plan.json")
        if plan.get("run_id") != run_id:
            raise ValueError("The fixed plan has a conflicting run ID.")
        config = _object(plan["configuration"])
        if config.get("revision") != claim["commit"] or any(
            config.get(key) != value
            for key, value in _object(claim["metadata"]).items()
        ):
            raise ValueError("The fixed plan differs from the loop allocation.")
        request, selection = _object(claim["request"]), _object(plan["selection"])
        expected = {
            "corpus": "corpus_dev",
            "tiers": request["tiers"],
            "levels": request["levels"],
            "quick": request["quick"] or request["kind"] in ("quick", "noise"),
            "probe": request["kind"] == "probe",
        }
        if selection != expected or plan["llm_cache"] != request["llm_cache"]:
            raise ValueError("The fixed selection differs from the loop request.")
        document = _object(
            json.loads(_encode(self.backend.publish(self.workspace, run_id)))
        )
        if document != _read(run / "scoreboard.json"):
            raise ValueError(
                "The returned scoreboard differs from its published record."
            )
        validate_score(document, plan, run)
        return document

    def _finish(self, claim: dict[str, object]) -> dict[str, object]:
        run_id = str(claim["run_id"])
        run = _run(self.workspace, run_id)
        if _object(claim["request"])["kind"] == "noise":
            dependencies = claim.get("dependencies")
            if dependencies != [f"{run_id}-a", f"{run_id}-b"]:
                raise ValueError("Unknown noise dependency state.")
            left = self._child(str(dependencies[0]), claim)
            pending = _run(self.workspace, str(dependencies[1]))
            if not (pending / "plan.json").exists():
                pending.mkdir(parents=True, exist_ok=True)
                with _physical(pending / "evaluation.lock").open("a+b") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if any(
                        path.name not in ("evaluation.lock", "plan.json")
                        for path in pending.iterdir()
                    ):
                        raise ValueError("Unknown unfinished noise child state.")
                    plan = _read(
                        _run(self.workspace, str(dependencies[0])) / "plan.json"
                    )
                    # Both trials use this fixed selection. Recovery starts no work.
                    _immutable(
                        pending / "plan.json",
                        {
                            **plan,
                            "run_id": dependencies[1],
                            "dependencies": [
                                f"{dependencies[1]}-p",
                                f"{dependencies[1]}-check",
                            ],
                        },
                    )
                    for suffix in ("-p", "-check"):
                        _run(self.workspace, f"{dependencies[1]}{suffix}").mkdir(
                            exist_ok=True
                        )
            children = [left, self._child(str(dependencies[1]), claim)]
            snapshot = _read(run / "noise-identity.json")
            expected = [children[0]["corpus_hash"], children[0]["heldout_hash"]]
            identity = _object(_object(claim["metadata"])["configuration_identity"])
            if snapshot != {
                "commit": children[0]["commit"],
                "data": expected,
                "configuration_identity": identity,
            }:
                raise ValueError("Noise differs from its initial commit or data.")
            verified = run / "noise-verified.json"
            if not verified.exists():
                if (
                    revision(self.checkout) != snapshot["commit"]
                    or list(self.backend.noise_identity(self.workspace)) != expected
                    or self.backend.configuration_identity() != identity
                ):
                    raise ValueError("Commit or data changed during noise recovery.")
                _immutable(verified, snapshot)
            elif _read(verified) != snapshot:
                raise ValueError("The noise verification record changed.")
            document = noise_document(run_id, children, identity)
            document["result_refs"] = {
                child: hashlib.sha256(
                    (_run(self.workspace, child) / "scoreboard.json").read_bytes()
                ).hexdigest()
                for child in cast(list[str], dependencies)
            }
            plan = _read(_run(self.workspace, str(dependencies[0])) / "plan.json")
            _immutable(
                run / "plan.json",
                {**plan, "run_id": run_id, "dependencies": dependencies},
            )
            _immutable(run / "scoreboard.json", document)
        else:
            document = self._child(run_id, claim)
        append_row(self.scoreboard, document)
        return document

    def execute(self, request: Request, run_id: str | None = None) -> dict[str, object]:
        runs = _physical(self.workspace / "runs")
        runs.mkdir(parents=True, exist_ok=True)
        with (
            _physical(runs / ".loop.lock").open("a+b") as lock,
            _physical(runs / ".archive.lock").open("a+b") as archive,
        ):
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("Another workspace loop is active.") from error
            fcntl.flock(archive, fcntl.LOCK_SH)
            if self.active.exists():
                active = _read(self.active)
                if set(active) != {"schema", "run_id"} or active["schema"] != 1:
                    raise ValueError(
                        "Unknown active-loop state. Preserve it for recovery."
                    )
                prior = self._claim(str(active["run_id"]))
                if self._preselection_failed(prior):
                    with self._unselected(prior) as safe:
                        if not safe:
                            raise ValueError(
                                "Unknown preselection failure state. Preserve it."
                            )
                        self.active.unlink()
                else:
                    recovered = self._finish(prior)
                    self.active.unlink()
                    if run_id == prior["run_id"]:
                        if prior["request"] != request.record():
                            raise ValueError("The run ID has a conflicting request.")
                        return recovered
            commit = revision(self.checkout)
            run_id = (
                run_id
                or f"r0-{request.kind}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
                f"-{uuid.uuid4().hex[:8]}"
            )
            run = _run(self.workspace, run_id)
            if len(run_id) > (88 if request.kind == "noise" else 90):
                raise ValueError("The run ID leaves no space for evaluator suffixes.")
            if (run / "loop.json").exists():
                prior = self._claim(run_id)
                if prior["request"] != request.record() or prior["commit"] != commit:
                    raise ValueError("The run ID has a conflicting request or commit.")
                if self._preselection_failed(prior):
                    raise ValueError(
                        "The run failed before selection. Use a new run ID."
                    )
                return self._finish(prior)
            if run.exists():
                raise ValueError("The run ID already exists without a loop allocation.")
            _, rows = table(self.scoreboard)
            if any(row[1] == run_id for row in rows):
                raise ValueError(
                    "The run ID is already published without its allocation."
                )
            status = (self.checkout / "docs/STATUS.md").read_text()
            match = re.search(r"^Milestone: (R\d+),", status, re.MULTILINE)
            if match is None or match[1] != "R0":
                raise ValueError("The R0 loop requires milestone R0 in docs/STATUS.md.")
            used = sum(row[5] == "full" and row[7] == "R0" for row in rows)
            if request.kind == "full" and used >= 3:
                raise ValueError("The R0 full-loop budget of 3 is used.")
            configuration_identity = self.backend.configuration_identity()
            metadata: dict[str, object] = {
                "row": len(rows) + 1,
                "loop": request.kind,
                "milestone": match[1],
                "experiment": [used + 1, 3] if request.kind == "full" else None,
                "noise_ref": self._noise_reference(rows, configuration_identity),
                "configuration_identity": configuration_identity,
                "label": request.label,
            }
            dependencies = (
                [f"{run_id}-a", f"{run_id}-b"] if request.kind == "noise" else []
            )
            for child in dependencies:
                if _run(self.workspace, child).exists():
                    raise ValueError("A noise child run ID already exists.")
            claim = {
                "schema": 1,
                "run_id": run_id,
                "checkout": str(self.checkout),
                "commit": commit,
                "request": request.record(),
                "metadata": metadata,
                "dependencies": dependencies,
            }
            _immutable(run / "loop.json", claim)
            _atomic(self.active, _encode({"schema": 1, "run_id": run_id}))
            try:
                if request.kind == "noise":
                    identity = self.backend.noise_identity(self.workspace)
                    _immutable(
                        run / "noise-identity.json",
                        {
                            "commit": commit,
                            "data": list(identity),
                            "configuration_identity": configuration_identity,
                        },
                    )
                    for child in dependencies:
                        if (
                            revision(self.checkout) != commit
                            or self.backend.noise_identity(self.workspace) != identity
                            or self.backend.configuration_identity()
                            != configuration_identity
                        ):
                            raise ValueError("Commit or data changed during noise.")
                        self.backend.evaluate(self.workspace, child, request, metadata)
                    if (
                        revision(self.checkout) != commit
                        or self.backend.noise_identity(self.workspace) != identity
                        or self.backend.configuration_identity()
                        != configuration_identity
                    ):
                        raise ValueError("Commit or data changed during noise.")
                else:
                    self.backend.evaluate(self.workspace, run_id, request, metadata)
            except (
                ValueError,
                OSError,
                KeyError,
                WorkerError,
                subprocess.SubprocessError,
            ) as error:
                self._record_preselection_failure(claim, error)
                raise
            document = self._finish(claim)
            self.active.unlink()
            return document


class Evaluator:
    """Load the evaluator only at the command boundary."""

    def configuration_identity(self) -> dict[str, object]:
        return _object(
            importlib.import_module("phoenix_eval.run_plan").model_identity()
        )

    def evaluate(
        self,
        workspace: Path,
        run_id: str,
        request: Request,
        metadata: dict[str, object],
    ) -> None:
        records = importlib.import_module("phoenix_eval.run_records")
        selection = records.Selection(
            tiers=request.tiers,
            levels=request.levels,
            quick=request.quick_selection,
            probe=request.kind == "probe",
        )
        importlib.import_module("phoenix_eval.run").evaluate(
            workspace, run_id, selection, request.llm_cache, metadata=metadata
        )

    def publish(self, workspace: Path, run_id: str) -> dict[str, object]:
        run = _run(workspace, run_id)
        plan = importlib.import_module("phoenix_eval.run_records").RunPlan.load(
            run / "plan.json"
        )
        with _physical(run / "evaluation.lock").open("a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(f"Evaluation run {run_id} is still active.") from error
            return _object(
                importlib.import_module("phoenix_eval.run").publish(
                    workspace, run, plan
                )
            )

    def noise_identity(self, workspace: Path) -> tuple[str, str]:
        selection = importlib.import_module("phoenix_eval.run_records").Selection(
            quick=True
        )
        _, corpus, heldout = importlib.import_module(
            "phoenix_eval.run_plan"
        )._selection(workspace, selection)
        return _hash(corpus), _hash(heldout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("noise",))
    parser.add_argument("--tier", default="D0,D1")
    parser.add_argument("--opt", default="O0,O2,Os")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--llm-cache", choices=("on", "off"), default=None)
    parser.add_argument("--label")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        if args.command and (args.quick or args.probe):
            raise ValueError("Noise cannot also be a quick or probe row.")
        kind = args.command or (
            "probe" if args.probe else "quick" if args.quick else "full"
        )
        request = Request(
            kind,
            tuple(args.tier.split(",")),
            tuple(args.opt.split(",")),
            args.llm_cache != "off" if args.llm_cache is not None else kind != "noise",
            args.label,
            args.quick and args.probe,
        )
        workspace = Path(os.environ["PHOENIX_ROOT"])
        checkout = Path(__file__).resolve().parent.parent
        if not checkout.is_relative_to(workspace) or not workspace.is_absolute():
            raise ValueError("Keep the checkout and runs under PHOENIX_ROOT.")
        document = Loop(workspace, checkout, Evaluator()).execute(request, args.run_id)
        print(f"Published row {document['row']} for run {document['run_id']}.")
    except (
        ValueError,
        OSError,
        KeyError,
        WorkerError,
        subprocess.SubprocessError,
    ) as error:
        print(f"Loop failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
