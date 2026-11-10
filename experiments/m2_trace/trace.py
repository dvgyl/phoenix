"""Parse PhoenixPublicTraceV1 without executing the observed program."""

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from struct import unpack_from

from phoenix.ingest import inspect_binary

MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 10_000
U64 = (1 << 64) - 1
CALLS = {"call", "indirect", "fread", "fwrite"}
GAPS = {"register", "mapping", "witness", "stack", "memory", "pending", "limit", "vcpu"}


def uint(text: str, *, decimal: bool = False) -> int:
    pattern = r"0|[1-9][0-9]{0,19}" if decimal else r"[0-9a-f]{16}"
    if not re.fullmatch(pattern, text):
        raise ValueError("Invalid unsigned integer.")
    value = int(text, 10 if decimal else 16)
    if value > U64:
        raise ValueError("Unsigned integer overflow.")
    return value


def digest(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("Invalid SHA-256 digest.")
    return text


def byte_string(text: str, cap: int) -> bytes:
    if text == "-":
        return b""
    if not re.fullmatch(r"(?:[0-9a-f]{2}){1," + str(cap) + "}", text):
        raise ValueError("Invalid bounded byte string.")
    return bytes.fromhex(text)


@dataclass(frozen=True)
class Segment:
    index: int
    address: int
    offset: int
    size: int


@dataclass(frozen=True)
class Site:
    kind: str
    address: int
    witness: bytes

    @property
    def continuation(self) -> int:
        return self.address + len(self.witness)


@dataclass(frozen=True)
class Plan:
    binary: str
    raw: bytes
    segments: tuple[Segment, ...]
    sites: tuple[Site, ...]

    @property
    def sha256(self) -> str:
        return sha256(self.raw).hexdigest()

    @property
    def start(self) -> int:
        return min(s.address for s in self.segments)

    @property
    def end(self) -> int:
        return max(s.address + s.size for s in self.segments)

    def code_ref(self, runtime_pc: int, bias: int) -> tuple[int, int] | None:
        for segment in self.segments:
            offset = runtime_pc - bias - segment.address
            if 0 <= offset < segment.size:
                return segment.index, offset
        return None


def parse_plan(binary: Path, raw: bytes) -> Plan:
    metadata = inspect_binary(binary)
    data = binary.read_bytes()
    if sha256(data).hexdigest() != metadata.sha256:
        raise ValueError("The binary changed during inspection.")
    if (
        len(raw) > 16_384
        or not raw.endswith(b"\n")
        or any(c not in (9, 10) and not 32 <= c <= 126 for c in raw)
    ):
        raise ValueError("Invalid plan size or ending.")
    rows = [line.split("\t") for line in raw.decode("ascii").splitlines()]
    if rows[0] != ["M2PLAN", "1", metadata.sha256]:
        raise ValueError("The plan does not bind this binary.")
    table = unpack_from("<Q", data, 32)[0]
    width, count = unpack_from("<HH", data, 54)
    if count > 128:
        raise ValueError("The prototype supports at most 128 program headers.")
    segments = []
    for index in range(count):
        kind, flags, offset, address, _, size, _, _ = unpack_from(
            "<IIQQQQQQ", data, table + index * width
        )
        if kind == 1 and flags & 1 and size:
            segments.append(Segment(index, address, offset, size))
    sites: list[Site] = []
    for row in rows[1:]:
        if (
            len(row) != 4
            or row[0] != "S"
            or row[1] not in CALLS | {"ret", "continuation"}
        ):
            raise ValueError("Invalid plan site.")
        site = Site(row[1], uint(row[2]), byte_string(row[3], 15))
        if not site.witness or any(s.address == site.address for s in sites):
            raise ValueError("Empty or repeated instruction witness.")
        for segment in segments:
            delta = site.address - segment.address
            if 0 <= delta and delta + len(site.witness) <= segment.size:
                if (
                    data[
                        segment.offset + delta : segment.offset
                        + delta
                        + len(site.witness)
                    ]
                    != site.witness
                ):
                    raise ValueError("The instruction witness differs from the binary.")
                break
        else:
            raise ValueError("The plan site is outside executable file data.")
        sites.append(site)
    if not 1 <= len(sites) <= 128:
        raise ValueError("Invalid plan site count.")
    by_address = {s.address: s for s in sites}
    for site in sites:
        if site.kind in CALLS and (
            site.continuation not in by_address
            or by_address[site.continuation].kind != "continuation"
        ):
            raise ValueError("A call needs a witnessed continuation.")
    return Plan(metadata.sha256, raw, tuple(segments), tuple(sites))


@dataclass(frozen=True)
class BufferSample:
    phase: str
    size: int
    count: int
    data: bytes


@dataclass(frozen=True)
class Event:
    kind: str
    fields: tuple[str, ...]

    @property
    def site_address(self) -> int:
        return uint(self.fields[0])

    @property
    def reference(self) -> int:
        return uint(self.fields[0], decimal=True)

    @property
    def first_argument(self) -> int:
        return uint(self.fields[1])

    @property
    def transfer_target(self) -> int:
        return uint(self.fields[1])

    @property
    def continuation_result(self) -> int:
        return uint(self.fields[2])

    @property
    def buffer_sample(self) -> BufferSample:
        return BufferSample(
            self.fields[1],
            uint(self.fields[3]),
            uint(self.fields[4]),
            byte_string(self.fields[7], 256),
        )


@dataclass(frozen=True)
class Observation:
    events: tuple[Event, ...]
    status: str
    bias: int
    sha256: str


def parse_trace(raw: bytes, plan: Plan) -> Observation:
    if (
        not 0 < len(raw) <= MAX_BYTES
        or not raw.endswith(b"\n")
        or any(c not in (9, 10) and not 32 <= c <= 126 for c in raw)
    ):
        raise ValueError("Invalid trace size or ending.")
    if raw.count(b"\n") > MAX_EVENTS + 2:
        raise ValueError("The trace exceeds the record limit.")
    lines = raw.splitlines(keepends=True)
    if len(lines) > MAX_EVENTS + 2 or any(len(line) > 2048 for line in lines):
        raise ValueError("The trace exceeds a record limit.")
    rows = [line[:-1].decode("ascii").split("\t") for line in lines]
    header, footer = rows[0], rows[-1]
    if len(header) != 6 or header[:4] != ["M2TRACE", "1", plan.binary, plan.sha256]:
        raise ValueError("The trace header does not bind the binary and plan.")
    start, end = map(uint, header[4:])
    bias = start - plan.start
    if bias < 0 or end != plan.end + bias or end > U64:
        raise ValueError("The executable PT_LOAD bounds differ.")
    if (
        len(footer) != 4
        or footer[0] != "END"
        or footer[3] not in {"complete", "gap", "limited"}
    ):
        raise ValueError("Invalid trace footer.")
    if (
        uint(footer[1], decimal=True) != len(rows) - 2
        or digest(footer[2]) != sha256(b"".join(lines[:-1])).hexdigest()
    ):
        raise ValueError("The trace count or digest differs.")
    sites = {s.address: s for s in plan.sites}
    events: list[Event] = []
    calls: dict[int, tuple[Site, tuple[int, ...]]] = {}
    frames: list[int] = []
    pending: int | None = None
    returned: int | None = None
    confirmed_return = False
    return_value: int | None = None
    samples: set[tuple[int, str]] = set()
    gaps: set[str] = set()
    total_sampled = 0
    for row in rows[1:-1]:
        if len(row) < 3 or uint(row[1], decimal=True) != len(events):
            raise ValueError("Noncontiguous event sequence.")
        seq = len(events)
        kind = row[0]
        if pending is not None and kind not in {"T", "B", "G"}:
            raise ValueError("A transfer confirmation is missing.")
        if confirmed_return and kind not in {"C", "G"}:
            raise ValueError("The return continuation is missing.")
        if kind == "A" and len(row) == 9:
            site = sites.get(uint(row[2]))
            if site is None or site.kind not in CALLS:
                raise ValueError("Unplanned call.")
            registers = tuple(map(uint, row[3:]))
            if registers[5] < 8:
                raise ValueError("Invalid call stack pointer.")
            calls[seq] = site, registers
            pending = seq
        elif kind == "T" and len(row) == 4:
            attempt, target = uint(row[2], decimal=True), uint(row[3])
            if attempt != pending:
                raise ValueError("Unmatched transfer.")
            if events[attempt].kind == "A":
                if len(frames) == 64:
                    raise ValueError("The frame limit was exceeded.")
                frames.append(attempt)
            else:
                if not frames or returned is None or target != returned:
                    raise ValueError("The return destination differs.")
                confirmed_return = True
            pending = None
        elif kind == "R" and len(row) == 6:
            site = sites.get(uint(row[2]))
            target, rsp, return_value = map(uint, row[3:])
            if site is None or site.kind != "ret" or not frames:
                raise ValueError("Unplanned or unmatched return.")
            call_site, regs = calls[frames[-1]]
            if rsp != regs[5] - 8 or target != call_site.continuation + bias:
                raise ValueError("The return stack differs.")
            pending, returned = seq, target
        elif kind == "C" and len(row) == 6:
            call = uint(row[2], decimal=True)
            site_pc, rax, rsp = map(uint, row[3:])
            if not frames or frames[-1] != call:
                raise ValueError("Unmatched continuation.")
            call_site, regs = calls[call]
            if site_pc != call_site.continuation or rsp != regs[5]:
                raise ValueError("The continuation differs.")
            if call_site.kind in {"call", "indirect"} and (
                not confirmed_return or rax != return_value
            ):
                raise ValueError("The program return confirmation is missing.")
            frames.pop()
            returned = None
            confirmed_return = False
            return_value = None
        elif kind == "B" and len(row) == 10:
            call, phase = uint(row[2], decimal=True), row[3]
            if call not in calls or (call, phase) in samples:
                raise ValueError("Unmatched or repeated sample.")
            site, regs = calls[call]
            pointer, size, count, result = map(uint, row[4:8])
            if (pointer, size, count) != regs[:3]:
                raise ValueError("The sample arguments differ.")
            if (
                site.kind == "fwrite"
                and phase == "entry"
                and pending == call
                and result == 0
            ):
                items = count
            elif (
                site.kind == "fread"
                and phase == "continuation"
                and events
                and events[-1].kind == "C"
                and uint(events[-1].fields[0], decimal=True) == call
            ):
                if result != uint(events[-1].fields[2]) or result > count:
                    raise ValueError("The sample return count differs.")
                items = result
            else:
                raise ValueError("The sample phase differs.")
            status, data = row[8], byte_string(row[9], 256)
            span = size * items
            requested = size * count
            if status == "ok":
                if (
                    requested > U64
                    or span > U64
                    or span > 256
                    or pointer + span > U64
                    or (span and not pointer)
                    or len(data) != span
                ):
                    raise ValueError("The sample span differs.")
            elif status not in {"null", "overflow", "unreadable", "limit"} or data:
                raise ValueError("Invalid failed sample.")
            else:
                gaps.add("memory" if status != "limit" else "limit")
            total_sampled += len(data)
            if total_sampled > 65536:
                raise ValueError("The total sample limit was exceeded.")
            samples.add((call, phase))
        elif kind == "G" and len(row) == 3 and row[2] in GAPS:
            gaps.add(row[2])
        else:
            raise ValueError("Invalid trace record.")
        events.append(Event(kind, tuple(row[2:])))
    status = footer[3]
    if status == "complete":
        if gaps or pending is not None or frames:
            raise ValueError("An incomplete trace claims completion.")
        for call, (site, _) in calls.items():
            phase = "entry" if site.kind == "fwrite" else "continuation"
            if site.kind in {"fread", "fwrite"} and (call, phase) not in samples:
                raise ValueError("A required buffer sample is missing.")
    elif not gaps or (status == "limited") != ("limit" in gaps):
        raise ValueError("The footer status does not describe its gaps.")
    return Observation(tuple(events), status, bias, sha256(raw).hexdigest())
