import json
import shutil
import signal
import subprocess
import sys
from base64 import b64decode
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import BinaryIO

from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.isolation import TARGET_GID, TARGET_UID, ProcessFilter, enter
from phoenix_eval.outcome import Exited, Outcome, Signaled
from phoenix_eval.tree import MAX_FILE_BYTES, populate, snapshot
from phoenix_eval.wire import PROTOCOL_VERSION, decode_invocation, encode_result

SCRATCH = Path("/scratch")
NATIVE_RUNTIME = Path("/opt/phoenix-runtime")
QEMU_RUNTIME = Path("/opt/phoenix-qemu-root")
TARGET = "/program"
MAX_PROGRAM_BYTES = 16 * 1024 * 1024
WALL_SECONDS = 15


def worker_args(use_qemu: bool, args: tuple[str, ...]) -> tuple[str, ...]:
    if use_qemu:
        return (
            "/usr/bin/qemu-x86_64",
            "-R",
            "0",
            "-L",
            "/",
            "-0",
            TARGET,
            TARGET,
            *args,
        )
    return (TARGET, *args)


def _launch(
    root: Path,
    case: Invocation,
    use_qemu: bool,
    process_filter: ProcessFilter,
    stdin: BinaryIO,
    stdout: BinaryIO,
    stderr: BinaryIO,
) -> int:
    completed = subprocess.run(
        worker_args(use_qemu, case.args),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=case.environment(),
        preexec_fn=partial(enter, root, process_filter),
        timeout=WALL_SECONDS,
        check=False,
    )
    return completed.returncode


def run_case(
    binary: bytes, case: Invocation, use_qemu: bool, process_filter: ProcessFilter
) -> CaseResult:
    runtime = QEMU_RUNTIME if use_qemu else NATIVE_RUNTIME
    with TemporaryDirectory(dir=SCRATCH) as name:
        root = Path(name)
        root.chmod(0o755)
        work = root / "work"
        try:
            shutil.copytree(runtime, root, dirs_exist_ok=True, symlinks=True)
            target = root / TARGET.lstrip("/")
            target.write_bytes(binary)
            target.chmod(0o555)
            populate(work, case.tree, TARGET_UID, TARGET_GID)
            with (
                TemporaryFile(dir=SCRATCH) as stdin,
                TemporaryFile(dir=SCRATCH) as stdout,
                TemporaryFile(dir=SCRATCH) as stderr,
            ):
                stdin.write(case.stdin)
                stdin.seek(0)
                status = _launch(
                    root, case, use_qemu, process_filter, stdin, stdout, stderr
                )
                stdout.seek(0)
                stderr.seek(0)
                out = stdout.read(MAX_FILE_BYTES + 1)
                err = stderr.read(MAX_FILE_BYTES + 1)
        except subprocess.TimeoutExpired:
            return CaseFailure(
                FailureKind.TIMEOUT, "The program exceeded the wall time limit."
            )
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return CaseFailure(FailureKind.LAUNCH, str(exc))

        if (
            status in (-signal.SIGXCPU, -signal.SIGXFSZ)
            or max(len(out), len(err)) >= MAX_FILE_BYTES
        ):
            return CaseFailure(
                FailureKind.LIMIT, "The program exceeded a resource limit."
            )
        try:
            tree = snapshot(work)
        except (ValueError, OSError) as exc:
            return CaseFailure(FailureKind.SNAPSHOT, str(exc))
        termination = Exited(status) if status >= 0 else Signaled(-status)
        return Outcome(out, err, termination, tree)


def main() -> None:
    header = json.loads(sys.stdin.readline())
    if header["version"] != PROTOCOL_VERSION or header["engine"] not in (
        "direct",
        "qemu",
    ):
        raise ValueError("Unsupported worker request.")
    binary = b64decode(header["binary"], validate=True)
    if not 0 < len(binary) <= MAX_PROGRAM_BYTES:
        raise ValueError("Invalid program size.")
    use_qemu = header["engine"] == "qemu"
    process_filter = ProcessFilter()
    for line in sys.stdin:
        print(
            encode_result(
                run_case(binary, decode_invocation(line), use_qemu, process_filter)
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
