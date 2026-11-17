import os
import subprocess
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from phoenix_eval.docker import Engine, docker_cli
from phoenix_eval.jobs import limited


class Compiler(StrEnum):
    GCC = "gcc"
    CLANG = "clang"


SOURCE_TOOL_OPTIONS = (
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--user=19704:19704",
    "--env=TMPDIR=/work",
    "--env=HOME=/nonexistent",
    "--env=SOURCE_DATE_EPOCH=1794268800",
)


class ToolTimeout(Exception):
    """The tool exceeded its time limit."""


def run_tool(
    platform: str,
    image: str,
    script: str,
    *arguments: str,
    options: tuple[str, ...],
    input: bytes,
    timeout: int,
    check: bool,
    timeout_error: Exception | None = None,
) -> subprocess.CompletedProcess[bytes]:
    docker = docker_cli()
    name = f"phoenix-tool-{uuid4().hex}"
    command = (
        *docker,
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--workdir=/work",
        "--entrypoint=/bin/sh",
        f"--platform=linux/{platform}",
        f"--name={name}",
        *options,
        image,
        "-ec",
        script,
        *arguments,
    )
    try:
        return subprocess.run(
            command, input=input, capture_output=True, timeout=timeout, check=check
        )
    except subprocess.TimeoutExpired as error:
        try:
            subprocess.run(
                (*docker, "rm", "-f", name),
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as cleanup_error:
            if timeout_error is None:
                raise error from cleanup_error
            raise
        # Keep cleanup exceptions separate from the launch timeout.
        if timeout_error is not None:
            raise timeout_error from None
        raise


@limited("compile")
def build_public(
    source: Path,
    output: Path,
    engine: Engine,
    compiler: Compiler,
    mutant: int = 0,
    *,
    image: str | None = None,
) -> None:
    if engine is Engine.QEMU_X86_64:
        raise ValueError("Use a native toolchain image to build a program.")
    if mutant < 0:
        raise ValueError("The mutation number cannot be negative.")
    result = run_tool(
        engine.platform,
        image or f"phoenix-worker:{engine.platform}",
        '"$1" -x c -std=c11 -Wall -Wextra -Werror -O2 "$2" -o program -; '
        "strip --strip-all program; cat program",
        "build-public",
        compiler,
        f"-DPHOENIX_MUTANT={mutant}",
        options=(
            "--pids-limit=64",
            "--tmpfs=/work:rw,nosuid,nodev,size=128m",
            "--env=TMPDIR=/work",
            "--env=SOURCE_DATE_EPOCH=1794268800",
        ),
        input=source.read_bytes(),
        timeout=120,
        check=False,
    )
    machine = int.from_bytes(result.stdout[18:20], "little")
    expected_machine = 62 if engine.platform == "amd64" else 183
    if (
        result.returncode
        or not result.stdout.startswith(b"\x7fELF\x02\x01")
        or machine != expected_machine
    ):
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace")
            or "The build did not emit ELF."
        )
    output.write_bytes(result.stdout)
    os.chmod(output, 0o600)
