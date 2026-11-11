import io
import json
import tarfile
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix_eval import corpus
from phoenix_eval.case import Invocation
from phoenix_eval.corpus import (
    CorpusError,
    Tier,
    heldout_cases,
    manifest_variants,
    release_manifest,
)
from phoenix_eval.wire import encode_invocation


def metadata() -> list[dict[str, object]]:
    return [
        {
            "name": f"case-{index}",
            "tier": "T1",
            "compiler": compiler,
            "flags": [flag],
            "sha256": sha256(b"opaque fixture").hexdigest(),
            "category": "synthetic",
        }
        for index in range(15)
        for compiler in ("gcc", "clang")
        for flag in ("-O0", "-O2", "-Os")
    ]


@pytest.fixture
def release(tmp_path: Path) -> Path:
    root = tmp_path / "release"
    root.mkdir()
    data = json.dumps(metadata()).encode()
    (root / "manifest.json").write_bytes(data)
    for variant in manifest_variants(data, Tier.T1):
        path = variant.executable(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"opaque fixture")
    return root


def test_t1_manifest_checks_all_binary_hashes(release: Path) -> None:
    variants, digest = release_manifest(release, Tier.T1)
    assert len(variants) == 90
    assert digest == sha256((release / "manifest.json").read_bytes()).hexdigest()
    for variant in variants:
        path = variant.executable(release)
        path.write_bytes(b"changed fixture")
        with pytest.raises(CorpusError, match="manifest hash"):
            release_manifest(release, Tier.T1)
        path.write_bytes(b"opaque fixture")


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "../bad"),
        ("name", 1),
        ("tier", "T0"),
        ("compiler", "other"),
        ("flags", ["-O1"]),
        ("flags", "-O0"),
        ("sha256", "a" * 63),
        ("category", ""),
        ("category", "x" * 129),
        ("category", "line\nbreak"),
        ("category", False),
    ],
)
def test_manifest_rejects_invalid_fields(field: str, value: object) -> None:
    records = metadata()
    records[0][field] = value
    with pytest.raises(CorpusError):
        manifest_variants(json.dumps(records).encode(), Tier.T1)


@given(st.integers(min_value=0, max_value=89))
def test_manifest_rejects_each_missing_variant(index: int) -> None:
    records = metadata()
    records.pop(index)
    with pytest.raises(CorpusError):
        manifest_variants(json.dumps(records).encode(), Tier.T1)


@given(st.text(min_size=1).filter(lambda key: key not in metadata()[0]))
def test_manifest_rejects_unknown_fields(key: str) -> None:
    records = metadata()
    records[0][key] = "opaque fixture"
    with pytest.raises(CorpusError):
        manifest_variants(json.dumps(records).encode(), Tier.T1)


def test_manifest_rejects_duplicate_fields_and_roster() -> None:
    data = json.dumps(metadata()).replace(
        '"tier": "T1"', '"tier": "T0", "tier": "T1"', 1
    )
    with pytest.raises(CorpusError):
        manifest_variants(data.encode(), Tier.T1)
    records = metadata()
    records[0] = records[1]
    with pytest.raises(CorpusError, match="every required"):
        manifest_variants(json.dumps(records).encode(), Tier.T1)


@pytest.mark.parametrize(
    "target",
    ["manifest", "binary", "parent", "missing", "manifest_size", "binary_size"],
)
def test_release_keeps_path_and_size_limits(
    release: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    variant = manifest_variants((release / "manifest.json").read_bytes(), Tier.T1)[0]
    path = variant.executable(release)
    if target == "manifest":
        path = release / "manifest.json"
    if target in ("manifest", "binary"):
        destination = path.with_suffix(".saved")
        path.rename(destination)
        path.symlink_to(destination)
    elif target == "parent":
        destination = path.parent.with_name("saved")
        path.parent.rename(destination)
        path.parent.symlink_to(destination, target_is_directory=True)
    elif target == "missing":
        path.unlink()
    elif target == "manifest_size":
        (release / "manifest.json").write_bytes(b" " * (65536 + 1))
    else:
        monkeypatch.setattr(corpus, "MAX_PROGRAM_BYTES", 2)
    with pytest.raises(CorpusError):
        release_manifest(release, Tier.T1)


def archive(path: Path, entries: list[tuple[str, bytes, bytes]]) -> str:
    with tarfile.open(path, "w:gz") as package:
        for name, content, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = (
                "t1/cases/case-0.jsonl"
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE)
                else ""
            )
            member.size = len(content) if kind == tarfile.REGTYPE else 0
            package.addfile(member, io.BytesIO(content))
    return sha256(path.read_bytes()).hexdigest()


def test_tier_archives_keep_names_separate(tmp_path: Path) -> None:
    path = tmp_path / "inputs.tar.gz"
    for tier in Tier:
        case = Invocation(stdin=tier.encode())
        digest = archive(
            path,
            [
                (
                    f"{tier.lower()}/cases/case-0.jsonl",
                    encode_invocation(case).encode(),
                    tarfile.REGTYPE,
                )
            ],
        )
        assert heldout_cases(path, digest, {"case-0"}, tier=tier) == {"case-0": (case,)}
        other = Tier.T1 if tier is Tier.T0 else Tier.T0
        with pytest.raises(CorpusError):
            heldout_cases(path, digest, {"case-0"}, tier=other)


@pytest.mark.parametrize(
    "name",
    [
        "t0/cases/case-0.jsonl",
        "../t1/cases/case-0.jsonl",
        "/t1/cases/case-0.jsonl",
        "t1/cases/../case-0.jsonl",
        "t1/cases/unknown.jsonl",
    ],
)
def test_archive_rejects_paths(tmp_path: Path, name: str) -> None:
    path = tmp_path / "inputs.tar.gz"
    digest = archive(
        path, [(name, encode_invocation(Invocation()).encode(), tarfile.REGTYPE)]
    )
    with pytest.raises(CorpusError):
        heldout_cases(path, digest, {"case-0"}, tier=Tier.T1)


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.DIRTYPE]
)
def test_archive_rejects_nonregular_cases(tmp_path: Path, kind: bytes) -> None:
    path = tmp_path / "inputs.tar.gz"
    digest = archive(path, [("t1/cases/case-0.jsonl", b"", kind)])
    with pytest.raises(CorpusError):
        heldout_cases(path, digest, {"case-0"}, tier=Tier.T1)


@pytest.mark.parametrize("directory", [False, True])
def test_archive_rejects_duplicate_members(tmp_path: Path, directory: bool) -> None:
    path = tmp_path / "inputs.tar.gz"
    entry = (
        ("t1/cases", b"", tarfile.DIRTYPE)
        if directory
        else (
            "t1/cases/case-0.jsonl",
            encode_invocation(Invocation()).encode(),
            tarfile.REGTYPE,
        )
    )
    digest = archive(path, [entry, entry])
    with pytest.raises(CorpusError):
        heldout_cases(path, digest, {"case-0"}, tier=Tier.T1)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "unknown",
        "tree",
        "entry",
        "duplicate",
        "count",
        "file_size",
        "archive_size",
        "symlink",
        "hash",
    ],
)
def test_archive_rejects_incomplete_or_unbounded_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    path = tmp_path / "inputs.tar.gz"
    data = json.loads(encode_invocation(Invocation()))
    if change == "unknown":
        data["unknown"] = 1
    elif change == "tree":
        data["tree"]["unknown"] = 1
    elif change == "entry":
        data["tree"]["entries"] = [{"unknown": 1}]
    content = json.dumps(data).encode()
    if change == "duplicate":
        content = content.replace(b'"args": []', b'"args": [], "args": []')
    if change == "count":
        monkeypatch.setattr(corpus, "_CASE_COUNT_LIMIT", 1)
        content = content + b"\n" + content
    if change == "file_size":
        monkeypatch.setattr(corpus, "_CASE_FILE_LIMIT", 1)
    if change == "archive_size":
        monkeypatch.setattr(corpus, "_ARCHIVE_LIMIT", 1)
    digest = archive(path, [("t1/cases/case-0.jsonl", content, tarfile.REGTYPE)])
    if change == "symlink":
        destination = path.with_suffix(".saved")
        path.rename(destination)
        path.symlink_to(destination)
    if change == "hash":
        digest = "0" * 64
    names = {"case-0", "case-1"} if change == "missing" else {"case-0"}
    with pytest.raises(CorpusError):
        heldout_cases(path, digest, names, tier=Tier.T1)
