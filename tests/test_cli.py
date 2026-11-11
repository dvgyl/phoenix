import json
import sys
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_provenance import DECOMPILER, PIPELINE_FILE, write_project, write_tools

from phoenix import __main__ as cli
from phoenix.__main__ import main
from phoenix.ingest import BinaryMetadata
from phoenix.pipeline import Method, Reconstruction, Settings
from phoenix_eval.provenance import (
    BuildEvidence,
    lifting_tool_identity,
    pipeline_source_digest,
)


@pytest.mark.parametrize("relative", ("sealed/t0-source.tar.gz", "holdout/cases.jsonl"))
def test_cli_rejects_an_alias_to_a_protected_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative: str,
) -> None:
    artifact = tmp_path / relative
    artifact.parent.mkdir()
    artifact.write_bytes(b"Synthetic protected data.")
    alias = tmp_path / "public.elf"
    alias.symlink_to(artifact)
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", str(alias), "--run-id", "case"])

    assert main() == 2
    assert "Use a permitted input file" in capsys.readouterr().err
    assert not (tmp_path / "runs/case/public/ingest/original.elf").exists()


@pytest.fixture
def saved_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Mock, Mock]:
    checkout = tmp_path / "checkout"
    write_project(checkout)
    ghidra, java = write_tools(tmp_path / "tools")
    binary = tmp_path / "public.elf"
    binary.write_bytes(b"Synthetic input")
    runtime = Mock()
    reconstruct = Mock(return_value=Reconstruction(tmp_path / "out", True))
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(cli, "_PIPELINE_ROOT", checkout)
    monkeypatch.setattr(cli, "pinned_lifting_tools", lambda *_: (ghidra, java))
    monkeypatch.setattr(
        cli, "evaluator_build", lambda _: BuildEvidence("revision", "worker-source")
    )
    monkeypatch.setattr(cli, "verify_runtime", runtime)
    monkeypatch.setattr(cli, "checker_source_digest", lambda _: "checker-source")
    monkeypatch.setattr(
        cli, "freeze_images", lambda _, digest, **_kw: {"amd64": digest}
    )
    monkeypatch.setattr(
        cli,
        "inspect_binary",
        lambda path: BinaryMetadata(sha256(path.read_bytes()).hexdigest(), 0, ()),
    )
    provider = Mock()
    provider.name = "synthetic"
    monkeypatch.setattr(cli, "select_provider", Mock(return_value=provider))
    monkeypatch.setattr(cli, "reconstruct", reconstruct)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "phoenix",
            "run",
            str(binary),
            "--run-id",
            "case",
            "--seed",
            "123",
            "--max-repairs",
            "0",
            "--method",
            "ghidra-raw",
        ],
    )
    assert main() == 0
    record = json.loads((tmp_path / "runs/case/public/run.json").read_text())
    assert record["pipeline_source_sha256"] == pipeline_source_digest(checkout)
    assert record["lifting_tool_identity"] == lifting_tool_identity(ghidra, java)
    assert record["checker_source_sha256"] == "checker-source"
    assert record["checker_images"] == {"amd64": "checker-source"}
    runtime.reset_mock()
    reconstruct.reset_mock()
    return checkout, ghidra, runtime, reconstruct


@pytest.mark.parametrize("command", ("--resume", "--replay"))
@pytest.mark.parametrize(
    ("change", "error"),
    (
        ("source", "recorded pipeline source"),
        ("tool", "recorded lifting tools"),
        ("settings", "recorded seed"),
        ("legacy", "recorded pipeline source"),
        ("input", "saved input binary SHA-256 has changed"),
        ("checker-source", "recorded checker source"),
        ("checker-images", "recorded checker images"),
    ),
)
def test_cli_rejects_changed_checkpoint_before_execution(
    saved_run: tuple[Path, Path, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    change: str,
    error: str,
) -> None:
    checkout, ghidra, runtime, reconstruct = saved_run
    record_path = tmp_path / "runs/case/public/run.json"
    options: list[str] = []
    if change == "source":
        (checkout / PIPELINE_FILE).write_bytes(b"Changed pipeline code")
    elif change == "tool":
        (ghidra / DECOMPILER).write_bytes(b"Changed decompiler")
    elif change == "settings":
        options = ["--seed", "999"]
    elif change == "legacy":
        record = json.loads(record_path.read_text())
        del record["pipeline_source_sha256"]
        del record["lifting_tool_identity"]
        record_path.write_text(json.dumps(record))
    elif change == "input":
        (record_path.parent / "ingest/original.elf").write_bytes(b"Changed input")
    elif change == "checker-source":
        monkeypatch.setattr(cli, "checker_source_digest", lambda _: "different")
    else:
        monkeypatch.setattr(
            cli,
            "freeze_images",
            lambda _, digest, **_kw: (
                {"amd64": f"{digest}-image"}
                if digest == "checker-source"
                else {"amd64": digest}
            ),
        )

    if command == "--replay":
        options += ["--run-id", "replayed"]
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", command, "case", *options])
    original_record = record_path.read_bytes()
    assert main() == 2
    assert error in capsys.readouterr().err
    if change == "checker-images":
        runtime.assert_called_once()
    else:
        runtime.assert_not_called()
    reconstruct.assert_not_called()
    assert record_path.read_bytes() == original_record
    assert not (tmp_path / "runs/replayed/public/run.json").exists()


@pytest.mark.parametrize("command", ("--resume", "--replay"))
def test_cli_uses_saved_settings(
    saved_run: tuple[Path, Path, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _, _, _, reconstruct = saved_run
    source = tmp_path / "runs/case/public/run.json"
    record = source.read_bytes()
    options = ["--run-id", "replayed"] if command == "--replay" else []
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", command, "case", *options])
    assert main() == 0
    reconstruct.assert_called_once()
    settings: Settings = reconstruct.call_args.args[4]
    assert (settings.seed, settings.repair_limit, settings.method) == (
        123,
        0,
        Method.GHIDRA_RAW,
    )
    assert source.read_bytes() == record
    if command == "--replay":
        replay = json.loads((tmp_path / "runs/replayed/public/run.json").read_text())
        original = json.loads(record)
        assert replay["pipeline_source_sha256"] == original["pipeline_source_sha256"]
        assert replay["lifting_tool_identity"] == original["lifting_tool_identity"]
        assert replay["checker_source_sha256"] == original["checker_source_sha256"]
        assert replay["checker_images"] == original["checker_images"]


def test_resume_preserves_replay_lineage_and_read_only_ledger(
    saved_run: tuple[Path, Path, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, reconstruct = saved_run
    monkeypatch.setattr(
        sys, "argv", ["phoenix", "run", "--replay", "case", "--run-id", "replayed"]
    )
    assert main() == 0
    replay = tmp_path / "runs/replayed/public/run.json"
    record = replay.read_bytes()
    original_ledger = tmp_path / "runs/case/llm.jsonl"
    original_ledger.write_bytes(b"Synthetic ledger.")
    reconstruct.reset_mock()
    provider = Mock()
    monkeypatch.setattr(cli, "select_provider", provider)
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", "--resume", "replayed"])
    assert main() == 0
    assert replay.read_bytes() == record
    provider.assert_not_called()
    reconstruct.assert_called_once()
    assert reconstruct.call_args.kwargs["replay"] is True
    assert reconstruct.call_args.args[5].path == original_ledger
    assert original_ledger.read_bytes() == b"Synthetic ledger."
    assert not (tmp_path / "runs/replayed/llm.jsonl").exists()


def test_replay_rejects_a_conflicting_destination_checkpoint(
    saved_run: tuple[Path, Path, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, runtime, reconstruct = saved_run
    monkeypatch.setattr(
        sys, "argv", ["phoenix", "run", "--replay", "case", "--run-id", "replayed"]
    )
    assert main() == 0
    record_path = tmp_path / "runs/replayed/public/run.json"
    record = json.loads(record_path.read_text())
    record["pipeline_source_sha256"] = "different"
    record_path.write_text(json.dumps(record))
    runtime.reset_mock()
    reconstruct.reset_mock()

    assert main() == 2
    assert "replay checkpoint differs" in capsys.readouterr().err
    runtime.assert_not_called()
    reconstruct.assert_not_called()


@pytest.mark.parametrize("command", ("--resume", "--replay"))
def test_cli_rejects_a_changed_checked_switch_setting(
    saved_run: tuple[Path, Path, Mock, Mock],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    _, _, runtime, reconstruct = saved_run
    monkeypatch.setattr(
        sys, "argv", ["phoenix", "run", command, "case", "--checked-switches"]
    )
    assert main() == 2
    assert "recorded checked_switches" in capsys.readouterr().err
    runtime.assert_not_called()
    reconstruct.assert_not_called()


def test_cli_records_and_replays_checked_switch_generation(
    saved_run: tuple[Path, Path, Mock, Mock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, reconstruct = saved_run
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "phoenix",
            "run",
            str(tmp_path / "public.elf"),
            "--run-id",
            "checked",
            "--checked-switches",
            "--max-repairs",
            "0",
        ],
    )
    assert main() == 0
    record = json.loads((tmp_path / "runs/checked/public/run.json").read_text())
    assert record["checked_switches"] is True
    assert reconstruct.call_args.args[4].checked_switches is True
    reconstruct.reset_mock()
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", "--replay", "checked"])
    assert main() == 0
    assert reconstruct.call_args.args[4].checked_switches is True
