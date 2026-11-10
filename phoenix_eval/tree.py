import os
import stat
from pathlib import Path

from phoenix_eval.outcome import EntryKind, TreeEntry, TreeSnapshot

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 4096


def populate(work: Path, tree: TreeSnapshot, uid: int, gid: int) -> None:
    if (
        len(tree.entries) > MAX_ENTRIES
        or sum(len(item.data) for item in tree.entries) > MAX_FILE_BYTES
    ):
        raise ValueError("The input tree exceeds the sandbox limits.")

    work.mkdir()
    directories = [(work, tree.root_mode)]
    for item in tree.entries:
        path = work / item.path
        if item.kind is EntryKind.DIRECTORY:
            path.mkdir()
            directories.append((path, item.mode))
        elif item.kind is EntryKind.SYMLINK:
            if item.mode != 0o777:
                raise ValueError("A Linux symbolic link must have mode 0777.")
            path.symlink_to(os.fsdecode(item.data))
            os.chown(path, uid, gid, follow_symlinks=False)
        else:
            path.write_bytes(item.data)
            os.chown(path, uid, gid)
            path.chmod(item.mode)

    for path, mode in reversed(directories):
        os.chown(path, uid, gid)
        path.chmod(mode)


def snapshot(work: Path) -> TreeSnapshot:
    entries: list[TreeEntry] = []
    directories = [work]
    remaining = MAX_FILE_BYTES
    while directories:
        directory = directories.pop()
        with os.scandir(directory) as children:
            for child in children:
                if len(entries) == MAX_ENTRIES:
                    raise ValueError("The output tree contains too many entries.")
                path = Path(child.path)
                mode = child.stat(follow_symlinks=False).st_mode
                data = b""
                if stat.S_ISDIR(mode):
                    kind = EntryKind.DIRECTORY
                    directories.append(path)
                elif stat.S_ISLNK(mode):
                    kind = EntryKind.SYMLINK
                    data = os.fsencode(os.readlink(path))
                elif stat.S_ISREG(mode):
                    kind = EntryKind.FILE
                    with path.open("rb") as file:
                        data = file.read(remaining + 1)
                else:
                    raise ValueError(
                        "The output tree contains an unsupported file type."
                    )
                remaining -= len(data)
                if remaining < 0:
                    raise ValueError("The output tree exceeds the byte limit.")
                entries.append(
                    TreeEntry(
                        path.relative_to(work).as_posix(),
                        kind,
                        stat.S_IMODE(mode),
                        data,
                    )
                )

    return TreeSnapshot(stat.S_IMODE(work.stat().st_mode), tuple(entries))
