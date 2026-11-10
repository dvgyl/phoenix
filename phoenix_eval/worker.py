import json
import os
import shutil
import signal
import subprocess
import sys
from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import BinaryIO

from phoenix_eval.case import (
    CaseFailure,
    CaseResult,
    FailureKind,
    Invocation,
    WorkerRuntime,
)
from phoenix_eval.outcome import Exited, Outcome, Signaled
from phoenix_eval.trace import MAX_TRACE_BYTES, parse_trace
from phoenix_eval.tree import MAX_FILE_BYTES, populate, snapshot
from phoenix_eval.wire import PROTOCOL_VERSION, decode_invocation, encode_result

SCRATCH = Path("/scratch")
NATIVE_RUNTIME = Path("/opt/phoenix-runtime")
QEMU_RUNTIME = Path("/opt/phoenix-qemu-root")
TARGET = "/program"
LAUNCHER = "/opt/launch-target"
TARGET_UID = TARGET_GID = 19704
MAX_PROGRAM_BYTES = 16 * 1024 * 1024
WALL_SECONDS = 15


def worker_args(
    runtime: WorkerRuntime, args: tuple[str, ...], trace: bool = False
) -> tuple[str, ...]:
    if runtime is WorkerRuntime.QEMU:
        options = (
            ("-plugin", "/code-coverage.so", "-d", "plugin", "-D", "/coverage.log")
            if trace
            else ()
        )
        return (
            "/usr/bin/qemu-x86_64",
            "-R",
            "0",
            "-L",
            "/",
            "-0",
            TARGET,
            *options,
            TARGET,
            *args,
        )
    return (TARGET, *args)


def _launch(
    root: Path,
    case: Invocation,
    runtime: WorkerRuntime,
    stdin: BinaryIO,
    stdout: BinaryIO,
    stderr: BinaryIO,
    trace: bool,
) -> int:
    with TemporaryFile(dir=SCRATCH) as setup:
        fd = setup.fileno()
        with subprocess.Popen(
            (
                LAUNCHER,
                runtime,
                str(fd),
                str(TARGET_UID),
                str(TARGET_GID),
                str(root),
                *worker_args(runtime, case.args, trace),
            ),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=case.environment(),
            pass_fds=(fd,),
            start_new_session=True,
        ) as process:
            try:
                status = process.wait(timeout=WALL_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
        setup.seek(0)
        diagnostic = setup.read(4096)
        if diagnostic:
            raise OSError(diagnostic.decode("utf-8", errors="replace"))
    return status


def run_case(
    binary: bytes,
    case: Invocation,
    runtime: WorkerRuntime,
    trace: bool = False,
) -> CaseResult:
    libraries = QEMU_RUNTIME if runtime is WorkerRuntime.QEMU else NATIVE_RUNTIME
    with TemporaryDirectory(dir=SCRATCH) as name:
        root = Path(name)
        root.chmod(0o755)
        work = root / "work"
        trace_path = root / "coverage.log"
        try:
            shutil.copytree(libraries, root, dirs_exist_ok=True, symlinks=True)
            target = root / TARGET.lstrip("/")
            target.write_bytes(binary)
            target.chmod(0o555)
            populate(work, case.tree, TARGET_UID, TARGET_GID)
            if trace:
                trace_path.touch(mode=0o600)
                os.chown(trace_path, TARGET_UID, TARGET_GID)
            with (
                TemporaryFile(dir=SCRATCH) as stdin,
                TemporaryFile(dir=SCRATCH) as stdout,
                TemporaryFile(dir=SCRATCH) as stderr,
            ):
                stdin.write(case.stdin)
                stdin.seek(0)
                status = _launch(root, case, runtime, stdin, stdout, stderr, trace)
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
            status in (-signal.SIGXCPU, -signal.SIGXFSZ, -signal.SIGKILL)
            or max(len(out), len(err)) >= MAX_FILE_BYTES
        ):
            return CaseFailure(
                FailureKind.LIMIT, "The program exceeded a resource limit."
            )
        if (
            runtime is WorkerRuntime.ROSETTA
            and status == -signal.SIGTRAP
            and err.startswith(b"rosetta error: ")
        ):
            return CaseFailure(
                FailureKind.LAUNCH, err.decode("utf-8", errors="replace").strip()
            )
        try:
            tree = snapshot(work)
        except (ValueError, OSError) as exc:
            return CaseFailure(FailureKind.SNAPSHOT, str(exc))
        termination = Exited(status) if status >= 0 else Signaled(-status)
        coverage = None
        if trace:
            try:
                with trace_path.open("rb") as stream:
                    coverage = parse_trace(stream.read(MAX_TRACE_BYTES + 1))
            except (ValueError, OSError) as exc:
                return CaseFailure(FailureKind.TRACE, str(exc))
        return Outcome(out, err, termination, tree, coverage)


def main() -> None:
    header = json.loads(sys.stdin.readline())
    if header["version"] != PROTOCOL_VERSION:
        raise ValueError("Unsupported worker request.")
    binary = b64decode(header["binary"], validate=True)
    if not 0 < len(binary) <= MAX_PROGRAM_BYTES:
        raise ValueError("Invalid program size.")
    runtime = WorkerRuntime(header["engine"])
    trace = header.get("trace", False)
    if not isinstance(trace, bool) or (trace and runtime is not WorkerRuntime.QEMU):
        raise ValueError("Tracing requires the QEMU engine.")
    for line in sys.stdin:
        print(
            encode_result(run_case(binary, decode_invocation(line), runtime, trace)),
            flush=True,
        )


if __name__ == "__main__":
    main()
