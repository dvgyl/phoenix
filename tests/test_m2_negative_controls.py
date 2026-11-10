import json
import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.m2_trace import negative_controls
from experiments.m2_trace.negative_controls import CONTROLS, check_control
from experiments.m2_trace.trace import Plan
from phoenix_eval.case import Invocation
from phoenix_eval.outcome import Exited, Outcome, Signaled, TreeSnapshot
from phoenix_eval.wire import encode_invocation, encode_result

BASELINE = Outcome(b"transformed", b"", Exited(0), TreeSnapshot())
API_FAILURE = Outcome(
    b"",
    b"qemu-x86_64: Could not load plugin /observer.so: plugin requires API "
    b"version 5, but this QEMU supports only up to version 4\n",
    Exited(1),
    TreeSnapshot(),
)
GAP = b"G\t0\tregister\n"
REGISTER_FAILURE = GAP + f"END\t1\t{sha256(GAP).hexdigest()}\tgap\n".encode()


def test_fixed_controls_accept_their_expected_linux_outcomes() -> None:
    check_control(CONTROLS[0], BASELINE, API_FAILURE, b"")
    check_control(CONTROLS[1], BASELINE, BASELINE, REGISTER_FAILURE)


@pytest.mark.parametrize(
    "outcome,raw",
    [
        (BASELINE, b""),
        (replace(API_FAILURE, stderr=b"plugin: GLIBC version not found"), b""),
        (replace(API_FAILURE, stdout=b"target executed"), b""),
        (replace(API_FAILURE, tree=TreeSnapshot(0o700)), b""),
        (replace(API_FAILURE, termination=Exited(0)), b""),
        (replace(API_FAILURE, termination=Exited(2)), b""),
        (replace(API_FAILURE, termination=Signaled(11)), b""),
        (API_FAILURE, b"partial trace"),
    ],
)
def test_wrong_api_requires_the_version_rejection_before_target_execution(
    outcome: Outcome, raw: bytes
) -> None:
    with pytest.raises(ValueError, match="wrong-API control"):
        check_control(CONTROLS[0], BASELINE, outcome, raw)


@pytest.mark.parametrize(
    "outcome,raw",
    [
        (replace(BASELINE, stdout=b"different"), REGISTER_FAILURE),
        (replace(BASELINE, stderr=b"different"), REGISTER_FAILURE),
        (replace(BASELINE, termination=Exited(1)), REGISTER_FAILURE),
        (replace(BASELINE, tree=TreeSnapshot(0o700)), REGISTER_FAILURE),
        (BASELINE, b""),
        (BASELINE, REGISTER_FAILURE[:-1]),
        (BASELINE, REGISTER_FAILURE.replace(b"END\t1", b"END\t2")),
        (BASELINE, REGISTER_FAILURE.replace(b"register", b"memory")),
        (BASELINE, REGISTER_FAILURE.replace(b"gap\n", b"complete\n")),
    ],
)
def test_missing_register_requires_the_original_outcome_and_exact_gap(
    outcome: Outcome, raw: bytes
) -> None:
    with pytest.raises(ValueError, match="missing-register control"):
        check_control(CONTROLS[1], BASELINE, outcome, raw)


def test_failed_control_retains_bound_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    binary = b"opaque synthetic fixture"
    (fixtures / "gcc-O0.original").write_bytes(binary)
    (fixtures / "gcc-O0.original.dis").write_text("synthetic disassembly")
    source = (negative_controls.HERE / "observer.c").read_bytes()
    base = "sha256:" + "a" * 64
    control_image = "sha256:" + "b" * 64
    case = Invocation(("inc",), b"\0")
    plan = Plan(sha256(binary).hexdigest(), b"synthetic plan\n", (), ())
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "public_calibration_passed": True,
                "observer": base,
                "gcc-O0_binary_sha256": {"original": sha256(binary).hexdigest()},
                "cases": [
                    {
                        "build": "gcc-O0",
                        "variant": "original",
                        "case": 1,
                        "invocation": encode_invocation(case),
                        "left": encode_result(BASELINE),
                        "right": encode_result(BASELINE),
                    }
                ],
            }
        )
    )

    def compile_control(directory: Path, text: str, _base: str, _tag: str) -> str:
        directory.mkdir()
        (directory / "control.c").write_text(text)
        (directory / "control.so").write_bytes(b"opaque synthetic plugin")
        return control_image

    def image_source(*_args: object, **_kwargs: object) -> bytes:
        return source

    monkeypatch.setattr(negative_controls, "image_id", lambda _: base)
    monkeypatch.setattr(negative_controls, "control_image", compile_control)
    monkeypatch.setattr(subprocess, "check_output", image_source)
    monkeypatch.setattr(negative_controls, "fixed_cases", lambda: (Invocation(), case))
    monkeypatch.setattr(negative_controls, "make_plan", lambda *_: (plan, {}))
    monkeypatch.setattr(
        negative_controls, "observe", lambda *_: (BASELINE, b"diagnostic trace")
    )
    output = tmp_path / "controls"
    with pytest.raises(ValueError, match="wrong-API control"):
        negative_controls.experiment(fixtures, reference, output)
    report = json.loads((output / "report.json").read_text())
    assert report["negative_controls_passed"] is False
    assert len(report["controls"]) == 1
    record = report["controls"][0]
    directory = output / "wrong-api"
    assert record["image"] == control_image
    for field, name in (
        ("source_sha256", "control.c"),
        ("plugin_sha256", "control.so"),
        ("trace_sha256", "trace.tsv"),
        ("outcome_sha256", "outcome.json"),
    ):
        assert record[field] == sha256((directory / name).read_bytes()).hexdigest()
    assert record["observation_complete"] is True
    assert record["control_passed"] is False
