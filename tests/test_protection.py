import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

from phoenix_eval.protection import (
    GUARD_ENV,
    GUARD_PROBE,
    guarded_command,
    inherited_guard,
)


def test_guard_claim_requires_a_denied_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(GUARD_ENV, raising=False)
    assert not inherited_guard(tmp_path)
    marker = tmp_path / "runs" / GUARD_PROBE
    marker.parent.mkdir()
    marker.touch()
    monkeypatch.setenv(GUARD_ENV, str(marker))
    with pytest.raises(ValueError, match="did not deny"):
        inherited_guard(tmp_path)


@pytest.mark.skipif(platform.system() != "Darwin", reason="The guard uses macOS.")
def test_guard_blocks_protected_reads_in_the_child(tmp_path: Path) -> None:
    for relative in ("sealed/src/file", "sealed/release/file", "holdout/file"):
        file = tmp_path / relative
        file.parent.mkdir(parents=True)
        file.write_bytes(b"Public synthetic fixture.")
    marker = tmp_path / "runs" / GUARD_PROBE
    marker.parent.mkdir()
    marker.touch()
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "holdout/file")
    check = """
import sys
from pathlib import Path
from phoenix_eval.protection import inherited_guard

root = Path(sys.argv[1])
assert inherited_guard(root)
assert (root / 'sealed/release/file').read_bytes() == b'Public synthetic fixture.'
for relative in ('sealed/src/file', 'holdout/file', 'alias'):
    try:
        (root / relative).read_bytes()
    except PermissionError:
        continue
    raise AssertionError(relative)
"""
    command = guarded_command(
        tmp_path,
        (sys.executable, "-c", check, str(tmp_path)),
        release=True,
        probe=marker,
    )
    subprocess.run(command, env={**os.environ, GUARD_ENV: str(marker)}, check=True)
