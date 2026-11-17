import subprocess
from unittest.mock import Mock

import pytest

from phoenix_eval import quality
from phoenix_eval.integrity import CompilerEvidence


def evidence(target: str, *names: str) -> CompilerEvidence:
    return CompilerEvidence(target, "18.1.3", (), (), names)


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
        "rax_١",
        "rbx২",
        "r8d𝟡",
        "xmm32",
        "r999",
    ],
)
def test_local_and_parameter_register_names_are_counted(name: str) -> None:
    assert (
        quality.register_named_locals((evidence("aarch64-linux-gnu", name, name),)) == 2
    )


@pytest.mark.parametrize(
    "name", ["array", "rax_value", "prefix_rax", "rax²", "r16", ""]
)
def test_other_names_are_not_counted(name: str) -> None:
    assert quality.register_named_locals((evidence("aarch64-linux-gnu", name),)) == 0


def test_only_arm64_evidence_is_counted_without_another_compiler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Mock(side_effect=AssertionError("Do not start another compiler."))
    monkeypatch.setattr(subprocess, "run", runner)
    monkeypatch.delenv("PHOENIX_ROOT")
    recorded = (
        evidence("x86_64-linux-gnu", "rax", "rbx", "rcx"),
        evidence("aarch64-linux-gnu", "rax", "count"),
    )
    assert quality.register_named_locals(recorded) == 1
    assert quality.register_named_locals(tuple(reversed(recorded))) == 1
    runner.assert_not_called()


@pytest.mark.parametrize(
    "recorded",
    [
        (),
        (evidence("x86_64-linux-gnu", "rax"),),
        (evidence("aarch64-linux-gnu"), evidence("aarch64-linux-gnu", "rax")),
    ],
)
def test_missing_or_ambiguous_arm64_evidence_cannot_claim_zero(
    recorded: tuple[CompilerEvidence, ...],
) -> None:
    assert quality.register_named_locals(recorded) is None


def test_complete_empty_name_evidence_produces_zero() -> None:
    assert quality.register_named_locals((evidence("aarch64-linux-gnu"),)) == 0


def test_goto_density_uses_statements_and_comment_free_source_lines() -> None:
    source = {
        "src/program.c": (
            b'/* goto\n ignored */\nint main(void) {\n const char *text = "goto"; '
            b"// goto\n goto end;\n end: return 0;\n}\n"
        )
    }
    assert quality.goto_density(source) == 20.0
