import os
import stat
from pathlib import Path

import pytest

from phoenix_eval.artifacts import atomic_bytes


def test_complete_bytes_replace_the_previous_artifact(tmp_path: Path) -> None:
    path = tmp_path / "nested/record"
    atomic_bytes(path, b"old")
    observed = []
    atomic_bytes(
        path, b"new\x00\xff", before_publish=lambda: observed.append(path.read_bytes())
    )
    assert observed == [b"old"]
    assert path.read_bytes() == b"new\x00\xff"
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize(
    "phase", ["file-sync", "callback", "replace", "directory-sync"]
)
def test_interrupted_publication_keeps_complete_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    path = tmp_path / "record"
    path.write_bytes(b"old")
    sync = os.fsync
    replace = Path.replace

    def interrupted_sync(descriptor: int) -> None:
        directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        if phase == ("directory-sync" if directory else "file-sync"):
            raise OSError("Fixture publication failure.")
        sync(descriptor)

    def interrupted_replace(source: Path, target: str | os.PathLike[str]) -> Path:
        if phase == "replace" and target == path:
            raise OSError("Fixture publication failure.")
        return replace(source, target)

    def callback() -> None:
        if phase == "callback":
            raise ValueError("Fixture publication failure.")

    monkeypatch.setattr(os, "fsync", interrupted_sync)
    monkeypatch.setattr(Path, "replace", interrupted_replace)
    with pytest.raises((OSError, ValueError), match="Fixture publication failure"):
        atomic_bytes(path, b"new", before_publish=callback)
    assert path.read_bytes() == (b"new" if phase == "directory-sync" else b"old")
    assert list(tmp_path.iterdir()) == [path]
