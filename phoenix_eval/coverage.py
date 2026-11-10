import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from phoenix_eval.case import CaseResult, Invocation
from phoenix_eval.docker import Engine, run_batch
from phoenix_eval.outcome import Outcome
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
    sites: frozenset[int]
    blocks: frozenset[int]

    def hits(self, trace: CodeTrace) -> frozenset[int]:
        bias = trace.entry - self.entry
        return frozenset(address - bias for address in trace.hits) & self.blocks


@dataclass(frozen=True)
class PublicCoverage:
    recovered_blocks: int
    covered_blocks: int
    selected_cases: int


def recover_blocks(entry: int, binutils: str) -> BlockInventory:
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
    return BlockInventory(entry, sites, frozenset(blocks) & sites)


def inspect_x86(binary: Path) -> BlockInventory:
    program = binary.read_bytes()
    if (
        not program.startswith(b"\x7fELF\x02\x01")
        or program[18:20] != b"\x3e\x00"
        or len(program) < 64
    ):
        raise ValueError("Coverage requires a little-endian x86-64 ELF.")
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
            "phoenix-worker:amd64",
            "-ec",
            "cat > program; objdump -d --no-show-raw-insn -j .text program; "
            "readelf -wf program",
        ),
        input=program,
        capture_output=True,
        timeout=60,
        check=True,
    )
    return recover_blocks(
        int.from_bytes(program[24:32], "little"), listing.stdout.decode("ascii")
    )


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


def measure_public(
    binary: Path,
    cases: tuple[Invocation, ...],
    baseline: tuple[CaseResult, ...],
    destination: Path,
) -> PublicCoverage:
    inventory = inspect_x86(binary)
    traced = run_batch(binary, cases, Engine.QEMU_X86_64, trace=True)
    selected, summary = select_cases(inventory, cases, baseline, traced)
    destination.write_text(
        "".join(encode_invocation(case) + "\n" for case in selected), encoding="ascii"
    )
    return summary
