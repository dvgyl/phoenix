import json
import subprocess
from hashlib import sha256
from pathlib import Path
from time import time
from unittest.mock import Mock

import pytest

from phoenix import pipeline, verify
from phoenix.__main__ import _RecordedProvider
from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.ingest import BinaryMetadata
from phoenix.llm.ledger import Budget, Ledger
from phoenix.llm.provider import Completion, Model, Usage
from phoenix.recover import Function, Program
from phoenix_eval import integrity
from phoenix_eval.build import BuildResult, ProjectSnapshot
from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine
from phoenix_eval.elf import Section
from phoenix_eval.integrity import IntegrityError
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.toolchain import Compiler
from phoenix_eval.trace import CodeTrace

_TEXT = b"Private original instruction bytes used only by this synthetic test."
_OUTPUT = b"Fixture output bytes appear only in this development stream.\n"
_BAD_BODY = 'puts("Fixture output bytes " "appear only in this development stream.");'
_INPUT = "private development argument"
_SOURCE = "src/program.c"


@pytest.mark.parametrize(
    ("failure", "repairs"),
    (("policy", 1), ("compiler", 1), ("policy", 0), ("malformed", 1), ("missing", 1)),
)
def test_development_integrity_gates_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, repairs: int
) -> None:
    binary = tmp_path / "original.elf"
    binary.write_bytes(b"synthetic original")
    metadata = BinaryMetadata(sha256(binary.read_bytes()).hexdigest(), 0, ())
    outcome = Outcome(_OUTPUT, b"", Exited(0), TreeSnapshot(), CodeTrace(0, 1, (0,)))
    analysis = Analysis(
        (DevelopmentCase(Invocation((_INPUT,)), outcome),), 1, 1, 1, 0, 0
    )
    program = Program(
        0,
        0,
        0,
        0,
        (Function(0, "main", "main", ((0, 1),), "return 0;", "int main(void)"),),
        (),
        (),
    )
    monkeypatch.setattr(pipeline, "analyze", lambda *_: analysis)
    monkeypatch.setattr(pipeline, "lift_binary", lambda *_: None)
    monkeypatch.setattr(pipeline, "recover", lambda *_: program)
    monkeypatch.setattr(pipeline, "reached_functions", lambda *_: frozenset({0}))
    monkeypatch.setattr(
        integrity, "elf_sections", lambda *_: {".text": Section(0, _TEXT)}
    )
    snapshots: dict[bytes, bytes] = {}

    def build(
        project: ProjectSnapshot,
        destination: Path,
        engine: Engine,
        compiler: Compiler,
        *,
        image: str,
    ) -> BuildResult:
        source = dict(project.files)[_SOURCE]
        snapshots[project.archive] = source
        destination.parent.mkdir(parents=True, exist_ok=True)
        program_bytes = (
            _TEXT
            if _BAD_BODY.encode() in source and engine is Engine.ROSETTA
            else b"synthetic rebuilt executable"
        )
        destination.write_bytes(program_bytes)
        return BuildResult(engine, compiler, destination, 0, "")

    def run_cases(binary: bytes, *_: object, image: str) -> tuple[Outcome, ...]:
        assert binary in (_TEXT, b"synthetic rebuilt executable")
        return (outcome,)

    def checker(
        command: tuple[str, ...], *, input: bytes, **_: object
    ) -> subprocess.CompletedProcess[bytes]:
        source = snapshots[input]
        target = command[-6].removeprefix("--target=")
        assert target in ("x86_64-linux-gnu", "aarch64-linux-gnu")
        rejected = _BAD_BODY.encode() in source
        if rejected and failure == "missing":
            raise FileNotFoundError("Missing synthetic checker")
        if rejected and failure == "malformed":
            return subprocess.CompletedProcess(command, 0, b"invalid evidence")
        if rejected and failure == "compiler":
            rejection = {
                "status": "unchecked",
                "error": {"category": "compiler_error", "message": _OUTPUT.decode()},
            }
            return subprocess.CompletedProcess(
                command, 1, json.dumps(rejection).encode()
            )
        records = (
            [
                {
                    "kind": "constant_output",
                    "file": _SOURCE,
                    "offset": source.index(b"puts"),
                    "bytes_hex": _OUTPUT.hex(),
                }
            ]
            if rejected
            else []
        )
        output = {
            "schema": 1,
            "policy": "m1-v1",
            "status": "complete",
            "target": target,
            "translation_unit": _SOURCE,
            "clang_version": "18.1.3",
            "record_count": len(records),
            "records": records,
            "calls": [],
            "functions": [{"name": "main", "branches": 0, "loops": 0, "switches": 0}],
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(output).encode())

    monkeypatch.setattr(verify, "build_project", build)
    monkeypatch.setattr(verify, "run_cases", run_cases)
    monkeypatch.setattr(subprocess, "run", checker)
    usage = Usage(1, 0, 1)
    provider = Mock()
    provider.name = "synthetic"
    provider.maximum_usage.return_value = usage
    provider.complete.side_effect = [
        Completion(
            json.dumps(
                {
                    "declarations": "#include <stdio.h>",
                    "functions": {
                        "0x0": {
                            "signature": "int main(void)",
                            "body": body,
                            "evidence": "Synthetic fixture.",
                        }
                    },
                }
            ),
            usage,
            Model.SOL,
        )
        for body in (f"{_BAD_BODY}\nreturn 0;", "return 0;")
    ]
    settings = pipeline.Settings(
        {"amd64": "worker-x86", "arm64": "worker-arm"},
        0,
        tmp_path,
        tmp_path,
        repairs,
        False,
        {"amd64": f"sha256:{'a' * 64}", "arm64": f"sha256:{'b' * 64}"},
    )
    run = tmp_path / "original"
    ledger = Ledger(run, Budget(1_000_000, 1_000_000))
    args = ("fixture", binary, metadata, settings, ledger)
    if failure in {"malformed", "missing"}:
        with pytest.raises(IntegrityError):
            pipeline.reconstruct(run, *args, provider, started=time())
        assert provider.complete.call_count == 1
        return

    result = pipeline.reconstruct(run, *args, provider, started=time())
    report = json.loads((result.project / "phoenix_report.json").read_text())
    source = (result.project / _SOURCE).read_text()
    assert report["development_behavior_passed"] is True
    assert report["development_integrity"]["checked_executables"] == 4
    assert result.development_passed is bool(repairs)
    assert provider.complete.call_count == 1 + repairs
    if not repairs:
        assert _BAD_BODY in source
        assert report["stop"] == "repair-limit"
        assert report["development_integrity"]["passed"] is False
        assert report["development_integrity"]["categories"] == {
            "embedded_text": 2,
            "memorized_output": 2,
        }
        return

    assert _BAD_BODY not in source
    assert report["stop"] == "development-passed"
    assert report["development_integrity"]["passed"] is True
    prompt = provider.complete.call_args.args[0].prompt
    category = "compiler_error 1" if failure == "compiler" else "memorized_output 2"
    assert category in prompt
    assert "embedded_text 2" in prompt
    assert _OUTPUT.decode().strip() not in prompt
    assert _OUTPUT.hex() not in prompt
    assert _TEXT.decode() not in prompt
    assert _INPUT not in prompt

    recorded = ledger.path.read_bytes()
    replayed = pipeline.reconstruct(
        tmp_path / "replayed",
        *args,
        _RecordedProvider(provider.name),
        started=time(),
        replay=True,
    )
    assert replayed.development_passed
    assert (replayed.project / _SOURCE).read_text() == source
    assert ledger.path.read_bytes() == recorded
    resumed = pipeline.reconstruct(run, *args, provider, started=time())
    assert resumed.development_passed
    assert ledger.path.read_bytes() == recorded
    assert provider.complete.call_count == 2

    executable = next((run / "fixture/build/round-00").glob("*.elf"))
    executable.write_bytes(b"Changed executable")
    with pytest.raises(ValueError, match="The tested executable has changed"):
        pipeline.reconstruct(run, *args, provider, started=time())
    assert ledger.path.read_bytes() == recorded
