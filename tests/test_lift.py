import json
import os
from pathlib import Path

import pytest

from phoenix.lift import LiftError, lift_binary


def fake_install(tmp_path: Path, script: str) -> tuple[Path, Path, Path]:
    installation = tmp_path / "Ghidra install"
    launcher = installation / "support" / "analyzeHeadless"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(f"#!/bin/sh\nset -eu\n{script}\n", encoding="utf-8")
    launcher.chmod(0o755)
    java_home = tmp_path / "Java home"
    java = java_home / "bin" / "java"
    java.parent.mkdir(parents=True)
    java.touch()
    binary = tmp_path / "fixture with spaces.elf"
    binary.write_bytes(b"public fixture")
    return binary, installation, java_home


def test_lift_publishes_the_headless_export(tmp_path: Path) -> None:
    binary, installation, java_home = fake_install(
        tmp_path,
        """
        test "$(command -v java)" = "$JAVA_HOME/bin/java"
        while [ "$1" != "-import" ]; do shift; done
        test "$(cat "$2")" = "public fixture"
        shift 2
        test "$1" = "-readOnly"
        while [ "$1" != "-postScript" ]; do shift; done
        test "$2" = "ExportLift.java"
        printf '%s\n' '{"schema_version":1}' > "$3"
        """,
    )
    (java_home / "bin" / "java").chmod(0o755)
    output = tmp_path / "new run" / "lift.json"

    result = lift_binary(binary, output, installation, java_home)

    assert result.export_path == output
    assert json.loads(output.read_text(encoding="utf-8")) == {"schema_version": 1}
    assert binary.read_bytes() == b"public fixture"


@pytest.mark.parametrize(
    "script",
    [
        "echo 'post-script failed'; exit 0",
        """
        for output do :; done
        printf '{}' > "$output"
        echo 'post-script failed'
        exit 1
        """,
    ],
)
def test_failed_lift_keeps_previous_export(tmp_path: Path, script: str) -> None:
    binary, installation, java_home = fake_install(tmp_path, script)
    output = tmp_path / "lift.json"
    output.write_bytes(b"previous export")

    with pytest.raises(LiftError, match="post-script failed"):
        lift_binary(binary, output, installation, java_home)

    assert output.read_bytes() == b"previous export"


def test_lift_rejects_binary_as_output(tmp_path: Path) -> None:
    binary, installation, java_home = fake_install(tmp_path, "exit 1")
    alias = tmp_path / "alias"
    alias.symlink_to(binary)

    with pytest.raises(ValueError, match="output path"):
        lift_binary(binary, alias, installation, java_home)

    assert binary.read_bytes() == b"public fixture"


def test_headless_bitstats(tmp_path: Path) -> None:
    fixture = os.environ.get("PHOENIX_LIFT_FIXTURE")
    if fixture is None:
        pytest.skip("Set PHOENIX_LIFT_FIXTURE to the public bitstats ELF path.")
    binary = Path(fixture)
    installation = Path(os.environ["PHOENIX_LIFT_GHIDRA"])
    java_home = Path(os.environ["PHOENIX_LIFT_JAVA"])
    result = lift_binary(
        binary,
        tmp_path / ".new run" / "lift.json",
        installation,
        java_home,
    )
    export = json.loads(result.export_path.read_text(encoding="utf-8"))

    assert export["schema_version"] == 1
    assert export["image_base"]["space"] == "ram"
    assert int(export["image_base"]["offset"], 16) >= 0
    getenv = next(
        item["address"] for item in export["imports"] if item["name"] == "getenv"
    )
    usage = next(
        item["address"]
        for item in export["strings"]
        if item["value"] == "use sum or count\n"
    )
    usage_sites = [
        ref["from"] for ref in export["data_references"] if ref["to"] == usage
    ]
    function = next(
        fn
        for fn in export["functions"]
        if any(ins["address"] in usage_sites for ins in fn["instructions"])
    )
    assert export["main"]["entry"] == function["entry"]
    assert any(
        edge["caller"] == export["main"]["startup"]
        and edge["site"] == export["main"]["call"]
        for edge in export["call_edges"]
    )

    decompilation = function["decompilation"]
    assert decompilation["status"] == "ok"
    assert "getenv(" in decompilation["raw_c"]
    assert any(
        op["opcode"] == "CALL" and op["sequence"]["address"] == ins["address"]
        for ins in function["instructions"]
        for op in ins["pcode"]
    )
    analyzed = decompilation["analyzed_pcode"]
    assert any(
        stmt["operation"] == op["sequence"]
        for stmt in decompilation["statements"]
        for op in analyzed
        if op["opcode"] == "CALL"
    )
    assert any(
        edge["from_block"]["space"] == edge["to_block"]["space"]
        and int(edge["from_block"]["offset"], 16) >= int(edge["to_block"]["offset"], 16)
        for edge in function["flow_edges"]
    )
    getenv_targets = [getenv] + [
        fn["entry"] for fn in export["functions"] if fn["thunk_target"] == getenv
    ]
    assert any(
        edge["caller"] == function["entry"] and edge["target"] in getenv_targets
        for edge in export["call_edges"]
    )

    init = next(fn["entry"] for fn in export["functions"] if fn["name"] == "_DT_INIT")
    call = next(
        edge
        for edge in export["call_edges"]
        if edge["caller"] == init and edge["indirect"]
    )
    assert call["target"] is not None
    original = binary.read_bytes()
    pattern = bytes.fromhex("ffd04883c408c3")
    assert original.count(pattern) == 1
    unknown_call = tmp_path / "bitstats-unknown-call.elf"
    # RCX has no known value at this call. RAX holds the original import pointer.
    unknown_call.write_bytes(original.replace(pattern, bytes.fromhex("ffd14883c408c3")))
    result = lift_binary(
        unknown_call, tmp_path / "unknown-call.json", installation, java_home
    )
    modified = json.loads(result.export_path.read_text(encoding="utf-8"))
    assert any(
        edge["site"] == call["site"] and edge["indirect"] and edge["target"] is None
        for edge in modified["call_edges"]
    )
