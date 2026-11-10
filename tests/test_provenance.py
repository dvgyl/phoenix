from hashlib import sha256
from pathlib import Path

import pytest

from phoenix_eval.provenance import lifting_tool_identity, pipeline_source_digest

PIPELINE_FILE = "phoenix/generate/raw.py"
DECOMPILER = "Ghidra/Features/Decompiler/os/mac_arm_64/decompile"
DECOMPILER_JAR = "Ghidra/Features/Decompiler/lib/Decompiler.jar"
PROJECT_FILES = (
    PIPELINE_FILE,
    "ghidra_scripts/ExportLift.java",
    "schemas/lift.schema.json",
    "pyproject.toml",
    "tools.lock",
)


def write_project(root: Path) -> None:
    for name in PROJECT_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())


def write_tools(root: Path) -> tuple[Path, Path]:
    ghidra = root / "ghidra"
    java = root / "jdk"
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
        DECOMPILER_JAR,
        "Ghidra/Processors/x86/lib/x86.jar",
        "Ghidra/Processors/x86/data/languages/x86-64.sla",
        DECOMPILER,
    ):
        path = ghidra / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    (java / "bin").mkdir(parents=True)
    (java / "bin/java").write_bytes(b"Java launcher")
    (java / "release").write_bytes(b'JAVA_VERSION="25.0.5"')
    return ghidra, java


@pytest.mark.parametrize("name", PROJECT_FILES)
def test_pipeline_source_digest_uses_file_content(tmp_path: Path, name: str) -> None:
    write_project(tmp_path)
    before = pipeline_source_digest(tmp_path)
    (tmp_path / name).write_bytes(name.upper().encode())
    assert pipeline_source_digest(tmp_path) != before


def test_pipeline_source_digest_uses_paths_and_ignores_caches(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    write_project(first)
    write_project(second)
    before = pipeline_source_digest(first)
    for name in (
        "phoenix/__pycache__/raw.py",
        "phoenix/.pytest_cache/data",
        "phoenix/loose.pyc",
        "ghidra_scripts/ExportLift.class",
        "outside.py",
    ):
        path = second / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Excluded file")
    assert pipeline_source_digest(second) == before
    (second / PIPELINE_FILE).rename(second / "phoenix/generate/moved.py")
    assert pipeline_source_digest(second) != before


@pytest.mark.parametrize(
    ("prefix", "name"),
    (
        ("ghidra", "support/analyzeHeadless"),
        ("ghidra", DECOMPILER),
        ("ghidra", DECOMPILER_JAR),
        ("ghidra", "Ghidra/Processors/x86/data/languages/x86-64.sla"),
        ("java", "bin/java"),
        ("java", "release"),
    ),
)
def test_lifting_tool_identity_uses_installed_bytes(
    tmp_path: Path, prefix: str, name: str
) -> None:
    ghidra, java = write_tools(tmp_path)
    path = (ghidra if prefix == "ghidra" else java) / name
    before = lifting_tool_identity(ghidra, java)
    key = f"{prefix}/{name}"
    assert before[key] == sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b"Changed tool file")
    after = lifting_tool_identity(ghidra, java)
    assert after == {**before, key: sha256(b"Changed tool file").hexdigest()}
