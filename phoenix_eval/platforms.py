import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

from phoenix_eval.docker import docker_cli

_X86_64_ELF = {
    0: 0x7F,
    1: 0x45,
    2: 0x4C,
    3: 0x46,
    4: 2,
    5: 1,
    6: 1,
    18: 0x3E,
    19: 0,
}
_BINFMT_SCRIPT = """
cd /proc/sys/fs/binfmt_misc
cat status
for entry in *; do
    case "$entry" in status|register) continue ;; esac
    printf '\nregistration %s\n' "$entry"
    cat "$entry"
done
"""


@dataclass(frozen=True)
class RuntimeEvidence:
    daemon_architecture: str
    engine_version: str
    amd64_engine: str | None
    arm64_engine: str | None
    binfmt_registrations: str | None = None


def verify_binfmt(output: str) -> None:
    state, *registrations = output.split("\nregistration ")
    if state.strip() != "enabled":
        raise ValueError("The Linux binary format registry is disabled.")
    rosetta = False
    for registration in registrations:
        name, state, *lines = registration.splitlines()
        if state == "disabled":
            continue
        if state != "enabled":
            raise ValueError("A binary format registration has an invalid status.")
        fields = dict(line.split(" ", 1) for line in lines)
        if "extension" in fields:
            continue
        magic = bytes.fromhex(fields["magic"])
        mask = bytes.fromhex(fields.get("mask", "ff" * len(magic)))
        offset = int(fields["offset"])
        if not magic or len(magic) != len(mask) or offset < 0:
            raise ValueError("A binary format registration has an invalid magic rule.")
        matches_x86 = all(
            (byte & bits) == (_X86_64_ELF[position] & bits)
            for position, (byte, bits) in enumerate(
                zip(magic, mask, strict=True), offset
            )
            if position in _X86_64_ELF
        )
        if not matches_x86:
            continue
        if name != "rosetta" or fields["interpreter"] != "/mnt/lima-rosetta/rosetta":
            raise ValueError(
                f"An unexpected binary handler can run x86-64 ELF files. {name}"
            )
        rosetta = True
    if not rosetta:
        raise ValueError(
            "The workspace VM does not have the expected active Rosetta registration."
        )


def verify_runtime(mode: str) -> RuntimeEvidence:
    if os.environ.get("DOCKER_CONTEXT"):
        raise ValueError("Clear the Docker context override before evaluation.")
    status = subprocess.run(
        (
            *docker_cli(),
            "info",
            "--format",
            "{{.OSType}} {{.Architecture}} {{.ServerVersion}}",
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    system, architecture, version = status.stdout.strip().split()
    aliases = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "x86_64": "amd64",
        "amd64": "amd64",
    }
    architecture = aliases.get(architecture, architecture)
    if system != "linux":
        raise ValueError("A Linux Docker daemon is required.")
    if mode in ("native-amd64", "native-arm64"):
        if mode != f"native-{architecture}" or platform.system() != "Linux":
            raise ValueError(
                "The selected native mode does not match the Linux host and daemon."
            )
        return RuntimeEvidence(
            architecture,
            version,
            "native" if architecture == "amd64" else None,
            "native" if architecture == "arm64" else None,
        )

    if (
        mode != "apple-silicon"
        or architecture != "arm64"
        or platform.system() != "Darwin"
        or platform.machine() != "arm64"
    ):
        raise ValueError("The Apple Silicon mode requires an ARM64 host and daemon.")
    home = os.environ.get("COLIMA_HOME")
    if (
        not home
        or os.environ.get("DOCKER_HOST")
        != f"unix://{Path(home) / 'default/docker.sock'}"
    ):
        raise ValueError("Source the workspace Colima environment before evaluation.")
    registration = subprocess.run(
        ("colima", "ssh", "--", "/bin/sh", "-ec", _BINFMT_SCRIPT),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    ).stdout
    verify_binfmt(registration)
    return RuntimeEvidence(architecture, version, "rosetta", "native", registration)
