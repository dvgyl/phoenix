"""Retain immutable image references around a serialized image build."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phoenix_eval.docker import docker_cli
from phoenix_eval.jobs import Slots, file_lock

REPO = Path(__file__).resolve().parents[1]


def retain(docker: tuple[str, ...]) -> set[str]:
    result = subprocess.run(
        (*docker, "image", "ls", "--all", "--quiet", "--no-trunc"),
        capture_output=True,
        text=True,
        check=True,
    )
    images = set(result.stdout.split())
    if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", item) for item in images):
        raise ValueError("Docker returned an invalid image ID.")
    for image in sorted(images):
        subprocess.run(
            (*docker, "tag", image, "phoenix-retained:" + image.replace(":", "-")),
            check=True,
        )
    return images


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("worker", "integrity"))
    parser.add_argument("architecture", choices=("amd64", "arm64"))
    args = parser.parse_args(argv)
    root = os.environ.get("PHOENIX_ROOT")
    if not root:
        raise ValueError("Source the Phoenix workspace environment.")
    workspace = Path(root).resolve()
    slots = Slots.from_environment()
    with (
        file_lock(workspace / "slots/image-build.lock"),
        slots.acquire("compile"),
        slots.acquire("execution"),
    ):
        docker = docker_cli()
        before = retain(docker)
        try:
            subprocess.run(
                (str(REPO / f"scripts/build-{args.kind}"), args.architecture),
                cwd=REPO,
                check=True,
            )
        finally:
            after = retain(docker)
            if before - after:
                raise ValueError("The build lost a retained image reference.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2) from None
