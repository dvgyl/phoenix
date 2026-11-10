"""Run one public observer case in the existing Linux target sandbox."""

import json
import os
import shutil
import signal
import subprocess
import sys
from base64 import b64decode, b64encode
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile

from experiments.m2_trace.trace import MAX_BYTES, parse_plan
from phoenix_eval.outcome import Exited, Outcome, Signaled
from phoenix_eval.tree import MAX_FILE_BYTES, populate, snapshot
from phoenix_eval.wire import decode_invocation, encode_result
from phoenix_eval.worker import (
    LAUNCHER,
    MAX_PROGRAM_BYTES,
    QEMU_RUNTIME,
    SCRATCH,
    TARGET,
    TARGET_GID,
    TARGET_UID,
    WALL_SECONDS,
)


def main() -> None:
    request = json.loads(sys.stdin.buffer.read(32 * 1024 * 1024 + 1))
    binary = b64decode(request["binary"], validate=True)
    plan = b64decode(request["plan"], validate=True)
    case = decode_invocation(request["case"])
    if not 0 < len(binary) <= MAX_PROGRAM_BYTES:
        raise ValueError("Invalid public fixture size.")
    with TemporaryDirectory(dir=SCRATCH) as directory:
        root = Path(directory)
        root.chmod(0o755)
        shutil.copytree(QEMU_RUNTIME, root, dirs_exist_ok=True, symlinks=True)
        target = root / TARGET[1:]
        target.write_bytes(binary)
        target.chmod(0o555)
        parse_plan(target, plan)
        (root / "plan.tsv").write_bytes(plan)
        (root / "plan.tsv").chmod(0o444)
        evidence = root / "events.tsv"
        evidence.touch(mode=0o600)
        os.chown(evidence, TARGET_UID, TARGET_GID)
        populate(root / "work", case.tree, TARGET_UID, TARGET_GID)
        with (
            TemporaryFile(dir=SCRATCH) as setup,
            TemporaryFile(dir=SCRATCH) as stdin,
            TemporaryFile(dir=SCRATCH) as stdout,
            TemporaryFile(dir=SCRATCH) as stderr,
        ):
            stdin.write(case.stdin)
            stdin.seek(0)
            command = (
                LAUNCHER,
                "qemu",
                str(setup.fileno()),
                str(TARGET_UID),
                str(TARGET_GID),
                str(root),
                "/usr/bin/qemu-x86_64",
                "-R",
                "0",
                "-L",
                "/",
                "-0",
                TARGET,
                "-plugin",
                "/observer.so,plan=/plan.tsv,out=/events.tsv",
                TARGET,
                *case.args,
            )
            with subprocess.Popen(
                command,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=case.environment(),
                pass_fds=(setup.fileno(),),
                start_new_session=True,
            ) as process:
                try:
                    status = process.wait(timeout=WALL_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            setup.seek(0)
            if setup.read(4096):
                raise ValueError("The target sandbox failed to launch.")
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(MAX_FILE_BYTES + 1), stderr.read(MAX_FILE_BYTES + 1)
        if max(len(out), len(err)) >= MAX_FILE_BYTES or status in (
            -signal.SIGXCPU,
            -signal.SIGXFSZ,
            -signal.SIGKILL,
        ):
            raise ValueError("The observation exceeded a sandbox limit.")
        outcome = Outcome(
            out,
            err,
            Exited(status) if status >= 0 else Signaled(-status),
            snapshot(root / "work"),
        )
        with evidence.open("rb") as stream:
            trace = stream.read(MAX_BYTES + 1)
        if len(trace) > MAX_BYTES:
            raise ValueError("The observer exceeded the trace byte limit.")
        print(
            json.dumps(
                {
                    "outcome": encode_result(outcome),
                    "trace": b64encode(trace).decode("ascii"),
                }
            )
        )


if __name__ == "__main__":
    main()
