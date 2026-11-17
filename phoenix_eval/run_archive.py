"""Archive development records and their declared run dependencies.

Only stopped or complete evaluation records can be archived. Callers must stop
all writers before archiving and use runs/.archive.lock during resume. Archives
are immutable. A changed existing dependency, including an appended ledger,
causes restore to fail. Restore never truncates or replaces that dependency.
Only the selected evaluation root is removed. Dependency roots stay in place.
File bytes, permission bits and nanosecond modification times are preserved.
Ownership and access times are not part of the archive contract.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO


@dataclass(frozen=True)
class ArchiveEntry:
    """Describe one directory or regular file relative to runs/."""

    path: str
    kind: str
    mode: int
    mtime_ns: int
    size: int
    sha256: str


def _run_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is None
        or "sealed" in value.lower()
        or "holdout" in value.lower()
        or value.lower().startswith("m1-t0-")
    ):
        raise ValueError("Invalid or protected development run ID.")
    return value


def _relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("Invalid archive path.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise ValueError("Invalid archive path.")
    _run_id(parts[0])
    if any(
        "sealed" in part.lower()
        or "holdout" in part.lower()
        or part.lower().startswith("m1-t0-")
        for part in parts
    ):
        raise ValueError("Protected archive path.")
    return value


def _plain(path: Path, *, directory: bool = False) -> os.stat_result:
    if any(
        "sealed" in part.lower()
        or "holdout" in part.lower()
        or part.lower().startswith("m1-t0-")
        for part in path.parts
    ):
        raise ValueError("Protected input path.")
    info = path.lstat()
    if directory:
        valid = stat.S_ISDIR(info.st_mode)
    else:
        valid = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not valid:
        raise ValueError(f"Unsafe file type or hardlink: {path}")
    if stat.S_IMODE(info.st_mode) & ~0o777:
        raise ValueError(f"Unsupported permission bits: {path}")
    return info


def _runs(workspace: Path) -> Path:
    if not workspace.is_absolute() or ".." in workspace.parts:
        raise ValueError("The workspace must be an absolute path without traversal.")
    for path in reversed((workspace, *workspace.parents)):
        if (
            "sealed" in path.name.lower()
            or "holdout" in path.name.lower()
            or path.name.lower().startswith("m1-t0-")
        ):
            raise ValueError("Protected workspace path.")
        _plain(path, directory=True)
    runs = workspace / "runs"
    _plain(runs, directory=True)
    return runs


@contextmanager
def _lock(runs: Path) -> Iterator[None]:
    descriptor = os.open(
        runs / ".archive.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Unsafe archive lock.")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _json(data: bytes) -> dict[str, object]:
    value: object = json.loads(data, object_pairs_hook=_object)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object.")
    return value


@contextmanager
def _open(path: Path) -> Iterator[BinaryIO]:
    for parent in reversed(path.parents):
        _plain(parent, directory=True)
    _plain(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & ~0o777
        ):
            raise ValueError("Unsafe input file.")
        yield stream


def _read(path: Path) -> bytes:
    with _open(path) as stream:
        return stream.read()


def _digest(path: Path) -> str:
    with _open(path) as stream:
        return _stream_hash(stream)


def _stream_hash(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".archive-write-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _sync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _index(runs: Path) -> dict[str, object]:
    path = runs / "archive-index.json"
    if not path.exists() and not path.is_symlink():
        return {}
    document = _json(_read(path))
    if set(document) != {"version", "archives"} or type(document["version"]) is not int:
        raise ValueError("Invalid archive index.")
    archives = document["archives"]
    if document["version"] != 1 or not isinstance(archives, dict):
        raise ValueError("Invalid archive index.")
    for key, record in archives.items():
        _run_id(key)
        if not isinstance(record, dict) or set(record) != {"sha256", "roots"}:
            raise ValueError("Invalid archive index entry.")
        _hash(record["sha256"])
        _roots(record["roots"], key)
    return archives


def _hash(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid SHA-256.")
    return value


def _roots(value: object, run_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("Invalid dependency roots.")
    roots = tuple(_run_id(item) for item in value)
    if roots != tuple(sorted(set(roots))) or run_id not in roots:
        raise ValueError("Invalid dependency roots.")
    return roots


def _dependencies(
    runs: Path, run_id: str, *, required: bool = False
) -> tuple[str, ...]:
    root = runs / _run_id(run_id)
    _plain(root, directory=True)
    plan = root / "plan.json"
    if not plan.exists() and not plan.is_symlink() and not required:
        return ()
    document = _json(_read(plan))
    if document.get("corpus", "corpus_dev") != "corpus_dev":
        raise ValueError("Only development records can be archived.")
    dependencies = document.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError(f"Missing or invalid dependencies: {run_id}")
    return tuple(_run_id(item) for item in dependencies)


def _closure(runs: Path, run_id: str) -> tuple[str, ...]:
    pending = [run_id]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(_edges(runs, current, required=current == run_id))
    return tuple(sorted(seen))


def _edges(runs: Path, run_id: str, *, required: bool = False) -> tuple[str, ...]:
    pipeline = runs / f"{run_id}-p"
    implicit = (
        (_run_id(pipeline.name),) if pipeline.exists() or pipeline.is_symlink() else ()
    )
    return (*_dependencies(runs, run_id, required=required), *implicit)


def _terminal(runs: Path, run_id: str) -> None:
    root = runs / run_id
    _plain(root, directory=True)
    if any(
        (root / marker).exists() or (root / marker).is_symlink()
        for marker in (".active", "active", "active.json", ".running")
    ):
        raise ValueError(f"The run is active: {run_id}")
    document = _json(_read(root / "scoreboard.json"))
    if document.get("corpus", "corpus_dev") != "corpus_dev":
        raise ValueError("Only development records can be archived.")
    state = document.get("run_state")
    if not isinstance(state, str) or state not in {"complete", "completed", "stopped"}:
        raise ValueError(f"The run is active or its state is unknown: {run_id}")


def _inventory(base: Path, roots: tuple[str, ...]) -> tuple[ArchiveEntry, ...]:
    entries: list[ArchiveEntry] = []

    def visit(path: Path) -> None:
        relative = _relative(path.relative_to(base).as_posix())
        info = path.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        _plain(path, directory=directory)
        entries.append(
            ArchiveEntry(
                relative,
                "dir" if directory else "file",
                stat.S_IMODE(info.st_mode),
                info.st_mtime_ns,
                0 if directory else info.st_size,
                "" if directory else _digest(path),
            )
        )
        if directory:
            for child in sorted(path.iterdir()):
                visit(child)

    for root in roots:
        _plain(base / root, directory=True)
        visit(base / root)
    return tuple(sorted(entries, key=lambda entry: entry.path))


def _manifest(
    data: bytes, run_id: str
) -> tuple[tuple[str, ...], tuple[ArchiveEntry, ...]]:
    document = _json(data)
    if set(document) != {"version", "run_id", "roots", "entries"}:
        raise ValueError("Invalid archive manifest.")
    if (
        type(document["version"]) is not int
        or document["version"] != 1
        or document["run_id"] != run_id
    ):
        raise ValueError("Invalid archive identity.")
    roots = _roots(document["roots"], run_id)
    raw = document["entries"]
    if not isinstance(raw, list):
        raise ValueError("Invalid archive entries.")
    entries: dict[str, ArchiveEntry] = {}
    fields = {"path", "kind", "mode", "mtime_ns", "size", "sha256"}
    for item in raw:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Invalid archive entry.")
        path = _relative(item["path"])
        kind = item["kind"]
        mode, mtime, size = (item[name] for name in ("mode", "mtime_ns", "size"))
        if (
            not isinstance(kind, str)
            or kind not in {"dir", "file"}
            or type(mode) is not int
            or not 0 <= mode <= 0o777
            or type(mtime) is not int
            or mtime < 0
            or type(size) is not int
            or size < 0
        ):
            raise ValueError("Invalid archive entry metadata.")
        digest = _hash(item["sha256"]) if kind == "file" else ""
        if kind == "dir" and (size != 0 or item["sha256"] != ""):
            raise ValueError("Invalid directory metadata.")
        if path in entries or path.split("/")[0] not in roots:
            raise ValueError("Duplicate or undeclared archive destination.")
        entries[path] = ArchiveEntry(path, kind, mode, mtime, size, digest)
    for root in roots:
        if root not in entries or entries[root].kind != "dir":
            raise ValueError("Missing archive root.")
    for path in entries:
        parent = str(PurePosixPath(path).parent)
        if parent != "." and (parent not in entries or entries[parent].kind != "dir"):
            raise ValueError("Missing archive parent directory.")
    return roots, tuple(entries[path] for path in sorted(entries))


def _extract(
    archive: Path, destination: Path, run_id: str, expected_hash: str
) -> tuple[tuple[str, ...], tuple[ArchiveEntry, ...]]:
    with _open(archive) as archive_bytes:
        if _stream_hash(archive_bytes) != expected_hash:
            raise ValueError("Archive SHA-256 mismatch.")
        archive_bytes.seek(0)
        result = _extract_stream(archive_bytes, destination, run_id)
        archive_bytes.seek(0)
        if _stream_hash(archive_bytes) != expected_hash:
            raise ValueError("The archive changed during extraction.")
        return result


def _extract_stream(
    archive_bytes: BinaryIO, destination: Path, run_id: str
) -> tuple[tuple[str, ...], tuple[ArchiveEntry, ...]]:
    with tarfile.open(fileobj=archive_bytes, mode="r:gz") as stream:
        members = stream.getmembers()
        names: dict[str, tarfile.TarInfo] = {}
        for member in members:
            if (
                member.name in names
                or member.type
                not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}
                or member.sparse is not None
            ):
                raise ValueError("Duplicate or unsafe archive member.")
            if (
                member.linkname
                or member.mode & ~0o777
                or member.pax_headers.keys() - {"mtime", "path"}
            ):
                raise ValueError("Unsafe archive member metadata.")
            names[member.name] = member
        manifest = names.get("manifest.json")
        if manifest is None or not manifest.isreg() or manifest.size > 16 * 1024 * 1024:
            raise ValueError("Missing or invalid archive manifest.")
        source = stream.extractfile(manifest)
        if source is None:
            raise ValueError("Missing manifest bytes.")
        roots, entries = _manifest(source.read(), run_id)
        expected = {"manifest.json", *(f"payload/{entry.path}" for entry in entries)}
        if set(names) != expected:
            raise ValueError("Unexpected or missing archive member.")
        for entry in entries:
            member = names[f"payload/{entry.path}"]
            if (
                member.isdir() != (entry.kind == "dir")
                or member.size != entry.size
                or member.mode != entry.mode
            ):
                raise ValueError("Archive member does not match its manifest.")
        for entry in entries:
            path = destination / entry.path
            if entry.kind == "dir":
                path.mkdir(mode=0o700)
            else:
                content = stream.extractfile(names[f"payload/{entry.path}"])
                if content is None:
                    raise ValueError("Missing archive file bytes.")
                with path.open("xb") as output:
                    shutil.copyfileobj(content, output)
                    output.flush()
                    os.fsync(output.fileno())
                if _digest(path) != entry.sha256:
                    raise ValueError("Archive file hash mismatch.")
        for entry in reversed(entries):
            path = destination / entry.path
            os.chmod(path, entry.mode)
            os.utime(path, ns=(entry.mtime_ns, entry.mtime_ns))
    if _inventory(destination, roots) != entries:
        raise ValueError("Restored archive metadata or bytes differ.")
    if _closure(destination, run_id) != roots:
        raise ValueError("Archive dependency closure differs.")
    _terminal(destination, run_id)
    return roots, entries


def _compare(left: Path, right: Path, roots: tuple[str, ...]) -> None:
    if _inventory(left, roots) != _inventory(right, roots):
        raise ValueError(
            "Existing run or dependency changed; restore in a separate workspace."
        )
    for entry in _inventory(right, roots):
        if entry.kind == "file":
            with (
                _open(left / entry.path) as original,
                _open(right / entry.path) as restored,
            ):
                while chunk := original.read(1024 * 1024):
                    if chunk != restored.read(len(chunk)):
                        raise ValueError("Restored file bytes differ.")
                if restored.read(1):
                    raise ValueError("Restored file bytes differ.")


def _verified(
    runs: Path, run_id: str, record: object, destination: Path
) -> tuple[str, ...]:
    if not isinstance(record, dict):
        raise ValueError("The archive is not registered.")
    archive = runs / f"{run_id}.tar.gz"
    roots, _ = _extract(archive, destination, run_id, _hash(record["sha256"]))
    if list(roots) != record["roots"]:
        raise ValueError("Archive index roots differ.")
    return roots


def archive_run(workspace: Path, run_id: str) -> Path:
    """Verify and register an immutable archive, then remove only its record root.

    Keep every dependency directory. Refuse a changed snapshot on retry.
    Writers must be stopped and must honor runs/.archive.lock during resume.
    """
    run_id = _run_id(run_id)
    runs = _runs(workspace)
    with _lock(runs):
        return _archive_run_locked(runs, run_id)


def _archive_run_locked(runs: Path, run_id: str) -> Path:
    """Archive a validated run while the caller holds the exclusive archive lock."""
    with tempfile.TemporaryDirectory(prefix=".archive-", dir=runs) as name:
        temporary = Path(name)
        restored = temporary / "restored"
        restored.mkdir()
        archives = _index(runs)
        archive = runs / f"{run_id}.tar.gz"
        if run_id in archives:
            roots = _verified(runs, run_id, archives[run_id], restored)
            if not (runs / run_id).exists() and not (runs / run_id).is_symlink():
                return archive
        else:
            if archive.exists() or archive.is_symlink():
                raise ValueError(
                    "An unregistered archive already exists. Keep the source run."
                )
            _terminal(runs, run_id)
            roots = _closure(runs, run_id)
            entries = _inventory(runs, roots)
            manifest = json.dumps(
                {
                    "version": 1,
                    "run_id": run_id,
                    "roots": roots,
                    "entries": [asdict(entry) for entry in entries],
                }
            ).encode()
            pending = temporary / "archive.tar.gz"
            with tarfile.open(pending, "w:gz", format=tarfile.PAX_FORMAT) as stream:
                info = tarfile.TarInfo("manifest.json")
                info.size = len(manifest)
                stream.addfile(info, io.BytesIO(manifest))
                for entry in entries:
                    info = tarfile.TarInfo(f"payload/{entry.path}")
                    info.type = (
                        tarfile.DIRTYPE if entry.kind == "dir" else tarfile.REGTYPE
                    )
                    info.mode, info.size = entry.mode, entry.size
                    if entry.kind == "file":
                        with _open(runs / entry.path) as content:
                            stream.addfile(info, content)
                    else:
                        stream.addfile(info)
            with pending.open("rb") as content:
                os.fsync(content.fileno())
            checksum = _digest(pending)
            _extract(pending, restored, run_id, checksum)
            _compare(runs, restored, roots)
            if _digest(pending) != checksum:
                raise ValueError("The archive changed during verification.")
            archives[run_id] = {"sha256": checksum, "roots": list(roots)}
            os.link(pending, archive)
            pending.unlink()
            _sync(runs)
            _atomic(
                runs / "archive-index.json",
                json.dumps(
                    {"version": 1, "archives": archives}, sort_keys=True
                ).encode(),
            )
        current = archives[run_id]
        if not isinstance(current, dict) or _digest(archive) != current["sha256"]:
            raise ValueError("The published archive changed. Keep the source run.")
        _terminal(runs, run_id)
        _compare(runs, restored, roots)
        detached = runs / f".archive-source-{run_id}"
        if detached.exists() or detached.is_symlink():
            raise ValueError("An interrupted source removal needs manual recovery.")
        detached.mkdir(mode=0o700)
        os.rename(runs / run_id, detached / run_id)
        try:
            _compare(detached, restored, (run_id,))
        except BaseException:
            os.rename(detached / run_id, runs / run_id)
            detached.rmdir()
            raise
        shutil.rmtree(detached / run_id)
        detached.rmdir()
        _sync(runs)
        return archive


def restore_run(workspace: Path, run_id: str) -> Path:
    """Restore missing roots. Reject every changed existing root before publication."""
    run_id = _run_id(run_id)
    runs = _runs(workspace)
    with _lock(runs), tempfile.TemporaryDirectory(prefix=".restore-", dir=runs) as name:
        temporary = Path(name)
        archives = _index(runs)
        roots = _verified(runs, run_id, archives.get(run_id), temporary)
        missing: list[str] = []
        for root in roots:
            path = runs / root
            if path.exists() or path.is_symlink():
                _compare(runs, temporary, (root,))
            else:
                missing.append(root)
        # Publish dependencies before the record so an interruption is retryable.
        for root in sorted(missing, key=lambda root: root == run_id):
            os.rename(temporary / root, runs / root)
            _sync(runs)
        return runs / run_id


def _gc_order(runs: Path, candidates: tuple[str, ...]) -> tuple[str, ...]:
    """Order dependents before ancestors. Keep cycles and their ancestors."""
    selected = set(candidates)
    dependencies: dict[str, set[str]] = {}
    for identifier in candidates:
        roots = _closure(runs, identifier)
        dependencies[identifier] = set(roots) & selected
        # A closure includes its root even when no dependency leads back to it.
        if not any(identifier in _edges(runs, root) for root in roots):
            dependencies[identifier].remove(identifier)
    ordered: list[str] = []
    while dependencies:
        ancestors = {root for roots in dependencies.values() for root in roots}
        ready = [
            identifier for identifier in dependencies if identifier not in ancestors
        ]
        if not ready:
            break
        ordered.extend(ready)
        for identifier in ready:
            del dependencies[identifier]
    return tuple(ordered)


def gc_candidates(workspace: Path, scoreboard: Path) -> tuple[str, ...]:
    """Keep four full loops, the current noise run, and all kept dependencies.

    A parse error keeps every run. Unknown directories are never candidates.
    Read only scoreboard-listed development metadata to select candidates.
    Order dependents before ancestors. Keep cycles and their ancestors.
    Callers that remove runs must hold the exclusive archive lock throughout.
    """
    runs = _runs(workspace)
    try:
        lines = _read(scoreboard).decode().splitlines()
        header: list[str] | None = None
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()
        for line in lines:
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if header is None:
                if len(set(cells)) != len(cells) or not {
                    "run_id",
                    "loop",
                    "corpus",
                } <= set(cells):
                    return ()
                header = cells
                continue
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            if len(cells) != len(header):
                return ()
            row = dict(zip(header, cells, strict=True))
            identifier = row["run_id"]
            if (
                "sealed" in identifier.lower()
                or "holdout" in identifier.lower()
                or identifier.lower().startswith("m1-t0-")
            ):
                continue
            identifier = _run_id(identifier)
            if row["corpus"] != "corpus_dev" or row["loop"] not in {
                "full",
                "quick",
                "probe",
                "noise",
                "replay",
            }:
                return ()
            if identifier in seen:
                return ()
            seen.add(identifier)
            rows.append((identifier, row["loop"]))
        if header is None:
            return ()
        kept = set([identifier for identifier, kind in rows if kind == "full"][-4:])
        kept.update([identifier for identifier, kind in rows if kind == "noise"][-1:])
        archives = _index(runs)
        for identifier, _ in rows:
            path = runs / identifier
            if not path.exists() and not path.is_symlink():
                continue
            try:
                _terminal(runs, identifier)
            except (OSError, ValueError, TypeError):
                kept.add(identifier)
        protected = set(kept)
        for identifier in kept:
            if (runs / identifier).exists() or (runs / identifier).is_symlink():
                protected.update(_closure(runs, identifier))
            else:
                item = archives.get(identifier)
                if not isinstance(item, dict):
                    return ()
                protected.update(_roots(item["roots"], identifier))
        candidates = tuple(
            identifier
            for identifier, _ in rows
            if identifier not in protected
            and (runs / identifier).is_dir()
            and not (runs / identifier).is_symlink()
        )
        return _gc_order(runs, candidates)
    except (OSError, ValueError, TypeError, KeyError):
        return ()


def main() -> int:
    """Run archive, restore, or conservative development-run cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("archive", "restore", "gc"))
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--scoreboard", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "gc":
            if arguments.scoreboard is None or arguments.run_id is not None:
                parser.error("gc requires --scoreboard and no run ID.")
            runs = _runs(arguments.workspace)
            with nullcontext() if arguments.dry_run else _lock(runs):
                protected: set[str] = set()
                for run_id in gc_candidates(arguments.workspace, arguments.scoreboard):
                    if run_id in protected:
                        continue
                    print(f"Action: archive verified development record {run_id}")
                    if not arguments.dry_run:
                        try:
                            _archive_run_locked(runs, run_id)
                        except (OSError, ValueError, tarfile.TarError) as error:
                            print(f"Keep {run_id}: {error}")
                            protected.update(_closure(runs, run_id))
        else:
            if arguments.run_id is None or arguments.dry_run:
                parser.error("archive and restore require a run ID and no --dry-run.")
            operation = archive_run if arguments.command == "archive" else restore_run
            print(operation(arguments.workspace, arguments.run_id))
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f"Archive operation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
