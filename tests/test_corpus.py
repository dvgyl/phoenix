import io
import json
import tarfile
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix_eval.case import Invocation
from phoenix_eval.corpus import CorpusError, committed_hash, heldout_cases, t0_manifest
from phoenix_eval.wire import encode_invocation


@pytest.fixture
def release(tmp_path: Path) -> Path:
    manifest = []
    for index in range(10):
        name = f"case-{index}"
        for compiler in ("gcc", "clang"):
            for flag in ("-O0", "-O2"):
                binary = tmp_path / name / compiler / f"{flag[1:]}.elf"
                binary.parent.mkdir(parents=True, exist_ok=True)
                data = f"{name}-{compiler}-{flag}".encode("ascii")
                binary.write_bytes(data)
                manifest.append(
                    {
                        "name": name,
                        "tier": "T0",
                        "compiler": compiler,
                        "flags": [flag],
                        "sha256": sha256(data).hexdigest(),
                        "category": "fixture",
                    }
                )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_release_binds_every_variant_to_its_hash(release: Path) -> None:
    variants, digest = t0_manifest(release)
    assert len(variants) == 40
    assert digest == sha256((release / "manifest.json").read_bytes()).hexdigest()
    binary = variants[0].executable(release)
    binary.write_bytes(b"changed")
    with pytest.raises(CorpusError, match="manifest hash"):
        t0_manifest(release)


def test_release_rejects_a_duplicate_variant(release: Path) -> None:
    file = release / "manifest.json"
    records = json.loads(file.read_text())
    records[0] = records[1]
    file.write_text(json.dumps(records))
    with pytest.raises(CorpusError, match="every required variant"):
        t0_manifest(release)


def _archive(path: Path, name: str, content: bytes) -> str:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(content))
    return sha256(path.read_bytes()).hexdigest()


def test_reads_cases_only_from_the_committed_archive(tmp_path: Path) -> None:
    archive = tmp_path / "inputs.tar.gz"
    case = Invocation(("synthetic",), b"input")
    digest = _archive(
        archive, "t0/cases/case-0.jsonl", encode_invocation(case).encode()
    )
    commitments = tmp_path / "commitments.md"
    commitments.write_text(f"| `inputs.tar.gz` | `{digest}` |\n")
    assert committed_hash(commitments, archive.name) == digest
    assert heldout_cases(archive, digest, {"case-0"}) == {"case-0": (case,)}
    with pytest.raises(CorpusError, match="match its commitment"):
        heldout_cases(archive, "0" * 64, {"case-0"})


@pytest.mark.parametrize(
    ("member", "content"),
    (("../fixture", b"{}"), ("t0/cases/case-0.jsonl", b"private synthetic input")),
)
def test_archive_errors_do_not_expose_case_data(
    tmp_path: Path, member: str, content: bytes
) -> None:
    archive = tmp_path / "inputs.tar.gz"
    digest = _archive(archive, member, content)
    with pytest.raises(CorpusError, match="invalid case set") as failure:
        heldout_cases(archive, digest, {"case-0"})
    assert content.decode() not in str(failure.value)
