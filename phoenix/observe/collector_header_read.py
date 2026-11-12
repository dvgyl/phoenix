"""Decode the finite typed-header grammar. This is not compiled-data inspection."""

import io
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from phoenix.observe.collector_data import FrozenRecord, RecordValue

# Each descriptor fixes a native field type and its logical meaning.
# r is one record, a is a slice, o is an option, and v is a tagged variant.
SCHEMA: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("uints", "$scalar", (("value", "u"),)),
    ("strings", "$scalar", (("value", "s"),)),
    ("registers", "$pair", (("name", "s"), ("width", "u"))),
    ("plan_gaps", "$pair", (("address", "u"), ("reason", "s"))),
    ("positions", "$pair", (("route_sha256", "h"), ("position", "u"))),
    (
        "dispositions",
        "$pair",
        (("address", "u"), ("disposition", "v:user,transit,omitted")),
    ),
    ("dynamic", "$pair", (("tag", "i"), ("value", "u"))),
    ("original", "Original", (("bytes", "u"), ("sha256", "h"))),
    (
        "geometry",
        "Geometry",
        (
            ("executable_file_start", "u"),
            ("executable_file_end_exclusive", "end:executable_file_start"),
            ("load_memory_start", "u"),
            ("load_memory_end_exclusive", "end:load_memory_start"),
        ),
    ),
    (
        "transport_limits",
        "TransportLimits",
        tuple(
            (name, "u")
            for name in (
                "data_bytes",
                "elf_segments",
                "gap_records",
                "lift_bytes",
                "mapping_bytes",
                "omissions",
                "original_bytes",
                "route_memberships",
                "route_path_positions",
                "routes",
                "users",
            )
        ),
    ),
    (
        "trace_limits",
        "TraceLimits",
        tuple(
            (name, "u")
            for name in (
                "events",
                "execution_callbacks",
                "frames",
                "snapshot_bytes",
                "translated_instructions",
                "wire_bytes",
            )
        ),
    ),
    (
        "capture_limits",
        "CaptureLimits",
        tuple(
            (name, "u")
            for name in (
                "events",
                "execution_callbacks",
                "frames",
                "full_plan_bytes",
                "full_plan_sites",
                "guarded_instructions",
                "receipt_bytes",
                "route_entries",
                "scope_bytes",
                "snapshot_bytes",
                "thunk_neutral_bytes",
                "thunk_neutral_instructions",
                "translated_instructions",
                "wire_bytes",
            )
        ),
    ),
    (
        "import_id",
        "ImportId",
        (
            ("needed_library", "o:s"),
            ("symbol", "s"),
            ("version", "o:s"),
            ("version_hidden", "b"),
        ),
    ),
    (
        "import_binding",
        "ImportBinding",
        (
            ("address_proof_sha256", "h"),
            ("binary_sha256", "h"),
            ("function", "o:u"),
            ("gap", "o:s"),
            ("identity", "o:r:import_id"),
            ("lift_sha256", "h"),
            ("relocation_file_offset", "o:u"),
            ("relocation_kind", "o:u"),
            ("relocation_slot", "o:u"),
            ("site", "u"),
            ("symbol_index", "o:u"),
            ("thunk_path", "a:uints"),
        ),
    ),
    (
        "call",
        "Call",
        (
            ("continuation", "u"),
            ("import_gaps", "a:strings"),
            ("imported", "o:r:import_binding"),
            ("kind", "e:direct_call|indirect_call"),
        ),
    ),
    ("jump", "Jump", (("kind", "e:indirect_jump"),)),
    ("return", "Return", (("kind", "e:return"),)),
    (
        "trace_site",
        "TraceSite",
        (
            ("address", "u"),
            ("continuation_of", "a:uints"),
            ("entry", "b"),
            ("owner", "u"),
            ("transfer", "v0:call,jump,return"),
            ("witness_hex", "w"),
        ),
    ),
    (
        "trace_plan",
        "TracePlan",
        (
            ("address_proof_sha256", "h"),
            ("binary_sha256", "h"),
            ("gaps", "a:plan_gaps"),
            ("lift_sha256", "h"),
            ("limits", "r:trace_limits"),
            ("registers", "a:registers"),
            ("schema", "n:2"),
            ("scope", "a:uints"),
            ("sites", "a:trace_site"),
        ),
    ),
    (
        "lift_main",
        "LiftMain",
        (
            ("kind", "e:lift_main"),
            ("lift_sha256", "h"),
            ("main_elf", "u"),
        ),
    ),
    (
        "explicit_entry",
        "ExplicitEntry",
        (
            ("kind", "e:explicit_entry"),
            ("request_sha256", "h"),
        ),
    ),
    (
        "requested_scope",
        "RequestedScope",
        (
            ("policy", "e:main-window-six-v1"),
            ("root", "u"),
            ("root_evidence", "v:lift_main,explicit_entry"),
            ("users", "a:uints"),
        ),
    ),
    ("user", "User", (("kind", "e:user"), ("owner", "u"))),
    ("transit", "Transit", (("kind", "e:transit"), ("route_ids", "a:strings"))),
    (
        "omitted",
        "Omitted",
        (
            ("kind", "e:omitted"),
            ("reason", "e:outside_requested_users|runtime_lifecycle_outside_window"),
        ),
    ),
    (
        "omitted_site",
        "OmittedSite",
        (
            ("address", "u"),
            ("full_roles", "a:strings"),
            ("owner", "u"),
            ("reason", "e:outside_requested_users|runtime_lifecycle_outside_window"),
            ("witness_sha256", "h"),
        ),
    ),
    (
        "transit_route",
        "TransitRoute",
        (
            ("binding_sha256", "h"),
            ("call_site", "u"),
            ("entries", "a:uints"),
            ("instruction_path", "a:uints"),
            ("request", "r:import_id"),
            ("slot", "u"),
            ("terminal", "u"),
        ),
    ),
    ("ordinary", "Ordinary", (("kind", "e:ordinary"), ("successor", "u"))),
    ("local_direct", "LocalDirect", (("destination", "u"), ("kind", "e:local_direct"))),
    (
        "local_conditional",
        "LocalConditional",
        (
            ("fallthrough", "u"),
            ("kind", "e:local_conditional"),
            ("taken", "u"),
        ),
    ),
    (
        "planned_roles",
        "PlannedRoles",
        (
            ("continuation", "o:u"),
            ("destination", "o:u"),
            ("kind", "e:planned_roles"),
            ("transfer_kind", "e:direct_call|indirect_call|indirect_jump|return"),
        ),
    ),
    (
        "transit_instruction",
        "TransitInstruction",
        (
            ("kind", "e:transit_instruction"),
            ("positions", "a:positions"),
        ),
    ),
    ("reject", "Reject", (("kind", "e:reject"), ("reason", "s"))),
    (
        "guard_instruction",
        "GuardInstruction",
        (
            ("address", "u"),
            ("full_roles", "a:strings"),
            ("owner", "u"),
            (
                "rule",
                "v:ordinary,local_direct,local_conditional,planned_roles,transit_instruction,reject",
            ),
            ("witness_hex", "w"),
        ),
    ),
    (
        "dormant_outside_window",
        "DormantOutsideWindow",
        (
            ("kind", "e:dormant_outside_window"),
            ("reason", "s"),
        ),
    ),
    ("guard_reject", "GuardReject", (("kind", "e:guard_reject"), ("reason", "s"))),
    (
        "local_branch_guard",
        "LocalBranchGuard",
        (
            ("destination", "u"),
            ("fallthrough", "o:u"),
            ("kind", "e:local_branch_guard"),
            ("rule", "e:local_direct|local_conditional"),
        ),
    ),
    ("metadata_only", "MetadataOnly", (("kind", "e:metadata_only"), ("reason", "s"))),
    (
        "gap_record",
        "GapRecord",
        (
            ("address", "u"),
            (
                "disposition",
                "v:dormant_outside_window,guard_reject,local_branch_guard,metadata_only",
            ),
            ("domain", "e:ghidra"),
            ("elf", "o:u"),
            ("index", "u"),
            ("reason", "s"),
        ),
    ),
    (
        "exit_from_supported_bits",
        "ExitFromSupportedBits",
        (
            ("register", "s"),
            ("transform", "s"),
            ("width", "u"),
        ),
    ),
    ("exact_signal", "ExactSignal", (("signal", "u"),)),
    (
        "termination_contract",
        "TerminationContract",
        (
            ("behavior", "e:process-termination"),
            ("binary_sha256", "h"),
            ("call_site", "u"),
            ("callbacks", "e:forbidden"),
            ("cleanup", "e:no-unobserved-main-reentry"),
            ("full_plan_sha256", "h"),
            ("import_binding_sha256", "o:h"),
            ("permitted_physical_route_sha256", "h"),
            ("provider_evidence_sha256", "h"),
            ("rule_sha256", "h"),
            ("runtime_manifest_base_sha256", "h"),
            ("schema", "n:1"),
            ("termination_rule", "v:exit_from_supported_bits,exact_signal"),
        ),
    ),
    (
        "scope_selection",
        "ScopeSelection",
        (
            ("active_unlisted", "e:reject"),
            ("address_proof_sha256", "h"),
            ("binary_sha256", "h"),
            ("claim", "e:requested-main-activation"),
            ("contracts", "a:termination_contract"),
            ("dispositions", "a:dispositions"),
            ("full_plan_sha256", "h"),
            ("gap_dispositions", "a:gap_record"),
            ("guard_instructions", "a:guard_instruction"),
            ("lazy_resolver", "e:unsupported"),
            ("lift_sha256", "h"),
            ("limits", "r:capture_limits"),
            ("omitted", "a:omitted_site"),
            ("outside_window", "e:all-sites-outside-frame-capture"),
            ("policy", "e:main-window-six-v1"),
            ("policy_implementation_sha256", "h"),
            ("registers", "a:registers"),
            ("request", "r:requested_scope"),
            ("root", "u"),
            ("routes", "a:transit_route"),
            ("schema", "n:1"),
            ("transit_profile", "e:eager-only"),
            ("users", "a:uints"),
        ),
    ),
    (
        "load_segment",
        "LoadSegment",
        tuple(
            (name, "u")
            for name in (
                "alignment",
                "file_offset",
                "file_size",
                "flags",
                "index",
                "memory_size",
                "va",
            )
        ),
    ),
    (
        "elf_image",
        "ElfImage",
        (
            ("dynamic", "a:dynamic"),
            ("entry", "u"),
            ("kind", "u"),
            ("segments", "a:load_segment"),
        ),
    ),
    (
        "collector_data",
        "CollectorData",
        (
            ("address_proof_sha256", "h"),
            ("c_data_schema", "e:phoenix-eager-c-data-1"),
            ("full_plan", "r:trace_plan"),
            ("full_plan_sha256", "h"),
            ("geometry", "r:geometry"),
            ("image", "r:elf_image"),
            ("lift_sha256", "h"),
            ("original", "r:original"),
            ("policy_implementation_sha256", "h"),
            ("profile", "e:main-window-six-v1"),
            ("schema", "e:phoenix-eager-collector-data-1"),
            ("scope", "r:scope_selection"),
            ("scope_sha256", "h"),
            ("transport_limits", "r:transport_limits"),
        ),
    ),
)

TABLES = ("bytes", *(name for name, _, _ in SCHEMA))
FIELDS = {name: fields for name, _, fields in SCHEMA}
KINDS = {name: kind for name, kind, _ in SCHEMA}
PREFIX = '#include "collector_data_v1.h"\n'
SUFFIX = "};\n"
NATIVE_NAME = "phoenix/observe/native/collector_data_v1.h"
MAX_SOURCE = 64 * 1024 * 1024
MAX_STORAGE = 32 * 1024 * 1024
MAX_NATIVE = 2 * 1024 * 1024
U64 = (1 << 64) - 1
DIRECTORY_BYTES = 3 * 32 + len(TABLES) * 7 * 8


class HeaderReadError(ValueError):
    """The source is outside the fixed header grammar or its bounds."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HeaderReadError(message)


def width(descriptor: str) -> int:
    if descriptor.startswith("o:"):
        return 1 + width(descriptor[2:])
    if descriptor.startswith(("v:", "v0:")):
        return 1 + 2 * len(descriptor.split(":", 1)[1].split(","))
    if descriptor in ("s", "h", "w", "i") or descriptor.startswith(("a:", "r:", "e:")):
        return 2
    return 1


def field_bytes(descriptor: str) -> int:
    if descriptor.startswith("o:"):
        return 8 + field_bytes(descriptor[2:])
    if descriptor.startswith(("v:", "v0:")):
        return 8 + 8 * len(descriptor.split(":", 1)[1].split(","))
    if descriptor == "i":
        return 16
    return 8


def element_bytes(table: str) -> int:
    return 1 if table == "bytes" else sum(field_bytes(d) for _, d in FIELDS[table])


def native_bytes() -> bytes:
    path = Path(__file__).resolve().parents[2] / NATIVE_NAME
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_NATIVE + 1)
    except OSError as error:
        raise HeaderReadError("Cannot read the fixed native declarations.") from error
    require(0 < len(raw) <= MAX_NATIVE, "The native declarations exceed their bound.")
    return raw


def renderer_identity() -> str:
    """Hash actual fixed Python source bytes through an acyclic manifest."""
    root = Path(__file__).resolve().parents[2]
    entries = []
    for name in (
        "phoenix/observe/collector_header.py",
        "phoenix/observe/collector_header_read.py",
    ):
        try:
            with (root / name).open("rb") as stream:
                raw = stream.read(MAX_NATIVE + 1)
        except OSError as error:
            raise HeaderReadError("Cannot read a fixed renderer source.") from error
        require(0 < len(raw) <= MAX_NATIVE, "A renderer source exceeds its bound.")
        entries.append((name, len(raw), sha256(raw).hexdigest()))
    manifest = (json.dumps(entries, separators=(",", ":")) + "\n").encode("ascii")
    return sha256(manifest).hexdigest()


def uint(value: int) -> str:
    return f"UINT64_C(0x{value:016x})"


def declaration(table: str, count: int) -> str:
    ctype = "uint8_t" if table == "bytes" else f"struct phoenix_{table}_v1"
    return f"static const {ctype} phoenix_{table}[{max(1, count)}] = {{\n"


def directory_entry(table: str, count: int) -> str:
    tag = TABLES.index(table) + 1
    size = element_bytes(table)
    ctype = "uint8_t" if table == "bytes" else f"struct phoenix_{table}_v1"
    return (
        "    {"
        + ", ".join(uint(n) for n in (tag, count, size, count * size))
        + f", sizeof({ctype}), sizeof(phoenix_{table}), phoenix_{table}"
        + "},\n"
    )


DIRECTORY = (
    "PHOENIX_DATA_EXPORT const struct phoenix_data_directory_v1 "
    "phoenix_collector_data_v1 = {\n"
)


@dataclass(frozen=True, slots=True)
class DecodedHeader:
    record: FrozenRecord
    logical_data_sha256: str
    renderer_sha256: str
    native_source_sha256: str
    counts: tuple[tuple[str, int], ...]
    initializer_bytes: int


type Cell = int | tuple[Cell, ...]


class _LineParser:
    def __init__(self, line: str) -> None:
        self.line = line
        self.at = 0

    def literal(self, text: str) -> None:
        require(self.line.startswith(text, self.at), "Invalid initializer syntax.")
        self.at += len(text)

    def number(self) -> int:
        token = self.line[self.at : self.at + 28]
        require(
            re.fullmatch(r"UINT64_C\(0x[0-9a-f]{16}\)", token) is not None,
            "Invalid unsigned constant.",
        )
        self.at += 28
        return int(token[11:27], 16)

    def pair(self) -> tuple[int, int]:
        self.literal("{")
        first = self.number()
        self.literal(", ")
        second = self.number()
        self.literal("}")
        return first, second

    def field(self, descriptor: str) -> Cell:
        if descriptor.startswith("o:"):
            self.literal("{")
            tag = self.number()
            self.literal(", ")
            payload = self.field(descriptor[2:])
            self.literal("}")
            return tag, payload
        if descriptor.startswith(("v:", "v0:")):
            self.literal("{")
            tag = self.number()
            payloads: list[Cell] = [tag]
            for _ in descriptor.split(":", 1)[1].split(","):
                self.literal(", ")
                payloads.append(self.pair())
            self.literal("}")
            return tuple(payloads)
        if width(descriptor) == 2:
            return self.pair()
        return self.number()

    def row(self, table: str) -> tuple[Cell, ...]:
        self.literal("    {")
        output = []
        for index, (_, descriptor) in enumerate(FIELDS[table]):
            if index:
                self.literal(", ")
            output.append(self.field(descriptor))
        self.literal("},\n")
        require(self.at == len(self.line), "Trailing initializer source.")
        return tuple(output)


class _Decoder:
    def __init__(
        self, tables: dict[str, tuple[tuple[Cell, ...], ...]], raw_bytes: bytes
    ) -> None:
        self.tables = tables
        self.raw_bytes = raw_bytes
        self.cursors = dict.fromkeys(TABLES, 0)

    def slice(self, table: str, cell: Cell) -> tuple[int, int]:
        require(type(cell) is tuple and len(cell) == 2, "Invalid slice shape.")
        offset, count = cast(tuple[int, int], cell)
        total = len(self.raw_bytes) if table == "bytes" else len(self.tables[table])
        require(
            offset <= total and count <= total - offset, "The slice exceeds its table."
        )
        require(offset == self.cursors[table], "Noncanonical or reused logical slice.")
        self.cursors[table] += count
        return offset, count

    def value(
        self, descriptor: str, cell: Cell, previous: dict[str, RecordValue]
    ) -> RecordValue:
        if descriptor.startswith("o:"):
            tag, payload = cast(tuple[int, Cell], cell)
            require(tag in (0, 1), "Invalid option tag.")
            if tag == 0:
                require(_zero(payload), "A null option has a payload.")
                return None
            return self.value(descriptor[2:], payload, previous)
        if descriptor.startswith(("v:", "v0:")):
            parts = cast(tuple[Cell, ...], cell)
            tag = cast(int, parts[0])
            alternatives = descriptor.split(":", 1)[1].split(",")
            require(
                (0 if descriptor.startswith("v0:") else 1) <= tag <= len(alternatives),
                "Invalid variant tag.",
            )
            for index, payload in enumerate(parts[1:], 1):
                if index != tag:
                    require(_zero(payload), "An inactive variant has a payload.")
            return (
                None
                if tag == 0
                else self.value("r:" + alternatives[tag - 1], parts[tag], previous)
            )
        if descriptor.startswith(("a:", "r:")):
            table = descriptor[2:]
            offset, count = self.slice(table, cell)
            if descriptor.startswith("r:"):
                require(count == 1, "A record reference must contain one row.")
            decoded = tuple(
                self.record(table, row)
                for row in self.tables[table][offset : offset + count]
            )
            return decoded[0] if descriptor.startswith("r:") else decoded
        if descriptor in ("s", "h", "w") or descriptor.startswith("e:"):
            offset, count = self.slice("bytes", cell)
            raw = self.raw_bytes[offset : offset + count]
            if descriptor == "w":
                require(1 <= count <= 15, "Invalid instruction witness length.")
                return raw.hex()
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeError as error:
                raise HeaderReadError("Invalid UTF-8 data.") from error
            if descriptor == "h":
                require(
                    re.fullmatch("[0-9a-f]{64}", text) is not None,
                    "Invalid digest data.",
                )
            if descriptor.startswith("e:"):
                require(text in descriptor[2:].split("|"), "Invalid literal value.")
            return text
        if descriptor == "i":
            sign, magnitude = cast(tuple[int, int], cell)
            require(
                sign in (0, 1)
                and magnitude <= (1 << 63) - (1 - sign)
                and not (sign and magnitude == 0),
                "Invalid signed dynamic tag.",
            )
            return -magnitude if sign else magnitude
        value = cast(int, cell)
        if descriptor == "b":
            require(value in (0, 1), "Invalid Boolean value.")
            return bool(value)
        if descriptor.startswith("n:"):
            require(value == int(descriptor[2:]), "Invalid schema number.")
        if descriptor.startswith("end:"):
            value += cast(int, previous[descriptor[4:]])
            require(value <= 1 << 64, "Geometry overflows unsigned 64-bit bounds.")
        return value

    def record(self, table: str, row: tuple[Cell, ...]) -> RecordValue:
        output: dict[str, RecordValue] = {}
        for (name, descriptor), cell in zip(FIELDS[table], row, strict=True):
            output[name] = self.value(descriptor, cell, output)
        if KINDS[table] == "$scalar":
            return output["value"]
        if KINDS[table] == "$pair":
            return tuple(output.values())
        return FrozenRecord(tuple(sorted(output.items())))


def _zero(cell: Cell) -> bool:
    return (
        cell == 0
        if type(cell) is int
        else all(_zero(child) for child in cast(tuple[Cell, ...], cell))
    )


def _logical_digest(record: FrozenRecord) -> str:
    root = dict(record.entries)
    transport = root["transport_limits"]
    require(isinstance(transport, FrozenRecord), "Invalid logical transport limits.")
    maximum = dict(cast(FrozenRecord, transport).entries)["data_bytes"]
    require(
        type(maximum) is int and 0 < maximum <= 16 * 1024 * 1024,
        "Invalid logical data byte limit.",
    )
    digest = sha256()
    length = 1

    def append(token: str) -> None:
        nonlocal length
        length += len(token)
        require(
            length <= cast(int, maximum),
            "The logical record exceeds its lower byte bound.",
        )
        digest.update(token.encode("ascii"))

    def visit(value: RecordValue) -> None:
        if isinstance(value, FrozenRecord):
            append("{")
            for index, (name, child) in enumerate(value.entries):
                if index:
                    append(",")
                append(json.dumps(name) + ":")
                visit(child)
            append("}")
        elif isinstance(value, tuple):
            append("[")
            for index, child in enumerate(value):
                if index:
                    append(",")
                visit(child)
            append("]")
        elif isinstance(value, str):
            append('"')
            for character in value:
                append(json.dumps(character, ensure_ascii=True)[1:-1])
            append('"')
        else:
            append(json.dumps(value, ensure_ascii=True, separators=(",", ":")))

    visit(record)
    digest.update(b"\n")
    return digest.hexdigest()


def read_header(
    raw: bytes, *, source_bytes: int = MAX_SOURCE, initializer_bytes: int = MAX_STORAGE
) -> DecodedHeader:
    """Read exact generated syntax and validate the complete table directory."""
    require(
        type(source_bytes) is int
        and 0 < source_bytes <= MAX_SOURCE
        and type(initializer_bytes) is int
        and 0 < initializer_bytes <= MAX_STORAGE,
        "Invalid reader limits.",
    )
    require(
        type(raw) is bytes and 0 < len(raw) <= source_bytes,
        "Invalid header byte bound or type.",
    )
    try:
        text = raw.decode("ascii")
    except UnicodeError as error:
        raise HeaderReadError("The header source must be ASCII.") from error
    lines = io.StringIO(text)

    def take() -> str:
        return lines.readline()

    require(take() == PREFIX, "Invalid fixed include.")
    counts: list[tuple[str, int]] = []
    tables: dict[str, tuple[tuple[Cell, ...], ...]] = {}
    octets = bytearray()
    storage = DIRECTORY_BYTES
    require(storage <= initializer_bytes, "The directory exceeds its byte bound.")
    for table in TABLES:
        line = take()
        match = re.search(r"\[([1-9][0-9]*)\] = \{\n$", line)
        require(match is not None and len(match[1]) <= 10, "Invalid table extent.")
        assert match is not None
        extent = int(match[1])
        require(
            line == declaration(table, extent),
            "Missing, extra, or altered table declaration.",
        )
        first = take()
        empty = first == ("    0x00,\n" if table == "bytes" else "    {0},\n")
        count = 0 if empty else extent
        require(not empty or extent == 1, "Invalid empty table storage.")
        storage += count * element_bytes(table)
        require(
            storage <= initializer_bytes, "Logical constants exceed their byte bound."
        )
        rows = []
        for index in range(count):
            current = first if index == 0 else take()
            if table == "bytes":
                require(
                    re.fullmatch(r"    0x[0-9a-f]{2},\n", current) is not None,
                    "Invalid byte constant.",
                )
                octets.append(int(current[6:8], 16))
            else:
                rows.append(_LineParser(current).row(table))
        require(take() == SUFFIX, "Invalid table terminator or extra row.")
        counts.append((table, count))
        if table != "bytes":
            tables[table] = tuple(rows)
    require(take() == DIRECTORY, "Missing fixed table directory.")
    identities = []
    for _ in range(3):
        line = take()
        require(
            re.fullmatch(r"    \{0x[0-9a-f]{2}(, 0x[0-9a-f]{2}){31}\},\n", line)
            is not None,
            "Invalid directory identity.",
        )
        identities.append(
            bytes(
                int(token, 16) for token in re.findall(r"0x([0-9a-f]{2})", line)
            ).hex()
        )
    require(take() == "    {\n", "Invalid directory inventory.")
    for table, count in counts:
        require(
            take() == directory_entry(table, count), "Altered table directory entry."
        )
    require(
        take() == "    }\n" and take() == SUFFIX and take() == "",
        "Trailing or incomplete source.",
    )
    require(len(tables["collector_data"]) == 1, "The root table must have one row.")
    decoder = _Decoder(tables, bytes(octets))
    decoder.cursors["collector_data"] = 1
    record = decoder.record("collector_data", tables["collector_data"][0])
    require(isinstance(record, FrozenRecord), "Invalid logical root.")
    require(
        all(decoder.cursors[table] == count for table, count in counts),
        "Unreferenced table rows or bytes.",
    )
    require(
        _logical_digest(cast(FrozenRecord, record)) == identities[0],
        "The logical data identity differs.",
    )
    require(
        renderer_identity() == identities[1], "The renderer source identity differs."
    )
    require(
        sha256(native_bytes()).hexdigest() == identities[2],
        "The native declaration identity differs.",
    )
    return DecodedHeader(
        cast(FrozenRecord, record),
        identities[0],
        identities[1],
        identities[2],
        tuple(counts),
        storage,
    )
