from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix_eval.outcome import (
    Difference,
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
    compare,
)


@given(st.binary(), st.binary(), st.integers(0, 255))
def test_compare_accepts_identical_outcomes(
    stdout: bytes, stderr: bytes, code: int
) -> None:
    original = Outcome(stdout, stderr, Exited(code), TreeSnapshot())
    rebuild = Outcome(stdout, stderr, Exited(code), TreeSnapshot())
    assert compare(original, rebuild) == ()


@given(st.binary(), st.binary(), st.binary(), st.binary())
def test_compare_uses_exact_stream_bytes(
    stdout: bytes, stderr: bytes, new_stdout: bytes, new_stderr: bytes
) -> None:
    original = Outcome(stdout, stderr, Exited(0), TreeSnapshot())
    rebuild = replace(original, stdout=new_stdout, stderr=new_stderr)
    differences = compare(original, rebuild)
    assert (Difference.STDOUT in differences) == (stdout != new_stdout)
    assert (Difference.STDERR in differences) == (stderr != new_stderr)


def test_compare_distinguishes_an_exit_code_from_a_signal() -> None:
    original = Outcome(b"", b"", Exited(137), TreeSnapshot())
    rebuild = replace(original, termination=Signaled(9))
    assert compare(original, rebuild) == (Difference.TERMINATION,)


@given(st.binary(), st.integers(0, 0o7777))
def test_compare_accepts_directory_entries_in_any_order(data: bytes, mode: int) -> None:
    parent = TreeEntry("dir", EntryKind.DIRECTORY, 0o755)
    child = TreeEntry("dir/file", EntryKind.FILE, mode, data)
    original = Outcome(b"", b"", Exited(0), TreeSnapshot(entries=(parent, child)))
    rebuild = replace(original, tree=TreeSnapshot(entries=(child, parent)))
    assert compare(original, rebuild) == ()


def test_compare_reports_changes_to_tree_metadata_and_contents() -> None:
    entry = TreeEntry("file", EntryKind.FILE, 0o644, b"data")
    original = Outcome(b"", b"", Exited(0), TreeSnapshot(entries=(entry,)))
    changed_trees = (
        replace(original.tree, root_mode=0o700),
        TreeSnapshot(),
        TreeSnapshot(entries=(replace(entry, data=b"other"),)),
        TreeSnapshot(entries=(replace(entry, mode=0o600),)),
        TreeSnapshot(entries=(replace(entry, kind=EntryKind.SYMLINK),)),
        TreeSnapshot(entries=(replace(entry, path="other"),)),
    )
    for tree in changed_trees:
        assert compare(original, replace(original, tree=tree)) == (Difference.TREE,)


@pytest.mark.parametrize(
    "path", ["", ".", "a/./b", "/a", "a//b", "a/../b", "a/", "a\0b"]
)
def test_tree_entry_rejects_ambiguous_or_escaping_paths(path: str) -> None:
    with pytest.raises(ValueError, match="canonical relative"):
        TreeEntry(path, EntryKind.FILE, 0o644)


def test_tree_requires_unique_paths_and_directory_parents() -> None:
    entry = TreeEntry("file", EntryKind.FILE, 0o644)
    with pytest.raises(ValueError, match="only once"):
        TreeSnapshot(entries=(entry, entry))
    with pytest.raises(ValueError, match="parent path"):
        TreeSnapshot(entries=(entry, replace(entry, path="file/child")))
