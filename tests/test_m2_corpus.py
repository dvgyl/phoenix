import io
import json
import tarfile
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix_eval import dev_corpus as dc
from phoenix_eval import run_archive as archive
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import _case
from phoenix_eval.outcome import EntryKind, TreeEntry, TreeSnapshot
from phoenix_eval.wire import encode_invocation

arguments = st.text(alphabet=st.characters(exclude_characters="\0"))


@given(st.lists(arguments).map(tuple), st.binary(), st.binary(), arguments)
def test_case_round_trip(
    args: tuple[str, ...], stdin: bytes, file: bytes, environment: str
) -> None:
    case = Invocation(
        args,
        stdin,
        TreeSnapshot(entries=(TreeEntry("file", EntryKind.FILE, 0o640, file),)),
        (("PHOENIX_TEST", environment),),
    )
    assert _case(encode_invocation(case)) == case


@pytest.mark.parametrize("level", ["case", "tree", "entry"])
@pytest.mark.parametrize("change", ["missing", "unknown", "duplicate"])
def test_case_rejects_invalid_fields(level: str, change: str) -> None:
    data = json.loads(
        encode_invocation(
            Invocation(
                tree=TreeSnapshot(entries=(TreeEntry("file", EntryKind.FILE, 0o640),))
            )
        )
    )
    target = {"case": data, "tree": data["tree"], "entry": data["tree"]["entries"][0]}[
        level
    ]
    field = {"case": "args", "tree": "entries", "entry": "path"}[level]
    if change == "missing":
        del target[field]
    elif change == "unknown":
        target["unknown"] = 1
    encoded = json.dumps(data)
    if change == "duplicate":
        encoded = encoded.replace(f'"{field}":', f'"{field}": null, "{field}":', 1)
    with pytest.raises(ValueError):
        _case(encoded)


@pytest.mark.parametrize("content", ["private synthetic input", '{"private": 1}'])
def test_case_errors_do_not_expose_case_data(content: str) -> None:
    with pytest.raises(ValueError) as failure:
        _case(content)
    assert content not in str(failure.value)


@pytest.mark.parametrize("count", [0, 1, 99, 100])
def test_development_cases_require_complete_sets(tmp_path: Path, count: int) -> None:
    (tmp_path / "holdout").mkdir()
    (tmp_path / "meta.json").write_text('{"tier": "D0"}')
    (tmp_path / "holdout/cases.jsonl").write_text(
        (encode_invocation(Invocation()) + "\n") * count
    )
    if count < 100:
        with pytest.raises(ValueError, match="at least 100"):
            dc._cases(tmp_path)
    else:
        assert dc._cases(tmp_path) == (Invocation(),) * count


def test_development_case_file_rejects_symlink(tmp_path: Path) -> None:
    (tmp_path / "holdout").mkdir()
    (tmp_path / "cases.jsonl").write_text(encode_invocation(Invocation()) + "\n")
    (tmp_path / "holdout/cases.jsonl").symlink_to(tmp_path / "cases.jsonl")
    with pytest.raises(ValueError, match="regular file"):
        dc._cases(tmp_path)


@pytest.fixture
def archived_run(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "runs/dev-one"
    root.mkdir(parents=True)
    (root / "plan.json").write_text('{"dependencies": []}')
    (root / "scoreboard.json").write_text('{"run_state": "complete"}')
    (root / "cases.jsonl").write_text(encode_invocation(Invocation()) + "\n")
    return tmp_path, archive.archive_run(tmp_path, "dev-one")


def test_archive_reads_cases_from_verified_bytes(
    archived_run: tuple[Path, Path],
) -> None:
    workspace, path = archived_run
    assert path.is_file()
    restored = archive.restore_run(workspace, "dev-one")
    assert _case((restored / "cases.jsonl").read_text()) == Invocation()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "unknown",
        "case-directory",
        "case-size",
        "manifest-size",
        "manifest-symlink",
        "duplicate-file",
        "duplicate-json",
        "run-id",
        "long-kind",
        "newline-kind",
        "boolean-kind",
        "empty-kind",
    ],
)
def test_archive_rejects_incomplete_or_invalid_cases(
    archived_run: tuple[Path, Path], change: str
) -> None:
    workspace, path = archived_run
    replacement = workspace / "replacement.tar.gz"
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(replacement, "w:gz") as target,
    ):
        for member in source.getmembers():
            content = source.extractfile(member) if member.isreg() else None
            data = content.read() if content is not None else b""
            if member.name == "manifest.json":
                if change == "manifest-size":
                    data = b" " * (16 * 1024 * 1024 + 1)
                elif change == "manifest-symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "payload/dev-one/cases.jsonl"
                    data = b""
                elif change == "duplicate-json":
                    data = data.replace(b'"version": 1', b'"version": 0, "version": 1')
                elif change in {
                    "run-id",
                    "long-kind",
                    "newline-kind",
                    "boolean-kind",
                    "empty-kind",
                }:
                    document = json.loads(data)
                    if change == "run-id":
                        document["run_id"] = "dev-other"
                    else:
                        document["entries"][0]["kind"] = {
                            "long-kind": "x" * 129,
                            "newline-kind": "line\nbreak",
                            "boolean-kind": False,
                            "empty-kind": "",
                        }[change]
                    data = json.dumps(document).encode()
                member.size = len(data)
            elif member.name.endswith("/cases.jsonl"):
                if change == "missing":
                    continue
                if change == "unknown":
                    member.name = "payload/dev-one/unknown.jsonl"
                elif change == "case-directory":
                    member.type = tarfile.DIRTYPE
                    member.size = 0
                    data = b""
                elif change == "case-size":
                    data += b"private synthetic input"
                    member.size = len(data)
                elif change == "duplicate-file":
                    target.addfile(member, io.BytesIO(data))
            target.addfile(member, io.BytesIO(data) if member.isreg() else None)
    replacement.replace(path)
    index = workspace / "runs/archive-index.json"
    document = json.loads(index.read_text())
    document["archives"]["dev-one"]["sha256"] = sha256(path.read_bytes()).hexdigest()
    index.write_text(json.dumps(document))
    with pytest.raises(ValueError) as failure:
        archive.restore_run(workspace, "dev-one")
    assert "private synthetic input" not in str(failure.value)
    assert not (workspace / "runs/dev-one").exists()


@pytest.mark.parametrize("target", ["archive", "index", "parent", "missing"])
def test_run_archive_keeps_path_checks(
    archived_run: tuple[Path, Path], target: str
) -> None:
    workspace, path = archived_run
    if target in {"archive", "index"}:
        if target == "index":
            path = path.parent / "archive-index.json"
        destination = path.with_suffix(".saved")
        path.rename(destination)
        path.symlink_to(destination)
    elif target == "parent":
        destination = workspace / "outside"
        path.parent.rename(destination)
        path.parent.symlink_to(destination, target_is_directory=True)
    else:
        path.unlink()
        with pytest.raises(FileNotFoundError):
            archive.restore_run(workspace, "dev-one")
        return
    with pytest.raises(ValueError):
        archive.restore_run(workspace, "dev-one")


@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "g" * 64, False])
def test_archive_rejects_invalid_committed_hash(
    archived_run: tuple[Path, Path], digest: object
) -> None:
    workspace, _ = archived_run
    index = workspace / "runs/archive-index.json"
    document = json.loads(index.read_text())
    document["archives"]["dev-one"]["sha256"] = digest
    index.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="SHA-256"):
        archive.restore_run(workspace, "dev-one")
