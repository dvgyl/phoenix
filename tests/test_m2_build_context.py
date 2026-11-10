import ast
import io
import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDED = {
    "THIRD_PARTY_NOTICES",
    "phoenix/__init__.py",
    "phoenix/ingest/__init__.py",
    "phoenix_eval/__init__.py",
    *(
        f"phoenix_eval/{name}.py"
        for name in (
            "case",
            "outcome",
            "trace",
            "tree",
            "wire",
            "worker",
        )
    ),
    *(
        f"experiments/m2_trace/{name}"
        for name in (
            "Dockerfile",
            "COPYING",
            "observer.c",
            "__init__.py",
            "trace.py",
            "worker.py",
        )
    ),
}


def test_observer_context_contains_only_required_files() -> None:
    path = ROOT / "experiments/m2_trace/Dockerfile.dockerignore"
    assert path.is_file(), "The observer needs its own restricted Docker context."
    rules = path.read_text().splitlines()
    assert rules[0] == "**"
    assert set(rules[1:]) == {"!" + name for name in NEEDED}
    assert len(rules) == len(NEEDED) + 1
    assert all((ROOT / name).is_file() for name in NEEDED)
    assert not any(
        name.startswith(("runs/", "sealed/", "holdout/", ".git/", "tools/"))
        for name in NEEDED
    )


def test_observer_context_contains_copy_inputs_and_imports() -> None:
    for line in (ROOT / "experiments/m2_trace/Dockerfile").read_text().splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        _, source, _ = line.split()
        assert source in NEEDED or any(name.startswith(source + "/") for name in NEEDED)
    for name in NEEDED:
        if not name.endswith(".py"):
            continue
        for node in ast.walk(ast.parse((ROOT / name).read_text())):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module.split(".")[0] not in {
                "phoenix",
                "phoenix_eval",
                "experiments",
            }:
                continue
            module = node.module.replace(".", "/")
            assert f"{module}.py" in NEEDED or f"{module}/__init__.py" in NEEDED


def test_production_docker_ignore_rules_are_preserved() -> None:
    assert (ROOT / ".dockerignore").read_text() == (
        "*\n!containers/\n!containers/**\n!phoenix_eval/\n!phoenix_eval/**\n"
        "!corpus_public/\n!corpus_public/**\n!tools.lock\n**/__pycache__/\n"
    )


def test_fixture_build_streams_sources_without_a_shared_mount(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    docker = tools / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'case " $* " in *" --mount "*) exit 125 ;; esac\n'
        'case " $* " in *" -i "*) ;; *) exit 125 ;; esac\n'
        'case " $* " in *" --env TMPDIR=/work "*) ;; *) exit 126 ;; esac\n'
        'cat > "$TRACE_INPUT"\n'
        'tar -cf - -C "$TRACE_RESULT" transport.ok\n'
    )
    docker.chmod(0o755)
    result = tmp_path / "result"
    result.mkdir()
    (result / "transport.ok").write_text("streamed\n")
    archive = tmp_path / "input.tar"
    output = tmp_path / "fixtures"
    completed = subprocess.run(
        ["sh", str(ROOT / "experiments/m2_trace/build-fixtures"), "image", str(output)],
        input=b"",
        capture_output=True,
        env={
            **os.environ,
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
            "TRACE_INPUT": str(archive),
            "TRACE_RESULT": str(result),
        },
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (output / "transport.ok").read_text() == "streamed\n"
    expected = {"fixture.h", "main.c", "walk.c", "cases.json", "fixture-sha256.txt"}
    with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as package:
        assert set(package.getnames()) == expected
        for name in expected:
            member = package.extractfile(name)
            assert member is not None
            assert member.read() == (ROOT / "experiments/m2_trace" / name).read_bytes()
