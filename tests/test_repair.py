import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from phoenix.generate import request_candidate
from phoenix.llm.ledger import Ledger, ReplayMissing
from phoenix.llm.provider import Completion, Request, Usage
from phoenix.recover import Program
from phoenix.repair import _output_differences, feedback
from phoenix.verify import BUILD_CONFIGURATIONS, Check, Verification
from phoenix_eval.build import BuildResult
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot


def test_feedback_exposes_difference_positions_and_lengths() -> None:
    original = Outcome(b"prefix-original answer", b"", Exited(0), TreeSnapshot())
    rebuilt = Outcome(b"prefix-other", b"", Exited(0), TreeSnapshot())
    result = _output_differences(original, rebuilt)
    assert "stdout first differs at byte 8" in result
    assert "original has 22 bytes" in result
    assert "rebuild has 12 bytes" in result
    assert "original answer" not in result


class RecordedProvider:
    name = "synthetic-recorded-provider"

    def maximum_usage(self, request: Request) -> Usage:
        raise AssertionError("Token reservations are prohibited during replay.")

    def complete(self, request: Request) -> Completion:
        raise AssertionError("Provider calls are prohibited during replay.")


def failed_build_feedback(diagnostics: str) -> str:
    verification = Verification(
        tuple(
            Check(BuildResult(engine, compiler, None, 0, diagnostics), (), ())
            for engine, compiler in BUILD_CONFIGURATIONS
        ),
        1,
    )
    before = asdict(verification)
    result = feedback(
        Path("unused"), Program(0, 0, 0, 0, (), (), ()), verification, (), (), {}
    )
    assert asdict(verification) == before
    assert all(check.build.diagnostics == diagnostics for check in verification.checks)
    return result


def recorded_ledger(directory: Path, request: Request) -> tuple[Ledger, Completion]:
    body = asdict(request)
    key = hashlib.sha256(
        json.dumps(("synthetic", RecordedProvider.name, body), sort_keys=True).encode(
            "ascii"
        )
    ).hexdigest()
    completion = Completion("Synthetic recorded answer.", Usage(1, 0, 1), request.model)
    started = {
        "attempt": "synthetic-attempt",
        "key": key,
        "binary": "synthetic",
        "provider": RecordedProvider.name,
        "service_tier": "standard",
        "request": body,
        "cost_nanodollars": 12_000,
        "state": "started",
    }
    completed = {**started, "state": "completed", "completion": asdict(completion)}
    ledger = Ledger(directory)
    ledger.path.write_text(
        "\n".join(json.dumps(event) for event in (started, completed)) + "\n"
    )
    return ledger, completion


def build_diagnostics(configuring: str = "1.6", generating: str = "0.0") -> str:
    return (
        f"-- Configuring done ({configuring}s)\n"
        f"-- Generating done ({generating}s)\n"
        "-- Build files have been written to: /work/build\n"
        "/work/src/program.c:1: error: unknown type name 'synthetic_type'\n"
        "/work/src/program.c:2: warning: unused variable 'elapsed_1_6s'\n"
    )


@pytest.mark.parametrize(
    "configuring,generating", [("1.4", "0.0"), ("1.6", "0.2"), ("100.4", "10.25")]
)
@pytest.mark.parametrize("long_log", [False, True])
def test_cmake_times_preserve_feedback_and_exact_recorded_replay(
    tmp_path: Path, configuring: str, generating: str, long_log: bool
) -> None:
    prefix = "p" * 4_100 + "\n" if long_log else ""
    suffix = "x" * 3_650 + "\n" if long_log else ""
    original = failed_build_feedback(prefix + build_diagnostics() + suffix)
    replay = failed_build_feedback(
        prefix + build_diagnostics(configuring, generating) + suffix
    )
    program = Program(0, 0, 0, 0, (), (), ())
    request = request_candidate(program, difference=original, round_number=2)
    replay_request = request_candidate(program, difference=replay, round_number=2)
    ledger, expected = recorded_ledger(tmp_path, request)
    before = ledger.path.read_bytes()
    assert (
        ledger.call("synthetic", request, RecordedProvider(), replay=True) == expected
    )
    assert (
        ledger.call("synthetic", replay_request, RecordedProvider(), replay=True)
        == expected
    )
    assert ledger.path.read_bytes() == before
    assert original == replay
    assert request == replay_request
    stable_diagnostics = (
        prefix + "-- Configuring done\n"
        "-- Generating done\n"
        "-- Build files have been written to: /work/build\n"
        "/work/src/program.c:1: error: unknown type name 'synthetic_type'\n"
        "/work/src/program.c:2: warning: unused variable 'elapsed_1_6s'\n" + suffix
    )
    assert original == "The rosetta gcc build failed.\n" + stable_diagnostics[-4_000:]


def test_compiler_error_changes_still_require_an_exact_recorded_response(
    tmp_path: Path,
) -> None:
    program = Program(0, 0, 0, 0, (), (), ())
    original = failed_build_feedback(build_diagnostics())
    changed = failed_build_feedback(
        build_diagnostics("1.4", "0.2").replace("synthetic_type", "different_type")
    )
    request = request_candidate(program, difference=original, round_number=2)
    changed_request = request_candidate(program, difference=changed, round_number=2)
    ledger, expected = recorded_ledger(tmp_path, request)
    before = ledger.path.read_bytes()
    assert (
        ledger.call("synthetic", request, RecordedProvider(), replay=True) == expected
    )
    assert "error: unknown type name 'different_type'" in changed
    assert changed != original
    with pytest.raises(ReplayMissing, match="no recorded response for this request"):
        ledger.call("synthetic", changed_request, RecordedProvider(), replay=True)
    assert ledger.path.read_bytes() == before


def test_feedback_preserves_other_diagnostic_text_exactly() -> None:
    diagnostics = (
        "/work/src/program.c:1: error: expected token before '(1.6s)'\n"
        "-- Configuring incomplete, errors occurred!\n"
        "-- Configuring done (1.6s) extra\n"
        "-- Generating done (unknowns)\n"
        "CMake Error: -- Generating done (0.0s)\n"
        "-- Building done (0.0s)\n"
        "  -- Configuring done (1.6s)\n"
        "-- Generating done\n"
    )
    assert failed_build_feedback(diagnostics) == (
        "The rosetta gcc build failed.\n" + diagnostics
    )
