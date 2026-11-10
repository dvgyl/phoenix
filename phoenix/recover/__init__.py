import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from phoenix_eval.coverage import read_executable_bounds
from phoenix_eval.elf import elf_sections


class RecoveryError(ValueError):
    pass


class _Location(TypedDict):
    space: str
    offset: str


class _Range(TypedDict):
    start: _Location
    end: _Location


class _Instruction(TypedDict):
    address: _Location


class _Flow(TypedDict):
    target: _Location | None


class _Call(_Flow):
    caller: _Location | None


_Reference = TypedDict("_Reference", {"from": _Location, "to": _Location})


class _Decompilation(TypedDict):
    status: str
    raw_c: str | None


class _Parameter(TypedDict):
    name: str
    type: str


class _Signature(TypedDict):
    return_type: str
    parameters: list[_Parameter]
    variadic: bool


class _Function(TypedDict):
    name: str
    entry: _Location
    ranges: list[_Range]
    instructions: list[_Instruction]
    decompilation: _Decompilation
    signature: _Signature
    flow_edges: list[_Flow]
    thunk_target: _Location | None


class _Main(TypedDict):
    entry: _Location
    startup: _Location
    setup: _Location
    call: _Location


class _Import(TypedDict):
    name: str


class _String(TypedDict):
    address: _Location
    value: str


class _Export(TypedDict):
    schema_version: int
    main: _Main | None
    functions: list[_Function]
    call_edges: list[_Call]
    data_references: list[_Reference]
    imports: list[_Import]
    strings: list[_String]


@dataclass(frozen=True, slots=True)
class Function:
    entry: int
    ghidra_name: str
    name: str
    ranges: tuple[tuple[int, int], ...]
    raw_c: str
    ghidra_signature: str


@dataclass(frozen=True, slots=True)
class DataEvidence:
    address: int
    section: str
    bytes_hex: str
    ascii_candidate: str | None


@dataclass(frozen=True, slots=True)
class Program:
    startup: int
    main: int
    main_setup: int
    main_call: int
    functions: tuple[Function, ...]
    imports: tuple[str, ...]
    strings: tuple[tuple[int, str], ...]
    data: tuple[DataEvidence, ...] = ()


def _address(location: _Location | None) -> int | None:
    if location is None or location["space"] != "ram":
        return None
    return int(location["offset"], 16)


def _ram(location: _Location) -> int:
    address = _address(location)
    if address is None:
        raise RecoveryError("The lift has a function outside the RAM address space.")
    return address


def _functions(export: _Export) -> dict[int, _Function]:
    return {
        entry: function
        for function in export["functions"]
        if (entry := _address(function["entry"])) is not None
        and (
            function["thunk_target"] is None
            or _address(function["thunk_target"]) is not None
        )
    }


def _reachable(main: int, functions: dict[int, _Function], export: _Export) -> set[int]:
    edges: dict[int, set[int]] = defaultdict(set)
    owners = {
        _ram(instruction["address"]): entry
        for entry, function in functions.items()
        for instruction in function["instructions"]
    }
    for entry, function in functions.items():
        for edge in function["flow_edges"]:
            target = _address(edge["target"])
            if target is not None and target in functions:
                edges[entry].add(target)
    for call in export["call_edges"]:
        caller = _address(call["caller"])
        callee = _address(call["target"])
        if caller is not None and callee is not None and callee in functions:
            edges[caller].add(callee)
    for reference in export["data_references"]:
        site = _address(reference["from"])
        target = _address(reference["to"])
        if site is not None and site in owners and target is not None:
            if target in functions:
                edges[owners[site]].add(target)

    pending = [main]
    visited: set[int] = set()
    while pending:
        entry = pending.pop()
        if entry not in visited:
            visited.add(entry)
            pending.extend(edges[entry] - visited)
    return visited


def _recover_function(entry: int, main: int, function: _Function) -> Function:
    decompilation = function["decompilation"]
    raw = decompilation["raw_c"]
    if decompilation["status"] != "ok" or raw is None or not raw.strip():
        raise RecoveryError(f"Ghidra did not decompile function {entry:#x}.")
    signature = function["signature"]
    parameters = [
        f"{parameter['type']} {parameter['name']}"
        for parameter in signature["parameters"]
    ]
    if signature["variadic"]:
        parameters.append("...")
    return Function(
        entry=entry,
        ghidra_name=function["name"],
        name="main" if entry == main else f"fn_{entry:x}",
        ranges=tuple(
            (_ram(region["start"]), _ram(region["end"]))
            for region in function["ranges"]
        ),
        raw_c=raw,
        ghidra_signature=(
            f"{signature['return_type']} {function['name']}({', '.join(parameters)})"
        ),
    )


def _data_evidence(
    binary: Path,
    startup: int,
    export: _Export,
    functions: dict[int, _Function],
    reachable: set[int],
) -> tuple[DataEvidence, ...]:
    sites = {
        _ram(instruction["address"])
        for entry in reachable
        for instruction in functions[entry]["instructions"]
    }
    references = sorted(
        {
            target
            for ref in export["data_references"]
            if _address(ref["from"]) in sites
            and (target := _address(ref["to"])) is not None
        }
    )
    original = binary.read_bytes()
    link_entry, _ = read_executable_bounds(original)
    bias = startup - link_entry
    regions = elf_sections(original, ".rodata", ".data")
    evidence = []
    for name, region in regions.items():
        offsets = [
            address - bias - region.address
            for address in references
            if 0 <= address - bias - region.address < len(region.data)
        ]
        if not offsets:
            continue
        for start, end in zip(offsets, (*offsets[1:], len(region.data)), strict=True):
            data = region.data[start : min(end, start + 96)]
            text, nul, _ = data.partition(b"\0")
            ascii_candidate = (
                text.decode("ascii")
                if text
                and nul
                and all(32 <= byte < 127 or byte in b"\r\n\t" for byte in text)
                else None
            )
            evidence.append(
                DataEvidence(
                    bias + region.address + start, name, data.hex(), ascii_candidate
                )
            )
    return tuple(evidence)


def recover(lift: Path, binary: Path | None = None) -> Program:
    export = cast(_Export, json.loads(lift.read_text(encoding="utf-8")))
    if export.get("schema_version") != 1:
        raise RecoveryError("The lift uses an unsupported schema version.")
    evidence = export.get("main")
    if evidence is None:
        raise RecoveryError("The lift has no glibc main entry evidence.")
    main = _ram(evidence["entry"])
    functions = _functions(export)
    if main not in functions:
        raise RecoveryError("The lift has no body for the glibc main entry.")
    reachable = _reachable(main, functions, export)
    startup = _ram(evidence["startup"])
    return Program(
        startup=startup,
        main=main,
        main_setup=_ram(evidence["setup"]),
        main_call=_ram(evidence["call"]),
        functions=tuple(
            _recover_function(entry, main, functions[entry])
            for entry in sorted(reachable)
        ),
        imports=tuple(sorted({item["name"] for item in export["imports"]})),
        strings=tuple(
            (address, item["value"])
            for item in export["strings"]
            if (address := _address(item["address"])) is not None
        ),
        data=(
            _data_evidence(binary, startup, export, functions, reachable)
            if binary is not None
            else ()
        ),
    )
