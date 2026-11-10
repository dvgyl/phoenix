"""Collect development cases from a stripped Linux executable."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from phoenix_eval.case import CaseResult, Invocation
from phoenix_eval.coverage import BlockInventory, inspect_x86, mutate_inputs
from phoenix_eval.docker import MAX_BATCH, Engine, WorkerError, run_batch
from phoenix_eval.elf import elf_sections
from phoenix_eval.outcome import EntryKind, Outcome, TreeEntry, TreeSnapshot

__all__ = ["Analysis", "DevelopmentCase", "analyze"]

_OPTION = re.compile(
    rb"(?<=[\x00\s\[(])(?:--[a-zA-Z0-9][a-zA-Z0-9-]{0,23}|-[a-zA-Z])"
    rb"(?=[\x00\s=,\])])"
)
_WORD = re.compile(rb"(?:^|\0)([A-Za-z][A-Za-z0-9_.-]{1,23})(?=\0)")


@dataclass(frozen=True)
class DevelopmentCase:
    invocation: Invocation
    expected: Outcome


@dataclass(frozen=True)
class Analysis:
    cases: tuple[DevelopmentCase, ...]
    covered_blocks: int
    recovered_blocks: int
    candidate_count: int
    emulator_sensitive: int
    invalid_candidates: int


def _seeds(binary: Path) -> tuple[Invocation, ...]:
    text = b"alpha,1\nbeta,2\n"
    file = TreeEntry("input.txt", EntryKind.FILE, 0o644, text)
    seeds = (
        Invocation(),
        Invocation(("--help",)),
        Invocation(("--version",)),
        Invocation(("0",)),
        Invocation(("sample", "1")),
        Invocation(stdin=text),
        Invocation(stdin=b"\x00\x01\x7f\x80\xff\n"),
        Invocation(args=(file.path,), tree=TreeSnapshot(entries=(file,))),
    )
    binary_data = binary.read_bytes()
    try:
        rodata = elf_sections(binary_data, ".rodata").get(".rodata")
    except ValueError:
        rodata = None
    evidence = rodata.data if rodata is not None else binary_data[: 1024 * 1024]
    hints: dict[Invocation, None] = {}
    for match in _OPTION.finditer(evidence):
        hint = Invocation((match[0].decode("ascii"),))
        if hint not in seeds:
            hints[hint] = None
            if len(hints) == 6:
                break
    words = []
    if rodata is not None:
        values = dict.fromkeys(
            match[1].decode("ascii") for match in _WORD.finditer(evidence)
        )
        for value in tuple(values)[:8]:
            words.append(Invocation((value,), stdin=text))
            if value.endswith((".txt", ".csv", ".dat")):
                entry = TreeEntry(value, EntryKind.FILE, 0o644, text)
                words.append(Invocation((value,), tree=TreeSnapshot(entries=(entry,))))
    return tuple(dict.fromkeys((*seeds, *hints, *words)))


def _run(
    binary: Path,
    cases: tuple[Invocation, ...],
    engine: Engine,
    image: str,
    *,
    trace: bool = False,
) -> Iterator[CaseResult]:
    for offset in range(0, len(cases), MAX_BATCH):
        batch = cases[offset : offset + MAX_BATCH]
        results = run_batch(binary, batch, engine, trace=trace, image=image)
        if len(results) != len(batch):
            raise WorkerError("The analysis worker returned the wrong result count.")
        if any(
            isinstance(result, Outcome) and (result.trace is not None) != trace
            for result in results
        ):
            raise WorkerError("The analysis worker returned an unexpected trace state.")
        yield from results


def _observe(
    binary: Path,
    cases: tuple[Invocation, ...],
    images: dict[str, str],
    inventory: BlockInventory,
) -> tuple[list[tuple[DevelopmentCase, frozenset[int]]], int]:
    rosetta = _run(binary, cases, Engine.ROSETTA, images["amd64"])
    qemu = _run(binary, cases, Engine.QEMU_X86_64, images["arm64"])
    matched = {}
    sensitive = 0
    for case, first, second in zip(cases, rosetta, qemu, strict=True):
        if isinstance(first, Outcome) and isinstance(second, Outcome):
            if first == second:
                matched[case] = first
            else:
                sensitive += 1

    observed = []
    traced = _run(
        binary, tuple(matched), Engine.QEMU_X86_64, images["arm64"], trace=True
    )
    for (case, expected), result in zip(matched.items(), traced, strict=True):
        if (
            isinstance(result, Outcome)
            and result.trace is not None
            and result == expected
        ):
            hits = inventory.hits(result.trace)
            if inventory.entry in hits:
                observed.append((DevelopmentCase(case, result), hits))
    return observed, sensitive


def _input_kind(case: Invocation) -> str:
    if case.tree.entries:
        return "file"
    if case.stdin:
        return "binary" if b"\0" in case.stdin else "text"
    return "argv" if case.args else "empty"


def analyze(binary: Path, images: dict[str, str], seed: int) -> Analysis:
    """Select matched cases and report coverage of recovered block entries.

    The candidate count includes distinct seeds and mutations. Invalid
    candidates include sandbox failures and unusable traced outcomes.
    """
    for platform in ("amd64", "arm64"):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", images.get(platform, "")):
            raise ValueError(f"Analysis requires a pinned {platform} worker image ID.")

    inventory = inspect_x86(binary, images["amd64"])
    seeds = _seeds(binary)
    observed, sensitive = _observe(binary, seeds, images, inventory)
    if not observed:
        raise ValueError("Analysis found no valid development cases.")

    selected = []
    covered: set[int] = set()
    kinds = set()
    for case, hits in observed:
        kind = _input_kind(case.invocation)
        if hits - covered or kind not in kinds:
            selected.append(case)
            covered.update(hits)
            kinds.add(kind)

    mutations = tuple(
        case
        for case in mutate_inputs(tuple(case.invocation for case in selected), seed)
        if case not in seeds
    )
    mutated, mutation_sensitive = _observe(binary, mutations, images, inventory)
    for case, hits in mutated:
        if hits - covered:
            selected.append(case)
            covered.update(hits)

    candidate_count = len(seeds) + len(mutations)
    sensitive += mutation_sensitive
    return Analysis(
        cases=tuple(selected),
        covered_blocks=len(covered),
        recovered_blocks=len(inventory.blocks),
        candidate_count=candidate_count,
        emulator_sensitive=sensitive,
        invalid_candidates=candidate_count - sensitive - len(observed) - len(mutated),
    )
