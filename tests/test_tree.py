import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from phoenix_eval import tree
from phoenix_eval.outcome import EntryKind, TreeEntry, TreeSnapshot


@pytest.fixture(autouse=True)
def allow_all_modes() -> Iterator[None]:
    mask = os.umask(0)
    try:
        yield
    finally:
        os.umask(mask)


def test_populate_and_snapshot_preserve_tree(tmp_path: Path) -> None:
    expected = TreeSnapshot(
        0o750,
        (
            TreeEntry("folder", EntryKind.DIRECTORY, 0o755),
            TreeEntry("folder/empty", EntryKind.DIRECTORY, 0o700),
            TreeEntry("folder/file", EntryKind.FILE, 0o640, b"data\xff"),
            TreeEntry("link", EntryKind.SYMLINK, 0o777, b"folder/file"),
        ),
    )
    work = tmp_path / "work"
    tree.populate(work, expected, os.getuid(), os.getgid())
    assert tree.snapshot(work) == expected


def test_snapshot_keeps_symlinks_without_reading_their_targets(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_text("Outside the working directory.")
    work = tmp_path / "work"
    work.mkdir(mode=0o755)
    (work / "link").symlink_to("../outside")
    assert tree.snapshot(work) == TreeSnapshot(
        entries=(TreeEntry("link", EntryKind.SYMLINK, 0o777, b"../outside"),)
    )


def test_snapshot_rejects_special_files(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "fifo")
    with pytest.raises(ValueError, match="unsupported file"):
        tree.snapshot(tmp_path)


def test_snapshot_rejects_excess_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "file").write_bytes(b"AB")
    monkeypatch.setattr(tree, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        tree.snapshot(tmp_path)


def test_snapshot_rejects_excess_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "file").touch()
    monkeypatch.setattr(tree, "MAX_ENTRIES", 0)
    with pytest.raises(ValueError, match="too many entries"):
        tree.snapshot(tmp_path)


def test_populate_rejects_excess_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tree, "MAX_ENTRIES", 0)
    with pytest.raises(ValueError, match="sandbox limits"):
        tree.populate(
            tmp_path / "work",
            TreeSnapshot(entries=(TreeEntry("file", EntryKind.FILE, 0o644),)),
            os.getuid(),
            os.getgid(),
        )


def test_populate_rejects_unsupported_link_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="symbolic link"):
        tree.populate(
            tmp_path / "work",
            TreeSnapshot(
                entries=(TreeEntry("link", EntryKind.SYMLINK, 0o700, b"file"),)
            ),
            os.getuid(),
            os.getgid(),
        )
