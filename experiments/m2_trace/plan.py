"""Make calibration plans from public fixture disassembly."""

import re
from pathlib import Path

from experiments.m2_trace.trace import Plan, parse_plan

DIRECT_SYMBOLS = {"fread": "fread@plt", "call": "walk", "fwrite": "fwrite@plt"}


def make_plan(binary: Path, disassembly: str) -> tuple[Plan, dict[str, int]]:
    instructions: dict[int, tuple[bytes, str, str]] = {}
    symbols = {}
    owner = ""
    for line in disassembly.splitlines():
        label = re.fullmatch(r"([0-9a-f]+) <([^>]+)>:", line)
        if label:
            owner = label[2]
            symbols[owner] = int(label[1], 16)
        match = re.match(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(\S.*)", line)
        if match:
            instructions[int(match[1], 16)] = bytes.fromhex(match[2]), match[3], owner
    sites: dict[int, tuple[str, bytes]] = {}
    found: set[str] = set()
    for address, (code, text, function) in instructions.items():
        kind = None
        if function == "walk" and re.match(r"callq?\s+\*", text):
            kind = "indirect"
        elif function == "main" and re.match(r"callq?\s", text):
            for candidate, symbol in DIRECT_SYMBOLS.items():
                if f"<{symbol}>" in text:
                    kind = candidate
        if kind:
            sites[address] = kind, code
            found.add(kind)
            continuation = address + len(code)
            if continuation not in instructions:
                raise ValueError("The call has no disassembled continuation.")
            sites[continuation] = "continuation", instructions[continuation][0]
        elif function in {"walk", "increment", "exclusive_or"} and re.fullmatch(
            r"retq?", text
        ):
            sites[address] = "ret", code
    if (
        found != {"indirect", "fread", "fwrite", "call"}
        or not {*DIRECT_SYMBOLS.values(), "increment", "exclusive_or"} <= symbols.keys()
    ):
        raise ValueError("The fixture lacks a required call mechanism or symbol.")
    from hashlib import sha256

    raw = f"M2PLAN\t1\t{sha256(binary.read_bytes()).hexdigest()}\n"
    raw += "".join(
        f"S\t{kind}\t{address:016x}\t{code.hex()}\n"
        for address, (kind, code) in sorted(sites.items())
    )
    return parse_plan(binary, raw.encode("ascii")), symbols
