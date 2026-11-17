"""Measure source properties with C tokens and Clang declarations."""

import io
import json
import re
import subprocess
import tarfile
from typing import cast

from phoenix_eval.docker import Engine, docker_cli, freeze_images
from phoenix_eval.jobs import limited
from phoenix_eval.provenance import worker_source_digest

_TOKEN = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
_REGISTER = re.compile(
    r"(?:(?:in|unaff|extraout)_)?(?:"
    r"[re]?(?:ax|bx|cx|dx|si|di|sp|bp|ip|flags)|[abcd][lh]|[sd]il|[bs]pl|"
    r"[cdefgs]s|(?:mm|st|k|bnd|cr|dr)[0-9]|"
    r"r(?:[89]|1[0-5])(?:[bwd])?|(?:xmm|ymm|zmm)(?:[0-9]|[12][0-9]|3[01])"
    r")(?:_?\d+)?",
    re.I,
)


def _code(data: bytes, *, strings: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        text = match.group()
        if text.startswith(("/*", "//")) or strings:
            return " " + "\n" * text.count("\n")
        return text

    return _TOKEN.sub(replace, data.decode("utf-8"))


def goto_density(source: dict[str, bytes]) -> float:
    files = [data for name, data in source.items() if name.endswith((".c", ".h"))]
    lines = sum(
        sum(bool(line.strip()) for line in _code(data, strings=False).splitlines())
        for data in files
    )
    count = sum(
        len(re.findall(r"\bgoto\b", _code(data, strings=True))) for data in files
    )
    return 100 * count / lines if lines else 0.0


def _locals(node: dict[str, object]) -> int:
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
    return sum(_locals(child) for child in children)


@limited("compile")
def register_named_locals(source: dict[str, bytes], *, image: str | None = None) -> int:
    if image is None:
        image = freeze_images((Engine.ARM64,), worker_source_digest())["arm64"]
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as stream:
        for name, data in sorted(source.items()):
            if not name.endswith((".c", ".h")):
                continue
            if not re.fullmatch(r"(?:src|include)/[A-Za-z0-9_.-]+", name):
                raise ValueError("Use regular project source paths.")
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            stream.addfile(entry, io.BytesIO(data))
    count = 0
    for name in sorted(name for name in source if name.endswith(".c")):
        result = subprocess.run(
            (
                *docker_cli(),
                "run",
                "--rm",
                "-i",
                "--pull=never",
                "--platform=linux/arm64",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--pids-limit=32",
                "--memory=1536m",
                "--tmpfs=/work:rw,nosuid,nodev,size=64m",
                "--workdir=/work",
                "--entrypoint=/bin/sh",
                image,
                "-ec",
                "tar -xf -; clang -std=c11 -D_POSIX_C_SOURCE=200809L -Iinclude "
                '-Xclang -ast-dump=json -fsyntax-only "$1"',
                "quality",
                name,
            ),
            input=archive.getvalue(),
            capture_output=True,
            timeout=60,
            check=True,
        )
        document = json.loads(result.stdout)
        if not isinstance(document, dict):
            raise ValueError("Clang returned an invalid syntax tree.")
        count += _locals(document)
    return count
