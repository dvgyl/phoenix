from dataclasses import replace

import pytest

from phoenix_eval.case import Invocation
from phoenix_eval.coverage import PublicCoverage, recover_blocks, select_cases
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.trace import CodeTrace, parse_trace
from phoenix_eval.wire import decode_result, encode_result

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
    inventory = recover_blocks(0x1000, LISTING)
    assert inventory.blocks == frozenset((0x1000, 0x1004, 0x1005, 0x1007))
    for base in (0x100000, 0x220000):
        trace = parse_trace(
            (
                f"image {base:x} {base + 10:x} {base:x}\n"
                f"hit {base:x}\nhit {base + 7:x}\ndone 2\n"
            ).encode()
        )
        assert inventory.hits(trace) == frozenset((0x1000, 0x1007))


@pytest.mark.parametrize(
    "text",
    [
        b"",
        b"image 10 20 10\nhit 10\ndone 0",
        b"image 10 20 10\nhit 10\nhit 10\ndone 2",
        b"image 10 20 10\nhit 40\ndone 1",
        b"image 10 20 40\nhit 10\ndone 1",
        b"image 10 20 10\nother 10\ndone 1",
    ],
)
def test_invalid_trace_fails_closed(text: bytes) -> None:
    with pytest.raises(ValueError):
        parse_trace(text)


def test_select_cases_adds_only_new_block_entries() -> None:
    cases = (Invocation(("first",)), Invocation(("repeat",)), Invocation(("new",)))
    outcome = Outcome(b"same", b"", Exited(0), TreeSnapshot())
    first = replace(outcome, trace=CodeTrace(0x1000, 0x100A, 0x1000, (0x1000, 0x1004)))
    new = replace(outcome, trace=CodeTrace(0x1000, 0x100A, 0x1000, (0x1000, 0x1007)))
    inventory = recover_blocks(0x1000, LISTING)
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
