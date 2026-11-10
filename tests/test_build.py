import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval.build import build_project
from phoenix_eval.docker import Engine
from phoenix_eval.toolchain import Compiler


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.c").write_text("int main(void) { return 0; }\n")
    (tmp_path / "CMakeLists.txt").write_text("add_executable(program src/main.c)\n")
    return tmp_path


@pytest.mark.parametrize("remove_source", [True, False])
def test_rejects_missing_and_linked_sources(
    project: Path, monkeypatch: pytest.MonkeyPatch, remove_source: bool
) -> None:
    source = project / "src/main.c"
    source.unlink()
    if not remove_source:
        source.symlink_to(project / "CMakeLists.txt")
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(ValueError):
        build_project(project, project / "program", Engine.ARM64, Compiler.CLANG)
    runner.assert_not_called()


@pytest.mark.parametrize("returncode, machine", [(1, 183), (0, 62), (0, 183)])
def test_only_a_successful_build_for_the_selected_architecture_emits_an_elf(
    project: Path, monkeypatch: pytest.MonkeyPatch, returncode: int, machine: int
) -> None:
    elf = b"\x7fELF\x02\x01" + b"\0" * 12 + machine.to_bytes(2, "little")
    diagnostics = b"main.c:1: warning: unused variable\n"
    runner = Mock(
        return_value=subprocess.CompletedProcess(
            ("docker",), returncode, elf, diagnostics
        )
    )
    monkeypatch.setattr(subprocess, "run", runner)
    destination = project / "program"
    result = build_project(project, destination, Engine.ARM64, Compiler.GCC)
    assert result.warnings == 1
    assert result.diagnostics == diagnostics.decode("ascii")
    if returncode == 0 and machine == 183:
        assert result.executable == destination
        assert destination.read_bytes() == elf
        assert not destination.stat().st_mode & 0o111
    else:
        assert result.executable is None
        assert not destination.exists()
