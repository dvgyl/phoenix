import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from phoenix.ingest import InputRejected, inspect_binary
from phoenix.lift import LiftError
from phoenix.llm import select_provider
from phoenix.llm.ledger import NANODOLLARS, Budget, Ledger
from phoenix.llm.provider import (
    Completion,
    Provider,
    ProviderError,
    Request,
    RetryLater,
    Usage,
)
from phoenix.pipeline import Settings, reconstruct, write_json
from phoenix_eval.docker import Engine, WorkerError, freeze_images
from phoenix_eval.m0 import SEED
from phoenix_eval.platforms import verify_runtime
from phoenix_eval.provenance import CHECKOUT, evaluator_build
from phoenix_eval.worker import MAX_PROGRAM_BYTES

_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}")


class _RunRecord(TypedDict):
    version: int
    binary_sha256: str
    revision: str
    worker_source_sha256: str
    images: dict[str, str]
    seed: int
    ghidra: str
    java_home: str
    repair_limit: int
    astra_repair: bool
    provider: str
    budget_binary: int
    budget_run: int
    started: float


class _RecordedProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    def maximum_usage(self, request: Request) -> Usage:
        raise AssertionError("Replay cannot reserve tokens.")

    def complete(self, request: Request) -> Completion:
        raise AssertionError("Replay cannot call a model.")


def _dollars(value: str) -> int:
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise ValueError
        nanodollars = number * NANODOLLARS
        if nanodollars != int(nanodollars):
            raise ValueError
        return int(nanodollars)
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError("Use a positive dollar amount.") from exc


def _identifier(value: str) -> str:
    if not _ID.fullmatch(value):
        raise ValueError(
            "Use a run or binary ID with letters, numbers, dots, or dashes."
        )
    return value


def _default_tools(workspace: Path) -> tuple[Path, Path]:
    with (CHECKOUT / "tools.lock").open("rb") as stream:
        tools = tomllib.load(stream)
    ghidra = workspace / "tools/ghidra" / f"ghidra_{tools['ghidra']}_PUBLIC"
    java = workspace / "tools/jdk" / f"jdk-{tools['temurin_macos_arm64']}/Contents/Home"
    return ghidra, java


def _safe_input(path: Path, workspace: Path) -> Path:
    path = path.resolve()
    sealed = workspace / "sealed"
    if (
        not path.is_relative_to(workspace)
        or path.is_relative_to(workspace / "holdout")
        or (path.is_relative_to(sealed) and not path.is_relative_to(sealed / "release"))
    ):
        raise ValueError("Use a permitted input file in the Phoenix workspace.")
    return path


def _load_record(path: Path) -> _RunRecord:
    record = cast(_RunRecord, json.loads(path.read_text(encoding="utf-8")))
    if record.get("version") != 1:
        raise ValueError("The run record has an unsupported version.")
    return record


def _existing_key(source: Path, supplied: str | None) -> str:
    if supplied is not None:
        return _identifier(supplied)
    options = [path.name for path in source.iterdir() if (path / "run.json").is_file()]
    if len(options) != 1:
        raise ValueError("Specify the binary ID for this run.")
    return _identifier(options[0])


def _locked_run(
    args: argparse.Namespace,
    workspace: Path,
    run: Path,
    source: Path | None,
    key: str,
) -> int:
    directory = run / key
    original = directory / "ingest/original.elf"
    record_path = directory / "run.json"
    previous = _load_record(source / key / "run.json") if source is not None else None
    if record_path.exists() and not args.resume:
        raise ValueError("Use --resume for an existing binary ID.")
    if not args.resume:
        assert args.binary is not None or source is not None
        requested = (
            args.binary if source is None else source / key / "ingest/original.elf"
        )
        requested = _safe_input(requested, workspace)
        requested_metadata = inspect_binary(requested)
        with requested.open("rb") as stream:
            binary_data = stream.read(MAX_PROGRAM_BYTES + 1)
        if len(binary_data) > MAX_PROGRAM_BYTES:
            raise ValueError("The executable exceeds the sandbox program size limit.")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(binary_data)
        original.chmod(0o600)
    metadata = inspect_binary(_safe_input(original, workspace))
    if not args.resume and metadata.sha256 != requested_metadata.sha256:
        raise ValueError("The input binary changed while it was being copied.")
    if previous is not None and metadata.sha256 != previous["binary_sha256"]:
        raise ValueError("The saved input binary SHA-256 has changed.")

    verify_runtime("apple-silicon")
    provenance = evaluator_build()
    images = freeze_images(
        (Engine.ROSETTA, Engine.ARM64), provenance.worker_source_sha256
    )
    if previous is not None:
        if (
            provenance.commit != previous["revision"]
            or provenance.worker_source_sha256 != previous["worker_source_sha256"]
            or images != previous["images"]
        ):
            raise ValueError(
                "Resume and replay require the recorded revision and images."
            )
        settings = Settings(
            images,
            previous["seed"],
            Path(previous["ghidra"]),
            Path(previous["java_home"]),
            previous["repair_limit"],
            previous["astra_repair"],
        )
        budget = Budget(previous["budget_binary"], previous["budget_run"])
    else:
        ghidra, java = _default_tools(workspace)
        settings = Settings(
            images,
            args.seed,
            (args.ghidra or ghidra).resolve(),
            (args.java_home or java).resolve(),
            args.max_repairs,
            args.astra_repair,
        )
        budget = Budget(args.budget_binary, args.budget_run)

    if args.replay:
        assert previous is not None and source is not None
        selected: Provider = _RecordedProvider(previous["provider"])
        ledger = Ledger(source, budget)
    else:
        selected = select_provider(workspace, directory)
        ledger = Ledger(run, budget)
    if previous is not None and selected.name != previous["provider"]:
        raise ValueError("Resume requires the recorded model provider.")
    started = (
        previous["started"] if args.resume and previous is not None else time.time()
    )
    record: _RunRecord = {
        "version": 1,
        "binary_sha256": metadata.sha256,
        "revision": provenance.commit,
        "worker_source_sha256": provenance.worker_source_sha256,
        "images": images,
        "seed": settings.seed,
        "ghidra": str(settings.ghidra),
        "java_home": str(settings.java_home),
        "repair_limit": settings.repair_limit,
        "astra_repair": settings.astra_repair,
        "provider": selected.name,
        "budget_binary": budget.per_binary,
        "budget_run": budget.per_run,
        "started": started,
    }
    write_json(record_path, record)
    write_json(directory / "ingest/metadata.json", asdict(metadata))
    result = reconstruct(
        run,
        key,
        original,
        metadata,
        settings,
        ledger,
        selected,
        started=started,
        replay=bool(args.replay),
    )
    print(result.project)
    return 0 if result.development_passed else 1


def _run(args: argparse.Namespace) -> int:
    root = os.environ.get("PHOENIX_ROOT")
    if not root:
        raise ValueError("Source the Phoenix workspace environment.")
    workspace = Path(root).resolve()
    runs = workspace / "runs"
    if runs.resolve() != runs:
        raise ValueError("The run directory cannot be a symbolic link.")
    from_id = args.resume or args.replay
    if from_id:
        if args.binary is not None:
            raise ValueError("Resume and replay use the saved input binary.")
        source = runs / _identifier(from_id)
        if source.resolve() != source:
            raise ValueError("The saved run cannot be a symbolic link.")
        key = _existing_key(source, args.binary_id)
    else:
        if args.binary is None:
            raise ValueError("Supply the input executable.")
        source = None
        key = _identifier(args.binary_id or args.binary.stem)
    run = (
        source
        if args.resume
        else runs / _identifier(args.run_id or f"phoenix-{uuid4().hex}")
    )
    assert run is not None
    if run.resolve() != run:
        raise ValueError("The run must stay in the workspace run directory.")
    directory = run / key
    if directory.resolve() != directory:
        raise ValueError("The binary directory cannot be a symbolic link.")
    run.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.mkdir(exist_ok=True, mode=0o700)
    descriptor = os.open(
        directory / "run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _locked_run(args, workspace, run, source, key)


def main() -> int:
    parser = argparse.ArgumentParser(prog="phoenix")
    commands = parser.add_subparsers(required=True)
    run = commands.add_parser("run", help="Rebuild a stripped Linux executable.")
    run.add_argument("binary", type=Path, nargs="?")
    run.add_argument("--run-id")
    run.add_argument("--binary-id")
    prior = run.add_mutually_exclusive_group()
    prior.add_argument("--resume", metavar="RUN_ID")
    prior.add_argument("--replay", metavar="RUN_ID")
    run.add_argument("--ghidra", type=Path)
    run.add_argument("--java-home", type=Path)
    run.add_argument("--seed", type=int, default=SEED)
    run.add_argument("--max-repairs", type=int, default=20)
    run.add_argument("--astra-repair", action="store_true")
    run.add_argument("--budget-binary", type=_dollars, default=5 * NANODOLLARS)
    run.add_argument("--budget-run", type=_dollars, default=200 * NANODOLLARS)
    args = parser.parse_args()
    try:
        return _run(args)
    except RetryLater as error:
        print(
            f"Resume the run when model service is available. {error}", file=sys.stderr
        )
        return 75
    except InputRejected as error:
        print(f"{error.reason} {error}", file=sys.stderr)
        return 2
    except (
        OSError,
        ValueError,
        LiftError,
        ProviderError,
        WorkerError,
        subprocess.SubprocessError,
    ) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
