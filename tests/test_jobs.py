import fcntl
import json
import multiprocessing
import subprocess
from io import BytesIO
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path

import pytest

from phoenix_eval.jobs import SlotClass, Slots


def _worker(root: str, kind: SlotClass, connection: Connection) -> None:
    slots = Slots(Path(root), 4, 3)
    with slots.acquire(kind):
        connection.send("entered")
        assert connection.recv() == "release"
    connection.send("released")
    connection.close()


def _process(root: Path, kind: SlotClass) -> tuple[BaseProcess, Connection]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_worker, args=(str(root), kind, child))
    process.start()
    child.close()
    return process, parent


@pytest.mark.parametrize("kind", ["compile", "execution", "llm"])
def test_processes_share_slots(tmp_path: Path, kind: SlotClass) -> None:
    slots = Slots(tmp_path, 4, 3)
    workers = [_process(tmp_path, kind) for _ in range(slots.count(kind))]
    extra: tuple[BaseProcess, Connection] | None = None
    try:
        for _, pipe in workers:
            assert pipe.recv() == "entered"
        for path in (tmp_path / kind).glob("*.lock"):
            with path.open() as stream, pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        extra = _process(tmp_path, kind)
        workers[0][1].send("release")
        assert workers[0][1].recv() == "released"
        assert extra[1].recv() == "entered"
        assert len(tuple((tmp_path / kind).glob("*.lock"))) == slots.count(kind)
        for _, pipe in workers[1:]:
            pipe.send("release")
            assert pipe.recv() == "released"
        extra[1].send("release")
        assert extra[1].recv() == "released"
    finally:
        for process, pipe in [*workers, *([extra] if extra is not None else [])]:
            pipe.close()
            process.join(timeout=30)
            if process.is_alive():
                process.kill()
                process.join()
            assert process.exitcode == 0


def test_exception_releases_slot(tmp_path: Path) -> None:
    slots = Slots(tmp_path, 1)
    with pytest.raises(RuntimeError, match="Synthetic"):
        with slots.acquire("compile"):
            raise RuntimeError("Synthetic failure.")
    with (tmp_path / "compile/0.lock").open() as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_process_death_releases_existing_lock_file(tmp_path: Path) -> None:
    process, pipe = _process(tmp_path, "compile")
    try:
        assert pipe.recv() == "entered"
        path = tmp_path / "compile/0.lock"
        inode = path.stat().st_ino
        process.kill()
        process.join(timeout=30)
        with path.open() as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert path.stat().st_ino == inode
    finally:
        pipe.close()
        if process.is_alive():
            process.kill()
        process.join()


def test_budget_defaults_and_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.delenv("PHOENIX_JOBS", raising=False)
    monkeypatch.delenv("PHOENIX_LLM_SLOTS", raising=False)
    monkeypatch.setattr("phoenix_eval.jobs.physical_cores", lambda: 10)
    slots = Slots.from_environment()
    assert slots.root == tmp_path / "slots"
    assert (
        slots.jobs,
        slots.count("compile"),
        slots.count("execution"),
        slots.llm,
    ) == (5, 2, 3, 8)
    monkeypatch.setenv("PHOENIX_JOBS", "1")
    monkeypatch.setenv("PHOENIX_LLM_SLOTS", "2")
    slots = Slots.from_environment()
    assert (slots.count("compile"), slots.count("execution"), slots.llm) == (1, 1, 2)
    monkeypatch.setenv("PHOENIX_JOBS", "0")
    with pytest.raises(ValueError, match="positive"):
        Slots.from_environment()


def _assert_only_slot(root: Path, held: SlotClass) -> None:
    for kind in ("compile", "execution", "llm"):
        path = root / "slots" / kind / "0.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+") as stream:
            if kind == held:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_container_calls_use_separate_slot_classes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phoenix_eval.build import ProjectSnapshot, build_project
    from phoenix_eval.case import Invocation
    from phoenix_eval.docker import Engine, run_batch
    from phoenix_eval.integrity import IntegrityError, inspect_project
    from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
    from phoenix_eval.toolchain import Compiler
    from phoenix_eval.wire import encode_result

    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setenv("PHOENIX_JOBS", "1")
    expected = Outcome(b"", b"", Exited(0), TreeSnapshot())

    def compile(
        command: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        _assert_only_slot(tmp_path, "compile")
        return subprocess.CompletedProcess(
            command, 1, b"", b"Synthetic compiler error."
        )

    monkeypatch.setattr(subprocess, "run", compile)
    project = ProjectSnapshot(
        (("src/program.c", b"int main(void) { return 0; }"),), b"archive"
    )
    assert (
        build_project(
            project, tmp_path / "build", Engine.ARM64, Compiler.GCC
        ).executable
        is None
    )
    with pytest.raises(IntegrityError):
        inspect_project(project, {"amd64": "sha256:" + "a" * 64})

    def execute(
        command: tuple[str, ...], *, stdout: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        from typing import BinaryIO, cast

        _assert_only_slot(tmp_path, "execution")
        cast(BinaryIO, stdout).write((encode_result(expected) + "\n").encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", execute)
    assert run_batch(b"Synthetic program.", (Invocation(),), Engine.ARM64) == (
        expected,
    )


def test_model_calls_use_llm_slots_and_explicit_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from urllib.request import Request as HttpRequest

    from phoenix.llm.codex import CodexProvider
    from phoenix.llm.provider import Request
    from phoenix.llm.responses import ResponsesProvider

    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setenv("PHOENIX_JOBS", "1")
    monkeypatch.setenv("PHOENIX_LLM_SLOTS", "1")
    monkeypatch.setattr("phoenix.llm.codex.platform.system", lambda: "Darwin")
    monkeypatch.setattr("phoenix.llm.codex.inherited_guard", lambda _: True)
    request = Request("Synthetic prompt.", effort="high")

    def codex(
        command: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        _assert_only_slot(tmp_path, "llm")
        assert 'model_reasoning_effort="high"' in command
        events = (
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "answer"},
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "output_tokens": 1,
                },
            },
        )
        return subprocess.CompletedProcess(
            command, 0, "\n".join(json.dumps(event) for event in events)
        )

    monkeypatch.setattr(subprocess, "run", codex)
    assert CodexProvider(tmp_path, tmp_path).complete(request).text == "answer"

    def responses(message: HttpRequest, **_kwargs: object) -> BytesIO:
        _assert_only_slot(tmp_path, "llm")
        assert isinstance(message.data, bytes)
        body = json.loads(message.data)
        assert body["reasoning"] == {"effort": "high"}
        assert body["service_tier"] == "default"
        return BytesIO(
            json.dumps(
                {
                    "status": "completed",
                    "service_tier": "default",
                    "model": request.model,
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "answer"}],
                        }
                    ],
                    "usage": {
                        "input_tokens": 1,
                        "input_tokens_details": {},
                        "output_tokens": 1,
                    },
                }
            ).encode()
        )

    monkeypatch.setattr("phoenix.llm.responses.urlopen", responses)
    assert ResponsesProvider("synthetic-key").complete(request).text == "answer"
