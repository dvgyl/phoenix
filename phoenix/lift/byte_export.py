"""Collect unpublished ordinary byte evidence. No result grants emission authority."""

import errno
import json
import os
import signal
import subprocess
import time
import tomllib
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast

from phoenix.lift.byte_graph import (
    ByteGraph,
    ByteGraphError,
    ByteGraphLimits,
    FunctionKey,
    parse_byte_graph,
)
from phoenix.lift.byte_source import (
    ByteSourceError,
    ByteSourceLimits,
    ByteSourceObservation,
    parse_byte_source,
)
from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import (
    GhidraVA,
    MappingError,
    bounded_read,
    digest,
    hex_address,
    load_json,
    object_fields,
    parse_mapping,
)
from phoenix_eval.provenance import lifting_tool_identity

MAX_PROGRAM_BYTES = 16 * 1024 * 1024
_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = (
    "ExportLift.java",
    "ExportMapping.java",
    "OrdinarySwitchEvidence.java",
    "OrdinaryByteEvidence.java",
)
_SOURCES = (
    "tools.lock",
    "phoenix/lift/__init__.py",
    "phoenix/lift/byte_export.py",
    "phoenix/lift/byte_graph.py",
    "phoenix/lift/byte_source.py",
    "phoenix/lift/index.py",
    "phoenix/lift/evidence.py",
    "phoenix/lift/mapping.py",
    "phoenix_eval/provenance.py",
    *(f"ghidra_scripts/{name}" for name in _SCRIPTS),
)
type ExportReason = Literal[
    "decompile_unavailable",
    "region_limit",
    "unsupported_profile",
    "graph_unrepresentable",
    "sequence_unrepresentable",
    "block_unrepresentable",
    "value_unrepresentable",
    "value_id_conflict",
    "definition_unrepresentable",
    "constant_unrepresentable",
    "value_flags_conflict",
    "operation_ownership_conflict",
    "entry_unrepresentable",
    "operation_id_conflict",
    "dead_partition_conflict",
    "operation_inventory_conflict",
    "conditional_unrepresentable",
    "phi_unrepresentable",
    "edge_unrepresentable",
    "address_unrepresentable",
    "source_link_unavailable",
    "printer_bytes_differ",
    "empty_printer_token",
    "evidence_gap",
]
_REASONS: tuple[ExportReason, ...] = (
    "decompile_unavailable",
    "region_limit",
    "unsupported_profile",
    "graph_unrepresentable",
    "sequence_unrepresentable",
    "block_unrepresentable",
    "value_unrepresentable",
    "value_id_conflict",
    "definition_unrepresentable",
    "constant_unrepresentable",
    "value_flags_conflict",
    "operation_ownership_conflict",
    "entry_unrepresentable",
    "operation_id_conflict",
    "dead_partition_conflict",
    "operation_inventory_conflict",
    "conditional_unrepresentable",
    "phi_unrepresentable",
    "edge_unrepresentable",
    "address_unrepresentable",
    "source_link_unavailable",
    "printer_bytes_differ",
    "empty_printer_token",
    "evidence_gap",
)
type ErrorCode = Literal[
    "format", "limit", "identity", "io", "tool", "headless", "timeout"
]


class ByteExportError(ValueError):
    """Reject the entire result. No partial graph or source is returned."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


def _io[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OSError as error:
        raise ByteExportError(
            "io", "Cannot complete a diagnostic file operation."
        ) from error


def _resolve(path: Path, *, strict: bool = False) -> Path:
    try:
        return _io(lambda: path.resolve(strict=strict))
    except RuntimeError as error:
        context = error.__context__
        if (
            type(error) is not RuntimeError
            or not isinstance(context, OSError)
            or context.errno != errno.ELOOP
            or error.__cause__ is not None
            or error.__suppress_context__
        ):
            raise
        raise ByteExportError(
            "io", "Cannot complete a diagnostic file operation."
        ) from error


@dataclass(frozen=True, slots=True)
class ByteExportLimits:
    max_program_bytes: int = MAX_PROGRAM_BYTES
    max_lift_bytes: int = 64 * 1024 * 1024
    max_mapping_bytes: int = 64 * 1024 * 1024
    max_companion_bytes: int = 16 * 1024 * 1024
    max_bundle_bytes: int = 160 * 1024 * 1024
    max_functions: int = 32
    graph: ByteGraphLimits = ByteGraphLimits()
    source: ByteSourceLimits = ByteSourceLimits()

    def __post_init__(self) -> None:
        for member in fields(self):
            value = getattr(self, member.name)
            if isinstance(member.default, int):
                if type(value) is not int or not 0 < value <= member.default:
                    raise ByteExportError("limit", f"Invalid limit: {member.name}.")
        if (
            type(self.graph) is not ByteGraphLimits
            or type(self.source) is not ByteSourceLimits
        ):
            raise ByteExportError("limit", "Invalid nested reader limits.")
        try:
            self.graph.__post_init__()
            self.source.__post_init__()
        except (ByteGraphError, ByteSourceError) as error:
            raise ByteExportError("limit", "Invalid nested reader limits.") from error


@dataclass(frozen=True, slots=True)
class OrdinaryBytePass:
    function: FunctionKey
    call_ordinal: int
    ghidra_version: str
    ghidra_revision: str
    language_id: str
    compiler_spec_id: str
    simplification_style: str
    source_manifest_sha256: str
    tool_manifest_sha256: str

    def record(self) -> dict[str, object]:
        result: dict[str, object] = {
            member.name: getattr(self, member.name) for member in fields(self)
        }
        result.update(
            schema=1,
            function=_key_record(self.function),
            configured_options=None,
            timeout_seconds=60,
        )
        return result

    @property
    def pass_id(self) -> str:
        return sha256(canonical(self.record())).hexdigest()


@dataclass(frozen=True, slots=True)
class ByteFunctionDiagnostic:
    ordinary_pass: OrdinaryBytePass
    reason: ExportReason | None
    graph: ByteGraph | None
    source: ByteSourceObservation | None
    facts: bytes | None

    def record(self) -> dict[str, object]:
        return {
            "function": _key_record(self.ordinary_pass.function),
            "pass": self.ordinary_pass.record(),
            "pass_id": self.ordinary_pass.pass_id,
            "status": "complete" if self.reason is None else "gap",
            "reason": self.reason,
            "graph": None if self.graph is None else self.graph.record(),
            "source": None if self.source is None else self.source.record(),
            "facts": None if self.facts is None else load_json(self.facts),
        }


@dataclass(frozen=True, slots=True)
class UnpublishedByteExport:
    binary_sha256: str
    lift: bytes
    mapping: bytes
    draft: bytes
    context: bytes
    functions: tuple[ByteFunctionDiagnostic, ...]
    status: Literal["UNPUBLISHED"] = "UNPUBLISHED"

    def to_bytes(self) -> bytes:
        """Return the canonical diagnostic record. Keep ordinary bytes separately."""
        return canonical(
            {
                "schema": 1,
                "status": self.status,
                "binary_sha256": self.binary_sha256,
                "lift_sha256": sha256(self.lift).hexdigest(),
                "mapping_sha256": sha256(self.mapping).hexdigest(),
                "draft_sha256": sha256(self.draft).hexdigest(),
                "context": load_json(self.context),
                "functions": [item.record() for item in self.functions],
            }
        )


def canonical(value: object) -> bytes:
    """Use the same canonical JSON encoding as the strict evidence readers."""
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("ascii")
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ByteExportError("format", "Invalid canonical diagnostic data.") from error


def _key_record(key: FunctionKey) -> dict[str, object]:
    return {"binary_sha256": key.binary_sha256, "ghidra_entry": hex(key.ghidra_entry)}


def _read(path: Path, maximum: int) -> bytes:
    try:
        if path.stat().st_size > maximum:
            raise ByteExportError("limit", "The diagnostic file exceeds its limit.")
        return bounded_read(path, limit=maximum, private=True)
    except (OSError, MappingError) as error:
        raise ByteExportError(
            "io", "Cannot read a private regular diagnostic file."
        ) from error


def _properties(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as error:
        raise ByteExportError("tool", "Invalid installed tool properties.") from error
    return {
        key: value.strip('"')
        for line in lines
        if "=" in line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }


def _context(
    binary: bytes, installation: Path, java_home: Path, limits: ByteExportLimits
) -> dict[str, object]:
    """Measure installed files. No caller-supplied digest is accepted here."""
    pins = tomllib.loads(_read(_ROOT / "tools.lock", 65536).decode("utf-8"))
    properties = _properties(
        _read(installation / "Ghidra/application.properties", 65536)
    )
    release = _properties(_read(java_home / "release", 65536))
    if (
        properties.get("application.version") != pins["ghidra"]
        or properties.get("application.revision.ghidra") != pins["ghidra_commit"]
        or release.get("SEMANTIC_VERSION") != pins["temurin_macos_arm64"]
        or release.get("JAVA_RUNTIME_VERSION") != pins["temurin_macos_arm64"] + "-LTS"
    ):
        raise ByteExportError("tool", "Installed tools do not match tools.lock.")
    if not any(installation.glob("Ghidra/Features/Decompiler/os/*/decompile")):
        raise ByteExportError("tool", "The installed native decompiler is missing.")
    try:
        tools = lifting_tool_identity(installation, java_home)
    except OSError as error:
        raise ByteExportError(
            "tool", "Cannot measure the installed lift tools."
        ) from error
    sources = {
        name: sha256(_read(_ROOT / name, 1024 * 1024)).hexdigest() for name in _SOURCES
    }
    return {
        "schema": 1,
        "binary_sha256": sha256(binary).hexdigest(),
        "ghidra_version": properties["application.version"],
        "ghidra_revision": properties["application.revision.ghidra"],
        "java_runtime_version": release["JAVA_RUNTIME_VERSION"],
        "sources": sources,
        "tools": tools,
        "limits": asdict(limits),
    }


def _size(raw: bytes, maximum: int) -> None:
    if type(raw) is not bytes:
        raise ByteExportError("format", "Expected exact bytes.")
    if len(raw) > maximum:
        raise ByteExportError(
            "limit", "The diagnostic artifact exceeds its byte limit."
        )


def _limits(limits: ByteExportLimits) -> None:
    if type(limits) is not ByteExportLimits:
        raise ByteExportError("limit", "Expected ByteExportLimits.")
    limits.__post_init__()


def _pass(
    value: object, ordinal: int, function: FunctionKey, context: dict[str, object]
) -> OrdinaryBytePass:
    record = object_fields(
        value,
        "schema function call_ordinal ghidra_version ghidra_revision language_id "
        "compiler_spec_id simplification_style configured_options timeout_seconds "
        "source_manifest_sha256 tool_manifest_sha256",
    )
    expected = OrdinaryBytePass(
        function,
        ordinal,
        cast(str, context["ghidra_version"]),
        cast(str, context["ghidra_revision"]),
        "x86:LE:64:default",
        "gcc",
        "decompile",
        sha256(canonical(context["sources"])).hexdigest(),
        sha256(canonical(context["tools"])).hexdigest(),
    )
    if canonical(record) != canonical(expected.record()):
        raise ByteExportError(
            "identity", "The ordinary pass differs from the retained profile."
        )
    return expected


def _facts(value: object, graph: ByteGraph) -> bytes:
    item = object_fields(value, "value_flags operation_states")
    flags, states = item["value_flags"], item["operation_states"]
    if type(flags) is not list or len(flags) != len(graph.values):
        raise ByteExportError("format", "The value flag inventory is incomplete.")
    graph_record = graph.record()
    raw_values = cast(list[dict[str, object]], graph_record["values"])
    for raw, observed, retained in zip(flags, graph.values, raw_values, strict=True):
        flag = object_fields(raw, "id is_input is_free")
        if canonical(flag["id"]) != canonical(retained["id"]):
            raise ByteExportError("identity", "A value flag names a different object.")
        is_input, is_free = flag["is_input"], flag["is_free"]
        if type(is_input) is not bool or type(is_free) is not bool:
            raise ByteExportError("format", "Expected actual Boolean value flags.")
        if observed.kind != "constant" and (is_input, is_free) != (
            observed.kind == "input",
            observed.kind == "free",
        ):
            raise ByteExportError("format", "The value flags contradict its kind.")
    expected = []
    for block in cast(list[dict[str, object]], graph_record["blocks"]):
        for operation in cast(list[dict[str, object]], block["operations"]):
            expected.append(
                {"id": operation["id"], "is_dead": False, "parent": block["id"]}
            )
    for operation_id in cast(list[object], graph_record["excluded_dead"]):
        expected.append({"id": operation_id, "is_dead": True, "parent": None})
    if type(states) is not list or len(states) != len(expected):
        raise ByteExportError("format", "The operation state inventory is incomplete.")
    expected_bytes = {canonical(state) for state in expected}
    actual_bytes = set()
    for state in states:
        obj = object_fields(state, "id is_dead parent")
        normalized = canonical({**obj, "is_dead": obj["parent"] is None})
        if type(obj["is_dead"]) is not bool or (
            obj["parent"] is None and obj["is_dead"] is not True
        ):
            raise ByteExportError(
                "format", "Excluded operations require an actual dead flag."
            )
        if obj["parent"] is not None and obj["is_dead"]:
            required = {
                "code": "cfg_unclosed",
                "block": None,
                "operation": obj["id"],
                "value": None,
            }
            if canonical(required) not in {
                canonical(gap)
                for gap in cast(list[object], graph_record["export_gaps"])
            }:
                raise ByteExportError(
                    "format", "A block-owned dead flag requires its API conflict gap."
                )
        if normalized not in expected_bytes or normalized in actual_bytes:
            raise ByteExportError(
                "format", "An operation state contradicts actual ownership."
            )
        actual_bytes.add(normalized)
    return canonical(item)


def _convert(
    binary: bytes,
    lift: bytes,
    mapping: bytes,
    draft: bytes,
    context: dict[str, object],
    limits: ByteExportLimits,
) -> UnpublishedByteExport:
    _limits(limits)
    for raw, maximum in (
        (binary, limits.max_program_bytes),
        (lift, limits.max_lift_bytes),
        (mapping, limits.max_mapping_bytes),
        (draft, limits.max_companion_bytes),
    ):
        _size(raw, maximum)
    if sum(map(len, (binary, lift, mapping, draft))) > limits.max_bundle_bytes:
        raise ByteExportError("limit", "The complete bundle exceeds its byte limit.")
    try:
        item = object_fields(load_json(draft), "schema status context functions")
        if (
            canonical(item) != draft
            or type(item["schema"]) is not int
            or item["schema"] != 1
        ):
            raise ByteExportError("format", "Expected canonical draft schema 1.")
        if item["status"] != "UNPUBLISHED" or canonical(item["context"]) != canonical(
            context
        ):
            raise ByteExportError(
                "identity", "The draft context differs from actual source or tools."
            )
        records = item["functions"]
        if type(records) is not list or not 0 < len(records) <= limits.max_functions:
            raise ByteExportError("limit", "Invalid complete function roster.")
        # Check the ordinary roster before the old reader builds its function indexes.
        ordinary = load_json(lift)
        roster = ordinary.get("functions")
        if type(roster) is not list or len(roster) != len(records):
            raise ByteExportError(
                "identity", "The draft does not retain every ordinary function."
            )
        entries = [
            hex_address(
                object_fields(object_fields(fn).get("entry"), "space offset")["offset"]
            )
            for fn in roster
        ]
        del ordinary
        index = parse_lift(lift, binary)
        mapped = parse_mapping(mapping, binary, lift)
        if (index.image_base, index.startup) != (mapped.image_base, mapped.startup):
            raise ByteExportError("identity", "The ordinary lift and mapping disagree.")
        functions = []
        for ordinal, raw_record in enumerate(records):
            record = object_fields(
                raw_record, "function pass pass_id status reason graph source facts"
            )
            key = object_fields(record["function"], "binary_sha256 ghidra_entry")
            function = FunctionKey(
                digest(key["binary_sha256"]), GhidraVA(hex_address(key["ghidra_entry"]))
            )
            if (
                function.binary_sha256 != index.binary_sha256
                or function.ghidra_entry != entries[ordinal]
            ):
                raise ByteExportError(
                    "identity", "The function roster or binary differs."
                )
            ordinary_pass = _pass(record["pass"], ordinal, function, context)
            if digest(record["pass_id"]) != ordinary_pass.pass_id:
                raise ByteExportError(
                    "identity", "The pass digest differs from the retained record."
                )
            reason = record["reason"]
            if reason is not None and (
                type(reason) is not str or reason not in _REASONS
            ):
                raise ByteExportError("format", "Unknown diagnostic gap.")
            if record["status"] != ("complete" if reason is None else "gap"):
                raise ByteExportError("format", "The disposition contradicts its gap.")
            graph = None
            source = None
            facts = None
            if record["graph"] is None:
                if (
                    record["source"] is not None
                    or record["facts"] is not None
                    or reason
                    not in (
                        "decompile_unavailable",
                        "region_limit",
                        "unsupported_profile",
                        "graph_unrepresentable",
                        "sequence_unrepresentable",
                        "block_unrepresentable",
                        "value_unrepresentable",
                        "value_id_conflict",
                        "definition_unrepresentable",
                        "constant_unrepresentable",
                        "value_flags_conflict",
                        "operation_ownership_conflict",
                        "entry_unrepresentable",
                        "operation_id_conflict",
                        "dead_partition_conflict",
                        "operation_inventory_conflict",
                        "conditional_unrepresentable",
                        "phi_unrepresentable",
                        "edge_unrepresentable",
                        "address_unrepresentable",
                        "source_link_unavailable",
                    )
                ):
                    raise ByteExportError(
                        "format", "An absent graph requires an explicit gap."
                    )
            else:
                graph_item = object_fields(
                    record["graph"],
                    " ".join(
                        f.name for f in fields(ByteGraph) if f.name != "lift_sha256"
                    ),
                )
                source_item = object_fields(
                    record["source"],
                    " ".join(
                        f.name
                        for f in fields(ByteSourceObservation)
                        if f.name != "lift_sha256"
                    ),
                )
                graph_bytes = canonical(
                    {**graph_item, "lift_sha256": index.lift_sha256}
                )
                source_bytes = canonical(
                    {**source_item, "lift_sha256": index.lift_sha256}
                )
                graph = parse_byte_graph(graph_bytes, index, limits=limits.graph)
                source = parse_byte_source(
                    source_bytes, index, graph, limits=limits.source
                )
                if graph.function != function or graph.pass_id != ordinary_pass.pass_id:
                    raise ByteExportError(
                        "identity", "The graph belongs to a different ordinary call."
                    )
                facts = _facts(record["facts"], graph)
                has_gap = bool(graph.export_gaps or source.gaps)
                if source.source_status == "unavailable":
                    if reason not in (
                        "region_limit",
                        "empty_printer_token",
                        "printer_bytes_differ",
                        "source_link_unavailable",
                    ):
                        raise ByteExportError(
                            "format", "An unavailable source needs its printer gap."
                        )
                elif reason != ("evidence_gap" if has_gap else None):
                    raise ByteExportError(
                        "format", "The disposition omits or invents an evidence gap."
                    )
            functions.append(
                ByteFunctionDiagnostic(ordinary_pass, reason, graph, source, facts)
            )
        result = UnpublishedByteExport(
            index.binary_sha256,
            lift,
            mapping,
            draft,
            canonical(context),
            tuple(functions),
        )
        final = result.to_bytes()
        if (
            len(final) > limits.max_companion_bytes
            or sum(map(len, (binary, lift, mapping, final))) > limits.max_bundle_bytes
        ):
            raise ByteExportError(
                "limit", "The finalized bundle exceeds its byte limit."
            )
        return result
    except MappingError as error:
        raise ByteExportError(
            "format", "Invalid ordinary lift or diagnostic record."
        ) from error
    except (ByteGraphError, ByteSourceError) as error:
        raise ByteExportError(
            "format", "The strict byte reader rejected a complete proposal."
        ) from error


def convert_byte_export(
    binary: bytes,
    lift: bytes,
    mapping: bytes,
    draft: bytes,
    *,
    installation: Path,
    java_home: Path,
    limits: ByteExportLimits = ByteExportLimits(),
) -> UnpublishedByteExport:
    """Validate an unpublished draft against current installed source and tool bytes.

    Pass IDs bind a configuration and call ordinal. They do not authenticate a process.
    """
    _limits(limits)
    _size(binary, limits.max_program_bytes)
    context = _context(binary, _resolve(installation), _resolve(java_home), limits)
    return _convert(binary, lift, mapping, draft, context, limits)


def _headless(command: list[str], work: Path, env: dict[str, str]) -> None:
    deadline = time.monotonic() + 300
    log = work / "headless.log"
    with ExitStack() as cleanup:
        stream = _io(lambda: log.open("xb"))
        cleanup.callback(_io, stream.close)
        try:
            process = subprocess.Popen(
                command,
                cwd=work,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            raise ByteExportError(
                "headless", "Cannot start the pinned headless job."
            ) from error
        try:
            while True:
                if _io(lambda: log.stat().st_size) > 8 * 1024 * 1024:
                    raise ByteExportError(
                        "limit", "The headless diagnostic log exceeds 8 MiB."
                    )
                if time.monotonic() >= deadline:
                    raise ByteExportError(
                        "timeout", "The headless job exceeded 300 seconds."
                    )
                try:
                    exit_code = process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if _io(lambda: log.stat().st_size) > 8 * 1024 * 1024:
                raise ByteExportError(
                    "limit", "The headless diagnostic log exceeds 8 MiB."
                )
            if exit_code:
                raise ByteExportError(
                    "headless", f"The headless job failed with exit {exit_code}."
                )
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def export_byte_diagnostic(
    binary: Path,
    staging_root: Path,
    *,
    installation: Path,
    java_home: Path,
    limits: ByteExportLimits = ByteExportLimits(),
) -> UnpublishedByteExport:
    """Run one static job in owned external staging. Never publish or select it."""
    _limits(limits)
    workspace = _resolve(Path(os.environ["PHOENIX_ROOT"]))
    staging_root = _resolve(staging_root, strict=True)
    if staging_root == workspace or workspace not in staging_root.parents:
        raise ByteExportError(
            "io", "Use an owned staging directory under PHOENIX_ROOT."
        )
    original = _read(binary, limits.max_program_bytes)
    installation, java_home = _resolve(installation), _resolve(java_home)
    context = _context(original, installation, java_home, limits)
    with ExitStack() as cleanup:
        owned = _io(
            lambda: TemporaryDirectory(prefix="byte-diagnostic-", dir=staging_root)
        )
        cleanup.callback(_io, owned.cleanup)
        work = Path(owned.name)
        scripts, output = work / "scripts", work / "output"
        _io(scripts.mkdir)
        _io(output.mkdir)
        for name in _SCRIPTS:
            raw_script = _read(_ROOT / "ghidra_scripts" / name, 1024 * 1024)
            _io(lambda: (scripts / name).write_bytes(raw_script))
        source = work / "input.elf"
        _io(lambda: source.write_bytes(original))
        context_path = work / "context.json"
        context_raw = canonical(context)
        _io(lambda: context_path.write_bytes(context_raw))
        java_path = str(work).replace("\\", "\\\\").replace('"', '\\"')
        java_args = "-Xmx512m\n" + "".join(
            f'-D{name}="{java_path}"\n'
            for name in (
                "user.home",
                "java.io.tmpdir",
                "application.settingsdir",
                "application.cachedir",
                "application.tempdir",
            )
        )
        _io(lambda: (work / "java.args").write_text(java_args, encoding="utf-8"))
        env = {
            **os.environ,
            "JAVA_HOME": str(java_home),
            "JDK_JAVA_OPTIONS": "@java.args",
            "PATH": f"{java_home / 'bin'}{os.pathsep}{os.defpath}",
            "XDG_CONFIG_HOME": str(work),
            "XDG_CACHE_HOME": str(work),
            "XDG_DATA_HOME": str(work),
            "TMPDIR": str(work),
            "GHIDRA_HEADLESS_MAXMEM": "512M",
            "GHIDRA_JAVA_OPTIONS": "",
            "GHIDRA_HEADLESS_JAVA_OPTIONS": "",
            "JAVA_TOOL_OPTIONS": "",
            "_JAVA_OPTIONS": "",
        }
        command = [
            str(installation / "support/analyzeHeadless"),
            str(work),
            "phoenix-byte-diagnostic",
            "-import",
            str(source),
            "-readOnly",
            "-max-cpu",
            "1",
            "-analysisTimeoutPerFile",
            "120",
            "-scriptPath",
            str(scripts),
            "-log",
            str(work / "analysis.log"),
            "-scriptlog",
            str(work / "script.log"),
            "-postScript",
            "ExportLift.java",
            str(output / "lift.json"),
            "--byte-diagnostic",
            str(output / "byte-draft.json"),
            str(context_path),
            "-postScript",
            "ExportMapping.java",
            str(output / "mapping.json"),
            str(output / "lift.json"),
        ]
        _headless(command, work, env)
        if _io(lambda: {path.name for path in output.iterdir()}) != {
            "lift.json",
            "mapping.json",
            "byte-draft.json",
        }:
            raise ByteExportError(
                "io", "The diagnostic output file set is incomplete or has extra files."
            )
        if (
            _read(binary, limits.max_program_bytes) != original
            or _read(source, limits.max_program_bytes) != original
        ):
            raise ByteExportError(
                "identity", "The input binary changed during the static job."
            )
        for name in _SCRIPTS:
            if (
                sha256(_read(scripts / name, 1024 * 1024)).hexdigest()
                != object_fields(context["sources"])[f"ghidra_scripts/{name}"]
            ):
                raise ByteExportError(
                    "identity", "A staged exporter changed during the static job."
                )
        if canonical(_context(original, installation, java_home, limits)) != canonical(
            context
        ):
            raise ByteExportError(
                "identity", "Source or tool bytes changed during the static job."
            )
        return _convert(
            original,
            _read(output / "lift.json", limits.max_lift_bytes),
            _read(output / "mapping.json", limits.max_mapping_bytes),
            _read(output / "byte-draft.json", limits.max_companion_bytes),
            context,
            limits,
        )
