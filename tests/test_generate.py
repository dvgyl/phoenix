import json
from pathlib import Path

import pytest

from phoenix.generate import InvalidCandidate, parse_candidate, write_project
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
