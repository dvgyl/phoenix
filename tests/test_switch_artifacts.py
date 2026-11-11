import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from test_recovery_switches import switch_fixture
from test_recovery_u1 import fake_install, fixture, mapping_wire, raw_json

from phoenix.lift import lift_binary
from phoenix.lift.mapping import (
    MappingError,
    load_json,
    read_companion,
    read_generation,
)
from phoenix.lift.switch_artifacts import read_switch_bundle
from phoenix.recover.switches import recover_switch


def test_switch_bundle_binds_one_graph_and_keeps_its_case_map(tmp_path: Path) -> None:
    binary, lift, proof, graph = switch_fixture("duplicate")
    raw = raw_json(graph)
    name = "graph-100100.json"
    (tmp_path / name).write_bytes(raw)
    manifest = raw_json(
        {
            "schema_version": 1,
            "binary_sha256": lift.binary_sha256,
            "lift_sha256": lift.lift_sha256,
            "graphs": [
                {
                    "function": graph["function"],
                    "file": name,
                    "sha256": sha256(raw).hexdigest(),
                }
            ],
            "gaps": [
                {
                    "function": {"space": "ram", "offset": "0x100140"},
                    "reason": "normalize_unavailable",
                }
            ],
        }
    )
    (tmp_path / "manifest.json").write_bytes(manifest)
    bundle = read_switch_bundle(tmp_path, lift)
    (checked,) = bundle.graphs
    assert bundle.manifest_sha256 == sha256(manifest).hexdigest()
    assert bundle.gaps == ((0x100140, "normalize_unavailable"),)
    assert [
        (c.selector, c.target)
        for c in recover_switch(checked, binary, lift, proof).cases
    ] == [
        (0, 0x118),
        (1, 0x118),
    ]


@pytest.mark.parametrize(
    "fault",
    [
        "file-bytes",
        "missing",
        "extra",
        "path",
        "alias",
        "duplicate",
        "gap",
        "identity",
        "size",
    ],
)
def test_switch_bundle_rejects_changed_or_unavailable_evidence(
    tmp_path: Path, fault: str
) -> None:
    _, lift, _, graph = switch_fixture()
    raw = raw_json(graph)
    name = "graph-100100.json"
    graph_file = tmp_path / name
    graph_file.write_bytes(raw)
    entry = {
        "function": graph["function"],
        "file": name,
        "sha256": sha256(raw).hexdigest(),
    }
    manifest = {
        "schema_version": 1,
        "binary_sha256": lift.binary_sha256,
        "lift_sha256": lift.lift_sha256,
        "graphs": [entry],
        "gaps": [],
    }
    if fault == "file-bytes":
        graph_file.write_bytes(raw + b"\n")
    elif fault == "missing":
        graph_file.unlink()
    elif fault == "extra":
        (tmp_path / "extra.json").write_bytes(b"{}")
    elif fault == "path":
        entry["file"] = f"../{name}"
    elif fault == "alias":
        old = graph_file.rename(tmp_path / "original")
        graph_file.symlink_to(old)
    elif fault == "duplicate":
        manifest["gaps"] = [
            {"function": graph["function"], "reason": "normalize_unavailable"}
        ]
    elif fault == "gap":
        manifest["gaps"] = [
            {
                "function": {"space": "ram", "offset": "0x100140"},
                "reason": "unsupported",
            }
        ]
    elif fault == "identity":
        manifest["binary_sha256"] = "0" * 64
    elif fault == "size":
        graph_file.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    (tmp_path / "manifest.json").write_bytes(raw_json(manifest))
    with pytest.raises(MappingError):
        read_switch_bundle(tmp_path, lift)


def test_launcher_publishes_only_complete_switch_generations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, document = fixture()
    binary, installation, java = fake_install(tmp_path, "")
    binary.write_bytes(original)
    ordinary_lift = raw_json(document)
    raw = ordinary_lift
    incomplete = False

    def launch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        scripts = [
            args[index + 1]
            for index, value in enumerate(args)
            if value == "-postScript"
        ]
        post = args.index("-postScript")
        assert scripts[:2] == ["ExportLift.java", "ExportMapping.java"]
        Path(args[post + 2]).write_bytes(raw)
        Path(args[post + 5]).write_bytes(raw_json(mapping_wire(original, raw)))
        if len(scripts) == 3:
            assert scripts[2] == "ExportSwitchGraphs.java"
            assert args[post + 10] == args[post + 2]
            switches = Path(args[post + 9])
            switches.mkdir()
            if not incomplete:
                (switches / "manifest.json").write_bytes(
                    raw_json(
                        {
                            "schema_version": 1,
                            "binary_sha256": sha256(original).hexdigest(),
                            "lift_sha256": sha256(raw).hexdigest(),
                            "graphs": [],
                            "gaps": [],
                        }
                    )
                )
        return subprocess.CompletedProcess(args, 0, "Public Ghidra control.")

    monkeypatch.setattr("phoenix.lift.subprocess.run", launch)
    output = tmp_path / "published" / "lift.json"
    with pytest.raises(ValueError, match="require a mapping companion"):
        lift_binary(binary, output, installation, java, switch_graphs=True)
    old = lift_binary(binary, output, installation, java, mapping_companion=True)
    assert read_generation(old.export_path.parent, original).switches is None
    assert not (old.export_path.parent / "switches").exists()
    incomplete = True
    raw = ordinary_lift + b"\n"
    with pytest.raises(MappingError, match="switch evidence file"):
        lift_binary(
            binary,
            output,
            installation,
            java,
            mapping_companion=True,
            switch_graphs=True,
        )
    assert read_companion(output.parent, original)[0] == ordinary_lift

    incomplete = False
    new = lift_binary(
        binary, output, installation, java, mapping_companion=True, switch_graphs=True
    )
    generation = new.export_path.parent
    manifest = generation / "switches" / "manifest.json"
    record = load_json((generation / "evidence-commit.json").read_bytes())
    evidence = read_generation(generation, original)
    assert evidence.switches is not None
    assert record == {
        "schema_version": 2,
        "lift_sha256": sha256(raw).hexdigest(),
        "mapping_sha256": sha256(
            (generation / "mapping.json").read_bytes()
        ).hexdigest(),
        "switch_manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
    }
    assert read_companion(output.parent, original)[0] == raw
    assert read_generation(old.export_path.parent, original).lift == ordinary_lift
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(MappingError, match="manifest differs"):
        read_companion(output.parent, original)
