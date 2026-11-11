import json
from dataclasses import replace
from pathlib import Path

import pytest
import test_checked_switch_emission as switch_test
from test_recovery_switches import BASE, switch_fixture
from test_recovery_u1 import raw_json

from phoenix.generate import (
    Candidate,
    Definition,
    InvalidCandidate,
    parse_candidate,
    request_candidate,
    write_project,
)
from phoenix.generate.checked_switch import emit_checked_switch
from phoenix.generate.protected_switch import ProtectedDefinition, protect_switch
from phoenix.lift.mapping import GhidraVA, MappingError
from phoenix.lift.switch_graph import parse_switch_graph
from phoenix.lift.switch_source import parse_ordinary_source
from phoenix.recover import Function, Program


@pytest.fixture
def protected(monkeypatch: pytest.MonkeyPatch) -> tuple[Program, ProtectedDefinition]:
    source = switch_test._SOURCE.replace(b"{switch", b"{uint result;switch")
    monkeypatch.setattr(switch_test, "_SOURCE", source)
    binary, lift, proof, raw_graph = switch_fixture(
        "duplicate", prepare_function=switch_test._function
    )
    lift = replace(lift, main=GhidraVA(BASE + 0x140))
    graph = parse_switch_graph(raw_json(raw_graph), lift)
    (body,) = parse_ordinary_source(
        raw_json(switch_test._artifact(lift.binary_sha256, lift.lift_sha256)), lift
    ).bodies
    emission = emit_checked_switch(binary, lift, proof, graph, body)
    function = Function(
        BASE + 0x100,
        "original",
        f"fn_{BASE + 0x100:x}",
        ((BASE + 0x100, BASE + 0x120),),
        source.decode(),
        "",
    )
    main = Function(BASE + 0x140, "entry", "main", (), "", "")
    program = Program(0, main.entry, 0, 0, (function, main), (), ())
    return program, protect_switch(emission, function, binary, lift, proof)


def _response(program: Program, *, extra: bool = False) -> str:
    functions = {
        hex(program.main): {
            "signature": "int main(void)",
            "body": "return 0;",
            "evidence": "The public test declares main.",
        }
    }
    if extra:
        functions[hex(program.functions[0].entry)] = {
            "signature": "uint fn_100100(uint select)",
            "body": "return 7;",
            "evidence": "This model edit must reject.",
        }
    return json.dumps({"declarations": "", "functions": functions})


def test_model_and_repair_cannot_replace_the_protected_definition(
    protected: tuple[Program, ProtectedDefinition],
) -> None:
    program, checked = protected
    response = _response(program)
    first = parse_candidate(response, program, protected=(checked,))
    request = request_candidate(
        program,
        protected=(checked,),
        previous=first,
        difference="Keep the exact protected function.",
        round_number=1,
    )
    assert checked.source.replace("\n", "\\n") in request.prompt
    assert '"protected_functions": {"0x100100":' in request.prompt
    second = parse_candidate(response, program, protected=(checked,))
    assert first.functions[0] is checked and second.functions[0] is checked
    with pytest.raises(InvalidCandidate, match="unprotected"):
        parse_candidate(_response(program, extra=True), program, protected=(checked,))


def test_writer_emits_protected_source_before_model_directives(
    protected: tuple[Program, ProtectedDefinition], tmp_path: Path
) -> None:
    program, checked = protected
    candidate = Candidate(
        "#define select different_after_the_checked_function",
        (checked, Definition(program.main, "int main(void)", "return 0;", "")),
    )
    write_project(tmp_path, candidate)
    source = (tmp_path / "src/program.c").read_text()
    assert source.count(checked.source) == 1
    assert source.index(checked.source) < source.index("#define select")
    assert "case 0u:case 1u:result = 11;" in source
    assert "#include <stdint.h>\ntypedef uint32_t uint;" in source


def test_writer_rejects_changed_protected_bytes(
    protected: tuple[Program, ProtectedDefinition], tmp_path: Path
) -> None:
    _, checked = protected
    changed = replace(checked, source=checked.source.replace("11", "12"))
    with pytest.raises(MappingError, match="changed"):
        write_project(tmp_path, Candidate("", (changed,)))


def test_candidate_rejects_an_invalid_protected_roster(
    protected: tuple[Program, ProtectedDefinition],
) -> None:
    program, checked = protected
    for roster in ((checked, checked), (replace(checked, entry=42),)):
        with pytest.raises(InvalidCandidate, match="roster"):
            parse_candidate(_response(program), program, protected=roster)
