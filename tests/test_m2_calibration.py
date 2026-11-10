import json
import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from test_m2_trace import hx, wire

from experiments.m2_trace import driver
from experiments.m2_trace.trace import Plan, Segment, Site, parse_trace
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import EntryKind, Exited, Outcome, TreeEntry, TreeSnapshot
from phoenix_eval.wire import decode_result

BIAS = 0x400000
PUBLIC_PLAN = Plan(
    "a" * 64,
    b"synthetic public plan\n",
    (Segment(1, 0x1000, 0, 0x1000),),
    (
        Site("fread", 0x1010, b"\xe8\xeb\x00\x00\x00"),
        Site("continuation", 0x1015, b"\x90"),
        Site("call", 0x1020, b"\xe8\xdb\x01\x00\x00"),
        Site("continuation", 0x1025, b"\x90"),
        Site("fwrite", 0x1030, b"\xe8\xdb\x00\x00\x00"),
        Site("continuation", 0x1035, b"\x90"),
        Site("indirect", 0x1200, b"\xff\xd0"),
        Site("continuation", 0x1202, b"\x90"),
        Site("ret", 0x1203, b"\xc3"),
        Site("ret", 0x1300, b"\xc3"),
        Site("ret", 0x1400, b"\xc3"),
    ),
)
SYMBOLS = {
    "fread@plt": 0x1100,
    "fwrite@plt": 0x1110,
    "walk": 0x1200,
    "increment": 0x1300,
    "exclusive_or": 0x1400,
}
DIRECT_ORDER = ("fread", "call", "fwrite")


def public_records(
    case: Invocation,
    direct_order: tuple[str, ...] = DIRECT_ORDER,
    *,
    operation: str | None = None,
    write_count: int | None = None,
) -> list[str]:
    rows: list[str] = []
    source = case.stdin[:8]
    selected = operation or case.args[0]
    target = SYMBOLS["increment" if selected == "inc" else "exclusive_or"]
    result = bytes(
        ((value + 1) & 255) if selected == "inc" else value ^ 0x5A for value in source
    )

    def add(kind: str, *fields: str) -> int:
        seq = len(rows)
        rows.append(kind + "\t" + "\t".join(fields))
        return seq

    def attempt(site: int, *regs: int) -> int:
        return add("A", hx(site), *map(hx, regs))

    def transfer(seq: int, pc: int) -> None:
        add("T", str(seq), hx(BIAS + pc))

    def continuation(seq: int, site: int, value: int, rsp: int) -> None:
        add("C", str(seq), hx(site), hx(value), hx(rsp))

    def sample(seq: int, phase: str, count: int, value: int, data: bytes) -> None:
        add(
            "B",
            str(seq),
            phase,
            hx(0x9000),
            hx(1),
            hx(count),
            hx(value),
            "ok",
            data.hex() or "-",
        )

    for kind in direct_order:
        if kind == "fread":
            seq = attempt(0x1010, 0x9000, 1, 8, 0xA000, 99, 0x8000)
            transfer(seq, SYMBOLS["fread@plt"])
            continuation(seq, 0x1015, len(source), 0x8000)
            sample(seq, "continuation", 8, len(source), source)
        elif kind == "call":
            walk = attempt(0x1020, 0x9100, BIAS + target, 0, 0, 99, 0x8000)
            transfer(walk, SYMBOLS["walk"])
            for value, changed in zip(source, result, strict=True):
                op = attempt(0x1200, value, 0, 0, 0, 99, 0x7FF0)
                transfer(op, target)
                ret = add("R", hx(target), hx(BIAS + 0x1202), hx(0x7FE8), hx(changed))
                transfer(ret, 0x1202)
                continuation(op, 0x1202, changed, 0x7FF0)
            ret = add("R", hx(0x1203), hx(BIAS + 0x1025), hx(0x7FF8), hx(len(source)))
            transfer(ret, 0x1025)
            continuation(walk, 0x1025, len(source), 0x8000)
        else:
            count = len(source) if write_count is None else write_count
            seq = attempt(0x1030, 0x9000, 1, count, 0xA000, 99, 0x8000)
            sample(seq, "entry", count, 0, result[:count])
            transfer(seq, SYMBOLS["fwrite@plt"])
            continuation(seq, 0x1035, count, 0x8000)
    return rows


def calibration(rows: list[str], case: Invocation) -> tuple[str, ...]:
    trace = parse_trace(wire(rows, plan=PUBLIC_PLAN), PUBLIC_PLAN)
    return driver.calibrate(trace, PUBLIC_PLAN, case, SYMBOLS)


@pytest.mark.parametrize("case", driver.fixed_cases())
def test_calibrate_fixed_cases(case: Invocation) -> None:
    signature = calibration(public_records(case), case)
    source = case.stdin[:8]
    expected = bytes(
        ((value + 1) & 255) if case.args == ("inc",) else value ^ 0x5A
        for value in source
    )
    assert signature[-2:] == (f"args={source.hex()}", f"results={expected.hex()}")
    for symbol in ("walk", "fread@plt", "fwrite@plt"):
        assert f"T:{SYMBOLS[symbol]:x}" in signature
    if source:
        selected = "increment" if case.args == ("inc",) else "exclusive_or"
        assert signature.count(f"T:{SYMBOLS[selected]:x}") == len(source)


@pytest.mark.parametrize("operation", ("inc", "xor"))
@pytest.mark.parametrize("site", (0x1010, 0x1020, 0x1030, 0x1200))
@pytest.mark.parametrize("destination", (0, BIAS + 0x1101, BIAS + 0x1400))
def test_calibrate_rejects_wrong_physical_targets(
    operation: str, site: int, destination: int
) -> None:
    case = Invocation(args=(operation,), stdin=b"\0")
    if site == 0x1200 and operation == "xor" and destination == BIAS + 0x1400:
        destination = BIAS + 0x1300
    rows = public_records(case)
    for index, row in enumerate(rows):
        fields = row.split("\t")
        if fields[0] == "T":
            attempt = rows[int(fields[1])].split("\t")
            if attempt[:2] == ["A", hx(site)]:
                fields[2] = hx(destination)
                rows[index] = "\t".join(fields)
    with pytest.raises(ValueError, match="target"):
        calibration(rows, case)


@pytest.mark.parametrize("operation", ("inc", "xor"))
@pytest.mark.parametrize("data", (b"", b"\0"))
@pytest.mark.parametrize(
    "order",
    (
        ("fread", "fread", "call", "fwrite"),
        ("fread", "call", "call", "fwrite"),
        ("fread", "call", "fwrite", "fwrite"),
        ("call", "fread", "fwrite"),
        ("fread", "fwrite", "call"),
        ("fwrite", "call", "fread"),
        ("fread", "fwrite"),
    ),
)
def test_calibrate_rejects_direct_call_count_or_order(
    operation: str, data: bytes, order: tuple[str, ...]
) -> None:
    case = Invocation(args=(operation,), stdin=data)
    with pytest.raises(ValueError, match="call order"):
        calibration(public_records(case, order), case)


@pytest.mark.parametrize("operation", ("inc", "xor"))
def test_calibrate_rejects_mutant_controls(operation: str) -> None:
    case = Invocation(args=(operation,), stdin=b"\0\xff")
    wrong_operation = "xor" if operation == "inc" else "inc"
    with pytest.raises(ValueError, match="target"):
        calibration(public_records(case, operation=wrong_operation), case)
    with pytest.raises(ValueError, match="stdio request"):
        calibration(public_records(case, write_count=1), case)


@pytest.mark.parametrize("fault", ("none", "outcome", "trace"))
def test_driver_records_positive_and_control_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    case = Invocation(args=("inc",), stdin=b"\0\xff")
    outcomes = {
        variant: Outcome(
            data,
            b"diagnostic\0",
            Exited(3),
            TreeSnapshot(0o750, (TreeEntry("result", EntryKind.FILE, 0o640, data),)),
        )
        for variant, data in (
            ("original", b"\x01\0"),
            ("unchanged", b"\x01\0"),
            ("wrong-target", b"\x5a\xa5"),
            ("wrong-count", b"\x01"),
        )
    }
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    manifest = []
    for compiler in ("gcc", "clang"):
        for level in ("O0", "O2"):
            for variant in outcomes:
                for suffix in ("", ".dis"):
                    name = f"{compiler}-{level}.{variant}{suffix}"
                    data = variant.encode()
                    (fixture / name).write_bytes(data)
                    manifest.append(f"{sha256(data).hexdigest()}  {name}\n")
    (fixture / "packages.txt").write_bytes(b"packages")
    manifest.append(f"{sha256(b'packages').hexdigest()}  packages.txt\n")
    (fixture / "compiled-sha256.txt").write_text("".join(manifest))
    monkeypatch.setattr(driver, "fixed_cases", lambda: (case,))
    monkeypatch.setattr(
        driver,
        "make_plan",
        lambda path, text: (replace(PUBLIC_PLAN, raw=path.read_bytes()), SYMBOLS),
    )
    monkeypatch.setattr(
        driver,
        "run_cases",
        lambda path, cases, engine, image: (outcomes[path.suffix[1:]],),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "arm64\nmanifest"),
    )

    def observe(
        binary: bytes, plan: Plan, case: Invocation, image: str
    ) -> tuple[Outcome, bytes]:
        variant = binary.decode()
        rows = public_records(
            case,
            operation="xor" if variant == "wrong-target" else "inc",
            write_count=1 if variant == "wrong-count" else None,
        )
        raw = wire(rows, plan=plan)
        outcome = outcomes[variant]
        if fault == "trace":
            raw = raw[:-1]
        elif fault == "outcome":
            outcome = replace(outcome, stderr=b"observer mismatch")
        return outcome, raw

    monkeypatch.setattr(driver, "observe", observe)
    output = tmp_path / "report"
    assert driver.experiment(fixture, output, "amd64", "arm64", "observer") == (
        fault == "none"
    )
    report = json.loads((output / "report.json").read_text())
    assert len(report["cases"]) == 16
    for record in report["cases"]:
        assert record["oracle_agreed"]
        variant = record["variant"]
        control = variant.startswith("wrong")
        assert record["trace_accepted"] == (not control and fault == "none")
        evidence = record["observation_0"]
        raw = (output / evidence["file"]).read_bytes()
        assert evidence["sha256"] == sha256(raw).hexdigest()
        assert (
            evidence["plan"]
            == sha256(
                (output / f"{record['build']}.{variant}.plan.tsv").read_bytes()
            ).hexdigest()
        )
        expected = outcomes[variant]
        if fault == "outcome":
            expected = replace(expected, stderr=b"observer mismatch")
        assert decode_result(evidence["outcome"]) == expected
        if fault != "none":
            assert "trace_rejection" in record
            assert "expected_calibration_rejection" not in record
        elif control:
            assert "expected_calibration_rejection" in record
        else:
            for repetition in range(3):
                assert record[f"observation_{repetition}"].keys() == evidence.keys()
