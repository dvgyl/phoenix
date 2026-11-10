import hashlib
import subprocess
import sys
import tomllib
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


def pipeline_source_digest(root: Path = CHECKOUT) -> str:
    """Hash pipeline files by relative path and content."""

    def raise_walk_error(error: OSError) -> None:
        raise error

    root = root.resolve()
    paths = [
        root / name
        for name in ("schemas/lift.schema.json", "pyproject.toml", "tools.lock")
    ]
    for name in ("phoenix", "ghidra_scripts"):
        directory = root / name
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"Use a project source directory at {directory}.")
        for parent, dirs, files in directory.walk(on_error=raise_walk_error):
            dirs[:] = [
                name
                for name in dirs
                if not name.startswith(".") and name != "__pycache__"
            ]
            paths.extend(
                parent / name
                for name in files
                if not name.startswith(".")
                and Path(name).suffix not in {".pyc", ".pyo", ".class"}
            )
    for path in paths:
        if path.resolve() != path or not path.is_file():
            raise ValueError(f"Use a regular project file at {path}.")
    return _source_digest(root, paths)


def lifting_tool_identity(ghidra: Path, java_home: Path) -> dict[str, str]:
    """Hash the pinned Ghidra lift components and the Java launcher and release."""
    ghidra_files = [
        ghidra / name
        for name in (
            "support/analyzeHeadless",
            "support/launch.sh",
            "support/launch.properties",
            "support/LaunchSupport.jar",
            "Ghidra/application.properties",
            "Ghidra/Configurations/Public_Release/lib/Public_Release.jar",
            "Ghidra/Framework/Utility/lib/Utility.jar",
            "Ghidra/Framework/SoftwareModeling/lib/SoftwareModeling.jar",
            "Ghidra/Features/Base/lib/Base.jar",
            "Ghidra/Features/Decompiler/lib/Decompiler.jar",
            "Ghidra/Processors/x86/lib/x86.jar",
        )
    ]
    native = sorted(ghidra.glob("Ghidra/Features/Decompiler/os/*/decompile"))
    if not native:
        raise ValueError("Install the Ghidra native decompiler.")
    ghidra_files.extend(native)
    ghidra_files.extend(
        path
        for path in sorted(ghidra.glob("Ghidra/Processors/x86/data/languages/*"))
        if path.suffix in {".sla", ".ldefs", ".pspec", ".cspec", ".opinion", ".dwarf"}
    )
    identity = {}
    for prefix, root, paths in (
        ("ghidra", ghidra, ghidra_files),
        ("java", java_home, [java_home / "bin/java", java_home / "release"]),
    ):
        for path in paths:
            with path.open("rb") as stream:
                key = f"{prefix}/{path.relative_to(root).as_posix()}"
                identity[key] = hashlib.file_digest(stream, "sha256").hexdigest()
    return identity


def pinned_lifting_tools(workspace: Path, root: Path = CHECKOUT) -> tuple[Path, Path]:
    with (root / "tools.lock").open("rb") as stream:
        tools = tomllib.load(stream)
    ghidra = workspace / "tools/ghidra" / f"ghidra_{tools['ghidra']}_PUBLIC"
    java = workspace / "tools/jdk" / f"jdk-{tools['temurin_macos_arm64']}/Contents/Home"
    return ghidra, java


def evaluator_build(root: Path = CHECKOUT) -> BuildEvidence:
    commit = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    return BuildEvidence(commit, worker_source_digest(root))


if __name__ == "__main__":
    print(
        checker_source_digest()
        if sys.argv[1:] == ["--integrity"]
        else worker_source_digest()
    )
