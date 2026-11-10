import json
import os
import signal
import subprocess
import sys
from base64 import b64encode
from io import StringIO
from pathlib import Path
from typing import BinaryIO
from unittest.mock import MagicMock, Mock

import pytest

from phoenix_eval import worker
from phoenix_eval.case import CaseFailure, FailureKind, Invocation, WorkerRuntime
from phoenix_eval.outcome import Exited, Outcome, Signaled, TreeSnapshot
from phoenix_eval.wire import PROTOCOL_VERSION, decode_result, encode_invocation


@pytest.fixture
def local_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(worker, "SCRATCH", tmp_path)
    monkeypatch.setattr(worker, "NATIVE_RUNTIME", runtime)
    monkeypatch.setattr(worker, "QEMU_RUNTIME", runtime)
    monkeypatch.setattr(worker, "TARGET_UID", os.getuid())
    monkeypatch.setattr(worker, "TARGET_GID", os.getgid())
    return tmp_path


@pytest.mark.parametrize(
    "status, termination", [(143, Exited(143)), (-15, Signaled(15))]
)
def test_worker_preserves_exit_or_signal(
    local_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    termination: Exited | Signaled,
) -> None:
    def launch(
        command: tuple[str, ...],
        *,
        stdin: BinaryIO,
        stdout: BinaryIO,
        stderr: BinaryIO,
        **_: object,
    ) -> MagicMock:
        assert command[0] == "/opt/launch-target"
        assert command[6:] == ("/program", "--", "a b")
        assert stdin.read() == b"\xff"
        stdout.write(b"\x80")
        stderr.write(b"\0")
        process = MagicMock()
        process.__enter__.return_value.wait.return_value = status
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    result = worker.run_case(
        b"ELF",
        Invocation(("--", "a b"), b"\xff"),
        WorkerRuntime.DIRECT,
    )
    assert result == Outcome(b"\x80", b"\0", termination, TreeSnapshot())
    assert list(local_worker.iterdir()) == [local_worker / "runtime"]


@pytest.mark.parametrize(
    "status, side_effect, expected",
    [
        (-signal.SIGXCPU, None, FailureKind.LIMIT),
        (-signal.SIGKILL, None, FailureKind.LIMIT),
        (0, OSError("exec failed"), FailureKind.LAUNCH),
        (0, subprocess.TimeoutExpired("test", 1), FailureKind.TIMEOUT),
    ],
)
def test_worker_does_not_report_infrastructure_failures_as_program_outcomes(
    local_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    side_effect: Exception | None,
    expected: FailureKind,
) -> None:
    monkeypatch.setattr(
        worker, "_launch", Mock(return_value=status, side_effect=side_effect)
    )
    result = worker.run_case(b"ELF", Invocation(), WorkerRuntime.QEMU)
    assert isinstance(result, CaseFailure)
    assert result.kind is expected


def test_worker_rejects_uncollectable_tree(
    local_worker: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def launch(root: Path, *_: object) -> int:
        os.mkfifo(root / "work" / "fifo")
        return 0

    monkeypatch.setattr(worker, "_launch", launch)
    result = worker.run_case(b"ELF", Invocation(), WorkerRuntime.DIRECT)
    assert isinstance(result, CaseFailure)
    assert result.kind is FailureKind.SNAPSHOT


def test_worker_protocol_does_not_put_program_output_on_control_channel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expected = Outcome(b'{"version":123}\n', b"", Exited(0), TreeSnapshot())
    program = b"ELF"
    case = Invocation(("sample",))
    header = {
        "version": PROTOCOL_VERSION,
        "engine": "qemu",
        "binary": b64encode(program).decode(),
    }
    monkeypatch.setattr(
        sys,
        "stdin",
        StringIO(json.dumps(header) + "\n" + encode_invocation(case)),
    )
    mock_run = Mock(return_value=expected)
    monkeypatch.setattr(worker, "run_case", mock_run)
    worker.main()
    assert decode_result(capsys.readouterr().out) == expected
    mock_run.assert_called_once_with(program, case, WorkerRuntime.QEMU, False)
    assert worker.worker_args(WorkerRuntime.QEMU, ("--arg",))[-3:] == (
        "/program",
        "/program",
        "--arg",
    )
