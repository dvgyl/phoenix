"""Synthetic transaction controls do not prove printer origin or live behavior."""

import errno
import json
import os
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, fields, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from test_byte_graph import sample, wire
from test_byte_source import source_sample
from test_lift_evidence import wire as static_evidence_wire
from test_recovery_u1 import mapping_wire

from phoenix.lift import byte_export as exporter
from phoenix.lift.byte_export import (
    ByteExportError,
    ByteExportLimits,
    UnpublishedByteExport,
    convert_byte_export,
    export_byte_diagnostic,
)
from phoenix.lift.byte_graph import ByteGraphLimits
from phoenix.lift.byte_source import ByteSourceLimits
from phoenix.lift.evidence import EvidenceError, parse_static_evidence
from phoenix.lift.index import LiftIndex, parse_lift
from phoenix.lift.mapping import parse_mapping


def diagnostic_sample() -> tuple[bytes, bytes, bytes, dict[str, Any], dict[str, Any]]:
    binary, document, graph = sample()
    source, _, _ = source_sample()
    graph["export_gaps"] = []
    lift = wire(document)
    context: dict[str, Any] = {
        "schema": 1,
        "binary_sha256": sha256(binary).hexdigest(),
        "ghidra_version": "12.2",
        "ghidra_revision": "8ca9077040cc43cd790babcfccf19475622a3e9a",
        "java_runtime_version": "25.0.5+8-LTS",
        "sources": {"synthetic": "1" * 64},
        "tools": {"synthetic": "2" * 64},
        "limits": asdict(ByteExportLimits()),
    }
    records = []
    for ordinal, function in enumerate(document["functions"]):
        key = {
            "binary_sha256": sha256(binary).hexdigest(),
            "ghidra_entry": function["entry"]["offset"],
        }
        retained_pass = {
            "schema": 1,
            "function": key,
            "call_ordinal": ordinal,
            "ghidra_version": context["ghidra_version"],
            "ghidra_revision": context["ghidra_revision"],
            "language_id": "x86:LE:64:default",
            "compiler_spec_id": "gcc",
            "simplification_style": "decompile",
            "configured_options": None,
            "timeout_seconds": 60,
            "source_manifest_sha256": sha256(wire(context["sources"])).hexdigest(),
            "tool_manifest_sha256": sha256(wire(context["tools"])).hexdigest(),
        }
        pass_id = sha256(wire(retained_pass)).hexdigest()
        if ordinal == 0:
            for item in (graph, source):
                del item["lift_sha256"]
            graph = json.loads(wire(graph).replace(b"a" * 64, pass_id.encode()))
            source = json.loads(wire(source).replace(b"a" * 64, pass_id.encode()))
            facts = {
                "value_flags": [
                    {
                        "id": value["id"],
                        "is_input": value["kind"] == "input",
                        "is_free": value["kind"] in ("free", "constant"),
                    }
                    for value in graph["values"]
                ],
                "operation_states": [
                    {"id": operation["id"], "is_dead": False, "parent": block["id"]}
                    for block in graph["blocks"]
                    for operation in block["operations"]
                ]
                + [
                    {"id": operation, "is_dead": True, "parent": None}
                    for operation in graph["excluded_dead"]
                ],
            }
        records.append(
            {
                "function": key,
                "pass": retained_pass,
                "pass_id": pass_id,
                "status": "complete" if ordinal == 0 else "gap",
                "reason": None if ordinal == 0 else "graph_unrepresentable",
                "graph": graph if ordinal == 0 else None,
                "source": source if ordinal == 0 else None,
                "facts": facts if ordinal == 0 else None,
            }
        )
    return (
        binary,
        lift,
        wire(mapping_wire(binary, lift)),
        {
            "schema": 1,
            "status": "UNPUBLISHED",
            "context": deepcopy(context),
            "functions": records,
        },
        context,
    )


def convert(
    sample: tuple[bytes, bytes, bytes, dict[str, Any], dict[str, Any]],
    limits: ByteExportLimits = ByteExportLimits(),
) -> UnpublishedByteExport:
    binary, lift, mapping, draft, context = sample
    if limits != ByteExportLimits():
        context["limits"] = asdict(limits)
        draft["context"]["limits"] = asdict(limits)
    return exporter._convert(binary, lift, mapping, wire(draft), context, limits)


def test_full_records_and_ordinary_bytes_survive_conversion() -> None:
    data = diagnostic_sample()
    result = convert(data)
    assert result.status == "UNPUBLISHED"
    assert (
        result.lift == data[1]
        and result.mapping == data[2]
        and result.draft == wire(data[3])
    )
    encoded = json.loads(result.to_bytes())
    assert len(encoded["functions"]) == len(json.loads(data[1])["functions"])
    for final, draft in zip(encoded["functions"], data[3]["functions"], strict=True):
        for name in ("graph", "source"):
            if final[name] is not None:
                assert final[name].pop("lift_sha256") == sha256(data[1]).hexdigest()
        assert final == draft
    assert result.to_bytes() == wire(json.loads(result.to_bytes()))
    with pytest.raises(FrozenInstanceError):
        setattr(result, "status", "published")
    data[3]["functions"][0]["facts"]["value_flags"].clear()
    assert result.functions[0].facts is not None
    assert json.loads(result.functions[0].facts)["value_flags"]


def test_ordered_edges_phi_dead_raw_and_reused_storage_are_retained() -> None:
    result = convert(diagnostic_sample())
    graph = result.functions[0].graph
    assert graph is not None
    assert len(graph.excluded_dead) == 1
    assert len(graph.raw_instruction_sites) == 6
    assert len(graph.blocks) == 5
    assert not graph.blocks[-1].operations and not graph.blocks[-1].incoming
    phi = graph.blocks[1].operations[0]
    assert phi.opcode == "MULTIEQUAL"
    assert [key.local_id for key in phi.inputs] == [2, 4]
    assert [
        (edge.other.index, edge.reciprocal_slot) for edge in graph.blocks[1].incoming
    ] == [(10, 0), (30, 0)]
    assert graph.values[3].storage == graph.values[4].storage
    assert graph.values[3].id != graph.values[4].id
    assert graph.values[3].definition != graph.values[4].definition


@pytest.mark.parametrize(
    "fault",
    [
        "active",
        "dead",
        "raw_site",
        "phi",
        "edge",
        "value",
        "dead_use",
        "width",
        "domain",
        "flag",
        "state",
        "extra_value",
    ],
)
def test_inventory_and_link_corruption_rejects(fault: str) -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][0]
    graph = record["graph"]
    if fault == "active":
        graph["blocks"][0]["operations"].clear()
    elif fault == "dead":
        graph["excluded_dead"].clear()
    elif fault == "raw_site":
        graph["raw_instruction_sites"].pop()
    elif fault == "phi":
        graph["blocks"][1]["operations"][0]["inputs"].reverse()
    elif fault == "edge":
        graph["blocks"][1]["incoming"][0]["reciprocal_slot"] = 1
    elif fault == "value":
        graph["values"][3]["id"]["local_id"] = 4
    elif fault == "dead_use":
        graph["values"][3]["definition"] = graph["excluded_dead"][0]
    elif fault == "width":
        graph["values"][0]["size_bytes"] = 4
    elif fault == "domain":
        graph["blocks"][0]["operations"][0]["id"]["domain"] = "raw"
    elif fault == "flag":
        record["facts"]["value_flags"][0]["is_input"] = False
    elif fault == "state":
        record["facts"]["operation_states"][-1]["is_dead"] = False
    else:
        graph["values"].append(deepcopy(graph["values"][0]))
    with pytest.raises(ByteExportError):
        convert(data)


@pytest.mark.parametrize(
    "field",
    [
        "ghidra_revision",
        "language_id",
        "compiler_spec_id",
        "simplification_style",
        "configured_options",
        "timeout_seconds",
        "source_manifest_sha256",
        "tool_manifest_sha256",
        "call_ordinal",
    ],
)
def test_coherent_pass_rename_cannot_change_the_profile(field: str) -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][0]
    previous = record["pass_id"]
    record["pass"][field] = "changed"
    current = sha256(wire(record["pass"])).hexdigest()
    data[3]["functions"][0] = json.loads(
        wire(record).replace(previous.encode(), current.encode())
    )
    with pytest.raises(ByteExportError, match="pass"):
        convert(data)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "tool",
        "binary",
        "pass",
        "graph_pass",
        "source_pass",
        "roster",
        "order",
        "extra_function",
        "lift",
        "mapping",
    ],
)
def test_bound_identity_changes_reject(fault: str) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    record = draft["functions"][0]
    if fault == "source":
        draft["context"]["sources"]["synthetic"] = "0" * 64
    elif fault == "tool":
        draft["context"]["tools"]["synthetic"] = "0" * 64
    elif fault == "binary":
        binary += b"x"
    elif fault == "pass":
        record["pass_id"] = "0" * 64
    elif fault in ("graph_pass", "source_pass"):
        record[fault.split("_")[0]]["pass_id"] = "0" * 64
    elif fault == "roster":
        draft["functions"].pop()
    elif fault == "order":
        draft["functions"].reverse()
    elif fault == "extra_function":
        draft["functions"].append(deepcopy(record))
    elif fault == "lift":
        lift += b" "
    else:
        mapping = b"{}"
    with pytest.raises(ByteExportError):
        convert((binary, lift, mapping, draft, context))


def test_unicode_spans_null_links_and_all_storage_fields_survive() -> None:
    data = diagnostic_sample()
    source = data[3]["functions"][0]["source"]
    token = source["tokens"][0]
    token.update(operation=None, value=None, formal_ordinal=None)
    token["symbol_storage"] = [
        {
            "address": {"space": "stack", "offset": hex(2**64 - 8)},
            "size": 8,
            "register": None,
            "stack_offset": -8,
        },
        {
            "address": {"space": "register", "offset": "0x20"},
            "size": 4,
            "register": "ESI",
            "stack_offset": None,
        },
    ]
    result = convert(data).functions[0].source
    assert result is not None
    record = result.record()
    record.pop("lift_sha256")
    assert record == source
    assert result.tokens[0].operation is None and result.tokens[0].value is None
    assert result.tokens[1].formal_ordinal == 0


@pytest.mark.parametrize(
    "fault", ["cut_utf8", "hash", "bytes", "order", "missing_span", "formal", "storage"]
)
def test_exact_source_contradictions_reject(fault: str) -> None:
    data = diagnostic_sample()
    source = data[3]["functions"][0]["source"]
    token = source["tokens"][1]
    if fault == "cut_utf8":
        token["span"]["start"] = 16
    elif fault == "hash":
        token["text_sha256"] = "0" * 64
    elif fault == "bytes":
        source["raw_c_bytes"] += 1
    elif fault == "order":
        source["tokens"].reverse()
    elif fault == "missing_span":
        del token["span"]
    elif fault == "formal":
        token["formal_ordinal"] = True
    else:
        token["symbol_storage"][0]["stack_offset"] = 0
    with pytest.raises(ByteExportError):
        convert(data)


def test_unavailable_printer_retains_graph_and_explicit_gap() -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][0]
    record.update(status="gap", reason="empty_printer_token")
    record["source"].update(
        source_status="unavailable",
        tokens=[],
        gaps=[
            {"code": "source_unbound", "block": None, "operation": None, "value": None}
        ],
    )
    result = convert(data).functions[0]
    assert result.graph is not None and result.source is not None
    assert (
        result.reason == "empty_printer_token"
        and result.source.source_status == "unavailable"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_reason",
        "unknown_reason",
        "partial_source",
        "partial_facts",
        "bad_status",
        "hidden_gap",
        "invented_gap",
    ],
)
def test_closed_dispositions_reject_partial_results(fault: str) -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][1]
    if fault == "missing_reason":
        record["reason"] = None
    elif fault == "unknown_reason":
        record["reason"] = "success_despite_gap"
    elif fault == "partial_source":
        record["source"] = data[3]["functions"][0]["source"]
    elif fault == "partial_facts":
        record["facts"] = data[3]["functions"][0]["facts"]
    elif fault == "bad_status":
        record["status"] = "emitted"
    elif fault == "hidden_gap":
        data[3]["functions"][0]["graph"]["export_gaps"] = [
            {"code": "ssa_unbound", "block": None, "operation": None, "value": None}
        ]
    else:
        data[3]["functions"][0].update(status="gap", reason="evidence_gap")
    with pytest.raises(ByteExportError):
        convert(data)


@pytest.mark.parametrize(
    "name", [f.name for f in fields(ByteExportLimits) if isinstance(f.default, int)]
)
@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_limits(name: str, bad: Any) -> None:
    with pytest.raises(ByteExportError):
        ByteExportLimits(**{name: bad})


@pytest.mark.parametrize(
    "name",
    [
        "max_program_bytes",
        "max_lift_bytes",
        "max_mapping_bytes",
        "max_companion_bytes",
        "max_bundle_bytes",
        "max_functions",
    ],
)
def test_caller_lower_limits_refuse_without_a_partial_result(name: str) -> None:
    lower: dict[str, Any] = {name: 1}
    with pytest.raises(ByteExportError):
        convert(diagnostic_sample(), replace(ByteExportLimits(), **lower))


@pytest.mark.parametrize(
    "name",
    [
        "max_operations",
        "max_raw_operations",
        "max_raw_instructions",
        "max_blocks",
        "max_values",
        "max_references",
        "max_inputs",
        "max_bytes",
    ],
)
def test_complete_graph_respects_lower_limits(name: str) -> None:
    with pytest.raises(ByteExportError):
        convert(
            diagnostic_sample(),
            ByteExportLimits(graph=replace(ByteGraphLimits(), **{name: 1})),
        )


@pytest.mark.parametrize("name", ["max_source_bytes", "max_tokens", "max_bytes"])
def test_complete_source_respects_lower_limits(name: str) -> None:
    with pytest.raises(ByteExportError):
        convert(
            diagnostic_sample(),
            ByteExportLimits(source=replace(ByteSourceLimits(), **{name: 1})),
        )


@pytest.mark.parametrize(
    "raw", [b"{", b'{"schema":1,"schema":1}', b'{"x":NaN}', b"\xff", b"[]", b"\x00"]
)
def test_malformed_wire_is_finite(raw: bytes) -> None:
    binary, lift, mapping, _, context = diagnostic_sample()
    with pytest.raises(ByteExportError):
        exporter._convert(binary, lift, mapping, raw, context, ByteExportLimits())


def test_noncanonical_draft_and_prefinal_lift_hash_reject() -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    with pytest.raises(ByteExportError):
        exporter._convert(
            binary, lift, mapping, wire(draft) + b"\n", context, ByteExportLimits()
        )
    draft["functions"][0]["graph"]["lift_sha256"] = sha256(lift).hexdigest()
    with pytest.raises(ByteExportError):
        convert((binary, lift, mapping, draft, context))


@given(st.integers(min_value=0, max_value=2**32 - 1))
@example(local_id=0)
@example(local_id=9)
@settings(max_examples=20, deadline=None)
def test_actual_value_object_ids_are_not_storage_keys(local_id: int) -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][0]
    assert record["graph"]["values"][0]["id"]["local_id"] == 0
    occupied = {
        value["id"]["local_id"]
        for value in record["graph"]["values"]
        if value["id"]["local_id"] != 0
    }

    def change(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("local_id") == 0:
                value["local_id"] = local_id
            for child in value.values():
                change(child)
        elif isinstance(value, list):
            for child in value:
                change(child)

    change(record)
    if local_id in occupied:
        with pytest.raises(ByteExportError):
            convert(data)
        return
    result = convert(data).functions[0].graph
    assert result is not None and result.values[0].id.local_id == local_id


def test_program_bound_precedes_context_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object) -> dict[str, object]:
        raise AssertionError("Tool measurement must not run.")

    monkeypatch.setattr(exporter, "_context", forbidden)
    with pytest.raises(ByteExportError) as caught:
        convert_byte_export(
            b"xx",
            b"",
            b"",
            b"",
            installation=Path("x"),
            java_home=Path("y"),
            limits=ByteExportLimits(max_program_bytes=1),
        )
    assert caught.value.code == "limit"


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "missing",
        "extra",
        "changed_input",
        "changed_source",
        "changed_tool",
        "symlink",
        "headless",
    ],
)
def test_one_job_transaction_is_unpublished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    binary_path = tmp_path / "public.elf"
    binary_path.write_bytes(binary)
    stage = tmp_path / "stage"
    stage.mkdir()
    root = tmp_path / "checkout"
    scripts = root / "ghidra_scripts"
    scripts.mkdir(parents=True)
    for name in exporter._SCRIPTS:
        (scripts / name).write_bytes(name.encode())
    context["sources"] = {
        f"ghidra_scripts/{name}": sha256(name.encode()).hexdigest()
        for name in exporter._SCRIPTS
    }
    for record in draft["functions"]:
        old = record["pass_id"]
        record["pass"]["source_manifest_sha256"] = sha256(
            wire(context["sources"])
        ).hexdigest()
        new = sha256(wire(record["pass"])).hexdigest()
        record.update(json.loads(wire(record).replace(old.encode(), new.encode())))
    draft["context"] = deepcopy(context)
    monkeypatch.setattr(exporter, "_ROOT", root)
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    calls = 0

    def measured(*args: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        result = deepcopy(context)
        if calls > 1 and failure == "changed_tool":
            result["tools"] = {"changed": "0" * 64}
        return result

    launches = []

    def headless(command: list[str], work: Path, env: dict[str, str]) -> None:
        launches.append(command)
        assert command.count("-postScript") == 2
        assert "ExportSwitchGraphs.java" not in command
        assert command[command.index("ExportLift.java") + 2] == "--byte-diagnostic"
        assert env["JDK_JAVA_OPTIONS"] == "@java.args"
        assert env["GHIDRA_HEADLESS_MAXMEM"] == "512M"
        assert str(work) in (work / "java.args").read_text()
        assert env["TMPDIR"] == str(work)
        output = work / "output"
        (output / "lift.json").write_bytes(lift)
        (output / "mapping.json").write_bytes(mapping)
        (output / "byte-draft.json").write_bytes(wire(draft))
        if failure == "missing":
            (output / "mapping.json").unlink()
        elif failure == "extra":
            (output / "evidence-current").write_text("no publication")
        elif failure == "changed_input":
            binary_path.write_bytes(b"changed")
        elif failure == "changed_source":
            (work / "scripts/ExportLift.java").write_bytes(b"changed")
        elif failure == "symlink":
            (output / "mapping.json").unlink()
            (output / "mapping.json").symlink_to(output / "lift.json")
        elif failure == "headless":
            raise ByteExportError("headless", "Synthetic failure.")

    monkeypatch.setattr(exporter, "_context", measured)
    monkeypatch.setattr(exporter, "_headless", headless)
    if failure is None:
        result = export_byte_diagnostic(
            binary_path, stage, installation=tmp_path, java_home=tmp_path
        )
        assert result.status == "UNPUBLISHED" and result.lift == lift
    else:
        with pytest.raises(ByteExportError):
            export_byte_diagnostic(
                binary_path, stage, installation=tmp_path, java_home=tmp_path
            )
    assert len(launches) == 1 and not list(stage.iterdir())
    assert not (tmp_path / "evidence-current").exists()


@pytest.mark.parametrize(
    "error_type", [RuntimeError, TypeError, UnicodeError, OverflowError]
)
def test_unexpected_context_failures_are_not_input_errors(
    monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    error = error_type("Coding failure.")

    def broken(*args: object) -> dict[str, object]:
        raise error

    monkeypatch.setattr(exporter, "_context", broken)
    with pytest.raises(error_type) as caught:
        convert_byte_export(
            b"x", b"", b"", b"", installation=Path("x"), java_home=Path("y")
        )
    assert caught.value is error


def test_headless_failure_has_no_background_process(tmp_path: Path) -> None:
    with pytest.raises(ByteExportError) as caught:
        exporter._headless(["/bin/sh", "-c", "exit 7"], tmp_path, dict(os.environ))
    assert caught.value.code == "headless"


def test_block_owned_dead_flag_is_retained_as_an_api_conflict() -> None:
    data = diagnostic_sample()
    record = data[3]["functions"][0]
    state = record["facts"]["operation_states"][0]
    state["is_dead"] = True
    with pytest.raises(ByteExportError):
        convert(data)
    record["graph"]["export_gaps"].append(
        {"code": "cfg_unclosed", "block": None, "operation": state["id"], "value": None}
    )
    record.update(status="gap", reason="evidence_gap")
    result = convert(data).functions[0]
    assert result.facts is not None and result.graph is not None
    assert json.loads(result.facts)["operation_states"][0]["is_dead"] is True
    assert result.graph.blocks[0].operations


def installed_fixture(tmp_path: Path) -> tuple[Path, Path]:
    from test_provenance import write_tools

    ghidra, java = write_tools(tmp_path)
    (ghidra / "Ghidra/application.properties").write_text(
        "application.version=12.2\n"
        "application.revision.ghidra=8ca9077040cc43cd790babcfccf19475622a3e9a\n"
    )
    (java / "release").write_text(
        'SEMANTIC_VERSION="25.0.5+8"\nJAVA_RUNTIME_VERSION="25.0.5+8-LTS"\n'
    )
    return ghidra, java


def test_tool_manifest_uses_actual_files_and_source_manifest_uses_actual_source(
    tmp_path: Path,
) -> None:
    ghidra, java = installed_fixture(tmp_path)
    before = exporter._context(b"synthetic", ghidra, java, ByteExportLimits())
    tools = before["tools"]
    assert isinstance(tools, dict)
    changed = ghidra / "Ghidra/Features/Decompiler/lib/Decompiler.jar"
    key = "ghidra/Ghidra/Features/Decompiler/lib/Decompiler.jar"
    assert tools[key] == sha256(changed.read_bytes()).hexdigest()
    changed.write_bytes(b"changed installed component")
    after = exporter._context(b"synthetic", ghidra, java, ByteExportLimits())
    assert after["tools"] != before["tools"]
    sources = after["sources"]
    assert isinstance(sources, dict)
    assert (
        sources["ghidra_scripts/OrdinaryByteEvidence.java"]
        == sha256(
            (exporter._ROOT / "ghidra_scripts/OrdinaryByteEvidence.java").read_bytes()
        ).hexdigest()
    )


@pytest.mark.parametrize("field", ["ghidra_version", "ghidra_revision", "java_release"])
def test_installed_tools_must_match_pins(tmp_path: Path, field: str) -> None:
    ghidra, java = installed_fixture(tmp_path)
    if field == "java_release":
        (java / "release").write_text('SEMANTIC_VERSION="24"\n')
    else:
        path = ghidra / "Ghidra/application.properties"
        text = path.read_text()
        text = (
            text.replace("12.2", "12.1")
            if field == "ghidra_version"
            else text.replace("8ca907", "000000")
        )
        path.write_text(text)
    with pytest.raises(ByteExportError) as caught:
        exporter._context(b"synthetic", ghidra, java, ByteExportLimits())
    assert caught.value.code == "tool"


@pytest.mark.parametrize(
    "field",
    [
        "max_program_bytes",
        "max_lift_bytes",
        "max_mapping_bytes",
        "max_companion_bytes",
        "max_bundle_bytes",
        "max_functions",
    ],
)
def test_limit_cannot_exceed_first_profile(field: str) -> None:
    values: dict[str, Any] = {field: getattr(ByteExportLimits(), field) + 1}
    with pytest.raises(ByteExportError):
        ByteExportLimits(**values)


@pytest.mark.parametrize(
    "record",
    [
        "top",
        "function",
        "pass",
        "graph",
        "source",
        "facts",
        "value_flags",
        "operation_states",
    ],
)
def test_draft_records_are_closed(record: str) -> None:
    data = diagnostic_sample()
    node = data[3]
    function = node["functions"][0]
    if record == "function":
        node = function
    elif record in ("pass", "graph", "source", "facts"):
        node = function[record]
    elif record in ("value_flags", "operation_states"):
        node = function["facts"][record][0]
    node["authority"] = "emitted"
    with pytest.raises(ByteExportError):
        convert(data)


def test_missing_ordinary_entry_has_a_finite_input_error() -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    ordinary = json.loads(lift)
    del ordinary["functions"][0]["entry"]
    with pytest.raises(ByteExportError):
        exporter._convert(
            binary, wire(ordinary), mapping, wire(draft), context, ByteExportLimits()
        )


@pytest.mark.parametrize("group", ["graph", "source"])
def test_mutated_nested_limit_has_a_finite_input_error(group: str) -> None:
    limits = ByteExportLimits()
    object.__setattr__(getattr(limits, group), "max_bytes", 0)
    try:
        with pytest.raises(ByteExportError) as caught:
            convert(diagnostic_sample(), limits)
        assert caught.value.code == "limit"
    finally:
        object.__setattr__(getattr(limits, group), "max_bytes", 16 * 1024 * 1024)


@pytest.mark.parametrize(
    "error_type",
    [ValueError, UnicodeError, RuntimeError, TypeError, RecursionError, OverflowError],
)
def test_unexpected_tool_hash_failures_remain_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    ghidra, java = installed_fixture(tmp_path)
    failure = error_type("Unexpected tool hash failure.")

    def broken(*args: object) -> dict[str, str]:
        raise failure

    monkeypatch.setattr(exporter, "lifting_tool_identity", broken)
    with pytest.raises(error_type) as caught:
        exporter._context(b"synthetic", ghidra, java, ByteExportLimits())
    assert caught.value is failure


@pytest.mark.parametrize("failure", ["missing", "file", "create", "write"])
def test_expected_staging_filesystem_errors_are_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    import errno

    binary, _, _, _, context = diagnostic_sample()
    binary_path = tmp_path / "program.elf"
    binary_path.write_bytes(binary)
    stage = tmp_path / "stage"
    stage.mkdir()
    selected = stage
    monkeypatch.setattr(exporter, "_context", lambda *args: context)

    def must_not_start(*args: object) -> None:
        raise AssertionError("A staging failure must precede the job.")

    monkeypatch.setattr(exporter, "_headless", must_not_start)
    if failure == "missing":
        selected = stage / "missing"
    elif failure == "file":
        selected = binary_path
    elif failure == "create":

        def denied(*args: object, **kwargs: object) -> None:
            raise PermissionError(errno.EACCES, "Staging creation refused.")

        monkeypatch.setattr(exporter, "TemporaryDirectory", denied)
    else:
        original_write = Path.write_bytes

        def full_disk(path: Path, raw: bytes) -> int:
            if path.name == "input.elf" and path.parent.name.startswith(
                "byte-diagnostic-"
            ):
                raise OSError(errno.ENOSPC, "The staging disk is full.")
            return original_write(path, raw)

        monkeypatch.setattr(Path, "write_bytes", full_disk)
    with pytest.raises(ByteExportError) as caught:
        export_byte_diagnostic(
            binary_path, selected, installation=tmp_path, java_home=tmp_path
        )
    assert caught.value.code == "io"
    assert not list(stage.iterdir())


def test_existing_headless_log_is_diagnostic(tmp_path: Path) -> None:
    (tmp_path / "headless.log").write_bytes(b"Existing owned log.")
    with pytest.raises(ByteExportError) as caught:
        exporter._headless(["/not-started"], tmp_path, {})
    assert caught.value.code == "io"


@pytest.mark.parametrize(
    "entry,site",
    [
        ("export", "staging"),
        ("export", "workspace"),
        ("export", "installation"),
        ("export", "java"),
        ("convert", "installation"),
        ("convert", "java"),
    ],
)
def test_real_path_loops_are_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, site: str
) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    binary, lift, mapping, _, context = diagnostic_sample()
    binary_path = tmp_path / "program.elf"
    binary_path.write_bytes(binary)
    stage = tmp_path / "stage"
    stage.mkdir()
    marker = stage / "evidence-current"
    marker.write_bytes(b"Previous selected generation.\n")
    cycle = tmp_path / "cycle"
    cycle.symlink_to("cycle")
    installation = cycle if site == "installation" else tmp_path
    java_home = cycle if site == "java" else tmp_path
    selected_stage = cycle if site == "staging" else stage
    if site == "workspace":
        monkeypatch.setenv("PHOENIX_ROOT", str(cycle))

    def must_not_run(*args: object) -> None:
        raise AssertionError("A path loop must precede the job and conversion.")

    monkeypatch.setattr(exporter, "_headless", must_not_run)
    monkeypatch.setattr(exporter, "_convert", must_not_run)
    monkeypatch.setattr(exporter, "_context", lambda *args: context)
    with pytest.raises(ByteExportError) as caught:
        if entry == "export":
            export_byte_diagnostic(
                binary_path,
                selected_stage,
                installation=installation,
                java_home=java_home,
            )
        else:
            exporter.convert_byte_export(
                binary,
                lift,
                mapping,
                b"",
                installation=installation,
                java_home=java_home,
            )
    assert caught.value.code == "io"
    cause = caught.value.__cause__
    assert type(cause) is RuntimeError
    assert isinstance(cause.__context__, OSError)
    assert cause.__context__.errno == errno.ELOOP
    assert marker.read_bytes() == b"Previous selected generation.\n"
    assert set(stage.iterdir()) == {marker}


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("kind", ["two_links", "parent"])
def test_resolver_rejects_real_cycles(tmp_path: Path, strict: bool, kind: str) -> None:
    if kind == "two_links":
        selected = tmp_path / "first"
        selected.symlink_to("second")
        (tmp_path / "second").symlink_to("first")
    else:
        (tmp_path / "parent").symlink_to("parent")
        selected = tmp_path / "parent" / "child"
    with pytest.raises(ByteExportError) as caught:
        exporter._resolve(selected, strict=strict)
    assert caught.value.code == "io"
    assert type(caught.value.__cause__) is RuntimeError


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "kind", ["absolute", "relative", "symlink", "symlink_parent", "missing", "dangling"]
)
def test_resolver_preserves_path_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strict: bool, kind: str
) -> None:
    (tmp_path / "real" / "nested").mkdir(parents=True)
    (tmp_path / "real" / "data").write_bytes(b"Public path control.")
    (tmp_path / "link").symlink_to("real/nested")
    (tmp_path / "file_link").symlink_to("real/data")
    (tmp_path / "dangling").symlink_to("absent")
    monkeypatch.chdir(tmp_path)
    selected = {
        "absolute": tmp_path / "real" / "data",
        "relative": Path("real/data"),
        "symlink": Path("file_link"),
        "symlink_parent": Path("link") / ".." / "data",
        "missing": Path("absent"),
        "dangling": Path("dangling"),
    }[kind]
    if strict and kind in {"missing", "dangling"}:
        with pytest.raises(ByteExportError) as caught:
            exporter._resolve(selected, strict=strict)
        assert caught.value.code == "io"
        assert isinstance(caught.value.__cause__, FileNotFoundError)
    else:
        assert exporter._resolve(selected, strict=strict) == selected.resolve(
            strict=strict
        )


@pytest.mark.parametrize(
    "kind",
    [
        "plain",
        "permission",
        "deep",
        "explicit",
        "suppressed",
        "recursion",
        "subclass",
        "type",
        "value",
        "legacy",
    ],
)
def test_resolver_converts_only_the_implicit_legacy_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    class OtherRuntimeError(RuntimeError):
        pass

    failure: Exception = RuntimeError("This text does not identify a path loop.")
    if kind == "recursion":
        failure = RecursionError("Keep the recursion failure.")
    elif kind == "subclass":
        failure = OtherRuntimeError("Keep the runtime subclass.")
    elif kind == "type":
        failure = TypeError("Keep the type failure.")
    elif kind == "value":
        failure = ValueError("Keep the value failure.")
    failure.__context__ = OSError(errno.ELOOP, "Underlying loop.")
    if kind == "plain":
        failure.__context__ = None
    elif kind == "permission":
        failure.__context__ = PermissionError(
            errno.EACCES, "Underlying permission failure."
        )
    elif kind == "deep":
        middle = ValueError("Intermediate failure.")
        middle.__context__ = failure.__context__
        failure.__context__ = middle
    elif kind == "explicit":
        failure.__cause__ = ValueError("Explicit cause.")
        failure.__suppress_context__ = False
    elif kind == "suppressed":
        failure.__suppress_context__ = True

    def broken(*args: object, **kwargs: object) -> Path:
        raise failure

    monkeypatch.setattr(Path, "resolve", broken)
    if kind == "legacy":
        with pytest.raises(ByteExportError) as caught:
            exporter._resolve(tmp_path)
        assert caught.value.code == "io"
        assert caught.value.__cause__ is failure
    else:
        with pytest.raises(type(failure)) as original:
            exporter._resolve(tmp_path)
        assert original.value is failure


@pytest.mark.parametrize("kind", ["loop", "permission"])
def test_resolver_keeps_native_oserror_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    failure = OSError(
        errno.ELOOP if kind == "loop" else errno.EACCES, "File operation failed."
    )

    def broken(*args: object, **kwargs: object) -> Path:
        raise failure

    monkeypatch.setattr(Path, "resolve", broken)
    with pytest.raises(ByteExportError) as caught:
        exporter._resolve(tmp_path)
    assert caught.value.code == "io"
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("site", ["temporary_directory", "context", "tool_hash"])
def test_legacy_loop_shape_outside_resolution_stays_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site: str
) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    binary, lift, mapping, _, context = diagnostic_sample()
    failure = RuntimeError("A programming failure outside path resolution.")
    failure.__context__ = OSError(errno.ELOOP, "Underlying loop.")

    def broken(*args: object, **kwargs: object) -> object:
        raise failure

    if site == "tool_hash":
        ghidra, java = installed_fixture(tmp_path)
        monkeypatch.setattr(exporter, "lifting_tool_identity", broken)
        with pytest.raises(RuntimeError) as caught:
            exporter._context(binary, ghidra, java, ByteExportLimits())
    elif site == "context":
        monkeypatch.setattr(exporter, "_context", broken)
        with pytest.raises(RuntimeError) as caught:
            exporter.convert_byte_export(
                binary, lift, mapping, b"", installation=tmp_path, java_home=tmp_path
            )
    else:
        binary_path = tmp_path / "program.elf"
        binary_path.write_bytes(binary)
        stage = tmp_path / "stage"
        stage.mkdir()
        monkeypatch.setattr(exporter, "_context", lambda *args: context)
        monkeypatch.setattr(exporter, "TemporaryDirectory", broken)
        with pytest.raises(RuntimeError) as caught:
            export_byte_diagnostic(
                binary_path, stage, installation=tmp_path, java_home=tmp_path
            )
    assert caught.value is failure


@pytest.mark.parametrize("entry", ["convert", "export"])
@pytest.mark.parametrize("function", [0, 1])
@pytest.mark.parametrize(
    "fault",
    [
        "valid",
        "null",
        "empty",
        "incomplete",
        "status",
        "register_width",
        "type_reference",
    ],
)
def test_static_evidence_refusal_has_a_diagnostic_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    function: int,
    fault: str,
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    root = tmp_path / "checkout"
    scripts = root / "ghidra_scripts"
    scripts.mkdir(parents=True)
    for name in exporter._SCRIPTS:
        (scripts / name).write_bytes(name.encode())
    context["sources"] = {
        f"ghidra_scripts/{name}": sha256(name.encode()).hexdigest()
        for name in exporter._SCRIPTS
    }
    for record in draft["functions"]:
        old = record["pass_id"]
        record["pass"]["source_manifest_sha256"] = sha256(
            wire(context["sources"])
        ).hexdigest()
        updated = sha256(wire(record["pass"])).hexdigest()
        record.update(json.loads(wire(record).replace(old.encode(), updated.encode())))
    draft["context"] = deepcopy(context)
    monkeypatch.setattr(exporter, "_ROOT", root)
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    original_parser = parse_lift
    parser_errors: list[EvidenceError] = []

    def observed_parser(lift_bytes: bytes, binary_bytes: bytes) -> LiftIndex:
        try:
            return original_parser(lift_bytes, binary_bytes)
        except EvidenceError as error:
            parser_errors.append(error)
            raise

    monkeypatch.setattr(exporter, "parse_lift", observed_parser)
    evidence: Any = deepcopy(static_evidence_wire())
    if fault == "null":
        evidence = None
    elif fault == "empty":
        evidence = {}
    elif fault == "incomplete":
        evidence = {"schema_version": 1}
    elif fault == "status":
        evidence["status"] = "verified"
    elif fault == "register_width":
        evidence["registers"][0]["bits"] = 0
    elif fault == "type_reference":
        evidence["listing"]["result"]["type"] = "absent"
    if fault == "valid":
        parse_static_evidence(evidence)
    else:
        with pytest.raises(EvidenceError):
            parse_static_evidence(evidence)
    document = json.loads(lift)
    document["functions"][function]["static_evidence"] = evidence
    changed_lift = wire(document)
    mapping_record = json.loads(mapping)
    mapping_record["lift_sha256"] = sha256(changed_lift).hexdigest()
    changed_mapping = wire(mapping_record)
    binary_path = tmp_path / "program.elf"
    binary_path.write_bytes(binary)
    stage = tmp_path / "stage"
    stage.mkdir()
    marker = stage / "evidence-current"
    marker.write_bytes(b"Previous selected generation.\n")
    jobs: list[Path] = []
    monkeypatch.setattr(exporter, "_context", lambda *args: context)

    def launch(command: list[str], work: Path, env: dict[str, str]) -> None:
        jobs.append(work)
        output = work / "output"
        (output / "lift.json").write_bytes(changed_lift)
        (output / "mapping.json").write_bytes(changed_mapping)
        (output / "byte-draft.json").write_bytes(wire(draft))

    def invoke() -> UnpublishedByteExport:
        if entry == "convert":
            return convert_byte_export(
                binary,
                changed_lift,
                changed_mapping,
                wire(draft),
                installation=tmp_path,
                java_home=tmp_path,
            )
        return export_byte_diagnostic(
            binary_path, stage, installation=tmp_path, java_home=tmp_path
        )

    monkeypatch.setattr(exporter, "_headless", launch)
    try:
        if fault == "valid":
            result = invoke()
            assert result.status == "UNPUBLISHED"
            assert result.lift == changed_lift and result.mapping == changed_mapping
        else:
            with pytest.raises(ByteExportError) as caught:
                invoke()
            assert caught.value.code == "format"
            assert isinstance(caught.value.__cause__, EvidenceError)
            assert len(parser_errors) == 1
            assert caught.value.__cause__ is parser_errors[0]
    finally:
        assert marker.read_bytes() == b"Previous selected generation.\n"
        assert set(stage.iterdir()) == {marker}
        assert len(jobs) == (entry == "export")


@pytest.mark.parametrize("site", ["hash", "context"])
def test_evidence_error_outside_ordinary_parser_remains_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site: str
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    failure = EvidenceError("Unexpected error outside the parser.")

    def broken(*args: object) -> None:
        raise failure

    monkeypatch.setattr(exporter, "_context", lambda *args: context)
    monkeypatch.setattr(exporter, "sha256" if site == "hash" else "_context", broken)
    with pytest.raises(EvidenceError) as caught:
        convert_byte_export(
            binary,
            lift,
            mapping,
            wire(draft),
            installation=tmp_path,
            java_home=tmp_path,
        )
    assert caught.value is failure


@pytest.mark.parametrize(
    "error_type",
    [
        EvidenceError,
        ValueError,
        RuntimeError,
        TypeError,
        AssertionError,
        OverflowError,
        RecursionError,
    ],
)
def test_ordinary_parser_normalizes_only_its_evidence_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    failure = error_type("Parser boundary control.")

    def broken(*args: object) -> LiftIndex:
        raise failure

    monkeypatch.setattr(exporter, "_context", lambda *args: context)
    monkeypatch.setattr(exporter, "parse_lift", broken)
    if error_type is EvidenceError:
        with pytest.raises(ByteExportError) as caught:
            convert_byte_export(
                binary,
                lift,
                mapping,
                wire(draft),
                installation=tmp_path,
                java_home=tmp_path,
            )
        assert caught.value.code == "format" and caught.value.__cause__ is failure
    else:
        with pytest.raises(error_type) as original:
            convert_byte_export(
                binary,
                lift,
                mapping,
                wire(draft),
                installation=tmp_path,
                java_home=tmp_path,
            )
        assert original.value is failure


@pytest.mark.parametrize("site", ["canonical", "result"])
def test_evidence_error_from_other_operations_stays_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site: str
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    failure = EvidenceError("Unexpected calculation failure.")

    def broken(*args: object) -> None:
        raise failure

    monkeypatch.setattr(exporter, "_context", lambda *args: context)
    if site == "canonical":
        monkeypatch.setattr(exporter, "canonical", broken)
    else:
        monkeypatch.setattr(UnpublishedByteExport, "to_bytes", broken)
    with pytest.raises(EvidenceError) as caught:
        convert_byte_export(
            binary,
            lift,
            mapping,
            wire(draft),
            installation=tmp_path,
            java_home=tmp_path,
        )
    assert caught.value is failure


def test_evidence_error_from_hash_after_readers_stays_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary, lift, mapping, draft, context = diagnostic_sample()
    failure = EvidenceError("Unexpected later hash failure.")
    original_mapping = parse_mapping
    original_hash = sha256
    readers_complete = False

    def observed_mapping(*args: Any) -> Any:
        nonlocal readers_complete
        result = original_mapping(*args)
        readers_complete = True
        return result

    def later_hash(raw: bytes) -> Any:
        if readers_complete:
            raise failure
        return original_hash(raw)

    monkeypatch.setattr(exporter, "_context", lambda *args: context)
    monkeypatch.setattr(exporter, "parse_mapping", observed_mapping)
    monkeypatch.setattr(exporter, "sha256", later_hash)
    with pytest.raises(EvidenceError) as caught:
        convert_byte_export(
            binary,
            lift,
            mapping,
            wire(draft),
            installation=tmp_path,
            java_home=tmp_path,
        )
    assert readers_complete and caught.value is failure
