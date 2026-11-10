import random
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from struct import unpack_from

from phoenix_eval.case import CaseResult, Invocation
from phoenix_eval.docker import Engine, run_batch
from phoenix_eval.outcome import EntryKind, Outcome
from phoenix_eval.trace import CodeTrace
from phoenix_eval.wire import encode_invocation

_INSTRUCTION = re.compile(
    r"^[ \t]*([0-9a-f]+):[ \t]+([a-z][a-z0-9.]*)(?:[ \t]+(.*))?$", re.MULTILINE
)
_FDE = re.compile(r"\bFDE\b.*\bpc=([0-9a-f]+)\.\.")
_DESTINATION = re.compile(r"^([0-9a-f]+)(?:\s|$)")


@dataclass(frozen=True)
class BlockInventory:
    entry: int
    link_start: int
    sites: frozenset[int]
    blocks: frozenset[int]

    def hits(self, trace: CodeTrace) -> frozenset[int]:
        bias = trace.start - self.link_start
        return frozenset(address - bias for address in trace.hits) & self.blocks


@dataclass(frozen=True)
class PublicCoverage:
    recovered_blocks: int
    covered_blocks: int
    selected_cases: int
    mutation_candidates: int = 0
    emulator_sensitive_candidates: int = 0


def recover_blocks(entry: int, link_start: int, binutils: str) -> BlockInventory:
    instructions = [
        (int(address, 16), mnemonic, operands)
        for address, mnemonic, operands in _INSTRUCTION.findall(binutils)
    ]
    sites = frozenset(address for address, _, _ in instructions)
    if entry not in sites:
        raise ValueError("The ELF entry is outside the recovered .text instructions.")
    blocks = {
        entry,
        instructions[0][0],
        *(int(start, 16) for start in _FDE.findall(binutils)),
    }
    for index, (_, mnemonic, operands) in enumerate(instructions):
        if mnemonic.startswith(("j", "call", "ret", "loop")) or mnemonic in (
            "ud2",
            "hlt",
        ):
            if index + 1 < len(instructions):
                blocks.add(instructions[index + 1][0])
            target = _DESTINATION.match(operands)
            if target:
                blocks.add(int(target[1], 16))
    return BlockInventory(entry, link_start, sites, frozenset(blocks) & sites)


def read_executable_bounds(program: bytes) -> tuple[int, int]:
    if (
        not program.startswith(b"\x7fELF\x02\x01")
        or program[18:20] != b"\x3e\x00"
        or len(program) < 64
    ):
        raise ValueError("Coverage requires a little-endian x86-64 ELF.")
    entry, table = unpack_from("<QQ", program, 24)
    entry_size, count = unpack_from("<HH", program, 54)
    if entry_size != 56 or count == 0 or table + entry_size * count > len(program):
        raise ValueError("The ELF program header table is invalid.")
    starts = []
    for index in range(count):
        kind, flags, _, address = unpack_from(
            "<IIQQ", program, table + index * entry_size
        )
        if kind == 1 and flags & 1:
            starts.append(address)
    if not starts:
        raise ValueError("The ELF has no executable load segment.")
    return entry, min(starts)


def inspect_x86(binary: Path, image: str | None = None) -> BlockInventory:
    program = binary.read_bytes()
    entry, link_start = read_executable_bounds(program)
    listing = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--pids-limit=32",
            "--tmpfs=/work:rw,nosuid,nodev,size=32m",
            "--workdir=/work",
            "--entrypoint=/bin/sh",
            "--platform=linux/amd64",
            image or "phoenix-worker:amd64",
            "-ec",
            "cat > program; objdump -d --no-show-raw-insn -j .text program; "
            "readelf -wf program",
        ),
        input=program,
        capture_output=True,
        timeout=60,
        check=True,
    )
    return recover_blocks(entry, link_start, listing.stdout.decode("ascii"))


def select_cases(
    inventory: BlockInventory,
    cases: tuple[Invocation, ...],
    observed: tuple[CaseResult, ...],
    traced: tuple[CaseResult, ...],
) -> tuple[tuple[Invocation, ...], PublicCoverage]:
    covered: set[int] = set()
    selected = []
    for case, original, observation in zip(cases, observed, traced, strict=True):
        if not isinstance(original, Outcome) or not isinstance(observation, Outcome):
            raise ValueError("A coverage case has an invalid outcome.")
        if observation != original or observation.trace is None:
            raise ValueError(
                "A coverage run changed the observed behavior or omitted the trace."
            )
        hits = inventory.hits(observation.trace)
        if inventory.entry not in hits:
            raise ValueError("A coverage trace missed the executable entry.")
        if hits - covered:
            selected.append(case)
            covered.update(hits)
    if not selected:
        raise ValueError("The coverage run did not select any cases.")
    return tuple(selected), PublicCoverage(
        len(inventory.blocks), len(covered), len(selected)
    )


def _mutate(data: bytes, rng: random.Random) -> bytes:
    if not data:
        return rng.randbytes(1)
    offset = rng.randrange(len(data))
    return (
        data[:offset]
        + bytes((data[offset] ^ rng.randrange(1, 256),))
        + data[offset + 1 :]
    )


def mutate_inputs(seeds: tuple[Invocation, ...], seed: int) -> tuple[Invocation, ...]:
    rng = random.Random(seed)
    cases = []
    for case in seeds:
        entry = next(
            (item for item in case.tree.entries if item.kind is EntryKind.FILE), None
        )
        if entry is None:
            cases.append(replace(case, stdin=_mutate(case.stdin, rng)))
            continue
        updated = replace(entry, data=_mutate(entry.data, rng))
        tree = replace(
            case.tree,
            entries=tuple(
                updated if item.path == entry.path else item
                for item in case.tree.entries
            ),
        )
        cases.append(replace(case, tree=tree))
    return tuple(dict.fromkeys(cases))


def measure_public(
    binary: Path,
    cases: tuple[Invocation, ...],
    baseline: tuple[CaseResult, ...],
    destination: Path,
    seed: int,
    images: dict[str, str] | None = None,
) -> PublicCoverage:
    image_ids = images or {}
    amd64 = image_ids.get("amd64")
    arm64 = image_ids.get("arm64")
    inventory = inspect_x86(binary, amd64)
    traced = run_batch(binary, cases, Engine.QEMU_X86_64, trace=True, image=arm64)
    selected, summary = select_cases(inventory, cases, baseline, traced)

    candidates = tuple(
        case for case in mutate_inputs(selected, seed) if case not in cases
    )
    excluded = 0
    if candidates:
        rosetta = run_batch(binary, candidates, Engine.ROSETTA, image=amd64)
        qemu = run_batch(binary, candidates, Engine.QEMU_X86_64, image=arm64)
        agreed = []
        expected = []
        for case, first, second in zip(candidates, rosetta, qemu, strict=True):
            if not isinstance(first, Outcome) or not isinstance(second, Outcome):
                raise ValueError("A mutation candidate has an invalid outcome.")
            if first == second:
                agreed.append(case)
                expected.append(first)
            else:
                excluded += 1
        if agreed:
            additional = run_batch(
                binary, tuple(agreed), Engine.QEMU_X86_64, trace=True, image=arm64
            )
            selected, summary = select_cases(
                inventory,
                cases + tuple(agreed),
                baseline + tuple(expected),
                traced + additional,
            )
    destination.write_text(
        "".join(encode_invocation(case) + "\n" for case in selected), encoding="ascii"
    )
    return replace(
        summary,
        mutation_candidates=len(candidates),
        emulator_sensitive_candidates=excluded,
    )
