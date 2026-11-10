from pathlib import Path
from typing import BinaryIO

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine, WorkerError, run_batch
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.wire import decode_invocation, encode_result


@given(st.lists(st.text(alphabet=st.characters(exclude_characters="\0"))))
@example(["--privileged", "--cap-add=SETUID", "a b"])
@settings(deadline=None)
def test_target_arguments_go_to_worker_stdin(args: list[str]) -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as root, pytest.MonkeyPatch.context() as monkeypatch:
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
            import subprocess

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
    import subprocess

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
