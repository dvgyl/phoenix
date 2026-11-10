import os
import subprocess
from enum import StrEnum
from pathlib import Path

from phoenix_eval.docker import Engine


class Compiler(StrEnum):
    GCC = "gcc"
    CLANG = "clang"


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
    result = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--pids-limit=64",
            "--tmpfs=/work:rw,nosuid,nodev,size=128m",
            "--workdir=/work",
            "--env=TMPDIR=/work",
            "--env=SOURCE_DATE_EPOCH=1794268800",
            "--entrypoint=/bin/sh",
            "--platform",
            f"linux/{engine.platform}",
            image or f"phoenix-worker:{engine.platform}",
            "-ec",
            '"$1" -x c -std=c11 -Wall -Wextra -Werror -O2 "$2" -o program -; '
            "strip --strip-all program; cat program",
            "build-public",
            compiler,
            f"-DPHOENIX_MUTANT={mutant}",
        ),
        input=source.read_bytes(),
        capture_output=True,
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
