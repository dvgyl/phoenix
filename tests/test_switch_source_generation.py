import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from test_recovery_u1 import fake_install, fixture, loc, mapping_wire, raw_json

from phoenix.lift import lift_binary
from phoenix.lift.mapping import (
    MappingError,
    load_json,
    read_companion,
    read_generation,
)


def test_switch_source_selects_only_a_bound_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, document = fixture()
    binary, ghidra, java = fake_install(tmp_path, "")
    binary.write_bytes(original)
    lift = raw_json(document)
    fault = ""

    def launch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        lift_index = args.index("ExportLift.java")
        staged = Path(args[lift_index + 1])
        staged.write_bytes(lift)
        mapping = Path(args[args.index("ExportMapping.java") + 1])
        mapping.write_bytes(raw_json(mapping_wire(original, lift)))
        graphs = Path(args[args.index("ExportSwitchGraphs.java") + 1])
        graphs.mkdir()
        shared: dict[str, Any] = {
            "schema_version": 1,
            "binary_sha256": sha256(original).hexdigest(),
            "lift_sha256": sha256(lift).hexdigest(),
            "gaps": [],
        }
        (graphs / "manifest.json").write_bytes(raw_json({**shared, "graphs": []}))
        if args[lift_index + 2] != "-postScript" and fault != "missing":
            ordinary = Path(args[lift_index + 2])
            record = {**shared, "bodies": []}
            if fault == "roster":
                record["gaps"] = [
                    {"function": loc(0x100100), "reason": "ordinary_source_unavailable"}
                ]
            ordinary.write_bytes(raw_json(record))
            if fault == "alias":
                (tmp_path / "ordinary-alias").hardlink_to(ordinary)
        return subprocess.CompletedProcess(args, 0, "Public lift control.")

    monkeypatch.setattr("phoenix.lift.subprocess.run", launch)
    output = tmp_path / "published" / "lift.json"
    with pytest.raises(ValueError, match="requires switch graphs"):
        lift_binary(
            binary, output, ghidra, java, mapping_companion=True, switch_source=True
        )
    old = lift_binary(
        binary, output, ghidra, java, mapping_companion=True, switch_graphs=True
    )
    old_generation = old.export_path.parent
    selector = output.parent / "evidence-current"
    selected = selector.read_bytes()
    old_evidence = read_generation(old_generation, original)
    assert old_evidence.switches is not None and old_evidence.ordinary_switches is None

    for change, error in (
        ("missing", "Cannot read"),
        ("roster", "scopes differ"),
        ("alias", "hard-link alias"),
    ):
        fault = change
        with pytest.raises(MappingError, match=error):
            lift_binary(
                binary,
                output,
                ghidra,
                java,
                mapping_companion=True,
                switch_graphs=True,
                switch_source=True,
            )
        assert selector.read_bytes() == selected
        assert read_companion(output.parent, original)[0] == lift

    fault = ""
    published = lift_binary(
        binary,
        output,
        ghidra,
        java,
        mapping_companion=True,
        switch_graphs=True,
        switch_source=True,
    )
    generation = published.export_path.parent
    assert selector.read_bytes() != selected
    new_evidence = read_generation(generation, original)
    assert new_evidence.ordinary_switches is not None
    commit_path = generation / "evidence-commit.json"
    saved_commit = commit_path.read_bytes()
    record = load_json(saved_commit)
    assert isinstance(record, dict)
    assert record["schema_version"] == 3
    assert record["ordinary_switch_sha256"] == new_evidence.ordinary_switches.sha256
    assert read_generation(old_generation, original) == old_evidence

    graph_only = {**record, "schema_version": 2}
    del graph_only["ordinary_switch_sha256"]
    commit_path.write_bytes(raw_json(graph_only))
    with pytest.raises(MappingError, match="does not admit switch source"):
        read_generation(generation, original)
    commit_path.write_bytes(saved_commit)

    ordinary = generation / "ordinary-switches.json"
    ordinary.write_bytes(ordinary.read_bytes() + b"\n")
    with pytest.raises(MappingError, match="artifact differs"):
        read_generation(generation, original)
