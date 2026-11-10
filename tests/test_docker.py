import json
import subprocess
from base64 import b64decode
from pathlib import Path
from typing import BinaryIO
from unittest.mock import Mock

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from phoenix_eval.case import Invocation
from phoenix_eval.docker import (
    MAX_BATCH,
    Engine,
    WorkerError,
    freeze_images,
    run_batch,
    run_cases,
)
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.wire import decode_invocation, encode_result
from phoenix_eval.worker import MAX_PROGRAM_BYTES


@given(st.lists(st.text(alphabet=st.characters(exclude_characters="\0"))))
@example(["--privileged", "--cap-add=SETUID", "a b"])
@settings(deadline=None)
def test_target_arguments_go_to_worker_stdin(args: list[str]) -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as root, pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("DOCKER_HOST", raising=False)
        binary = Path(root) / "program"
        binary.write_bytes(b"binary")
        expected = Outcome(b"stdout", b"stderr", Exited(17), TreeSnapshot())

        def fake_docker(
            command: tuple[str, ...],
            *,
            stdin: BinaryIO,
            stdout: BinaryIO,
            stderr: BinaryIO,
            timeout: int,
            check: bool,
        ) -> object:
            assert command[0:2] == ("docker", "run")
            assert command[-1] == "phoenix-worker:arm64"
            assert "--network=none" in command
            assert "--read-only" in command
            assert "--privileged" not in command
            assert "--volume" not in command
            assert b'"engine": "qemu"' in stdin.readline()
            assert decode_invocation(stdin.readline().decode("ascii")).args == tuple(
                args
            )
            assert stdin.readline() == b""
            stdout.write((encode_result(expected) + "\n").encode("ascii"))
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr("phoenix_eval.docker.subprocess.run", fake_docker)
        assert run_batch(
            binary, (Invocation(args=tuple(args)),), Engine.QEMU_X86_64
        ) == (expected,)


@pytest.mark.parametrize("response", [b"", b"bad JSON\n", b"{}\n"])
def test_worker_rejects_incomplete_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: bytes
) -> None:
    binary = tmp_path / "program"
    binary.write_bytes(b"binary")

    def fake_docker(
        command: tuple[str, ...], *, stdout: BinaryIO, **kwargs: object
    ) -> object:
        stdout.write(response)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("phoenix_eval.docker.subprocess.run", fake_docker)
    with pytest.raises(WorkerError, match="invalid result|wrong number"):
        run_batch(binary, (Invocation(),), Engine.AMD64)


def test_worker_image_must_match_checkout_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = "sha256:" + "1" * 64
    result = subprocess.CompletedProcess(("docker",), 0, f"{image} current-source\n")
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: result)
    assert freeze_images((Engine.ROSETTA,), "current-source") == {"amd64": image}
    with pytest.raises(WorkerError, match="Rebuild the amd64"):
        freeze_images((Engine.AMD64,), "different-source")


def test_worker_receives_the_same_bytes_in_each_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = b"synthetic executable\x00\xff"
    expected = Outcome(b"", b"", Exited(0), TreeSnapshot())
    batches = []

    def fake_docker(
        command: tuple[str, ...], *, stdin: BinaryIO, stdout: BinaryIO, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        header = json.loads(stdin.readline())
        assert b64decode(header["binary"]) == program
        cases = tuple(decode_invocation(line.decode("ascii")) for line in stdin)
        batches.append(len(cases))
        stdout.write((encode_result(expected) + "\n").encode("ascii") * len(cases))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_docker)
    cases = (Invocation(),) * (MAX_BATCH + 1)
    assert run_cases(program, cases, Engine.AMD64) == (expected,) * len(cases)
    assert batches == [MAX_BATCH, 1]


@pytest.mark.parametrize("size", [0, MAX_PROGRAM_BYTES + 1])
def test_worker_rejects_invalid_byte_input_size(
    monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    runner = Mock()
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(ValueError, match="Invalid program size"):
        run_batch(bytes(size), (Invocation(),), Engine.AMD64)
    runner.assert_not_called()
