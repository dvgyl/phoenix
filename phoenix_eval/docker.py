import json
import subprocess
from base64 import b64encode
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryFile
from uuid import uuid4

from phoenix_eval.case import CaseResult, Invocation
from phoenix_eval.wire import PROTOCOL_VERSION, decode_result, encode_invocation
from phoenix_eval.worker import MAX_PROGRAM_BYTES, WALL_SECONDS

MAX_BATCH = 16


class Engine(StrEnum):
    AMD64 = "amd64"
    ARM64 = "arm64"
    QEMU_X86_64 = "qemu-x86-64"

    @property
    def platform(self) -> str:
        return "amd64" if self is Engine.AMD64 else "arm64"


class WorkerError(RuntimeError):
    pass


def docker_args(engine: Engine, container: str) -> tuple[str, ...]:
    return (
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--platform",
        f"linux/{engine.platform}",
        "--name",
        container,
        "--network=none",
        "--read-only",
        "--pids-limit=32",
        "--memory=1536m",
        "--memory-swap=1536m",
        "--tmpfs",
        "/scratch:rw,nosuid,nodev,size=256m,nr_inodes=16384",
        "--cap-drop=ALL",
        "--cap-add=SYS_CHROOT",
        "--cap-add=SETUID",
        "--cap-add=SETGID",
        "--cap-add=CHOWN",
        "--cap-add=DAC_OVERRIDE",
        "--security-opt=no-new-privileges",
        f"phoenix-worker:{engine.platform}",
    )


def run_batch(
    binary: Path, cases: tuple[Invocation, ...], engine: Engine
) -> tuple[CaseResult, ...]:
    if not 0 < len(cases) <= MAX_BATCH:
        raise ValueError(f"A worker batch must contain 1 to {MAX_BATCH} cases.")
    with binary.open("rb") as file:
        program = file.read(MAX_PROGRAM_BYTES + 1)
    if not 0 < len(program) <= MAX_PROGRAM_BYTES:
        raise ValueError("Invalid program size.")

    name = f"phoenix-{uuid4().hex}"
    header = {
        "version": PROTOCOL_VERSION,
        "engine": "qemu" if engine is Engine.QEMU_X86_64 else "direct",
        "binary": b64encode(program).decode("ascii"),
    }
    with (
        TemporaryFile() as request,
        TemporaryFile() as response,
        TemporaryFile() as diagnostics,
    ):
        request.write((json.dumps(header) + "\n").encode("ascii"))
        for case in cases:
            request.write((encode_invocation(case) + "\n").encode("ascii"))
        request.seek(0)
        try:
            completed = subprocess.run(
                docker_args(engine, name),
                stdin=request,
                stdout=response,
                stderr=diagnostics,
                timeout=len(cases) * WALL_SECONDS + 30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ("docker", "rm", "-f", name),
                capture_output=True,
                timeout=10,
                check=False,
            )
            raise WorkerError("The Docker worker exceeded its time limit.") from exc
        if completed.returncode:
            diagnostics.seek(0)
            message = diagnostics.read(4096).decode("utf-8", errors="replace").strip()
            raise WorkerError(
                f"The Docker worker failed with code {completed.returncode}. {message}"
            )
        response.seek(0)
        try:
            results = tuple(decode_result(line.decode("ascii")) for line in response)
        except (KeyError, ValueError) as exc:
            raise WorkerError("The Docker worker returned an invalid result.") from exc
    if len(results) != len(cases):
        raise WorkerError("The Docker worker returned the wrong number of results.")
    return results
