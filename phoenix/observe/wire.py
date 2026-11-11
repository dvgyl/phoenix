import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, cast

_MAX_BYTES = 8 * 1024 * 1024
_MAX_EVENTS = 10_000
_HEX = re.compile(rb"[0-9a-f]{16}")
_DIGEST = re.compile(rb"[0-9a-f]{64}")
_DECIMAL = re.compile(rb"0|[1-9][0-9]{0,4}")
_GAPS = frozenset(
    (
        "register",
        "mapping",
        "witness",
        "stack",
        "memory",
        "pending",
        "limit",
        "vcpu",
        "unsupported_transfer",
    )
)
type Origin = Literal["call", "external", "unknown"]
type Status = Literal["complete", "gap", "limited"]


class TraceWireError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TraceIdentity:
    binary_sha256: str
    plan_sha256: str
    invocation_sha256: str
    runtime_sha256: str


@dataclass(frozen=True, slots=True)
class Registers:
    rdi: int
    rsi: int
    rdx: int
    rcx: int
    rax: int
    rsp: int


@dataclass(frozen=True, slots=True)
class Entry:
    sequence: int
    site: int
    origin: Origin
    registers: Registers


@dataclass(frozen=True, slots=True)
class CallAttempt:
    sequence: int
    site: int
    registers: Registers


@dataclass(frozen=True, slots=True)
class JumpAttempt:
    sequence: int
    site: int


@dataclass(frozen=True, slots=True)
class ReturnAttempt:
    sequence: int
    site: int
    stack_target: int
    rsp: int
    rax: int


type Attempt = CallAttempt | JumpAttempt | ReturnAttempt


@dataclass(frozen=True, slots=True)
class Transfer:
    sequence: int
    attempt: int
    next_pc: int


@dataclass(frozen=True, slots=True)
class Continuation:
    sequence: int
    call: int
    site: int
    registers: Registers


@dataclass(frozen=True, slots=True)
class Gap:
    sequence: int
    reason: str


type Event = Entry | Attempt | Transfer | Continuation | Gap


@dataclass(frozen=True, slots=True)
class WireTrace:
    identity: TraceIdentity
    code_start: int
    code_end: int
    events: tuple[Event, ...]
    status: Status
    sha256: str


def _word(value: bytes) -> int:
    if _HEX.fullmatch(value) is None:
        raise TraceWireError("The trace word is not a canonical 64-bit value.")
    return int(value, 16)


def _number(value: bytes) -> int:
    if _DECIMAL.fullmatch(value) is None:
        raise TraceWireError("The trace sequence number is invalid.")
    number = int(value)
    if number > _MAX_EVENTS:
        raise TraceWireError("The trace sequence number exceeds its bound.")
    return number


def _digest(value: bytes) -> str:
    if _DIGEST.fullmatch(value) is None:
        raise TraceWireError("The trace digest is invalid.")
    return value.decode("ascii")


def _registers(values: list[bytes]) -> Registers:
    rdi, rsi, rdx, rcx, rax, rsp = map(_word, values)
    return Registers(rdi, rsi, rdx, rcx, rax, rsp)


def _event(fields: list[bytes], sequence: int) -> Event:
    if len(fields) < 2 or _number(fields[1]) != sequence:
        raise TraceWireError("The trace sequence is not contiguous.")
    kind = fields[0]
    if kind == b"E" and len(fields) == 10:
        origin = fields[3].decode("ascii")
        if origin not in ("call", "external", "unknown"):
            raise TraceWireError("The trace entry origin is invalid.")
        return Entry(
            sequence, _word(fields[2]), cast(Origin, origin), _registers(fields[4:])
        )
    if kind == b"A" and len(fields) == 9:
        return CallAttempt(sequence, _word(fields[2]), _registers(fields[3:]))
    if kind == b"J" and len(fields) == 3:
        return JumpAttempt(sequence, _word(fields[2]))
    if kind == b"R" and len(fields) == 6:
        return ReturnAttempt(sequence, *map(_word, fields[2:]))
    if kind == b"T" and len(fields) == 4:
        return Transfer(sequence, _number(fields[2]), _word(fields[3]))
    if kind == b"C" and len(fields) == 10:
        return Continuation(
            sequence, _number(fields[2]), _word(fields[3]), _registers(fields[4:])
        )
    if kind == b"G" and len(fields) == 3:
        reason = fields[2].decode("ascii")
        if reason in _GAPS:
            return Gap(sequence, reason)
    raise TraceWireError("The trace event kind or fields are invalid.")


def parse_trace_wire(raw: bytes, expected: TraceIdentity) -> WireTrace:
    if (
        not raw.endswith(b"\n")
        or len(raw) > _MAX_BYTES
        or raw.count(b"\n") > _MAX_EVENTS + 2
        or any(c not in (9, 10) and not 32 <= c <= 126 for c in raw)
    ):
        raise TraceWireError("The trace wire exceeds its limits or is not ASCII.")
    rows = raw[:-1].split(b"\n")
    header = rows[0].split(b"\t")
    if len(rows) < 2 or len(header) != 8 or header[:2] != [b"PXTRACE", b"2"]:
        raise TraceWireError("The trace header does not use schema 2.")
    identity = TraceIdentity(*map(_digest, header[2:6]))
    if identity != expected:
        raise TraceWireError("The trace header does not match its input identities.")
    code_start, code_end = map(_word, header[6:])
    if code_start >= code_end:
        raise TraceWireError("The trace code range is invalid.")
    footer = rows[-1].split(b"\t")
    if len(footer) != 4 or footer[0] != b"END" or _number(footer[1]) != len(rows) - 2:
        raise TraceWireError("The trace footer does not match its event count.")
    status = footer[3].decode("ascii")
    if status not in ("complete", "gap", "limited"):
        raise TraceWireError("The trace footer status is invalid.")
    if _digest(footer[2]) != sha256(raw[: -(len(rows[-1]) + 1)]).hexdigest():
        raise TraceWireError("The trace footer digest differs from its bytes.")

    events: list[Event] = []
    confirmed: set[int] = set()
    continued: set[int] = set()
    gaps: set[str] = set()
    attempts = 0
    for sequence, row in enumerate(rows[1:-1]):
        event = _event(row.split(b"\t"), sequence)
        if isinstance(event, (CallAttempt, JumpAttempt, ReturnAttempt)):
            attempts += 1
        elif isinstance(event, Transfer):
            if (
                event.attempt != sequence - 1
                or not events
                or not isinstance(events[-1], (CallAttempt, JumpAttempt, ReturnAttempt))
            ):
                raise TraceWireError("A transfer must follow its exact attempt.")
            confirmed.add(event.attempt)
        elif isinstance(event, Continuation):
            if (
                event.call not in confirmed
                or not isinstance(events[event.call], CallAttempt)
                or event.call in continued
            ):
                raise TraceWireError(
                    "A continuation must refer to a confirmed call once."
                )
            continued.add(event.call)
        elif isinstance(event, Gap):
            gaps.add(event.reason)
        events.append(event)
    if (
        status == "complete"
        and (gaps or len(confirmed) != attempts)
        or status == "gap"
        and (not gaps or "limit" in gaps)
        or status == "limited"
        and "limit" not in gaps
    ):
        raise TraceWireError("The trace footer status conflicts with its evidence.")
    return WireTrace(
        identity,
        code_start,
        code_end,
        tuple(events),
        cast(Status, status),
        sha256(raw).hexdigest(),
    )
