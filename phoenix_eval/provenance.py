import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
IMAGE_SOURCE_LABEL = "org.phoenix.worker-source-sha256"


@dataclass(frozen=True)
class BuildEvidence:
    commit: str
    worker_source_sha256: str


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
    result = hashlib.sha256()
    for path in sorted(paths):
        result.update(path.relative_to(root).as_posix().encode("utf-8"))
        result.update(b"\0")
        result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


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
    print(worker_source_digest())
