import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix_eval import dev_corpus as dc
from phoenix_eval import run_plan
from phoenix_eval.run_records import Selection


def metadata() -> list[dict[str, object]]:
    return [
        asdict(
            dc.DevBinary(
                name,
                "D0",
                compiler,
                ("-std=c11", f"-{level}", "-lm"),
                sha256(f"{name}-{compiler}-{level}".encode()).hexdigest(),
                "synthetic",
                False,
            )
        )
        for name in ("case_alpha", "case_beta")
        for compiler in dc.COMPILERS
        for level in dc.LEVELS
    ]


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    path = tmp_path / "dev_bin/manifest.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"binaries": metadata()}))
    for binary in dc.read_manifest(path):
        target = path.parent / binary.name / binary.key / binary.name
        target.parent.mkdir(parents=True)
        target.write_bytes(f"{binary.name}-{binary.compiler}-{binary.level}".encode())
    return path


def test_manifest_binds_every_variant_to_its_hash(manifest: Path) -> None:
    binaries = dc.read_manifest(manifest)
    assert len(binaries) == 16
    original = dc.corpus_hash(manifest.parents[1], binaries)
    for binary in binaries:
        path = dc.binary_path(manifest.parents[1], binary)
        content = path.read_bytes()
        assert sha256(content).hexdigest() == binary.sha256
        path.write_bytes(b"changed fixture")
        with pytest.raises(ValueError, match="hash or path changed"):
            dc.corpus_hash(manifest.parents[1], binaries)
        path.write_bytes(content)
    assert dc.corpus_hash(manifest.parents[1], binaries) == original


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
        ("category", False),
        ("twin_valid", 1),
    ],
)
def test_manifest_rejects_invalid_fields(
    manifest: Path, field: str, value: object
) -> None:
    records = metadata()
    records[0][field] = value
    manifest.write_text(json.dumps({"binaries": records}))
    with pytest.raises(ValueError):
        dc.read_manifest(manifest)


@given(st.text(min_size=1).filter(lambda key: key not in metadata()[0]))
def test_manifest_rejects_unknown_fields(key: str) -> None:
    records = metadata()
    records[0][key] = "opaque fixture"
    with TemporaryDirectory() as name:
        manifest = Path(name) / "manifest.json"
        manifest.write_text(json.dumps({"binaries": records}))
        with pytest.raises(ValueError, match="manifest fields"):
            dc.read_manifest(manifest)


def test_manifest_rejects_duplicate_roster(manifest: Path) -> None:
    records = metadata()
    records[0] = records[1]
    manifest.write_text(json.dumps({"binaries": records}))
    with pytest.raises(ValueError, match="repeats"):
        dc.read_manifest(manifest)


@pytest.mark.parametrize("index", range(16))
def test_selection_rejects_each_missing_accepted_variant(
    manifest: Path, monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    workspace = manifest.parents[1]
    corpus = workspace / "corpus_dev"
    corpus.mkdir()
    binaries = dc.read_manifest(manifest)
    (corpus / "accepted.json").write_text(
        json.dumps(
            {
                "corpus_hash": dc.corpus_hash(workspace, binaries),
                "heldout_hash": "a" * 64,
            }
        )
    )
    monkeypatch.setattr(run_plan, "CHECKOUT", workspace)
    monkeypatch.setattr(run_plan, "heldout_hash", lambda *_: "a" * 64)
    assert len(run_plan._selection(workspace, Selection())[0]) == 12
    records = metadata()
    records.pop(index)
    manifest.write_text(json.dumps({"binaries": records}))
    with pytest.raises(ValueError, match="differs from its acceptance record"):
        run_plan._selection(workspace, Selection())


@pytest.mark.parametrize("target", ["binary", "parent", "missing"])
def test_binary_keeps_path_checks(manifest: Path, target: str) -> None:
    workspace = manifest.parents[1]
    binary = dc.read_manifest(manifest)[0]
    path = dc.binary_path(workspace, binary)
    if target == "binary":
        destination = path.with_suffix(".saved")
        path.rename(destination)
        path.symlink_to(destination)
    elif target == "parent":
        destination = workspace / "outside"
        path.parent.rename(destination)
        path.parent.symlink_to(destination, target_is_directory=True)
    else:
        path.unlink()
    with pytest.raises(ValueError):
        dc.binary_path(workspace, binary)
