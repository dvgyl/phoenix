"""Measure source properties with C tokens and Clang declarations."""

import re

from phoenix_eval.integrity import CompilerEvidence

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


def register_named_locals(evidence: tuple[CompilerEvidence, ...]) -> int | None:
    arm = [item for item in evidence if item.target == "aarch64-linux-gnu"]
    if len(arm) != 1:
        return None
    return sum(_REGISTER.fullmatch(name) is not None for name in arm[0].local_names)
