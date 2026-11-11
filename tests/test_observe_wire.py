from dataclasses import replace
from hashlib import sha256

import pytest

from phoenix.observe.wire import (
    CallAttempt,
    Continuation,
    Entry,
    Gap,
    JumpAttempt,
    Registers,
    ReturnAttempt,
    TraceIdentity,
    TraceWireError,
    Transfer,
    parse_trace_wire,
)

IDENTITY = TraceIdentity("a" * 64, "b" * 64, "c" * 64, "d" * 64)
REGS = "\t".join(f"{value:016x}" for value in (1, 2, 3, 4, 5, 6))


def wire(events: list[str], status: str = "complete", version: str = "2") -> bytes:
    header = "\t".join(
        (
            "PXTRACE",
            version,
            IDENTITY.binary_sha256,
            IDENTITY.plan_sha256,
            IDENTITY.invocation_sha256,
            IDENTITY.runtime_sha256,
            "0000000000400000",
            "0000000000401000",
        )
    )
    body = ("\n".join([header, *events]) + "\n").encode("ascii")
    return body + f"END\t{len(events)}\t{sha256(body).hexdigest()}\t{status}\n".encode(
        "ascii"
    )


def test_wire_keeps_attempts_transfers_and_continuations_separate() -> None:
    raw = wire(
        [
            f"E\t0\t0000000000000100\texternal\t{REGS}",
            f"A\t1\t0000000000000110\t{REGS}",
            "T\t2\t1\t0000000000400120",
            f"E\t3\t0000000000000120\tcall\t{REGS}",
            "J\t4\t0000000000000124",
            "T\t5\t4\t0000000000400128",
            "R\t6\t0000000000000128\t0000000000400115\t0000000000000006\t0000000000000005",
            "T\t7\t6\t0000000000400115",
            f"C\t8\t1\t0000000000000115\t{REGS}",
        ]
    )
    parsed = parse_trace_wire(raw, IDENTITY)
    registers = Registers(1, 2, 3, 4, 5, 6)
    assert parsed.events == (
        Entry(0, 0x100, "external", registers),
        CallAttempt(1, 0x110, registers),
        Transfer(2, 1, 0x400120),
        Entry(3, 0x120, "call", registers),
        JumpAttempt(4, 0x124),
        Transfer(5, 4, 0x400128),
        ReturnAttempt(6, 0x128, 0x400115, 6, 5),
        Transfer(7, 6, 0x400115),
        Continuation(8, 1, 0x115, registers),
    )
    assert parsed.identity == IDENTITY
    assert (parsed.code_start, parsed.code_end) == (0x400000, 0x401000)
    assert parsed.sha256 == sha256(raw).hexdigest() and parsed.status == "complete"


@pytest.mark.parametrize(
    ("events", "status", "error"),
    [
        (["J\t1\t0000000000000100"], "complete", "not contiguous"),
        (["J\t00\t0000000000000100"], "complete", "sequence number"),
        (["J\t0\t000000000000010A"], "complete", "64-bit value"),
        (["J\t0\t0000000000000100"], "complete", "footer status conflicts"),
        (["T\t0\t0\t0000000000400100"], "complete", "follow its exact attempt"),
        (
            [f"A\t0\t0000000000000100\t{REGS}", f"C\t1\t0\t0000000000000105\t{REGS}"],
            "complete",
            "confirmed call",
        ),
        (
            [
                "J\t0\t0000000000000100",
                "T\t1\t0\t0000000000400105",
                f"C\t2\t0\t0000000000000105\t{REGS}",
            ],
            "complete",
            "confirmed call",
        ),
        (["G\t0\tlimit"], "gap", "footer status conflicts"),
        (["G\t0\tmapping"], "limited", "footer status conflicts"),
        (["G\t0\tunknown"], "gap", "event kind"),
        ([], "limited", "footer status conflicts"),
    ],
)
def test_wire_rejects_invalid_structure(
    events: list[str], status: str, error: str
) -> None:
    with pytest.raises(TraceWireError, match=error):
        parse_trace_wire(wire(events, status), IDENTITY)


def test_wire_keeps_diagnostic_gap_and_limit_states() -> None:
    gap = parse_trace_wire(
        wire(["J\t0\t0000000000000100", "G\t1\tpending"], "gap"), IDENTITY
    )
    limited = parse_trace_wire(wire(["G\t0\tlimit"], "limited"), IDENTITY)
    assert gap.events == (JumpAttempt(0, 0x100), Gap(1, "pending"))
    assert limited.events == (Gap(0, "limit"),)
    assert gap.status == "gap" and limited.status == "limited"


def test_wire_binds_exact_bytes_identity_version_and_size() -> None:
    raw = wire([])
    with pytest.raises(TraceWireError, match="input identities"):
        parse_trace_wire(raw, replace(IDENTITY, invocation_sha256="e" * 64))
    with pytest.raises(TraceWireError, match="footer digest"):
        parse_trace_wire(
            raw.replace(b"0000000000401000", b"0000000000402000"), IDENTITY
        )
    with pytest.raises(TraceWireError, match="schema 2"):
        parse_trace_wire(wire([], version="1"), IDENTITY)
    with pytest.raises(TraceWireError, match="not ASCII"):
        parse_trace_wire(b"\xff\n" + raw, IDENTITY)
    with pytest.raises(TraceWireError, match="exceeds its limits"):
        parse_trace_wire(wire(["G\t0\tlimit"] * 10_001), IDENTITY)
