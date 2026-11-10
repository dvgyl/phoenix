from dataclasses import replace
from pathlib import Path

import pytest

from phoenix_eval import coverage
from phoenix_eval.case import Invocation
from phoenix_eval.coverage import PublicCoverage, recover_blocks, select_cases
from phoenix_eval.docker import Engine
from phoenix_eval.outcome import EntryKind, Exited, Outcome, TreeEntry, TreeSnapshot
from phoenix_eval.trace import CodeTrace, parse_trace
from phoenix_eval.wire import decode_invocation, decode_result, encode_result

LISTING = """Disassembly of section .text:
    1000: xor %eax,%eax
    1002: jnz 1007 <other>
    1004: ret
    1005: nop
    1007: xor %eax,%eax
    1009: ret
00000018 00000014 0000001c FDE cie=00000000 pc=0000000000001000..000000000000100a
"""


def test_trace_normalizes_distinct_load_addresses() -> None:
    inventory = recover_blocks(0x1000, 0x1000, LISTING)
    assert inventory.blocks == frozenset((0x1000, 0x1004, 0x1005, 0x1007))
    for base in (0x100000, 0x220000):
        trace = parse_trace(
            (
                f"image {base:x} {base + 10:x}\n"
                f"hit {base:x}\nhit {base + 7:x}\ndone 2\n"
            ).encode()
        )
        assert inventory.hits(trace) == frozenset((0x1000, 0x1007))


@pytest.mark.parametrize(
    "text",
    [
        b"",
        b"image 10 20\nhit 10\ndone 0",
        b"image 10 20\nhit 10\nhit 10\ndone 2",
        b"image 10 20\nhit 40\ndone 1",
        b"image 20 10\nhit 10\ndone 1",
        b"image 10 20\nother 10\ndone 1",
    ],
)
def test_invalid_trace_fails_closed(text: bytes) -> None:
    with pytest.raises(ValueError):
        parse_trace(text)


def test_select_cases_adds_only_new_block_entries() -> None:
    cases = (Invocation(("first",)), Invocation(("repeat",)), Invocation(("new",)))
    outcome = Outcome(b"same", b"", Exited(0), TreeSnapshot())
    first = replace(outcome, trace=CodeTrace(0x1000, 0x100A, (0x1000, 0x1004)))
    new = replace(outcome, trace=CodeTrace(0x1000, 0x100A, (0x1000, 0x1007)))
    inventory = recover_blocks(0x1000, 0x1000, LISTING)
    selected, summary = select_cases(
        inventory, cases, (outcome,) * 3, (first, first, new)
    )
    assert selected == (cases[0], cases[2])
    assert summary == PublicCoverage(4, 3, 2)
    decoded = decode_result(encode_result(new))
    assert isinstance(decoded, Outcome)
    assert decoded.trace == new.trace
    with pytest.raises(ValueError, match="changed"):
        select_cases(
            inventory, cases[:1], (outcome,), (replace(first, stdout=b"changed"),)
        )


def test_development_generation_uses_a_case_that_adds_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Invocation(("read",))
    outcome = Outcome(b"same", b"", Exited(0), TreeSnapshot())
    inventory = recover_blocks(0x1000, 0x1000, LISTING)
    trace_empty = CodeTrace(0x1000, 0x100A, (0x1000, 0x1004))
    trace_input = CodeTrace(0x1000, 0x100A, (0x1000, 0x1007))

    def run(
        _: Path,
        cases: tuple[Invocation, ...],
        engine: Engine,
        *,
        trace: bool = False,
        **kwargs: object,
    ) -> tuple[Outcome, ...]:
        assert not trace or engine is Engine.QEMU_X86_64
        return tuple(
            replace(
                outcome,
                trace=(trace_input if case.stdin else trace_empty) if trace else None,
            )
            for case in cases
        )

    monkeypatch.setattr(coverage, "inspect_x86", lambda *_: inventory)
    monkeypatch.setattr(coverage, "run_batch", run)
    destination = tmp_path / "dev.jsonl"
    summary = coverage.measure_public(
        tmp_path / "program", (original,), (outcome,), destination, 23
    )
    generated = tuple(
        decode_invocation(line) for line in destination.read_text().splitlines()
    )
    assert generated == (original, *coverage.mutate_inputs((original,), 23))
    assert generated[1].stdin and generated[1].args == original.args
    assert summary == PublicCoverage(4, 3, 2, 1)


def test_development_generation_preserves_file_metadata() -> None:
    entry = TreeEntry("input", EntryKind.FILE, 0o640, b"test")
    case = Invocation(("write",), b"unchanged", TreeSnapshot(entries=(entry,)))
    (mutated,) = coverage.mutate_inputs((case,), 42)
    assert mutated.stdin == case.stdin
    (updated,) = mutated.tree.entries
    assert updated.data != entry.data
    assert replace(updated, data=entry.data) == entry


def test_elf_coverage_uses_the_first_executable_load_segment() -> None:
    from struct import pack_into

    program = bytearray(64 + 3 * 56)
    program[:6] = b"\x7fELF\x02\x01"
    pack_into("<H", program, 18, 62)
    pack_into("<QQ", program, 24, 0x1050, 64)
    pack_into("<HH", program, 54, 56, 3)
    pack_into("<IIQQ", program, 64, 1, 4, 0, 0x0000)
    pack_into("<IIQQ", program, 120, 1, 5, 0x3000, 0x3000)
    pack_into("<IIQQ", program, 176, 1, 5, 0x1000, 0x1000)
    assert coverage.read_executable_bounds(bytes(program)) == (0x1050, 0x1000)
    with pytest.raises(ValueError, match="program header table"):
        coverage.read_executable_bounds(bytes(program[:-1]))
