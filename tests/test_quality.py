import io
import json
import subprocess
import tarfile
from unittest.mock import Mock

import pytest

from phoenix_eval import quality


@pytest.mark.parametrize(
    "name",
    [
        "rax",
        "EAX",
        "r8d",
        "xmm3",
        "in_RAX",
        "unaff_RBX12",
        "extraout_EDX_2",
        "rip",
        "st0",
        "mm7",
        "fs",
    ],
)
def test_local_and_parameter_register_names_are_counted(name: str) -> None:
    tree: dict[str, object] = {
        "kind": "FunctionDecl",
        "inner": [
            {"kind": "ParmVarDecl", "name": name},
            {"kind": "CompoundStmt", "inner": [{"kind": "VarDecl", "name": name}]},
        ],
    }
    assert quality._locals(tree) == 2


def test_globals_prototypes_function_names_and_references_are_not_locals() -> None:
    tree: dict[str, object] = {
        "inner": [
            {"kind": "VarDecl", "name": "rax"},
            {
                "kind": "FunctionDecl",
                "name": "rax",
                "inner": [{"kind": "ParmVarDecl", "name": "rax"}],
            },
            {
                "kind": "FunctionDecl",
                "name": "rax",
                "inner": [
                    {
                        "kind": "CompoundStmt",
                        "inner": [
                            {
                                "kind": "DeclRefExpr",
                                "referencedDecl": {"kind": "VarDecl", "name": "rax"},
                            }
                        ],
                    }
                ],
            },
        ]
    }
    assert quality._locals(tree) == 0


def test_goto_density_uses_statements_and_comment_free_source_lines() -> None:
    source = {
        "src/program.c": (
            b'/* goto\n ignored */\nint main(void) {\n const char *text = "goto"; '
            b"// goto\n goto end;\n end: return 0;\n}\n"
        )
    }
    assert quality.goto_density(source) == 20.0


def test_source_paths_cannot_escape_the_compiler_container() -> None:
    with pytest.raises(ValueError, match="regular project"):
        quality.register_named_locals(
            {"../../escape.c": b"int main(void){return 0;}"}, image="fixture"
        )


def test_declarations_come_from_the_submitted_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {"src/program.c": b"int main(void) { int rax=0; return rax; }\n"}

    def compile(
        command: tuple[str, ...], *, input: bytes, **_: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert "--network=none" in command
        assert "--read-only" in command
        assert "fixture-image" in command
        with tarfile.open(fileobj=io.BytesIO(input)) as archive:
            stream = archive.extractfile("src/program.c")
            assert stream is not None
            assert stream.read() == source["src/program.c"]
        tree = {
            "kind": "FunctionDecl",
            "inner": [
                {"kind": "CompoundStmt", "inner": [{"kind": "VarDecl", "name": "rax"}]}
            ],
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(tree).encode(), b"")

    monkeypatch.setattr(subprocess, "run", compile)
    assert quality.register_named_locals(source, image="fixture-image") == 1


def test_compiler_error_cannot_produce_a_zero_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess, "run", Mock(side_effect=subprocess.CalledProcessError(1, "clang"))
    )
    with pytest.raises(subprocess.CalledProcessError):
        quality.register_named_locals({"src/program.c": b"invalid C"}, image="fixture")
