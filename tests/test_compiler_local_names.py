"""Check name evidence with isolated, pinned Clang 18 checker images."""

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

from phoenix_eval.build import PROJECT_CMAKE, snapshot_project
from phoenix_eval.docker import Engine, freeze_images
from phoenix_eval.integrity import compiler_evidence
from phoenix_eval.jobs import Slots
from phoenix_eval.provenance import CHECKER_SOURCE_LABEL, checker_source_digest
from phoenix_eval.quality import _REGISTER, register_named_locals
from phoenix_eval.toolchain import SOURCE_TOOL_OPTIONS, run_tool

REPOSITORY = os.environ.get("PHOENIX_LOCAL_NAMES_CHECKER_REPOSITORY", "")
BASELINE_IMAGE = os.environ.get("PHOENIX_LOCAL_NAMES_BASELINE_IMAGE", "")
WORKSPACE = os.environ.get("PHOENIX_ROOT", "")

pytestmark = pytest.mark.skipif(
    not REPOSITORY,
    reason="Set PHOENIX_LOCAL_NAMES_CHECKER_REPOSITORY to use an isolated checker.",
)


def _old_count(node: dict[str, object]) -> int:
    """Apply the previous JSON walker to the pinned compiler output."""
    children = cast(list[dict[str, object]], node.get("inner", []))
    if node.get("kind") == "FunctionDecl":
        if not any(child.get("kind") == "CompoundStmt" for child in children):
            return 0

        def declarations(item: dict[str, object]) -> int:
            name = item.get("name")
            own = int(
                item.get("kind") in ("VarDecl", "ParmVarDecl")
                and isinstance(name, str)
                and _REGISTER.fullmatch(name) is not None
            )
            return own + sum(
                declarations(child)
                for child in cast(list[dict[str, object]], item.get("inner", []))
            )

        return sum(declarations(child) for child in children)
    return sum(_old_count(child) for child in children)


@pytest.mark.parametrize(
    ("source", "headers", "names"),
    [
        (
            "int rax; struct S { int rbx; }; int proto(int rcx);\n"
            "int rdx(void) { return rax; }\n",
            {},
            (),
        ),
        (
            "int rax; struct S { int rbx; }; int proto(int rcx);\n"
            "int proto(int count) { int r9 = 0; return count + r9; }\n"
            "int wrapper(void) { int proto(int rdx); return proto(0); }\n",
            {},
            ("count", "r9", "rdx"),
        ),
        (
            '#include <stdio.h>\n#include "decls.h"\n'
            "int rax; struct Global { int rbx; }; int proto(int rcx);\n"
            "int run(int in_RAX) {\n"
            "    int rax = 0; { int extraout_EDX_2 = 1; }\n"
            "    int nested(int rdi); int nested(int rdi);\n"
            "    struct Local { int r12; };\n"
            "    int (*rbx)(int xmm0);\n"
            "    typedef int fn(int mm0); fn *r10;\n"
            "    int accepts(int (*r11)(int xmm2));\n"
            '#include "locals.h"\n'
            "    int rax_١ = 0; int rbx২ = 0; int r8d𝟡 = 0;\n"
            "    for (int r13 = 0; r13 < 1; ++r13) { int r14 = 0; }\n"
            "    extern int unaff_RBX; static int r15;\n"
            "    return in_RAX + rax + header_def(0);\n"
            "}\n",
            {
                "decls.h": "int header_proto(int r9);\n"
                "static int header_def(int r8) { int xmm1 = 0; return r8 + xmm1; }\n",
                "locals.h": "int xmm7; int inside(int zmm2);\n",
            },
            (
                "r8",
                "xmm1",
                "in_RAX",
                "rax",
                "extraout_EDX_2",
                "rdi",
                "rdi",
                "rbx",
                "r10",
                "r11",
                "xmm7",
                "zmm2",
                "rax_١",
                "rbx২",
                "r8d𝟡",
                "r13",
                "r14",
                "unaff_RBX",
                "r15",
            ),
        ),
    ],
)
def test_pinned_names_match_the_old_walker_and_preserve_integrity_json(
    tmp_path: Path, source: str, headers: dict[str, str], names: tuple[str, ...]
) -> None:
    assert WORKSPACE, "Source the Phoenix workspace environment."
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", BASELINE_IMAGE), (
        "Set PHOENIX_LOCAL_NAMES_BASELINE_IMAGE to the old checker image ID."
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    (tmp_path / "CMakeLists.txt").write_text(PROJECT_CMAKE)
    (tmp_path / "src/program.c").write_text(source)
    for name, text in headers.items():
        (tmp_path / "include" / name).write_text(text)
    snapshot = snapshot_project(tmp_path)
    slots = Slots.from_environment()
    # Use the shared workspace slots instead of the unit-test workspace slots.
    slots = Slots(Path(WORKSPACE) / "slots", slots.jobs, slots.llm)
    with slots.acquire("compile"):
        images = freeze_images(
            (Engine.ARM64,),
            checker_source_digest(),
            repository=REPOSITORY,
            source_label=CHECKER_SOURCE_LABEL,
        )

        def invoke(image: str, command: str, *args: str) -> bytes:
            result = run_tool(
                "arm64",
                image,
                "tar -xf -; " + command,
                "local-name-golden",
                *args,
                options=(
                    *SOURCE_TOOL_OPTIONS,
                    "--pids-limit=32",
                    "--memory=768m",
                    "--memory-swap=768m",
                    "--tmpfs=/work:rw,noexec,nosuid,nodev,size=64m,uid=19704,gid=19704,mode=0700",
                ),
                input=snapshot.archive,
                timeout=60,
                check=False,
            )
            assert result.returncode == 0, (result.stdout, result.stderr)
            return result.stdout

        command = '/opt/phoenix/bin/phoenix-c-integrity "$@"'
        args = (
            "--project=/work/project",
            "/work/project/src/program.c",
            "--",
            "--target=aarch64-linux-gnu",
            "-std=c11",
            "-pedantic-errors",
            "-Wall",
            "-Wextra",
            "-I/work/project/include",
        )
        old = json.loads(invoke(BASELINE_IMAGE, command, *args))
        raw = invoke(images["arm64"], command, *args)
        new = json.loads(raw)
        assert Counter(new.pop("local_names")) == Counter(names)
        assert new == old
        tree = json.loads(
            invoke(
                BASELINE_IMAGE,
                "clang-18 -std=c11 -D_POSIX_C_SOURCE=200809L -Iproject/include "
                "-Xclang -ast-dump=json -fsyntax-only project/src/program.c",
            )
        )
    recorded = compiler_evidence(
        raw, "aarch64-linux-gnu", "src/program.c", dict(snapshot.files)
    )
    assert register_named_locals((recorded,)) == _old_count(tree)
    assert register_named_locals((recorded,)) == sum(
        _REGISTER.fullmatch(name) is not None for name in names
    )
