import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from phoenix.generate import InvalidCandidate, parse_candidate, raw, write_project
from phoenix.recover import Function, Program


@pytest.fixture
def program() -> Program:
    return Program(
        startup=0x1000,
        main=0x1100,
        main_setup=0x1010,
        main_call=0x1017,
        functions=(Function(0x1100, "FUN_1100", "main", ((0x1100, 0x110F),), "", ""),),
        imports=(),
        strings=(),
    )


def test_project_marks_functions_without_a_passing_test(
    program: Program, tmp_path: Path
) -> None:
    response = json.dumps(
        {
            "declarations": "#include <stdio.h>",
            "functions": {
                "0x1100": {
                    "signature": "int main(void)",
                    "body": "return 0;",
                    "evidence": "The startup call passes this entry point.",
                }
            },
        }
    )
    candidate = parse_candidate(response, program)
    write_project(tmp_path, candidate)
    source = tmp_path / "src/program.c"
    assert "PHOENIX-UNVERIFIED" in source.read_text()
    assert "See phoenix_report.json for final confidence." in source.read_text()
    assert "int main(void)\n{\n    return 0;\n}" in source.read_text()


def test_candidate_cannot_omit_a_recovered_function(program: Program) -> None:
    with pytest.raises(InvalidCandidate, match="each recovered function"):
        parse_candidate('{"declarations":"", "functions":{}}', program)


def test_raw_project_matches_fortified_stdio_declarations(
    program: Program, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("This source regression needs an installed C compiler.")
    function = replace(program.functions[0], raw_c="int FUN_1100(void) { return 0; }")
    original = tmp_path / "original.elf"
    original.write_bytes(b"Synthetic original without referenced data.")
    monkeypatch.setattr(raw, "_data_declarations", lambda *_: [])
    project = tmp_path / "project"
    raw.write_raw_project(project, replace(program, functions=(function,)), original)
    declarations = tmp_path / "checked-stdio.h"
    declarations.write_text(
        "#include <stdio.h>\n"
        "extern int __printf_chk(int, const char *, ...);\n"
        "extern int __fprintf_chk(FILE *, int, const char *, ...);\n"
    )
    result = subprocess.run(
        (
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-O2",
            "-fstack-protector-all",
            "-fsyntax-only",
            "-include",
            str(declarations),
            "-I",
            str(project / "include"),
            str(project / "src/program.c"),
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
