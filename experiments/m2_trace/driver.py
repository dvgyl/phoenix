"""Run the fixed public call and stdio calibration experiment."""

import argparse
import json
import re
import subprocess
from base64 import b64decode, b64encode
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from experiments.m2_trace.plan import DIRECT_SYMBOLS, make_plan
from experiments.m2_trace.trace import Observation, Plan, parse_trace
from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine, docker_args, docker_cli, run_cases
from phoenix_eval.outcome import Outcome
from phoenix_eval.wire import decode_result, encode_invocation, encode_result

HERE = Path(__file__).resolve().parent


def fixed_cases() -> tuple[Invocation, ...]:
    for line in (HERE / "fixture-sha256.txt").read_text().splitlines():
        expected, name = line.split("  ")
        if sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError("The public fixture commitment differs.")
    return tuple(
        Invocation(args=(case["operation"],), stdin=bytes.fromhex(case["stdin_hex"]))
        for case in json.loads((HERE / "cases.json").read_text())
    )


def accepted_evidence(
    left: Outcome, right: Outcome, observed: Outcome, trace: Observation
) -> bool:
    return left == right == observed and trace.status == "complete"


def calibrate(
    trace: Observation, plan: Plan, case: Invocation, symbols: dict[str, int]
) -> tuple[str, ...]:
    if trace.status != "complete":
        raise ValueError("The trace has a capture gap.")
    sites = {site.address: site for site in plan.sites}
    source = case.stdin[:8]
    expected_calls = [
        ("A", "fread"),
        ("C", "fread"),
        ("A", "call"),
        *[(phase, "indirect") for _ in source for phase in ("A", "C")],
        ("C", "call"),
        ("A", "fwrite"),
        ("C", "fwrite"),
    ]
    call_sites = {
        seq: sites[event.site_address]
        for seq, event in enumerate(trace.events)
        if event.kind == "A"
    }
    actual_calls = [
        (event.kind, call_sites[seq if event.kind == "A" else event.reference].kind)
        for seq, event in enumerate(trace.events)
        if event.kind in {"A", "C"}
    ]
    if actual_calls != expected_calls:
        raise ValueError("The fixture call order or count differs.")
    operation_values = []
    operation_results = []
    samples = {}
    boundaries = {}
    order = []
    if case.args not in {("inc",), ("xor",)}:
        raise ValueError("The fixture operation is unsupported.")
    targets = {kind: symbols[symbol] for kind, symbol in DIRECT_SYMBOLS.items()}
    targets["indirect"] = symbols[
        "increment" if case.args == ("inc",) else "exclusive_or"
    ]
    for seq, event in enumerate(trace.events):
        if event.kind == "A":
            site = call_sites[seq]
            order.append(f"A:{site.address:x}")
            if site.kind == "indirect":
                operation_values.append(event.first_argument & 255)
        elif event.kind == "T":
            attempt = event.reference
            target = event.transfer_target - trace.bias
            if trace.events[attempt].kind == "A":
                kind = call_sites[attempt].kind
                if target != targets[kind]:
                    raise ValueError(f"The observed {kind} target differs.")
            order.append(f"T:{target:x}")
        elif event.kind == "R":
            order.append(f"R:{event.site_address:016x}")
        elif event.kind == "C":
            site = call_sites[event.reference]
            result = event.continuation_result
            order.append(f"C:{site.address:x}")
            if site.kind == "indirect":
                operation_results.append(result & 255)
            else:
                boundaries[site.kind] = result
        elif event.kind == "B":
            site = call_sites[event.reference]
            sample = event.buffer_sample
            samples[site.kind] = sample.data
            if sample.size != 1 or sample.count != (
                8 if site.kind == "fread" else len(source)
            ):
                raise ValueError("The stdio request differs.")
            order.append(f"B:{sample.phase}")
    expected = bytes(
        ((value + 1) & 255) if case.args == ("inc",) else value ^ 0x5A
        for value in source
    )
    if operation_values != list(source) or operation_results != list(expected):
        raise ValueError("The operation argument or result differs.")
    if samples != {"fread": source, "fwrite": expected} or boundaries != {
        "fread": len(source),
        "call": len(source),
        "fwrite": len(source),
    }:
        raise ValueError("The stdio sample or continuation result differs.")
    return (*order, f"args={source.hex()}", f"results={expected.hex()}")


def observe(
    binary: bytes, plan: Plan, case: Invocation, image: str
) -> tuple[Outcome, bytes]:
    request = json.dumps(
        {
            "binary": b64encode(binary).decode("ascii"),
            "plan": b64encode(plan.raw).decode("ascii"),
            "case": encode_invocation(case),
        }
    )
    name = f"phoenix-m2-public-{uuid4().hex}"
    try:
        result = subprocess.run(
            docker_args(Engine.QEMU_X86_64, name, image),
            input=request,
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            (*docker_cli(), "rm", "-f", name),
            capture_output=True,
            timeout=10,
            check=False,
        )
        raise
    response = json.loads(result.stdout)
    outcome = decode_result(response["outcome"])
    if not isinstance(outcome, Outcome):
        raise ValueError("The observer did not return an outcome.")
    return outcome, b64decode(response["trace"], validate=True)


def observation_record(
    output: Path, name: str, outcome: Outcome, raw: bytes, plan: Plan
) -> dict[str, str]:
    (output / name).write_bytes(raw)
    return {
        "file": name,
        "outcome": encode_result(outcome),
        "sha256": sha256(raw).hexdigest(),
        "plan": plan.sha256,
    }


def experiment(
    directory: Path, output: Path, amd64: str, arm64: str, observer: str
) -> bool:
    cases = fixed_cases()
    expected_files = {
        f"{compiler}-{level}.{variant}{suffix}"
        for compiler in ("gcc", "clang")
        for level in ("O0", "O2")
        for variant in ("original", "unchanged", "wrong-target", "wrong-count")
        for suffix in ("", ".dis")
    } | {"packages.txt"}
    commitment = (directory / "compiled-sha256.txt").read_text()
    hashes = dict(line.split("  ")[::-1] for line in commitment.splitlines())
    if hashes.keys() != expected_files or len(hashes) != len(commitment.splitlines()):
        raise ValueError("The compiled fixture commitment is incomplete.")
    for name, expected in hashes.items():
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError("A compiled fixture or disassembly changed.")
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, object] = {
        "scope": "public-development-only",
        "oracle_amd64": amd64,
        "oracle_arm64": arm64,
        "observer": observer,
        "fixture_commitment": (HERE / "fixture-sha256.txt").read_text(),
        "trace_pins": (HERE / "trace.lock.toml").read_text(),
        "compiled_commitment": commitment,
        "fixture_packages": (directory / "packages.txt").read_text(),
    }
    metadata = subprocess.run(
        (
            *docker_cli(),
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--platform=linux/arm64",
            "--entrypoint=/bin/cat",
            observer,
            "/opt/source/accepted-image-id",
            "/opt/source/guest-runtime.sha256",
            "/opt/source/observer.sha256",
            "/opt/source/packages.txt",
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if metadata.stdout.splitlines()[0] != arm64:
        raise ValueError("The observer guest runtime came from another oracle image.")
    report["observer_manifest"] = metadata.stdout
    records: list[dict[str, object]] = []
    report["cases"] = records
    passed = True
    finished = False
    try:
        for compiler in ("gcc", "clang"):
            for level in ("O0", "O2"):
                stem = f"{compiler}-{level}"
                binaries = {
                    variant: directory / f"{stem}.{variant}"
                    for variant in (
                        "original",
                        "unchanged",
                        "wrong-target",
                        "wrong-count",
                    )
                }
                plans = {
                    variant: make_plan(
                        path, path.with_suffix(path.suffix + ".dis").read_text()
                    )
                    for variant, path in binaries.items()
                }
                report[f"{stem}_binary_sha256"] = {
                    variant: sha256(path.read_bytes()).hexdigest()
                    for variant, path in binaries.items()
                }
                oracle = run_cases(
                    binaries["original"], cases, Engine.ROSETTA, image=amd64
                )
                qemu = run_cases(
                    binaries["original"], cases, Engine.QEMU_X86_64, image=arm64
                )
                baseline: list[tuple[str, ...] | None] = [None] * len(cases)
                for variant, binary in binaries.items():
                    left = (
                        oracle
                        if variant == "original"
                        else run_cases(binary, cases, Engine.ROSETTA, image=amd64)
                    )
                    right = (
                        qemu
                        if variant == "original"
                        else run_cases(binary, cases, Engine.QEMU_X86_64, image=arm64)
                    )
                    plan, symbols = plans[variant]
                    (output / f"{stem}.{variant}.plan.tsv").write_bytes(plan.raw)
                    detected = False
                    trace_control = False
                    for index, (case, a, b) in enumerate(
                        zip(cases, left, right, strict=True)
                    ):
                        record: dict[str, object] = {
                            "build": stem,
                            "variant": variant,
                            "case": index,
                            "invocation": encode_invocation(case),
                            "invocation_sha256": sha256(
                                encode_invocation(case).encode()
                            ).hexdigest(),
                            "left": encode_result(a),
                            "right": encode_result(b),
                            "oracle_agreed": isinstance(a, Outcome) and a == b,
                            "trace_accepted": False,
                        }
                        records.append(record)
                        if (
                            not isinstance(a, Outcome)
                            or not isinstance(b, Outcome)
                            or a != b
                        ):
                            record["trace_rejection"] = "oracle-disagreement-or-failure"
                            passed = False
                            continue
                        if variant in {"wrong-target", "wrong-count"}:
                            detected |= oracle[index] != a
                            if oracle[index] != a and not trace_control:
                                try:
                                    observed, raw = observe(
                                        binary.read_bytes(), plan, case, observer
                                    )
                                    record["observation_0"] = observation_record(
                                        output,
                                        f"{stem}.{variant}.{index}.control.tsv",
                                        observed,
                                        raw,
                                        plan,
                                    )
                                    trace = parse_trace(raw, plan)
                                    if not accepted_evidence(a, b, observed, trace):
                                        raise ValueError("Control outcome mismatch.")
                                    try:
                                        calibrate(trace, plan, case, symbols)
                                    except ValueError as exc:
                                        record["expected_calibration_rejection"] = str(
                                            exc
                                        )
                                        trace_control = True
                                    else:
                                        raise ValueError(
                                            "The mutated trace passed calibration."
                                        )
                                except (
                                    ValueError,
                                    OSError,
                                    subprocess.SubprocessError,
                                ) as exc:
                                    record["trace_rejection"] = str(exc)
                                    passed = False
                            continue
                        if variant == "unchanged" and oracle[index] != a:
                            raise ValueError("The unchanged rebuild outcome differs.")
                        signatures = []
                        try:
                            for repetition in range(3):
                                observed, raw = observe(
                                    binary.read_bytes(), plan, case, observer
                                )
                                name = f"{stem}.{variant}.{index}.{repetition}.tsv"
                                record[f"observation_{repetition}"] = (
                                    observation_record(
                                        output, name, observed, raw, plan
                                    )
                                )
                                trace = parse_trace(raw, plan)
                                if not accepted_evidence(a, b, observed, trace):
                                    raise ValueError(
                                        "Observer outcome mismatch or trace gap."
                                    )
                                signatures.append(calibrate(trace, plan, case, symbols))
                                try:
                                    parse_trace(raw[:-1], plan)
                                except ValueError:
                                    pass
                                else:
                                    raise ValueError(
                                        "The malformed trace control was accepted."
                                    )
                            if not all(value == signatures[0] for value in signatures):
                                raise ValueError("Repeated observations differ.")
                            if (
                                variant == "unchanged"
                                and signatures[0] != baseline[index]
                            ):
                                raise ValueError("The unchanged rebuild trace differs.")
                            if variant == "original":
                                baseline[index] = signatures[0]
                            record["trace_accepted"] = True
                        except (ValueError, OSError, subprocess.SubprocessError) as exc:
                            record["trace_rejection"] = str(exc)
                            passed = False
                    if variant in {"wrong-target", "wrong-count"}:
                        report[f"{stem}.{variant}.detected"] = detected
                        report[f"{stem}.{variant}.trace_control"] = trace_control
                        passed &= detected and trace_control
        finished = True
    finally:
        report["execution_completed"] = finished
        report["public_calibration_passed"] = passed and finished
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run public M2 trace calibration.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--oracle-amd64", required=True)
    parser.add_argument("--oracle-arm64", required=True)
    parser.add_argument("--observer", required=True)
    args = parser.parse_args()
    for image in (args.oracle_amd64, args.oracle_arm64, args.observer):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            parser.error("Use frozen local image IDs.")
    ok = experiment(
        args.directory, args.output, args.oracle_amd64, args.oracle_arm64, args.observer
    )
    print(f"Public calibration passed: {ok}. Report: {args.output / 'report.json'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
