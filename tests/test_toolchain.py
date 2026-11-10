import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval.docker import Engine
from phoenix_eval.toolchain import Compiler, build_public


def test_toolchain_checks_the_executable_architecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "program.c"
    source.write_text("int main(void) { return 0; }")
    executable = tmp_path / "program.elf"
    elf_header = b"\x7fELF\x02\x01" + b"\0" * 12 + (183).to_bytes(2, "little")
    runner = Mock(
        return_value=subprocess.CompletedProcess(("docker",), 0, elf_header, b"")
    )
    monkeypatch.setattr(subprocess, "run", runner)
    build_public(source, executable, Engine.ARM64, Compiler.GCC)
    assert executable.read_bytes() == elf_header
    with pytest.raises(RuntimeError, match="did not emit ELF"):
        build_public(source, executable, Engine.AMD64, Compiler.GCC)


@pytest.mark.parametrize(
    "engine, mutant", [(Engine.QEMU_X86_64, 0), (Engine.AMD64, -1)]
)
def test_toolchain_rejects_invalid_requests(
    tmp_path: Path, engine: Engine, mutant: int
) -> None:
    with pytest.raises(ValueError):
        build_public(
            tmp_path / "source", tmp_path / "program", engine, Compiler.CLANG, mutant
        )
