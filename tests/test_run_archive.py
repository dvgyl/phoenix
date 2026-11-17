"""Use synthetic development records to verify archive safety."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import pytest

from phoenix_eval import run_archive as archive
from phoenix_eval.artifacts import atomic_bytes


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "runs").mkdir()
    return tmp_path


def record(workspace: Path, name: str, dependencies: tuple[str, ...] = ()) -> Path:
    root = workspace / "runs" / name
    root.mkdir()
    (root / "plan.json").write_text(json.dumps({"dependencies": dependencies}))
    (root / "scoreboard.json").write_text(json.dumps({"run_state": "stopped"}))
    (root / "empty").mkdir()
    (root / "bytes.bin").write_bytes(bytes(range(256)) * 71)
    (root / "bytes.bin").chmod(0o640)
    os.utime(root / "bytes.bin", ns=(1700000000000000123, 1700000000000000123))
    return root


def tree(root: Path) -> dict[str, tuple[bytes | None, int, int]]:
    paths = [root, *sorted(root.rglob("*"))]
    return {
        str(path.relative_to(root)): (
            None if path.is_dir() else path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in paths
    }


def test_round_trip_and_idempotence(workspace: Path) -> None:
    primary = record(workspace, "dev-one", ("ancestor",))
    record(workspace, "ancestor", ("external-ledger",))
    record(workspace, "dev-one-p")
    ledger = workspace / "runs/external-ledger"
    ledger.mkdir()
    (ledger / "llm.jsonl").write_bytes(b'{"response":"synthetic"}\n')
    expected = {
        name: tree(workspace / "runs" / name)
        for name in ("dev-one", "dev-one-p", "ancestor", "external-ledger")
    }
    path = archive.archive_run(workspace, "dev-one")
    assert path == workspace / "runs/dev-one.tar.gz"
    assert not primary.exists()
    assert (workspace / "runs/dev-one-p").is_dir()
    assert archive.archive_run(workspace, "dev-one") == path
    for name in ("ancestor", "dev-one-p", "external-ledger"):
        shutil.rmtree(workspace / "runs" / name)
    assert archive.restore_run(workspace, "dev-one") == primary
    for name, contents in expected.items():
        assert tree(workspace / "runs" / name) == contents
    assert archive.restore_run(workspace, "dev-one") == primary
    assert archive.archive_run(workspace, "dev-one") == path
    assert not primary.exists()


def test_archive_version_one_layout(workspace: Path) -> None:
    root = record(workspace, "dev-one")
    expected = tree(root)
    path = archive.archive_run(workspace, "dev-one")
    index = json.loads((workspace / "runs/archive-index.json").read_bytes())
    assert index == {
        "version": 1,
        "archives": {
            "dev-one": {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "roots": ["dev-one"],
            }
        },
    }
    with tarfile.open(path, "r:gz") as stream:
        source = stream.extractfile("manifest.json")
        assert source is not None
        manifest = json.loads(source.read())
        assert set(manifest) == {"version", "run_id", "roots", "entries"}
        assert manifest["version"] == 1
        assert manifest["run_id"] == "dev-one"
        assert manifest["roots"] == ["dev-one"]
        entries = manifest["entries"]
        assert [item["path"] for item in entries] == sorted(
            "dev-one" if name == "." else f"dev-one/{name}" for name in expected
        )
        assert stream.getnames() == [
            "manifest.json",
            *(f"payload/{item['path']}" for item in entries),
        ]
        for item in entries:
            relative = Path(item["path"]).relative_to("dev-one").as_posix()
            data, mode, mtime = expected[relative]
            assert item == {
                "path": item["path"],
                "kind": "dir" if data is None else "file",
                "mode": mode,
                "mtime_ns": mtime,
                "size": 0 if data is None else len(data),
                "sha256": "" if data is None else hashlib.sha256(data).hexdigest(),
            }


def test_comparison_checks_bytes_after_matching_hashes(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(workspace, "dev-one")
    restored = workspace / "restored"
    shutil.copytree(workspace / "runs", restored)
    changed = restored / "dev-one/bytes.bin"
    info = changed.stat()
    changed.write_bytes(b"x" * info.st_size)
    os.utime(changed, ns=(info.st_atime_ns, info.st_mtime_ns))
    monkeypatch.setattr(archive, "_digest", lambda path: "0" * 64)
    with pytest.raises(ValueError, match="Restored file bytes differ"):
        archive._compare(workspace / "runs", restored, ("dev-one",))


@pytest.mark.parametrize("name", ["sealed-synthetic", "holdout_b", "m1-t0-test"])
def test_protected_names_are_filtered_before_filesystem_access(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    root = record(workspace, "dev-one")
    (root / name).mkdir()
    rows = scoreboard(workspace, [(name, "full")])
    original = Path.lstat
    original_stat = Path.stat
    original_iterdir = Path.iterdir

    def guarded(path: Path) -> os.stat_result:
        assert name not in path.parts
        return original(path)

    def guarded_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        assert name not in path.parts
        return original_stat(path, follow_symlinks=follow_symlinks)

    def guarded_iterdir(path: Path) -> Iterator[Path]:
        assert name not in path.parts
        return original_iterdir(path)

    monkeypatch.setattr(Path, "lstat", guarded)
    monkeypatch.setattr(Path, "stat", guarded_stat)
    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)
    with pytest.raises(ValueError, match="Protected"):
        archive.archive_run(workspace, "dev-one")
    with pytest.raises(ValueError, match="Protected"):
        archive.archive_run(workspace / name, "dev-one")
    assert archive.gc_candidates(workspace, rows) == ()


def test_corrupt_archive_never_restores(workspace: Path) -> None:
    record(workspace, "dev-one")
    path = archive.archive_run(workspace, "dev-one")
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/dev-one").exists()


def test_archive_hash_is_checked_after_extraction(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(workspace, "dev-one")
    path = archive.archive_run(workspace, "dev-one")
    extract = archive._extract_stream

    def corrupt(stream: BinaryIO, destination: Path, run_id: str) -> tuple[str, ...]:
        roots = extract(stream, destination, run_id)
        with path.open("ab") as output:
            output.write(b"changed after extraction")
        return roots

    monkeypatch.setattr(archive, "_extract_stream", corrupt)
    with pytest.raises(ValueError, match="changed during extraction"):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/dev-one").exists()


@pytest.mark.parametrize("registered", [False, True])
def test_restore_requires_matching_index_roots(
    workspace: Path, registered: bool
) -> None:
    if registered:
        record(workspace, "dev-one")
        archive.archive_run(workspace, "dev-one")
        index = workspace / "runs/archive-index.json"
        document = json.loads(index.read_bytes())
        document["archives"]["dev-one"]["roots"].append("extra")
        index.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="index roots differ|not registered"):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/dev-one").exists()


@pytest.mark.parametrize("change", ["append", "replace", "mode", "extra", "symlink"])
def test_changed_dependency_is_never_overwritten(workspace: Path, change: str) -> None:
    record(workspace, "dev-one", ("ledger",))
    dependency = record(workspace, "ledger")
    archive.archive_run(workspace, "dev-one")
    path = dependency / "bytes.bin"
    if change == "append":
        with path.open("ab") as stream:
            stream.write(b"later ledger response")
    elif change == "replace":
        path.write_bytes(b"different")
    elif change == "mode":
        path.chmod(0o600)
    elif change == "extra":
        (dependency / "new").write_bytes(b"new")
    else:
        path.unlink()
        path.symlink_to("plan.json")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="changed|Unsafe"):
        archive.restore_run(workspace, "dev-one")
    assert path.read_bytes() == before
    assert not (workspace / "runs/dev-one").exists()


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", "/absolute", "sealed-a", "holdout_b", "m1-t0-secret", "x/sealed"],
)
def test_protected_ids(workspace: Path, bad_id: str) -> None:
    with pytest.raises(ValueError):
        archive.archive_run(workspace, bad_id)
    with pytest.raises(ValueError):
        archive.restore_run(workspace, bad_id)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_unsafe_source_keeps_record(workspace: Path, kind: str) -> None:
    root = record(workspace, "dev-one")
    if kind == "symlink":
        (root / "bad").symlink_to("bytes.bin")
    elif kind == "hardlink":
        os.link(root / "bytes.bin", root / "bad")
    else:
        os.mkfifo(root / "bad")
    with pytest.raises(ValueError):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()
    assert not (workspace / "runs/archive-index.json").exists()


@pytest.mark.parametrize(
    "member_name,kind",
    [
        ("../escape", "file"),
        ("/absolute", "file"),
        ("payload/dev-one/../escape", "file"),
        ("payload/dev-one/link", "symlink"),
        ("payload/dev-one/link", "hardlink"),
        ("payload/dev-one/fifo", "fifo"),
        ("payload/dev-one/device", "device"),
        ("manifest.json", "file"),
        ("payload/dev-one", "dir"),
    ],
)
def test_malicious_members(workspace: Path, member_name: str, kind: str) -> None:
    record(workspace, "dev-one")
    path = archive.archive_run(workspace, "dev-one")
    replacement = workspace / "malicious.tar.gz"
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(replacement, "w:gz") as target,
    ):
        for member in source.getmembers():
            target.addfile(
                member, source.extractfile(member) if member.isreg() else None
            )
        bad = tarfile.TarInfo(member_name)
        bad.type = {
            "file": tarfile.REGTYPE,
            "dir": tarfile.DIRTYPE,
            "symlink": tarfile.SYMTYPE,
            "hardlink": tarfile.LNKTYPE,
            "fifo": tarfile.FIFOTYPE,
            "device": tarfile.CHRTYPE,
        }[kind]
        if kind in {"symlink", "hardlink"}:
            bad.linkname = "../../escape"
        target.addfile(bad, io.BytesIO())
    replacement.replace(path)
    index = workspace / "runs/archive-index.json"
    document = json.loads(index.read_text())
    document["archives"]["dev-one"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    index.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/dev-one").exists()
    assert not (workspace / "escape").exists()


def test_interrupted_publication_keeps_source(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = record(workspace, "dev-one")
    before = tree(root)

    def fail(path: Path, data: bytes) -> None:
        raise OSError("synthetic interruption")

    monkeypatch.setattr(archive, "atomic_bytes", fail)
    with pytest.raises(OSError, match="interruption"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before
    assert not (workspace / "runs/archive-index.json").exists()
    with pytest.raises(ValueError, match="unregistered"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before


def test_failed_restore_proof_keeps_source(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = record(workspace, "dev-one")
    before = tree(root)

    def fail(*args: object) -> None:
        raise ValueError("synthetic byte mismatch")

    monkeypatch.setattr(archive, "_compare", fail)
    with pytest.raises(ValueError, match="byte mismatch"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before
    assert not (workspace / "runs/archive-index.json").exists()


def test_dependency_cycle(workspace: Path) -> None:
    record(workspace, "dev-one", ("ancestor",))
    record(workspace, "ancestor", ("dev-one",))
    archive.archive_run(workspace, "dev-one")
    shutil.rmtree(workspace / "runs/ancestor")
    archive.restore_run(workspace, "dev-one")
    assert (workspace / "runs/ancestor/bytes.bin").is_file()


@pytest.mark.parametrize("state", ["running", "unknown", None])
def test_active_or_unknown_run_is_kept(workspace: Path, state: str | None) -> None:
    root = record(workspace, "dev-one")
    (root / "scoreboard.json").write_text(json.dumps({"run_state": state}))
    with pytest.raises(ValueError, match="active|unknown"):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()


def scoreboard(workspace: Path, rows: list[tuple[str, str]]) -> Path:
    path = workspace / "SCOREBOARD.md"
    path.write_text(
        "| run_id | corpus | loop |\n|---|---|---|\n"
        + "".join(f"| {name} | corpus_dev | {kind} |\n" for name, kind in rows)
    )
    return path


def test_gc_keep_rules(workspace: Path) -> None:
    rows: list[tuple[str, str]] = []
    for index in range(7):
        name = f"full-{index}"
        record(workspace, name)
        rows.append((name, "full"))
    record(workspace, "noise-old")
    record(workspace, "noise-current", ("full-0", "shared-pipeline"))
    record(workspace, "shared-pipeline")
    record(workspace, "probe-old")
    active = record(workspace, "active-run", ("full-1",))
    (active / "scoreboard.json").write_text('{"run_state":"running"}')
    record(workspace, "unknown-run")
    (workspace / "runs/m1-t0-synthetic").mkdir()
    (workspace / "runs/sealed-synthetic").mkdir()
    rows.extend(
        [
            ("noise-old", "noise"),
            ("noise-current", "noise"),
            ("shared-pipeline", "probe"),
            ("probe-old", "probe"),
            ("active-run", "probe"),
            ("m1-t0-synthetic", "full"),
            ("sealed-synthetic", "full"),
        ]
    )
    path = scoreboard(workspace, rows)
    assert archive.gc_candidates(workspace, path) == (
        "full-2",
        "noise-old",
        "probe-old",
    )


def test_gc_keeps_transitive_dependencies(workspace: Path) -> None:
    record(workspace, "old-root")
    record(workspace, "ancestor", ("old-root",))
    record(workspace, "noise-current", ("ancestor",))
    path = scoreboard(workspace, [("old-root", "probe"), ("noise-current", "noise")])
    assert archive.gc_candidates(workspace, path) == ()


@pytest.mark.parametrize(
    "suffix",
    [
        "|broken|\n",
        "| bad | corpus_dev | uncertain |\n",
        "| ../bad | corpus_dev | full |\n",
    ],
)
def test_gc_uncertain_fields_keep_every_run(workspace: Path, suffix: str) -> None:
    record(workspace, "old-root")
    path = scoreboard(workspace, [("old-root", "probe")])
    path.write_text(path.read_text() + suffix)
    assert archive.gc_candidates(workspace, path) == ()


def test_gc_dry_run_has_no_writes(workspace: Path) -> None:
    record(workspace, "old-root")
    path = scoreboard(workspace, [("old-root", "probe")])
    before = tree(workspace / "runs")
    result = subprocess.run(
        [
            str(Path.cwd() / ".venv/bin/python"),
            "-m",
            "phoenix_eval.run_archive",
            "gc",
            "--workspace",
            str(workspace),
            "--scoreboard",
            str(path),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "archive verified development record old-root" in result.stdout
    assert tree(workspace / "runs") == before


def test_restore_checks_all_collisions_before_publication(workspace: Path) -> None:
    record(workspace, "dev-one", ("a-missing", "z-changed"))
    record(workspace, "a-missing")
    record(workspace, "z-changed")
    archive.archive_run(workspace, "dev-one")
    shutil.rmtree(workspace / "runs/a-missing")
    (workspace / "runs/z-changed/bytes.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/a-missing").exists()
    assert not (workspace / "runs/dev-one").exists()


def test_dependency_replay_ancestor_pipeline_is_included(workspace: Path) -> None:
    record(workspace, "dev-one", ("ancestor",))
    record(workspace, "ancestor")
    record(workspace, "ancestor-p")
    expected = tree(workspace / "runs/ancestor-p")
    archive.archive_run(workspace, "dev-one")
    shutil.rmtree(workspace / "runs/ancestor-p")
    archive.restore_run(workspace, "dev-one")
    assert tree(workspace / "runs/ancestor-p") == expected


def test_publication_corruption_keeps_source(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = record(workspace, "dev-one")
    before = tree(root)
    write = atomic_bytes

    def corrupt(path: Path, data: bytes) -> None:
        write(path, data)
        (workspace / "runs/dev-one.tar.gz").write_bytes(b"corrupt after publication")

    monkeypatch.setattr(archive, "atomic_bytes", corrupt)
    with pytest.raises(ValueError, match="published archive changed"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before


def test_detached_source_is_restored_on_failed_comparison(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = record(workspace, "dev-one")
    before = tree(root)
    compare = archive._compare

    def fail(left: Path, right: Path, roots: tuple[str, ...]) -> None:
        if left.name.startswith(".archive-source-"):
            raise ValueError("synthetic source change")
        compare(left, right, roots)

    monkeypatch.setattr(archive, "_compare", fail)
    with pytest.raises(ValueError, match="source change"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before
    monkeypatch.setattr(archive, "_compare", compare)
    assert archive.archive_run(workspace, "dev-one").is_file()


def test_interrupted_restore_can_retry(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(workspace, "dev-one", ("ancestor",))
    record(workspace, "ancestor")
    archive.archive_run(workspace, "dev-one")
    shutil.rmtree(workspace / "runs/ancestor")
    rename = os.rename

    def interrupt(source: Path, destination: Path) -> None:
        if destination == workspace / "runs/dev-one":
            raise OSError("synthetic restore interruption")
        rename(source, destination)

    monkeypatch.setattr(os, "rename", interrupt)
    with pytest.raises(OSError, match="interruption"):
        archive.restore_run(workspace, "dev-one")
    assert (workspace / "runs/ancestor").is_dir()
    assert not (workspace / "runs/dev-one").exists()
    monkeypatch.setattr(os, "rename", rename)
    assert archive.restore_run(workspace, "dev-one").is_dir()


@pytest.mark.parametrize("bad", [None, "ancestor", ["sealed-a"], ["../ancestor"], [1]])
def test_invalid_dependencies_keep_source(workspace: Path, bad: object) -> None:
    root = record(workspace, "dev-one")
    (root / "plan.json").write_text(json.dumps({"dependencies": bad}))
    with pytest.raises(ValueError):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()


def test_gc_archived_keeper_protects_dependencies(workspace: Path) -> None:
    record(workspace, "old-root")
    record(workspace, "noise-current", ("old-root",))
    archive.archive_run(workspace, "noise-current")
    path = scoreboard(workspace, [("old-root", "probe"), ("noise-current", "noise")])
    assert archive.gc_candidates(workspace, path) == ()


def test_gc_dependency_of_active_run_is_kept(workspace: Path) -> None:
    record(workspace, "old-root")
    active = record(workspace, "active-run", ("old-root",))
    (active / ".active").write_text("synthetic")
    path = scoreboard(workspace, [("old-root", "probe"), ("active-run", "probe")])
    assert archive.gc_candidates(workspace, path) == ()


def test_gc_shell_dry_run_preserves_records_and_cleanup_rules(workspace: Path) -> None:
    repository = workspace / "repository"
    (repository / "scripts").mkdir(parents=True)
    (repository / "docs").mkdir()
    script = repository / "scripts/gc"
    shutil.copyfile(Path.cwd() / "scripts/gc", script)
    record(workspace, "old-root")
    rows = scoreboard(workspace, [("old-root", "probe")])
    shutil.copyfile(rows, repository / "docs/SCOREBOARD.md")
    (workspace / "tmp").mkdir()
    stale = workspace / "tmp/stale"
    stale.write_text("synthetic temporary file")
    (workspace / "tmp/.gc-mark").write_text("")
    os.utime(stale, ns=(1, 1))
    stubs = workspace / "stubs"
    stubs.mkdir()
    python = Path.cwd() / ".venv/bin/python"
    for name, body in {
        "uv": (
            f'#!/bin/sh\nexec "{python}" -m phoenix_eval.run_archive gc '
            f'--workspace "$PHOENIX_ROOT" --scoreboard "{rows}" --dry-run\n'
        ),
        "docker": (
            '#!/bin/sh\n[ "$1 $2" != "image ls" ] || '
            'printf "foreign abc\\nphoenix-build def\\n"\n'
        ),
        "colima": "#!/bin/sh\nexit 91\n",
        "df": '#!/bin/sh\nprintf "synthetic free space\\n"\n',
    }.items():
        path = stubs / name
        path.write_text(body)
        path.chmod(0o700)
    before = tree(workspace / "runs")
    environment = dict(
        os.environ, PHOENIX_ROOT=str(workspace), PATH=f"{stubs}:{os.environ['PATH']}"
    )
    result = subprocess.run(
        ["/bin/sh", str(script), "--dry-run"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "archive verified development record old-root" in result.stdout
    assert "builder> <prune>" in result.stdout
    assert "image> <rm> <abc>" in result.stdout
    assert "image> <rm> <def>" not in result.stdout
    assert "fstrim> <-av>" in result.stdout
    assert stale.read_text() == "synthetic temporary file"
    assert tree(workspace / "runs") == before


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "entry-type",
        "bool-mode",
        "duplicate",
        "traversal",
        "protected",
        "missing-root",
    ],
)
def test_invalid_archive_manifest_or_bytes(workspace: Path, change: str) -> None:
    record(workspace, "dev-one")
    path = archive.archive_run(workspace, "dev-one")
    replacement = workspace / "replacement.tar.gz"
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(replacement, "w:gz") as target,
    ):
        for member in source.getmembers():
            content = source.extractfile(member) if member.isreg() else None
            data = content.read() if content is not None else b""
            if member.name == "manifest.json":
                document = json.loads(data)
                if change == "entry-type":
                    document["entries"][0]["kind"] = []
                elif change == "bool-mode":
                    document["entries"][0]["mode"] = True
                elif change == "duplicate":
                    document["entries"].append(dict(document["entries"][0], mode=0o111))
                elif change == "traversal":
                    document["entries"][0]["path"] = "dev-one/../escape"
                elif change == "protected":
                    document["entries"][0]["path"] = "dev-one/sealed/content"
                elif change == "missing-root":
                    document["entries"] = document["entries"][1:]
                data = json.dumps(document).encode()
                member.size = len(data)
            elif change == "bytes" and member.name.endswith("bytes.bin"):
                data = bytes([data[0] ^ 0xFF]) + data[1:]
            target.addfile(member, io.BytesIO(data) if member.isreg() else None)
    replacement.replace(path)
    index = workspace / "runs/archive-index.json"
    document = json.loads(index.read_text())
    document["archives"]["dev-one"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    index.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        archive.restore_run(workspace, "dev-one")
    assert not (workspace / "runs/dev-one").exists()


def test_archive_retry_does_not_replace_old_ledger_snapshot(workspace: Path) -> None:
    record(workspace, "dev-one", ("ledger",))
    record(workspace, "ledger")
    path = archive.archive_run(workspace, "dev-one")
    archive.restore_run(workspace, "dev-one")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    root = workspace / "runs/dev-one"
    before = tree(root)
    with (workspace / "runs/ledger/bytes.bin").open("ab") as stream:
        stream.write(b"new response")
    with pytest.raises(ValueError, match="changed"):
        archive.archive_run(workspace, "dev-one")
    assert tree(root) == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


def test_lock_rejects_link(workspace: Path) -> None:
    root = record(workspace, "dev-one")
    (workspace / "runs/.archive.lock").symlink_to(root / "bytes.bin")
    with pytest.raises(OSError):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()


def test_duplicate_json_keys_are_rejected(workspace: Path) -> None:
    root = record(workspace, "dev-one")
    (root / "plan.json").write_text('{"dependencies": [], "dependencies": ["other"]}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()


def test_concurrent_archives_keep_all_index_entries(workspace: Path) -> None:
    identifiers = tuple(f"dev-{index}" for index in range(4))
    expected = {
        identifier: tree(record(workspace, identifier)) for identifier in identifiers
    }
    processes = [
        subprocess.Popen(
            [
                str(Path.cwd() / ".venv/bin/python"),
                "-m",
                "phoenix_eval.run_archive",
                "archive",
                identifier,
                "--workspace",
                str(workspace),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for identifier in identifiers
    ]
    for process in processes:
        output, error = process.communicate()
        assert process.returncode == 0, output + error
    document = json.loads((workspace / "runs/archive-index.json").read_text())
    assert set(document["archives"]) == set(identifiers)
    for identifier in identifiers:
        root = archive.restore_run(workspace, identifier)
        assert tree(root) == expected[identifier]


def test_gc_execution_keeps_unregistered_archive_and_unknown_record(
    workspace: Path,
) -> None:
    record(workspace, "eligible")
    record(workspace, "unverified")
    unknown = record(workspace, "unknown")
    unknown_before = tree(unknown)
    (workspace / "runs/unverified.tar.gz").write_bytes(b"unregistered")
    path = scoreboard(workspace, [("eligible", "probe"), ("unverified", "probe")])
    result = subprocess.run(
        [
            str(Path.cwd() / ".venv/bin/python"),
            "-m",
            "phoenix_eval.run_archive",
            "gc",
            "--workspace",
            str(workspace),
            "--scoreboard",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not (workspace / "runs/eligible").exists()
    assert archive.restore_run(workspace, "eligible").is_dir()
    assert "Keep unverified" in result.stdout
    assert (workspace / "runs/unverified").is_dir()
    assert (workspace / "runs/unverified.tar.gz").read_bytes() == b"unregistered"
    assert tree(unknown) == unknown_before


@pytest.mark.parametrize("metadata", ["plan.json", "scoreboard.json"])
def test_non_development_metadata_keeps_record(workspace: Path, metadata: str) -> None:
    root = record(workspace, "dev-one")
    document = json.loads((root / metadata).read_text())
    document["corpus"] = "sealed-a"
    (root / metadata).write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Only development"):
        archive.archive_run(workspace, "dev-one")
    assert root.is_dir()


def test_gc_rejects_symlink_parent_of_scoreboard(workspace: Path) -> None:
    record(workspace, "eligible")
    target = workspace / "metadata"
    target.mkdir()
    source = scoreboard(workspace, [("eligible", "probe")])
    shutil.copyfile(source, target / "SCOREBOARD.md")
    (workspace / "metadata-link").symlink_to(target, target_is_directory=True)
    assert (
        archive.gc_candidates(workspace, workspace / "metadata-link/SCOREBOARD.md")
        == ()
    )


def run_gc(workspace: Path, path: Path, *, dry_run: bool = False) -> str:
    result = subprocess.run(
        [
            str(Path.cwd() / ".venv/bin/python"),
            "-m",
            "phoenix_eval.run_archive",
            "gc",
            "--workspace",
            str(workspace),
            "--scoreboard",
            str(path),
            *(["--dry-run"] if dry_run else []),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_gc_selects_candidates_after_lock_acquisition(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ancestor = record(workspace, "ancestor")
    record(workspace, "noise-current", ("ancestor",))
    path = scoreboard(workspace, [("ancestor", "probe")])
    assert archive.gc_candidates(workspace, path) == ("ancestor",)
    expected = tree(ancestor)
    lock = archive._lock
    acquisitions = 0

    @contextmanager
    def publish_before_lock(runs: Path) -> Iterator[None]:
        nonlocal acquisitions
        acquisitions += 1
        scoreboard(workspace, [("ancestor", "probe"), ("noise-current", "noise")])
        with lock(runs):
            yield

    monkeypatch.setattr(archive, "_lock", publish_before_lock)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_archive",
            "gc",
            "--workspace",
            str(workspace),
            "--scoreboard",
            str(path),
        ],
    )
    assert archive.main() == 0
    assert tree(ancestor) == expected
    assert not (workspace / "runs/ancestor.tar.gz").exists()
    assert not (workspace / "runs/archive-index.json").exists()
    assert "Action: archive" not in capsys.readouterr().out
    assert acquisitions == 1


@pytest.mark.parametrize("transitive", [False, True])
def test_gc_archives_replay_before_ancestor_and_restores_closure(
    workspace: Path, transitive: bool
) -> None:
    record(workspace, "ancestor", ("ledger",))
    record(workspace, "ancestor-p")
    record(workspace, "ledger")
    dependency = "bridge" if transitive else "ancestor"
    if transitive:
        record(workspace, "bridge", ("ancestor",))
    record(workspace, "replay", (dependency,))
    record(workspace, "replay-p")
    independent = record(workspace, "independent")
    independent_before = tree(independent)
    path = scoreboard(
        workspace,
        [("ancestor", "probe"), ("replay", "replay"), ("independent", "probe")],
    )
    roots = ["ancestor", "ancestor-p", "ledger", "replay", "replay-p"]
    if transitive:
        roots.append("bridge")
    expected = {root: tree(workspace / "runs" / root) for root in roots}
    before = tree(workspace / "runs")
    dry_output = run_gc(workspace, path, dry_run=True)
    assert tree(workspace / "runs") == before
    assert dry_output.index("record replay") < dry_output.index("record ancestor")
    output = run_gc(workspace, path)
    assert "Keep " not in output
    assert output.index("record replay") < output.index("record ancestor")
    for root in ("replay", "ancestor", "independent"):
        assert not (workspace / "runs" / root).exists()
        assert (workspace / "runs" / f"{root}.tar.gz").is_file()
    for root in roots:
        if root not in {"replay", "ancestor"}:
            assert tree(workspace / "runs" / root) == expected[root]
            shutil.rmtree(workspace / "runs" / root)
    assert archive.restore_run(workspace, "replay") == workspace / "runs/replay"
    assert {root: tree(workspace / "runs" / root) for root in roots} == expected
    assert tree(archive.restore_run(workspace, "independent")) == independent_before


@pytest.mark.parametrize("cycle", ["self", "mutual", "transitive"])
def test_gc_keeps_candidate_cycles_and_their_ancestors(
    workspace: Path, cycle: str
) -> None:
    record(workspace, "ancestor")
    if cycle == "self":
        record(workspace, "cycle-a", ("cycle-a", "ancestor"))
    elif cycle == "mutual":
        record(workspace, "cycle-a", ("cycle-b", "ancestor"))
        record(workspace, "cycle-b", ("cycle-a",))
    else:
        record(workspace, "cycle-a", ("bridge", "ancestor"))
        record(workspace, "bridge", ("cycle-a",))
    record(workspace, "dependent", ("cycle-a",))
    record(workspace, "independent")
    rows = [("ancestor", "probe"), ("cycle-a", "replay")]
    if cycle == "mutual":
        rows.append(("cycle-b", "replay"))
    rows.extend([("dependent", "replay"), ("independent", "probe")])
    path = scoreboard(workspace, rows)
    kept = ["ancestor", "cycle-a"]
    if cycle == "mutual":
        kept.append("cycle-b")
    if cycle == "transitive":
        kept.append("bridge")
    expected = {root: tree(workspace / "runs" / root) for root in kept}
    assert archive.gc_candidates(workspace, path) == ("dependent", "independent")
    output = run_gc(workspace, path)
    assert "Keep " not in output
    assert {root: tree(workspace / "runs" / root) for root in kept} == expected
    for root in ("dependent", "independent"):
        assert not (workspace / "runs" / root).exists()
        assert (workspace / "runs" / f"{root}.tar.gz").is_file()
    for root in kept:
        assert not (workspace / "runs" / f"{root}.tar.gz").exists()


def test_gc_failed_replay_keeps_ancestor_and_archives_independent(
    workspace: Path,
) -> None:
    ancestor = record(workspace, "ancestor")
    record(workspace, "replay", ("ancestor",))
    snapshot = archive.archive_run(workspace, "replay")
    archive.restore_run(workspace, "replay")
    checksum = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with (ancestor / "bytes.bin").open("ab") as stream:
        stream.write(b"appended ledger response")
    record(workspace, "independent")
    path = scoreboard(
        workspace,
        [("ancestor", "probe"), ("replay", "replay"), ("independent", "probe")],
    )
    expected = {
        root: tree(workspace / "runs" / root) for root in ("ancestor", "replay")
    }
    output = run_gc(workspace, path)
    assert "Keep replay: Existing run or dependency changed" in output
    assert {
        root: tree(workspace / "runs" / root) for root in ("ancestor", "replay")
    } == expected
    assert not (workspace / "runs/ancestor.tar.gz").exists()
    assert not (workspace / "runs/independent").exists()
    assert (workspace / "runs/independent.tar.gz").is_file()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == checksum


def test_gc_keeps_cycle_through_an_implicit_pipeline_dependency(
    workspace: Path,
) -> None:
    record(workspace, "ancestor")
    record(workspace, "parent", ("ancestor",))
    record(workspace, "parent-p", ("parent",))
    record(workspace, "independent")
    rows = scoreboard(
        workspace,
        [("ancestor", "probe"), ("parent-p", "probe"), ("independent", "probe")],
    )
    before = {
        root: tree(workspace / "runs" / root)
        for root in ("ancestor", "parent", "parent-p")
    }
    assert archive.gc_candidates(workspace, rows) == ("independent",)
    run_gc(workspace, rows)
    assert {root: tree(workspace / "runs" / root) for root in before} == before
    assert not (workspace / "runs/independent").exists()
