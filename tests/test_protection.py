import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

from phoenix_eval.protection import (
    GUARD_ENV,
    GUARD_PROBE,
    PROFILES,
    guarded_command,
    inherited_guard,
)


def test_guard_claim_requires_a_denied_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(GUARD_ENV, raising=False)
    assert not inherited_guard(tmp_path)
    marker = tmp_path / "runs" / GUARD_PROBE
    marker.parent.mkdir()
    marker.touch()
    monkeypatch.setenv(GUARD_ENV, str(marker))
    with pytest.raises(ValueError, match="did not deny"):
        inherited_guard(tmp_path)


@pytest.fixture
def layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, list[tuple[str, Path]]]:
    for key in tuple(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    root = tmp_path.resolve()
    repo = root / "phoenix"
    repo.mkdir()
    commands = (
        ("init", "-b", "main", "--separate-git-dir", str(root / "git-data")),
        (
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "test",
        ),
        ("worktree", "add", "-b", "worker", str(root / "worktrees/worker")),
    )
    for command in commands:
        subprocess.run(
            ("git", "-C", str(repo), *command), check=True, capture_output=True
        )
    probes: list[tuple[str, Path]] = []
    for category, relative in (
        ("sealed", "sealed/src"),
        ("sealed", "sealed/release"),
        ("sealed", "holdout"),
        ("sealed", "sealed_b"),
        ("sealed", "holdout_b"),
        ("sealed", "sealed_c"),
        ("sealed", "holdout_c"),
        ("records", "sealed_runs/other"),
        ("records", "sealed_work/other"),
        ("records", "runs/m1-t0-example"),
        ("prompts", "cache/phoenix/llm"),
        ("prompts", "cache/phoenix/lift"),
        ("runs", "runs/public_pipeline"),
        ("development", "dev_bin/example/gcc-O0/p.twin"),
        ("binaries", "dev_bin/example/clang-O0/sibling"),
        ("development", "adequacy_runs/example"),
        ("git", "git-data/objects/example"),
    ):
        path = root / relative
        if not relative.endswith(".twin"):
            path /= "probe"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Synthetic fixture.\n")
        probes.append((category, path))
    for checkout in (repo, root / "worktrees/worker"):
        probes.append(("git", checkout / ".git"))
        for category, relative in (
            ("development", "corpus_dev/example/src"),
            ("development", "corpus_dev/example/holdout"),
            ("development", "corpus_dev/example/tasks"),
            ("prompts", "phoenix/analyze"),
            ("prompts", "phoenix/devset"),
            ("prompts", "phoenix/generate/prompts"),
            ("public", "phoenix/ingest"),
            ("corpus", "corpus_dev/shared"),
        ):
            path = checkout / relative / "probe"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic fixture.\n")
            probes.append((category, path))
    alias = root / "alias"
    alias.symlink_to(root / "holdout/probe")
    probes.append(("sealed", alias))
    return root, repo, probes


@pytest.mark.skipif(platform.system() != "Darwin", reason="The guard uses macOS.")
@pytest.mark.parametrize("profile", tuple(PROFILES))
def test_profile_reads_and_writes(
    layout: tuple[Path, Path, list[tuple[str, Path]]], profile: str
) -> None:
    root, repo, probes = layout
    denied_categories = {
        "pipeline": {
            "sealed",
            "records",
            "development",
            "corpus",
            "git",
            "runs",
            "binaries",
        },
        "engineer": {"sealed", "records"},
        "dev-author": {"sealed", "records", "prompts", "runs"},
        "corpus-author": {"records", "prompts", "development", "corpus", "runs"},
        "evaluator": set(),
    }
    expectations = []
    for category, path in probes:
        denied = category in denied_categories[profile]
        if profile == "pipeline":
            denied = denied or path.is_relative_to(root / "cache/phoenix")
        if profile == "corpus-author" and path.is_relative_to(root):
            denied = denied or "corpus_dev" in path.parts
        expectations.append(
            (
                str(path),
                denied,
                denied
                or (profile == "evaluator" and category == "sealed")
                or (profile != "evaluator" and path.is_relative_to(root / "dev_bin")),
            )
        )
    script = """
import json,sys
from pathlib import Path
for name, read_denied, write_denied in json.loads(sys.argv[1]):
    for mode, denied in [('rb', read_denied), ('ab', write_denied)]:
        try:
            with Path(name).open(mode):
                pass
        except PermissionError:
            assert denied, (name, mode, 'unexpected denial')
        else:
            assert not denied, (name, mode, 'unexpected access')
"""
    command = guarded_command(
        root, repo, (sys.executable, "-c", script, json.dumps(expectations)), profile
    )
    result = subprocess.run(command, check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.skipif(platform.system() != "Darwin", reason="The guard uses macOS.")
def test_pipeline_allow_and_inherited_probe(
    layout: tuple[Path, Path, list[tuple[str, Path]]],
) -> None:
    root, repo, _ = layout
    own = root / "runs/evaluation" / ("a" * 64)
    own.mkdir(parents=True)
    (own / "input.elf").write_bytes(b"input")
    sibling = own.parent / "sibling"
    sibling.mkdir()
    (sibling / "input.elf").touch()
    authority = own.parent / "submissions/authorized-budget"
    authority.parent.mkdir()
    authority.write_text("Synthetic authorization.")
    replay = own / ".replay-evidence"
    replay.mkdir()
    (replay / "input.elf").touch()
    marker = own / GUARD_PROBE
    marker.touch()
    script = """
import os
import sys
from pathlib import Path
from phoenix_eval.protection import inherited_guard
root, own = map(Path, sys.argv[1:])
assert inherited_guard(root)
assert (own / 'input.elf').read_bytes() == b'input'
(own / 'checkpoint').write_bytes(b'checkpoint')
assert (own / '.replay-evidence/input.elf').read_bytes() == b''
try:
    (own / '.replay-evidence/input.elf').open('ab')
except PermissionError:
    pass
else:
    raise AssertionError('The replay input was writable.')
for path in (own.parent / 'sibling/input.elf',
             own.parent / 'submissions/authorized-budget',
             root / 'runs/public_pipeline/probe',
             root / 'sealed_runs/other/probe', root / 'sealed_work/other/probe'):
    try:
        path.read_bytes()
    except PermissionError:
        pass
    else:
        raise AssertionError(path)
for path in (own.parent, root / 'runs'):
    try:
        os.listdir(path)
    except PermissionError:
        pass
    else:
        raise AssertionError(path)
"""
    command = guarded_command(
        root,
        repo,
        (sys.executable, "-c", script, str(root), str(own)),
        "pipeline",
        (own,),
    )
    result = subprocess.run(
        command,
        env={**os.environ, GUARD_ENV: str(marker)},
        check=False,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_invalid_profile_and_allow(
    layout: tuple[Path, Path, list[tuple[str, Path]]],
) -> None:
    root, repo, _ = layout
    with pytest.raises(ValueError, match="Unknown"):
        guarded_command(root, repo, ("true",), "unknown")
    for path in (
        "sealed",
        "sealed_work/run/binary",
        "runs",
        "runs/evaluation",
        "runs/m1-t0-example/probe",
    ):
        with pytest.raises(ValueError, match="current pipeline run"):
            guarded_command(root, repo, ("true",), "pipeline", (root / path,))
