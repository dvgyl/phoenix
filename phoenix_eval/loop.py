"""Publish development loop rows without changing evaluation records."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import cast

from phoenix_eval import run as evaluation
from phoenix_eval import run_plan
from phoenix_eval.artifacts import atomic_bytes
from phoenix_eval.docker import WorkerError
from phoenix_eval.run import Publication
from phoenix_eval.run_records import RunPlan, Selection, _boolean, _string, _strings
from phoenix_eval.run_records import directory as _run

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
    atomic_bytes(path, content)


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
    def selection(self) -> Selection:
        return Selection(
            tiers=self.tiers,
            levels=self.levels,
            quick=self.quick or self.kind in ("quick", "noise"),
            probe=self.kind == "probe",
        )


@dataclass(frozen=True)
class Claim:
    run_id: str
    checkout: str
    commit: str
    request: Request
    row: int
    experiment: int | None
    noise_ref: int | None
    configuration_identity: dict[str, object]
    noise_data: tuple[str, ...] | None = None
    noise_verified: bool = False
    failure: tuple[str, ...] | None = None

    @property
    def children(self) -> tuple[str, ...]:
        return (
            (f"{self.run_id}-a", f"{self.run_id}-b")
            if self.request.kind == "noise"
            else (self.run_id,)
        )

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "row": self.row,
            "loop": self.request.kind,
            "milestone": "R0",
            "experiment": [self.experiment, 3] if self.experiment is not None else None,
            "noise_ref": self.noise_ref,
            "configuration_identity": self.configuration_identity,
            "label": self.request.label,
        }

    @classmethod
    def load(cls, path: Path) -> Claim:
        record = _read(path)
        request = _object(record["request"])
        if set(record) != set(cls.__dataclass_fields__) or set(request) != set(
            Request.__dataclass_fields__
        ):
            raise ValueError("Unknown loop claim. Preserve it for recovery.")
        row = record["row"]
        if type(row) is not int or row < 1:
            raise ValueError("Unknown loop row. Preserve it for recovery.")
        claim = cls(
            _string(record["run_id"]),
            _string(record["checkout"]),
            _hash(record["commit"], 40),
            Request(
                _string(request["kind"]),
                _strings(request["tiers"]),
                _strings(request["levels"]),
                _boolean(request["llm_cache"]),
                _string(request["label"]) if request["label"] is not None else None,
                _boolean(request["quick"]),
            ),
            row,
            cast(int | None, record["experiment"]),
            cast(int | None, record["noise_ref"]),
            _object(record["configuration_identity"]),
            _strings(record["noise_data"])
            if record["noise_data"] is not None
            else None,
            _boolean(record["noise_verified"]),
            _strings(record["failure"]) if record["failure"] is not None else None,
        )
        if (
            claim.run_id != path.parent.name
            or any(
                type(value) is not int or not 1 <= value <= limit
                for value, limit in (
                    (claim.row, sys.maxsize),
                    (claim.experiment, 3),
                    (claim.noise_ref, claim.row - 1),
                )
                if value is not None
            )
            or (claim.experiment is not None) != (claim.request.kind == "full")
            or (claim.noise_data is not None and len(claim.noise_data) != 2)
            or (claim.failure is not None and len(claim.failure) != 2)
            or (
                claim.noise_verified
                and (claim.noise_data is None or claim.failure is not None)
            )
            or (claim.request.kind != "noise" and claim.noise_data is not None)
        ):
            raise ValueError("Unknown loop claim state. Preserve it for recovery.")
        if claim.noise_data is not None:
            for value in claim.noise_data:
                _hash(value)
        return claim


def noise_document(
    run_id: str,
    publications: list[Publication],
    configuration_identity: dict[str, object],
) -> dict[str, object]:
    """Count tier flips on identical binaries and held-out cases."""
    children = [publication.document for publication in publications]
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

    if any(
        publication.plan.configuration.get("configuration_identity")
        != configuration_identity
        for publication in publications
    ):
        raise ValueError("Noise configuration identities changed.")

    before, after = (
        {result.binary: result for result in publication.results}
        for publication in publications
    )
    if (
        before.keys() != after.keys()
        or not before
        or any(
            publications[0].plan.configuration[field]
            != publications[1].plan.configuration[field]
            for field in ("case_hashes", "case_counts")
        )
    ):
        raise ValueError("Noise binary or held-out identities changed.")
    counts: dict[str, list[int]] = {}
    audit = []
    for identity, old in before.items():
        new = after[identity]
        outcomes = [old.fully_successful, new.fully_successful]
        count = counts.setdefault(old.binary.tier, [0, 0])
        count[0] += outcomes[0] != outcomes[1]
        count[1] += 1
        audit.append({**new.record(), "noise_outcomes": outcomes})
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


def _noise_identity(workspace: Path) -> tuple[str, str]:
    _, corpus, heldout = run_plan._selection(workspace, Selection(quick=True))
    return _hash(corpus), _hash(heldout)


class Loop:
    def __init__(self, workspace: Path, checkout: Path):
        self.workspace = _physical(workspace)
        self.checkout = _physical(checkout)
        self.scoreboard = checkout / "docs/SCOREBOARD.md"
        self.active = workspace / "runs/.active-loop.json"

    def _save(self, claim: Claim, previous: Claim | None = None) -> Claim:
        path = _run(self.workspace, claim.run_id) / "loop.json"
        if previous is None:
            _immutable(path, asdict(claim))
        else:
            if _encode(_read(path)) != _encode(asdict(previous)):
                raise ValueError("The loop claim changed. Preserve it for recovery.")
            _atomic(path, _encode(asdict(claim)))
        return claim

    def _claim(self, run_id: str) -> Claim:
        claim = Claim.load(_run(self.workspace, run_id) / "loop.json")
        if claim.checkout != str(self.checkout):
            raise ValueError("Recover the active loop from its recorded checkout.")
        return claim

    @contextmanager
    def _unselected(self, claim: Claim) -> Iterator[bool]:
        with ExitStack() as locks:
            for identifier in dict.fromkeys((claim.run_id, *claim.children)):
                run = _run(self.workspace, identifier)
                if run.exists():
                    lock = locks.enter_context(
                        _physical(run / "evaluation.lock").open("a+b")
                    )
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    allowed = {"evaluation.lock"}
                    if identifier == claim.run_id:
                        allowed.add("loop.json")
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

    def _noise_reference(self, rows: list[list[str]]) -> int | None:
        noise_rows = [row for row in reversed(rows) if row[5] == "noise"]
        if not noise_rows:
            return None
        try:
            corpus, heldout = _noise_identity(self.workspace)
        except (ValueError, OSError, KeyError, WorkerError, subprocess.SubprocessError):
            return None
        for row in noise_rows:
            path = _run(self.workspace, row[1]) / "scoreboard.json"
            if not path.exists():
                continue
            noise = _read(path)
            expected = {
                "run_id": row[1],
                "row": int(row[0]),
                "loop": "noise",
                "corpus": "corpus_dev",
                "corpus_hash": corpus,
                "heldout_hash": heldout,
                "quick_set": 1,
                "configuration_identity": run_plan.model_identity(),
            }
            if all(noise.get(key) == value for key, value in expected.items()):
                return int(row[0])
        return None

    def _child(self, run_id: str, claim: Claim) -> Publication:
        path = _run(self.workspace, run_id) / "plan.json"
        if not path.exists():
            raise ValueError(
                f"Run {run_id} has no fixed plan. Preserve the active-loop record."
            )
        plan = RunPlan.load(path)
        if plan.replay_of is not None:
            raise ValueError("A loop allocation cannot use a replay plan.")
        if plan.configuration.get("revision") != claim.commit or any(
            plan.configuration.get(key) != value
            for key, value in claim.metadata.items()
        ):
            raise ValueError("The fixed plan differs from the loop allocation.")
        if (
            plan.selection != claim.request.selection
            or plan.llm_cache != claim.request.llm_cache
        ):
            raise ValueError("The fixed selection differs from the loop request.")
        return evaluation.publish(self.workspace, run_id)

    def _noise_check(self, claim: Claim) -> None:
        if (
            revision(self.checkout) != claim.commit
            or _noise_identity(self.workspace) != claim.noise_data
            or run_plan.model_identity() != claim.configuration_identity
        ):
            raise ValueError("Commit or data changed during noise recovery.")

    def _finish(self, claim: Claim) -> dict[str, object]:
        run = _run(self.workspace, claim.run_id)
        if claim.request.kind == "noise":
            left = self._child(claim.children[0], claim)
            pending = _run(self.workspace, claim.children[1])
            if not (pending / "plan.json").exists():
                pending.mkdir(parents=True, exist_ok=True)
                with _physical(pending / "evaluation.lock").open("a+b") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if any(
                        path.name != "evaluation.lock" for path in pending.iterdir()
                    ) or any(
                        _run(self.workspace, f"{pending.name}{suffix}").exists()
                        for suffix in ("-p", "-check")
                    ):
                        raise ValueError("Unknown unfinished noise child state.")
                    _immutable(
                        pending / "plan.json",
                        asdict(
                            replace(
                                left.plan,
                                run_id=pending.name,
                                dependencies=(
                                    f"{pending.name}-p",
                                    f"{pending.name}-check",
                                ),
                            )
                        ),
                    )
                    for suffix in ("-p", "-check"):
                        _run(self.workspace, f"{pending.name}{suffix}").mkdir(
                            exist_ok=True
                        )
            publications = [left, self._child(pending.name, claim)]
            if claim.noise_data != (left.plan.corpus_hash, left.plan.heldout_hash):
                raise ValueError("Noise differs from its initial data.")
            if not claim.noise_verified:
                self._noise_check(claim)
                self._save(replace(claim, noise_verified=True), claim)
            document = noise_document(
                claim.run_id, publications, claim.configuration_identity
            )
            document["result_refs"] = {
                publication.plan.run_id: publication.sha256
                for publication in publications
            }
            _immutable(
                run / "plan.json",
                asdict(
                    replace(left.plan, run_id=claim.run_id, dependencies=claim.children)
                ),
            )
            _immutable(run / "scoreboard.json", document)
        else:
            document = self._child(claim.run_id, claim).document
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
                prior = self._claim(_string(active["run_id"]))
                if prior.failure is not None:
                    with self._unselected(prior) as safe:
                        if not safe:
                            raise ValueError(
                                "Unknown preselection failure state. Preserve it."
                            )
                        self.active.unlink()
                else:
                    recovered = self._finish(prior)
                    self.active.unlink()
                if run_id == prior.run_id and prior.failure is None:
                    if prior.request != request:
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
                if prior.request != request or prior.commit != commit:
                    raise ValueError("The run ID has a conflicting request or commit.")
                if prior.failure is not None:
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
            if not re.search(r"^Milestone: R0,", status, re.MULTILINE):
                raise ValueError("The R0 loop requires milestone R0 in docs/STATUS.md.")
            used = sum(row[5] == "full" and row[7] == "R0" for row in rows)
            if request.kind == "full" and used >= 3:
                raise ValueError("The R0 full-loop budget of 3 is used.")
            claim = Claim(
                run_id,
                str(self.checkout),
                commit,
                request,
                len(rows) + 1,
                used + 1 if request.kind == "full" else None,
                self._noise_reference(rows),
                run_plan.model_identity(),
            )
            for child in claim.children if request.kind == "noise" else ():
                if _run(self.workspace, child).exists():
                    raise ValueError("A noise child run ID already exists.")
            self._save(claim)
            _atomic(self.active, _encode({"schema": 1, "run_id": run_id}))
            try:
                if request.kind == "noise":
                    claim = self._save(
                        replace(claim, noise_data=_noise_identity(self.workspace)),
                        claim,
                    )
                for child in claim.children:
                    if request.kind == "noise":
                        self._noise_check(claim)
                    evaluation.evaluate(
                        self.workspace,
                        child,
                        request.selection,
                        request.llm_cache,
                        metadata=claim.metadata,
                    )
                if request.kind == "noise":
                    self._noise_check(claim)
            except (
                ValueError,
                OSError,
                KeyError,
                WorkerError,
                subprocess.SubprocessError,
            ) as error:
                try:
                    with self._unselected(claim) as safe:
                        if safe:
                            self._save(
                                replace(
                                    claim, failure=(type(error).__name__, str(error))
                                ),
                                claim,
                            )
                            self.active.unlink()
                except (OSError, ValueError):
                    pass
                raise
            document = self._finish(claim)
            self.active.unlink()
            return document


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
        document = Loop(workspace, checkout).execute(request, args.run_id)
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
