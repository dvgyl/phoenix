import json
import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_ingest import _elf

from experiments.m2_trace import driver
from experiments.m2_trace.driver import accepted_evidence, fixed_cases
from experiments.m2_trace.plan import make_plan
from experiments.m2_trace.trace import (
    MAX_BYTES,
    MAX_EVENTS,
    Plan,
    Segment,
    Site,
    parse_plan,
    parse_trace,
)
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot

PLAN = Plan(
    "a" * 64,
    b"public test plan\n",
    (Segment(1, 0x1000, 0, 0x200), Segment(3, 0x2000, 0x200, 0x100)),
    (
        Site("indirect", 0x1010, b"\xff\xd0"),
        Site("continuation", 0x1012, b"\x90"),
        Site("ret", 0x1020, b"\xc3"),
        Site("fread", 0x1030, b"\xe8\x00\x00\x00\x00"),
        Site("continuation", 0x1035, b"\x90"),
        Site("fwrite", 0x1040, b"\xe8\x00\x00\x00\x00"),
        Site("continuation", 0x1045, b"\x90"),
    ),
)


def hx(value: int) -> str:
    return f"{value:016x}"


def wire(records: list[str], status: str = "complete", plan: Plan = PLAN) -> bytes:
    header = (
        f"M2TRACE\t1\t{plan.binary}\t{plan.sha256}\t"
        f"{hx(plan.start + 0x400000)}\t{hx(plan.end + 0x400000)}\n"
    )
    text = header + "".join(
        f"{kind}\t{seq}\t{rest}\n"
        for seq, row in enumerate(records)
        for kind, rest in [row.split("\t", 1)]
    )
    return (
        text + f"END\t{len(records)}\t{sha256(text.encode()).hexdigest()}\t{status}\n"
    ).encode()


def call() -> list[str]:
    return [
        "A\t" + "\t".join(map(hx, (0x1010, 41, 0, 0, 0, 99, 0x8000))),
        "T\t0\t" + hx(0x401100),
        "R\t" + "\t".join(map(hx, (0x1020, 0x401012, 0x7FF8, 42))),
        "T\t2\t" + hx(0x401012),
        "C\t0\t" + "\t".join(map(hx, (0x1012, 42, 0x8000))),
    ]


def stdio(kind: str, data: bytes = b"\x00\x01", pointer: int = 0x9000) -> list[str]:
    site = 0x1030 if kind == "fread" else 0x1040
    attempt = "A\t" + "\t".join(
        map(hx, (site, pointer, 1, len(data), 0xA000, 99, 0x8000))
    )
    sample = (
        "B\t0\t"
        + ("continuation" if kind == "fread" else "entry")
        + "\t"
        + "\t".join(
            map(hx, (pointer, 1, len(data), len(data) if kind == "fread" else 0))
        )
        + "\tok\t"
        + (data[:256].hex() or "-")
    )
    transfer = "T\t0\t" + hx(0x700000)
    continuation = "C\t0\t" + "\t".join(map(hx, (site + 5, len(data), 0x8000)))
    return (
        [attempt, transfer, continuation, sample]
        if kind == "fread"
        else [attempt, sample, transfer, continuation]
    )


def test_nonzero_argument_and_return_at_distinct_points() -> None:
    trace = parse_trace(wire(call()), PLAN)
    assert trace.status == "complete"
    assert trace.events[0].fields[1] == hx(41)
    assert trace.events[0].fields[5] == hx(99)
    assert trace.events[2].fields[-1] == hx(42)
    assert trace.events[4].fields[2] == hx(42)
    assert PLAN.code_ref(0x401100, trace.bias) == (1, 0x100)
    assert PLAN.code_ref(0x401500, trace.bias) is None


@pytest.mark.parametrize("kind", ("fread", "fwrite"))
@given(data=st.binary(max_size=256))
def test_bounded_stdio_samples(kind: str, data: bytes) -> None:
    assert parse_trace(wire(stdio(kind, data)), PLAN).status == "complete"


@pytest.mark.parametrize("kind", ("fread", "fwrite"))
@given(length=st.integers(min_value=257, max_value=4096))
def test_buffer_cap_exhaustion_cannot_complete(kind: str, length: int) -> None:
    rows = stdio(kind, b"x" * length)
    with pytest.raises(ValueError):
        parse_trace(wire(rows), PLAN)
    index = 3 if kind == "fread" else 1
    fields = rows[index].split("\t")
    fields[-2:] = ["limit", "-"]
    rows[index] = "\t".join(fields)
    rows.append("G\tlimit")
    assert parse_trace(wire(rows, "limited"), PLAN).status == "limited"


@given(
    index=st.integers(min_value=0, max_value=len(wire(call())) - 1),
    mask=st.integers(1, 255),
)
def test_byte_corruption_is_rejected(index: int, mask: int) -> None:
    raw = bytearray(wire(call()))
    raw[index] ^= mask
    with pytest.raises(ValueError):
        parse_trace(bytes(raw), PLAN)


@given(cut=st.integers(min_value=0, max_value=len(wire(call())) - 1))
def test_truncated_evidence_is_rejected(cut: int) -> None:
    with pytest.raises(ValueError):
        parse_trace(wire(call())[:cut], PLAN)


@given(raw=st.binary(max_size=2048))
def test_arbitrary_evidence_has_a_bounded_parse_failure(raw: bytes) -> None:
    with pytest.raises(ValueError):
        parse_trace(raw, PLAN)


@pytest.mark.parametrize(
    "mutation",
    (
        "sequence",
        "reference",
        "site",
        "return",
        "result",
        "stack",
        "width",
        "extra",
        "version",
        "binding",
        "bounds",
        "footer",
        "crlf",
    ),
)
def test_forged_evidence_is_rejected_with_a_recomputed_digest(mutation: str) -> None:
    rows = call()
    if mutation == "reference":
        rows[1] = "T\t1\t" + hx(0x401100)
    elif mutation == "site":
        rows[0] = rows[0].replace(hx(0x1010), hx(0x1011))
    elif mutation == "return":
        rows[3] = "T\t2\t" + hx(0x401013)
    elif mutation == "result":
        rows[4] = rows[4].replace(hx(42), hx(43))
    elif mutation == "stack":
        rows[4] = rows[4].replace(hx(0x8000), hx(0x8008))
    elif mutation == "width":
        rows[0] = rows[0].replace(hx(41), "29")
    elif mutation == "extra":
        rows[0] += "\tunknown"
    raw = wire(rows)
    replacements = {
        "sequence": (b"T\t1\t", b"T\t9\t"),
        "version": (b"M2TRACE\t1", b"M2TRACE\t2"),
        "binding": (PLAN.binary.encode(), b"b" * 64),
        "bounds": (hx(0x401000).encode(), hx(0x400000).encode()),
        "footer": (b"END\t5", b"END\t6"),
        "crlf": (b"\n", b"\r\n"),
    }
    if mutation in replacements:
        raw = raw.replace(*replacements[mutation])
        prefix, _, footer = raw.rpartition(b"END\t")
        fields = footer.split(b"\t")
        fields[1] = sha256(prefix).hexdigest().encode()
        raw = prefix + b"END\t" + b"\t".join(fields)
    with pytest.raises(ValueError):
        parse_trace(raw, PLAN)


def test_gaps_and_limits_cannot_claim_completion() -> None:
    for reason, status in (("limit", "limited"), ("memory", "gap")):
        assert parse_trace(wire(["G\t" + reason], status), PLAN).status == status
        with pytest.raises(ValueError):
            parse_trace(wire(["G\t" + reason]), PLAN)
    with pytest.raises(ValueError):
        parse_trace(wire(call()[:1]), PLAN)
    with pytest.raises(ValueError):
        parse_trace(wire([call()[0], call()[1], call()[4]]), PLAN)


def test_wire_record_and_sample_limits() -> None:
    for raw in (
        b"x" * (MAX_BYTES + 1),
        wire(["G\tlimit"] * (MAX_EVENTS + 1), "limited"),
        wire(
            stdio("fwrite", b"x" * 256)[:1]
            + [
                "B\t0\tentry\t"
                + "\t".join(map(hx, (0x9000, 1, 256, 0)))
                + "\tok\t"
                + "ab" * 257
            ],
            "gap",
        ),
    ):
        with pytest.raises(ValueError):
            parse_trace(raw, PLAN)


def test_frame_and_total_sample_limits() -> None:
    nested: list[str] = []
    for _ in range(65):
        seq = len(nested)
        nested.extend((call()[0], f"T\t{seq}\t{hx(0x401100)}"))
    nested.append("G\tlimit")
    with pytest.raises(ValueError, match="frame limit"):
        parse_trace(wire(nested, "limited"), PLAN)
    rows: list[str] = []
    for _ in range(257):
        seq = len(rows)
        rows.extend(
            row.replace("\t0\t", f"\t{seq}\t", 1) if index else row
            for index, row in enumerate(stdio("fwrite", b"x" * 256))
        )
    with pytest.raises(ValueError, match="total sample limit"):
        parse_trace(wire(rows), PLAN)


@pytest.mark.parametrize("kind", ("fread", "fwrite"))
def test_null_overflow_and_failed_reads_do_not_become_empty_success(kind: str) -> None:
    rows = stdio(kind, b"abc", pointer=0)
    with pytest.raises(ValueError):
        parse_trace(wire(rows), PLAN)
    rows = stdio(kind, b"abc", pointer=(1 << 64) - 2)
    with pytest.raises(ValueError):
        parse_trace(wire(rows), PLAN)
    rows = stdio(kind, b"abc")
    index = 3 if kind == "fread" else 1
    rows[index] = rows[index].replace("\tok\t616263", "\tunreadable\t-")
    rows.append("G\tmemory")
    assert parse_trace(wire(rows, "gap"), PLAN).status == "gap"
    with pytest.raises(ValueError):
        parse_trace(wire(rows), PLAN)


def test_plan_binding_witnesses_and_indirect_call_precondition(tmp_path: Path) -> None:
    binary = tmp_path / "public"
    data = _elf()
    data[0x180:0x183] = b"\xff\xd0\x90"
    binary.write_bytes(data)
    raw = (
        f"M2PLAN\t1\t{sha256(data).hexdigest()}\n"
        f"S\tindirect\t{hx(0x180)}\tffd0\n"
        f"S\tcontinuation\t{hx(0x182)}\t90\n"
    ).encode()
    plan = parse_plan(binary, raw)
    assert plan.start == 0 and plan.end == 0x200
    for changed in (
        raw.replace(b"ffd0", b"ffd1"),
        raw.replace(b"indirect", b"unknown"),
        raw.replace(b"\n", b"\r\n"),
        raw + raw.splitlines()[1] + b"\n",
        raw.replace(b"0000000000000180", b"0000000000000280"),
    ):
        with pytest.raises(ValueError):
            parse_plan(binary, changed)
    with pytest.raises(ValueError, match="mechanism"):
        make_plan(binary, "00000180 <walk>:\n 180: c3 ret\n")
    binary.write_bytes(bytes(data) + b"changed")
    with pytest.raises(ValueError):
        parse_plan(binary, raw)


def test_plan_reads_public_objdump_calls_and_rejects_devirtualization(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "public"
    data = _elf()
    disassembly = """0000000000000130 <fread@plt>:
0000000000000140 <fwrite@plt>:
0000000000000180 <main>:
 180:\te8 00 00 00 00       call   130 <fread@plt>
 185:\t90                   nop
 186:\te8 00 00 00 00       call   1a0 <walk>
 18b:\t90                   nop
 18c:\te8 00 00 00 00       call   140 <fwrite@plt>
 191:\t90                   nop
00000000000001a0 <walk>:
 1a0:\tff d0                call   *%rax
 1a2:\t90                   nop
 1a3:\tc3                   ret
00000000000001b0 <increment>:
 1b0:\tc3                   ret
00000000000001c0 <exclusive_or>:
 1c0:\tc3                   ret
"""
    for address in (0x180, 0x186, 0x18C):
        data[address : address + 6] = b"\xe8\0\0\0\0\x90"
    data[0x1A0:0x1A4] = b"\xff\xd0\x90\xc3"
    data[0x1B0] = data[0x1C0] = 0xC3
    binary.write_bytes(data)
    for symbol in ("fread@plt", "fwrite@plt"):
        incomplete = "\n".join(
            line
            for line in disassembly.splitlines()
            if not line.endswith(f"<{symbol}>:")
        )
        with pytest.raises(ValueError, match="symbol"):
            make_plan(binary, incomplete)
    plan, symbols = make_plan(binary, disassembly)
    assert symbols["walk"] == 0x1A0
    assert {site.kind for site in plan.sites} == {
        "call",
        "indirect",
        "fread",
        "fwrite",
        "ret",
        "continuation",
    }
    with pytest.raises(ValueError, match="mechanism"):
        make_plan(binary, disassembly.replace("call   *%rax", "call   1b0 <increment>"))


def test_outcome_and_capture_gaps_reject_trace_evidence() -> None:
    original = Outcome(b"A", b"", Exited(0), TreeSnapshot())
    changed = Outcome(b"B", b"", Exited(0), TreeSnapshot())
    trace = parse_trace(wire(call()), PLAN)
    assert not accepted_evidence(original, original, changed, trace)
    assert accepted_evidence(original, original, original, trace)
    limited = parse_trace(wire(["G\tlimit"], "limited"), PLAN)
    assert not accepted_evidence(original, original, original, limited)


def test_driver_retains_oracle_case_after_observer_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Outcome(b"A", b"", Exited(0), TreeSnapshot())
    changed = Outcome(b"B", b"", Exited(0), TreeSnapshot())
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    manifest = []
    for compiler in ("gcc", "clang"):
        for level in ("O0", "O2"):
            for variant in ("original", "unchanged", "wrong-target", "wrong-count"):
                for suffix in ("", ".dis"):
                    name = f"{compiler}-{level}.{variant}{suffix}"
                    data = variant.encode()
                    (fixture / name).write_bytes(data)
                    manifest.append(f"{sha256(data).hexdigest()}  {name}\n")
    (fixture / "packages.txt").write_bytes(b"packages")
    manifest.append(f"{sha256(b'packages').hexdigest()}  packages.txt\n")
    (fixture / "compiled-sha256.txt").write_text("".join(manifest))
    monkeypatch.setattr(driver, "fixed_cases", lambda: (Invocation(),))
    monkeypatch.setattr(
        driver,
        "make_plan",
        lambda path, text: (replace(PLAN, raw=path.read_bytes()), {}),
    )
    monkeypatch.setattr(
        driver,
        "run_cases",
        lambda path, cases, engine, image: (
            changed if path.suffix in {".wrong-target", ".wrong-count"} else original,
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, "arm64\npublic manifest"
        ),
    )

    def observe(
        binary: bytes, plan: Plan, case: Invocation, image: str
    ) -> tuple[Outcome, bytes]:
        return (original if binary == b"unchanged" else changed), wire(
            call(), plan=plan
        )

    def calibrate(
        trace: object, plan: Plan, case: object, symbols: object
    ) -> tuple[str, ...]:
        if plan.raw.startswith(b"wrong"):
            raise ValueError("The public mutation differs.")
        return ("same",)

    monkeypatch.setattr(driver, "observe", observe)
    monkeypatch.setattr(driver, "calibrate", calibrate)
    output = tmp_path / "report"
    assert not driver.experiment(fixture, output, "amd64", "arm64", "observer")
    report = json.loads((output / "report.json").read_text())
    originals = [row for row in report["cases"] if row["variant"] == "original"]
    assert len(originals) == 4
    assert all(row["oracle_agreed"] and not row["trace_accepted"] for row in originals)
    assert all("mismatch" in row["trace_rejection"] for row in originals)
    assert report["execution_completed"]
    assert not report["public_calibration_passed"]


def test_fixed_cases_cover_both_operations_and_buffer_boundary() -> None:
    cases = fixed_cases()
    assert len(cases) == 12
    for operation in ("inc", "xor"):
        selected = [case for case in cases if case.args == (operation,)]
        assert [len(case.stdin) for case in selected] == [0, 1, 2, 7, 8, 9]
        assert selected[-1].stdin.startswith(b"\0")
