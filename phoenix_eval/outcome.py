from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class EntryKind(StrEnum):
    DIRECTORY = "directory"
    FILE = "file"
    SYMLINK = "symlink"


@dataclass(frozen=True)
class TreeEntry:
    path: str
    kind: EntryKind
    mode: int
    data: bytes = b""

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or str(path) != self.path
            or "\0" in self.path
        ):
            raise ValueError("Tree entry paths must be canonical relative paths.")
        if not 0 <= self.mode <= 0o7777:
            raise ValueError("The tree entry mode must contain only permission bits.")
        if self.kind is EntryKind.DIRECTORY and self.data:
            raise ValueError("A directory entry cannot contain bytes.")
        if self.kind is EntryKind.SYMLINK and (not self.data or b"\0" in self.data):
            raise ValueError("The symbolic link target must be a nonempty path.")


@dataclass(frozen=True)
class TreeSnapshot:
    root_mode: int = 0o755
    entries: tuple[TreeEntry, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.root_mode <= 0o7777:
            raise ValueError("The root mode must contain only permission bits.")
        entries = {entry.path: entry for entry in self.entries}
        if len(entries) != len(self.entries):
            raise ValueError("Each path must occur only once.")
        for path in entries:
            parent, separator, _ = path.rpartition("/")
            if separator and (
                parent not in entries or entries[parent].kind is not EntryKind.DIRECTORY
            ):
                raise ValueError("Each parent path must be a directory entry.")
        object.__setattr__(
            self, "entries", tuple(entries[path] for path in sorted(entries))
        )


@dataclass(frozen=True)
class Exited:
    code: int

    def __post_init__(self) -> None:
        if not 0 <= self.code <= 255:
            raise ValueError("A Linux exit code must be in the range 0 to 255.")


@dataclass(frozen=True)
class Signaled:
    number: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 64:
            raise ValueError("A Linux signal number must be in the range 1 to 64.")


@dataclass(frozen=True)
class Outcome:
    stdout: bytes
    stderr: bytes
    termination: Exited | Signaled
    tree: TreeSnapshot


class Difference(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"
    TERMINATION = "termination"
    TREE = "tree"


def compare(original: Outcome, rebuild: Outcome) -> tuple[Difference, ...]:
    differences = []
    if original.stdout != rebuild.stdout:
        differences.append(Difference.STDOUT)
    if original.stderr != rebuild.stderr:
        differences.append(Difference.STDERR)
    if original.termination != rebuild.termination:
        differences.append(Difference.TERMINATION)
    if original.tree != rebuild.tree:
        differences.append(Difference.TREE)
    return tuple(differences)
