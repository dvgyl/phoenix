import json
import os
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Request, Usage
from phoenix_eval.model_ledger import summarize
from phoenix_eval.run_records import capture_ledger, read_ledger


class Provider:
    name = "synthetic"

    def __init__(self, text: str) -> None:
        self.text = text

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: Request) -> Completion:
        return Completion(self.text, Usage(5, 2, 3), request.model)


def publication(workspace: Path, text: str = "synthetic") -> tuple[Ledger, Path, bytes]:
    ledger = Ledger(workspace / "runs/pipeline")
    ledger.call("case", Request("fixture"), Provider(text))
    run = workspace / "evaluation"
    run.mkdir()
    snapshot = capture_ledger(workspace, run, "pipeline")
    assert summarize(snapshot.events, "case").cost_nanodollars == 36_200
    return ledger, run, snapshot.content


def test_snapshot_hashes_complete_large_file(tmp_path: Path) -> None:
    ledger, run, content = publication(tmp_path, "synthetic\n" * 200_000)
    identity = json.loads((run / "published-ledger.json").read_bytes())
    assert content == ledger.path.read_bytes()
    assert identity == {
        "pipeline_run": "pipeline",
        "bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }
    assert "synthetic" not in (run / "published-ledger.json").read_text()
    assert read_ledger(tmp_path, run).content == content


@pytest.mark.parametrize("content", [b"{}", b"[]", b" " * 4097])
def test_malformed_events_cannot_be_published(tmp_path: Path, content: bytes) -> None:
    ledger = tmp_path / "runs/pipeline/llm.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(content)
    run = tmp_path / "evaluation"
    run.mkdir()
    with pytest.raises(ValueError):
        capture_ledger(tmp_path, run, "pipeline")
    assert not (run / "published-ledger.json").exists()


@pytest.mark.parametrize("target", ["live", "snapshot"])
@pytest.mark.parametrize("kind", ["symlink", "cycle", "directory", "fifo"])
def test_unsafe_ledger_paths_are_rejected(
    tmp_path: Path, target: str, kind: str
) -> None:
    ledger, run, _ = publication(tmp_path)
    path = ledger.path if target == "live" else run / "published-ledger.jsonl"
    original = path.with_suffix(".saved")
    path.rename(original)
    if kind == "symlink":
        path.symlink_to(original)
    elif kind == "cycle":
        path.symlink_to(path.name)
    elif kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    with pytest.raises(ValueError, match="symbolic link|regular file"):
        read_ledger(tmp_path, run).content
    if target == "live":
        with pytest.raises(ValueError, match="symbolic link|regular file"):
            capture_ledger(tmp_path, run, "pipeline")


@pytest.mark.parametrize("target", ["live", "snapshot"])
@pytest.mark.parametrize("change", ["replace", "truncate", "empty", "missing"])
def test_published_prefix_cannot_change_or_disappear(
    tmp_path: Path, target: str, change: str
) -> None:
    ledger, run, content = publication(tmp_path)
    path = ledger.path if target == "live" else run / "published-ledger.jsonl"
    if change == "replace":
        path.write_bytes(content.replace(b"synthetic", b"different"))
    elif change == "truncate":
        path.write_bytes(content.splitlines(keepends=True)[0])
    elif change == "empty":
        path.write_bytes(b"")
    else:
        path.unlink()
    with pytest.raises(ValueError, match="changed|published prefix|missing"):
        read_ledger(tmp_path, run).content
    with pytest.raises(ValueError):
        capture_ledger(tmp_path, run, "pipeline")


@pytest.mark.parametrize("field,value", [("bytes", 0), ("sha256", "0" * 64)])
def test_snapshot_metadata_must_match_published_bytes(
    tmp_path: Path, field: str, value: object
) -> None:
    _, run, _ = publication(tmp_path)
    path = run / "published-ledger.json"
    identity = json.loads(path.read_bytes())
    identity[field] = value
    path.write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="published model ledger changed"):
        read_ledger(tmp_path, run).content
