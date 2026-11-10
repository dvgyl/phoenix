"""Run fixed public observer controls inside Linux containers."""

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from experiments.m2_trace.driver import fixed_cases, observe
from experiments.m2_trace.plan import make_plan
from experiments.m2_trace.trace import parse_trace
from phoenix_eval.docker import docker_cli
from phoenix_eval.outcome import Exited, Outcome
from phoenix_eval.wire import decode_result, encode_invocation, encode_result

BASE_TAG = "phoenix-m2-trace:arm64-qemu9.2.0-v1"
HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Control:
    name: str
    before: str
    after: str
    preserves_outcome: bool


CONTROLS = (
    Control(
        "wrong-api",
        "qemu_plugin_version = QEMU_PLUGIN_VERSION;",
        "qemu_plugin_version = QEMU_PLUGIN_VERSION + 1;",
        False,
    ),
    Control("missing-register", '"rdi"', '"phoenix_missing_register"', True),
)


def image_id(tag: str) -> str:
    return subprocess.check_output(
        (*docker_cli(), "image", "inspect", "--format", "{{.Id}}", tag),
        text=True,
        timeout=15,
    ).strip()


def control_image(directory: Path, source: str, base: str, tag: str) -> str:
    directory.mkdir()
    (directory / "control.c").write_text(source)
    command = (
        "gcc-13 -std=c11 -Wall -Wextra -Werror -fPIC -fvisibility=hidden "
        "-shared $(pkg-config --cflags glib-2.0) -I /opt/source -x c "
        "-o /work/control.so - $(pkg-config --libs glib-2.0); "
        "cat /work/control.so"
    )
    compiled = subprocess.run(
        (
            *docker_cli(),
            "run",
            "--rm",
            "--interactive",
            "--pull=never",
            "--platform=linux/arm64",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=512m",
            "--memory-swap=512m",
            "--user=19704:19704",
            "--tmpfs=/work:rw,exec,nosuid,nodev,size=128m,uid=19704,gid=19704,mode=0700",
            "--workdir=/work",
            "--env=TMPDIR=/work",
            "--env=SOURCE_DATE_EPOCH=1794268800",
            "--entrypoint=/bin/sh",
            base,
            "-ec",
            command,
        ),
        input=source.encode(),
        capture_output=True,
        check=False,
        timeout=120,
    )
    (directory / "compile.stderr").write_bytes(compiled.stderr)
    if compiled.returncode or not compiled.stdout.startswith(b"\x7fELF"):
        raise ValueError("The control plugin did not compile.")
    (directory / "control.so").write_bytes(compiled.stdout)
    (directory / "Dockerfile").write_text(
        f"FROM {BASE_TAG}\n"
        "COPY control.so /opt/phoenix-qemu-root/observer.so\n"
        "COPY control.c /opt/source/control.c\n"
    )
    built = subprocess.run(
        (
            *docker_cli(),
            "buildx",
            "build",
            "--load",
            "--platform=linux/arm64",
            "--network=none",
            "-t",
            tag,
            str(directory),
        ),
        capture_output=True,
        check=False,
        timeout=180,
    )
    (directory / "build.log").write_bytes(built.stdout + built.stderr)
    if built.returncode:
        raise ValueError("The control image did not build.")
    if image_id(BASE_TAG) != base:
        raise ValueError("The base observer image changed during the control build.")
    return image_id(tag)


def check_control(
    control: Control, baseline: Outcome, outcome: Outcome, raw: bytes
) -> None:
    if control.preserves_outcome:
        gap = b"G\t0\tregister\n"
        expected = gap + f"END\t1\t{sha256(gap).hexdigest()}\tgap\n".encode()
        if outcome != baseline or raw != expected:
            raise ValueError("The missing-register control did not retain its gap.")
    elif (
        outcome == baseline
        or not isinstance(outcome.termination, Exited)
        or outcome.termination.code != 1
        or outcome.stdout
        or outcome.tree != baseline.tree
        or raw
        or b"plugin requires API version 5, but this QEMU supports only up to version 4"
        not in outcome.stderr
    ):
        raise ValueError("The wrong-API control did not reject the plugin version.")


def experiment(fixtures: Path, reference: Path, output: Path) -> None:
    reference_bytes = reference.read_bytes()
    report = json.loads(reference_bytes)
    base = image_id(BASE_TAG)
    if (
        report.get("public_calibration_passed") is not True
        or report["observer"] != base
    ):
        raise ValueError("Use passing public evidence for the current observer image.")
    source = (HERE / "observer.c").read_bytes()
    retained_source = subprocess.check_output(
        (
            *docker_cli(),
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--platform=linux/arm64",
            "--entrypoint=/bin/cat",
            base,
            "/opt/source/observer.c",
        ),
        timeout=30,
    )
    if retained_source != source:
        raise ValueError("The observer image contains another plugin source.")
    binary = fixtures / "gcc-O0.original"
    data = binary.read_bytes()
    plan, _ = make_plan(binary, Path(str(binary) + ".dis").read_text())
    case = fixed_cases()[1]
    rows = [
        row
        for row in report["cases"]
        if (row["build"], row["variant"], row["case"]) == ("gcc-O0", "original", 1)
    ]
    if len(rows) != 1 or rows[0]["invocation"] != encode_invocation(case):
        raise ValueError("The reference does not contain the fixed control case.")
    baseline = decode_result(rows[0]["left"])
    if (
        not isinstance(baseline, Outcome)
        or baseline != decode_result(rows[0]["right"])
        or report["gcc-O0_binary_sha256"]["original"] != sha256(data).hexdigest()
    ):
        raise ValueError("The control binary or oracle evidence changed.")
    output.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "scope": "public-development-only",
        "observer": base,
        "reference_sha256": sha256(reference_bytes).hexdigest(),
        "binary_sha256": sha256(data).hexdigest(),
        "plan_sha256": plan.sha256,
        "invocation_sha256": sha256(encode_invocation(case).encode()).hexdigest(),
        "controls": results,
        "negative_controls_passed": False,
    }
    try:
        for control in CONTROLS:
            text = source.decode()
            if text.count(control.before) != 1:
                raise ValueError("The control no longer matches the plugin source.")
            modified = text.replace(control.before, control.after)
            directory = output / control.name
            tag = f"phoenix-m2-trace-control:{control.name}-{uuid4().hex}"
            image = control_image(directory, modified, base, tag)
            record: dict[str, object] = {
                **asdict(control),
                "image": image,
                "source_sha256": sha256(modified.encode()).hexdigest(),
                "plugin_sha256": sha256(
                    (directory / "control.so").read_bytes()
                ).hexdigest(),
                "observation_complete": False,
                "control_passed": False,
            }
            results.append(record)
            outcome, raw = observe(data, plan, case, image)
            (directory / "trace.tsv").write_bytes(raw)
            (directory / "outcome.json").write_text(encode_result(outcome) + "\n")
            record.update(
                {
                    "trace_sha256": sha256(raw).hexdigest(),
                    "outcome_sha256": sha256(
                        (directory / "outcome.json").read_bytes()
                    ).hexdigest(),
                    "observation_complete": True,
                }
            )
            try:
                trace = parse_trace(raw, plan)
            except ValueError as error:
                record["trace_rejection"] = str(error)
            else:
                record["trace_status"] = trace.status
                if trace.status == "complete":
                    raise ValueError("A negative control produced a complete trace.")
            check_control(control, baseline, outcome, raw)
            record["control_passed"] = True
        if image_id(BASE_TAG) != base:
            raise ValueError("The accepted observer image changed.")
        summary["negative_controls_passed"] = True
    finally:
        (output / "report.json").write_text(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    experiment(args.fixtures, args.reference, args.output)
    print(args.output / "report.json")


if __name__ == "__main__":
    main()
