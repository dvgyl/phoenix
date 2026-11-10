import sys
from pathlib import Path

import pytest

from phoenix.__main__ import main


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
