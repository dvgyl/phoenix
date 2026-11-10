import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
IMAGE_SOURCE_LABEL = "org.phoenix.worker-source-sha256"
CHECKER_SOURCE_LABEL = "org.phoenix.integrity-source-sha256"


@dataclass(frozen=True)
class BuildEvidence:
    commit: str
    worker_source_sha256: str


def _source_digest(root: Path, paths: list[Path]) -> str:
    result = hashlib.sha256()
    for path in sorted(paths):
        result.update(path.relative_to(root).as_posix().encode("utf-8"))
        result.update(b"\0")
        result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def worker_source_digest(root: Path = CHECKOUT) -> str:
    paths = [
        root / ".dockerignore",
        root / "tools.lock",
        root / "scripts/build-worker",
        root / "containers/Dockerfile",
        *root.glob("containers/*.c"),
        *root.glob("containers/*.sh"),
        *root.glob("phoenix_eval/*.py"),
    ]
    return _source_digest(root, paths)


def checker_source_digest(root: Path = CHECKOUT) -> str:
    return _source_digest(
        root,
        [
            root / "tools.lock",
            root / "containers/c-integrity.cc",
            root / "containers/Dockerfile.integrity",
            root / "scripts/build-integrity",
        ],
    )


def evaluator_build() -> BuildEvidence:
    commit = subprocess.run(
        ("git", "-C", str(CHECKOUT), "rev-parse", "HEAD"),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    return BuildEvidence(commit, worker_source_digest())


if __name__ == "__main__":
    print(
        checker_source_digest()
        if sys.argv[1:] == ["--integrity"]
        else worker_source_digest()
    )
