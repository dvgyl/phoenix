import fcntl
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval.docker import Engine
from phoenix_eval.toolchain import Compiler, build_public


def test_toolchain_checks_the_executable_architecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "program.c"
    source.write_text("int main(void) { return 0; }")
    executable = tmp_path / "program.elf"
    elf_header = b"\x7fELF\x02\x01" + b"\0" * 12 + (183).to_bytes(2, "little")
    runner = Mock(
        return_value=subprocess.CompletedProcess(("docker",), 0, elf_header, b"")
    )
    monkeypatch.setattr(subprocess, "run", runner)
    build_public(source, executable, Engine.ARM64, Compiler.GCC)
    assert executable.read_bytes() == elf_header
    with pytest.raises(RuntimeError, match="did not emit ELF"):
        build_public(source, executable, Engine.AMD64, Compiler.GCC)


@pytest.mark.parametrize(
    "engine, mutant", [(Engine.QEMU_X86_64, 0), (Engine.AMD64, -1)]
)
def test_toolchain_rejects_invalid_requests(
    tmp_path: Path, engine: Engine, mutant: int
) -> None:
    with pytest.raises(ValueError):
        build_public(
            tmp_path / "source", tmp_path / "program", engine, Compiler.CLANG, mutant
        )


def _invoke_tool(kind: str, tmp_path: Path) -> object:
    from struct import pack_into

    from phoenix_eval.build import ProjectSnapshot, build_project
    from phoenix_eval.coverage import inspect_x86
    from phoenix_eval.integrity import inspect_project
    from phoenix_eval.quality import register_named_locals

    source = tmp_path / "program.c"
    source.write_bytes(b"int main(void) { return 0; }")
    project = ProjectSnapshot((("src/program.c", source.read_bytes()),), b"archive")
    if kind == "public":
        return build_public(
            source,
            tmp_path / "program",
            Engine.ROSETTA,
            Compiler.CLANG,
            7,
            image="sha256:" + "a" * 64,
        )
    if kind == "build":
        return build_project(
            project,
            tmp_path / "program",
            Engine.ROSETTA,
            Compiler.CLANG,
            image="sha256:" + "a" * 64,
        )
    if kind == "integrity":
        return inspect_project(
            project, {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
        )
    if kind == "quality":
        return register_named_locals(dict(project.files), image="sha256:" + "a" * 64)
    assert kind == "coverage"
    elf = bytearray(120)
    elf[:6] = b"\x7fELF\x02\x01"
    pack_into("<H", elf, 18, 62)
    pack_into("<QQ", elf, 24, 0x1000, 64)
    pack_into("<HH", elf, 54, 56, 1)
    pack_into("<IIQQ", elf, 64, 1, 5, 0, 0x1000)
    return inspect_x86(bytes(elf), image="sha256:" + "a" * 64)


@pytest.mark.parametrize(
    "kind", ["public", "build", "integrity", "quality", "coverage"]
)
def test_tool_container_policy_and_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import json

    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        if kind == "integrity":
            target = "x86_64-linux-gnu" if len(calls) == 1 else "aarch64-linux-gnu"
            output = json.dumps(
                {
                    "schema": 1,
                    "policy": "m1-v1",
                    "status": "complete",
                    "target": target,
                    "translation_unit": "src/program.c",
                    "clang_version": "18.1.3",
                    "record_count": 0,
                    "records": [],
                    "calls": [],
                    "functions": [],
                }
            ).encode()
        else:
            output = {
                "public": b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\0",
                "build": b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\0",
                "quality": b"{}",
                "coverage": b"    1000: ret\n",
            }[kind]
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setenv("DOCKER_HOST", "unix:///synthetic/docker.sock")
    monkeypatch.setattr(subprocess, "run", run)
    _invoke_tool(kind, tmp_path)
    assert len(calls) == (2 if kind == "integrity" else 1)
    for index, (command, kwargs) in enumerate(calls):
        image = "sha256:" + ("b" if index else "a") * 64
        assert command[:4] == (
            "docker",
            "--host",
            "unix:///synthetic/docker.sock",
            "run",
        )
        image_index = command.index(image)
        options = iter(command[4:image_index])
        policy = {}
        for option in options:
            if option in ("--platform", "--name"):
                policy[option] = next(options)
            else:
                key, _, value = option.partition("=")
                policy["--interactive" if key == "-i" else key] = value
        policy.pop("--name", None)
        expected = {
            "--rm": "",
            "--interactive": "",
            "--pull": "never",
            "--network": "none",
            "--read-only": "",
            "--workdir": "/work",
            "--entrypoint": "/bin/sh",
            "--platform": "linux/amd64",
        }
        # Environment options can repeat. Check each value separately below.
        policy.pop("--env", None)
        if kind in ("build", "integrity"):
            expected.update(
                {
                    "--cap-drop": "ALL",
                    "--security-opt": "no-new-privileges",
                    "--user": "19704:19704",
                    "--memory": "1536m" if kind == "build" else "768m",
                    "--memory-swap": "1536m" if kind == "build" else "768m",
                }
            )
        if kind == "quality":
            expected.update(
                {"--cap-drop": "ALL", "--memory": "1536m", "--platform": "linux/arm64"}
            )
        if kind == "integrity" and index:
            expected["--platform"] = "linux/arm64"
        expected["--pids-limit"] = "64" if kind in ("public", "build") else "32"
        expected["--tmpfs"] = {
            "public": "/work:rw,nosuid,nodev,size=128m",
            "build": (
                "/work:rw,exec,nosuid,nodev,size=256m,uid=19704,gid=19704,mode=0700"
            ),
            "integrity": (
                "/work:rw,noexec,nosuid,nodev,size=64m,uid=19704,gid=19704,mode=0700"
            ),
            "quality": "/work:rw,nosuid,nodev,size=64m",
            "coverage": "/work:rw,nosuid,nodev,size=32m",
        }[kind]
        assert policy == expected
        environment = {
            option for option in command[4:image_index] if option.startswith("--env=")
        }
        assert environment == (
            {"--env=TMPDIR=/work", "--env=SOURCE_DATE_EPOCH=1794268800"}
            | ({"--env=HOME=/nonexistent"} if kind != "public" else set())
            if kind in ("public", "build", "integrity")
            else set()
        )
        assert command[image_index + 1] == "-ec"
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is (kind in ("quality", "coverage"))
        assert kwargs["timeout"] == {"public": 120, "build": 180}.get(kind, 60)
        assert isinstance(kwargs["input"], bytes)
        if kind in ("build", "integrity"):
            assert kwargs["input"] == b"archive"
        elif kind == "public":
            assert kwargs["input"] == (tmp_path / "program.c").read_bytes()
            assert command[-3:] == ("build-public", "clang", "-DPHOENIX_MUTANT=7")
        elif kind == "quality":
            assert command[-2:] == ("quality", "src/program.c")


@pytest.mark.parametrize(
    "kind", ["public", "build", "integrity", "quality", "coverage"]
)
@pytest.mark.parametrize("cleanup_error", [None, "os", "timeout", "process"])
@pytest.mark.parametrize("docker_host", [None, "unix:///synthetic/docker.sock"])
def test_timeout_classification_requires_successful_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    cleanup_error: str | None,
    docker_host: str | None,
) -> None:
    from phoenix_eval.build import BuildResult
    from phoenix_eval.integrity import IntegrityError

    failures = {
        "os": OSError("Synthetic cleanup failure."),
        "timeout": subprocess.TimeoutExpired("cleanup", 10),
        "process": subprocess.CalledProcessError(1, "cleanup"),
    }
    commands: list[tuple[str, ...]] = []
    launch_error = subprocess.TimeoutExpired("launch", 60, b"partial", b"diagnostic")
    held = "execution" if kind == "coverage" else "compile"

    def run(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        for slot in ("compile", "execution", "llm"):
            path = tmp_path / "slots" / slot / "0.lock"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a+") as stream:
                if slot == held:
                    with pytest.raises(BlockingIOError):
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if len(commands) == 1:
            raise launch_error
        name = next(
            option.split("=", 1)[1]
            for option in commands[0]
            if option.startswith("--name=")
        )
        docker = ("docker", "--host", docker_host) if docker_host else ("docker",)
        assert command == (*docker, "rm", "-f", name)
        assert kwargs == {"capture_output": True, "timeout": 10, "check": False}
        if cleanup_error:
            raise failures[cleanup_error]
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.delenv("DOCKER_HOST", raising=False)
    if docker_host:
        monkeypatch.setenv("DOCKER_HOST", docker_host)
    monkeypatch.setenv("PHOENIX_JOBS", "1")
    monkeypatch.setattr(subprocess, "run", run)
    if cleanup_error and kind in ("build", "integrity"):
        failure = failures[cleanup_error]
        with pytest.raises(type(failure)) as raised:
            _invoke_tool(kind, tmp_path)
        assert raised.value is failure
    elif kind == "build":
        result = _invoke_tool(kind, tmp_path)
        assert isinstance(result, BuildResult)
        assert result.executable is None
        assert result.warnings == 0
        assert result.diagnostics == "The build exceeded its time limit."
    elif kind == "integrity":
        with pytest.raises(
            IntegrityError, match="exceeded its time limit"
        ) as raised_integrity:
            _invoke_tool(kind, tmp_path)
        assert raised_integrity.value.category == "incomplete_source_check"
    else:
        with pytest.raises(subprocess.TimeoutExpired) as raised_launch:
            _invoke_tool(kind, tmp_path)
        assert raised_launch.value is launch_error
        if cleanup_error:
            assert raised_launch.value.__cause__ is failures[cleanup_error]
    assert len(commands) == 2
    assert not (tmp_path / "program").exists()
    with (tmp_path / "slots" / held / "0.lock").open() as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize(
    "kind", ["public", "build", "integrity", "quality", "coverage"]
)
@pytest.mark.parametrize(
    "failure",
    [
        OSError("Synthetic launch error."),
        subprocess.CalledProcessError(1, "launch", b"output", b"diagnostic"),
    ],
)
def test_non_timeout_errors_propagate_without_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, failure: Exception
) -> None:
    runner = Mock(side_effect=failure)
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(type(failure)) as raised:
        _invoke_tool(kind, tmp_path)
    assert raised.value is failure
    assert runner.call_count == 1
    assert not (tmp_path / "program").exists()
