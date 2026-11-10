import json
import os
import re
import subprocess
from base64 import b64encode
from enum import StrEnum
from itertools import batched
from pathlib import Path
from tempfile import TemporaryFile
from uuid import uuid4

from phoenix_eval.case import CaseResult, Invocation, WorkerRuntime
from phoenix_eval.provenance import IMAGE_SOURCE_LABEL
from phoenix_eval.wire import PROTOCOL_VERSION, decode_result, encode_invocation
from phoenix_eval.worker import MAX_PROGRAM_BYTES, WALL_SECONDS

MAX_BATCH = 16


class Engine(StrEnum):
    AMD64 = "amd64"
    ARM64 = "arm64"
    QEMU_X86_64 = "qemu-x86-64"
    ROSETTA = "rosetta"

    @property
    def platform(self) -> str:
        return "amd64" if self in (Engine.AMD64, Engine.ROSETTA) else "arm64"

    @property
    def runtime(self) -> WorkerRuntime:
        if self is Engine.ROSETTA:
            return WorkerRuntime.ROSETTA
        if self is Engine.QEMU_X86_64:
            return WorkerRuntime.QEMU
        return WorkerRuntime.DIRECT


class WorkerError(RuntimeError):
    pass


def docker_cli() -> tuple[str, ...]:
    endpoint = os.environ.get("DOCKER_HOST")
    return ("docker", "--host", endpoint) if endpoint else ("docker",)


def freeze_images(
    engines: tuple[Engine, ...],
    source_digest: str,
    *,
    repository: str = "phoenix-worker",
    source_label: str = IMAGE_SOURCE_LABEL,
) -> dict[str, str]:
    platforms = tuple(dict.fromkeys(engine.platform for engine in engines))
    result = subprocess.run(
        (
            *docker_cli(),
            "image",
            "inspect",
            f'--format={{{{.Id}}}} {{{{ index .Config.Labels "{source_label}" }}}}',
            *(f"{repository}:{platform}" for platform in platforms),
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    ids = {}
    for platform, line in zip(platforms, result.stdout.splitlines(), strict=True):
        image, _, digest = line.partition(" ")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise WorkerError("Docker returned an invalid worker image ID.")
        if digest.strip() != source_digest:
            raise WorkerError(
                f"Rebuild the {platform} image for {repository} in this checkout."
            )
        ids[platform] = image
    return ids


def docker_args(
    engine: Engine, container: str, image: str | None = None
) -> tuple[str, ...]:
    namespace = (
        ("--cap-add=SYS_ADMIN", "--security-opt=apparmor=unconfined")
        if engine is Engine.ROSETTA
        else ()
    )
    return (
        *docker_cli(),
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
        "/scratch:rw,exec,nosuid,nodev,size=256m,nr_inodes=16384",
        "--cap-drop=ALL",
        "--cap-add=SYS_CHROOT",
        "--cap-add=SETUID",
        "--cap-add=SETGID",
        "--cap-add=CHOWN",
        "--cap-add=FOWNER",
        "--cap-add=KILL",
        "--cap-add=FSETID",
        "--cap-add=DAC_OVERRIDE",
        "--security-opt=no-new-privileges",
        *namespace,
        image or f"phoenix-worker:{engine.platform}",
    )


def run_batch(
    binary: Path,
    cases: tuple[Invocation, ...],
    engine: Engine,
    *,
    trace: bool = False,
    image: str | None = None,
) -> tuple[CaseResult, ...]:
    if trace and engine is not Engine.QEMU_X86_64:
        raise ValueError("Tracing requires the QEMU engine.")
    if not 0 < len(cases) <= MAX_BATCH:
        raise ValueError(f"A worker batch must contain 1 to {MAX_BATCH} cases.")
    with binary.open("rb") as file:
        program = file.read(MAX_PROGRAM_BYTES + 1)
    if not 0 < len(program) <= MAX_PROGRAM_BYTES:
        raise ValueError("Invalid program size.")

    name = f"phoenix-{uuid4().hex}"
    header = {
        "version": PROTOCOL_VERSION,
        "engine": engine.runtime,
        "trace": trace,
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
                docker_args(engine, name, image),
                stdin=request,
                stdout=response,
                stderr=diagnostics,
                timeout=len(cases) * WALL_SECONDS + 30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                (*docker_cli(), "rm", "-f", name),
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


def run_cases(
    binary: Path,
    cases: tuple[Invocation, ...],
    engine: Engine,
    *,
    trace: bool = False,
    image: str | None = None,
) -> tuple[CaseResult, ...]:
    return tuple(
        result
        for batch in batched(cases, MAX_BATCH)
        for result in run_batch(binary, batch, engine, trace=trace, image=image)
    )
