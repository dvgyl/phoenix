import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeEvidence:
    daemon_architecture: str
    engine_version: str
    amd64_engine: str | None
    arm64_engine: str | None


def verify_runtime(mode: str) -> RuntimeEvidence:
    status = subprocess.run(
        (
            "docker",
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
        (
            "colima",
            "ssh",
            "--",
            "/bin/sh",
            "-ec",
            "cd /proc/sys/fs/binfmt_misc; cat rosetta; "
            "for handler in qemu-x86_64 qemu-amd64; do "
            'if [ -f "$handler" ] && grep -qx enabled "$handler"; then exit 1; fi; '
            "done",
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    ).stdout.splitlines()
    if (
        not registration
        or registration[0] != "enabled"
        or not any(
            line == "interpreter /mnt/lima-rosetta/rosetta" for line in registration
        )
    ):
        raise ValueError(
            "The workspace VM does not have the expected active Rosetta registration."
        )
    return RuntimeEvidence(architecture, version, "rosetta", "native")
