"""Installed candidate layouts. Neither definition approves native output."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

type Machine = Literal[62, 183]
type ProfileId = Literal["linux-x86_64-lp64-le-rela-1", "linux-aarch64-lp64-le-rela-1"]
type RecordKind = Literal["storage", "scalar", "pair", "object"]


@dataclass(frozen=True, slots=True)
class UInt64:
    pass


@dataclass(frozen=True, slots=True)
class Boolean64:
    pass


@dataclass(frozen=True, slots=True)
class ExactNumber:
    value: int


@dataclass(frozen=True, slots=True)
class EndFrom:
    prior_name: str


@dataclass(frozen=True, slots=True)
class Signed64:
    pass


@dataclass(frozen=True, slots=True)
class TextSlice:
    kind: Literal["text", "digest", "witness", "literal"]
    literals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TableSlice:
    target_tag: int
    mode: Literal["array", "record"]


@dataclass(frozen=True, slots=True)
class Option:
    payload: Descriptor


@dataclass(frozen=True, slots=True)
class Variant:
    nullable: bool
    target_tags: tuple[int, ...]


type Descriptor = (
    UInt64
    | Boolean64
    | ExactNumber
    | EndFrom
    | Signed64
    | TextSlice
    | TableSlice
    | Option
    | Variant
)


@dataclass(frozen=True, slots=True)
class FieldSpec:
    logical_name: str
    native_name: str
    offset: int
    descriptor: Descriptor


@dataclass(frozen=True, slots=True)
class TypeLayout:
    id: int
    name: str
    bytes: int
    alignment: int


@dataclass(frozen=True, slots=True)
class MemberLayout:
    id: int
    owner: int
    path: str
    offset: int
    bytes: int
    alignment: int
    type_code: int
    extent: int


@dataclass(frozen=True, slots=True)
class TableField:
    logical_name: str
    native_name: str
    descriptor: Descriptor


@dataclass(frozen=True, slots=True)
class TableLayout:
    tag: int
    name: str
    element_type: int
    logical_element_bytes: int
    record_kind: RecordKind
    fields: tuple[TableField, ...]


@dataclass(frozen=True, slots=True)
class LayoutDefinition:
    id: ProfileId
    machine: Machine
    declarations_sha256: str
    c_data_schema: Literal["phoenix-eager-c-data-1"]
    types: tuple[TypeLayout, ...]
    members: tuple[MemberLayout, ...]
    tables: tuple[TableLayout, ...]
    field_specs: tuple[tuple[FieldSpec, ...], ...]
    witness_words: int
    witness_bytes: int
    elf_contract: Literal["collector-elf-sysv-rela-1"]


@dataclass(frozen=True, slots=True)
class _TableSpec:
    tag: int
    name: str
    bytes: int
    alignment: int
    record_kind: RecordKind
    fields: tuple[FieldSpec, ...]


_DECLARATIONS_SHA256 = (
    "2e278603d75d6cd436aedc72af3f1903334dadc37d6d8847dfd3dd825018acb3"
)

_TABLE_SPECS = (
    _TableSpec(1, "bytes", 1, 1, "storage", ()),
    _TableSpec(
        2, "uints", 8, 8, "scalar", (FieldSpec("value", "f_value", 0, UInt64()),)
    ),
    _TableSpec(
        3,
        "strings",
        8,
        4,
        "scalar",
        (FieldSpec("value", "f_value", 0, TextSlice("text")),),
    ),
    _TableSpec(
        4,
        "registers",
        16,
        8,
        "pair",
        (
            FieldSpec("name", "f_name", 0, TextSlice("text")),
            FieldSpec("width", "f_width", 8, UInt64()),
        ),
    ),
    _TableSpec(
        5,
        "plan_gaps",
        16,
        8,
        "pair",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec("reason", "f_reason", 8, TextSlice("text")),
        ),
    ),
    _TableSpec(
        6,
        "positions",
        16,
        8,
        "pair",
        (
            FieldSpec("route_sha256", "f_route_sha256", 0, TextSlice("digest")),
            FieldSpec("position", "f_position", 8, UInt64()),
        ),
    ),
    _TableSpec(
        7,
        "dispositions",
        40,
        8,
        "pair",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec("disposition", "f_disposition", 8, Variant(False, (24, 25, 26))),
        ),
    ),
    _TableSpec(
        8,
        "dynamic",
        24,
        8,
        "pair",
        (
            FieldSpec("tag", "f_tag", 0, Signed64()),
            FieldSpec("value", "f_value", 16, UInt64()),
        ),
    ),
    _TableSpec(
        9,
        "original",
        16,
        8,
        "object",
        (
            FieldSpec("bytes", "f_bytes", 0, UInt64()),
            FieldSpec("sha256", "f_sha256", 8, TextSlice("digest")),
        ),
    ),
    _TableSpec(
        10,
        "geometry",
        32,
        8,
        "object",
        (
            FieldSpec("executable_file_start", "f_executable_file_start", 0, UInt64()),
            FieldSpec(
                "executable_file_end_exclusive",
                "f_executable_file_size",
                8,
                EndFrom("executable_file_start"),
            ),
            FieldSpec("load_memory_start", "f_load_memory_start", 16, UInt64()),
            FieldSpec(
                "load_memory_end_exclusive",
                "f_load_memory_size",
                24,
                EndFrom("load_memory_start"),
            ),
        ),
    ),
    _TableSpec(
        11,
        "transport_limits",
        88,
        8,
        "object",
        (
            FieldSpec("data_bytes", "f_data_bytes", 0, UInt64()),
            FieldSpec("elf_segments", "f_elf_segments", 8, UInt64()),
            FieldSpec("gap_records", "f_gap_records", 16, UInt64()),
            FieldSpec("lift_bytes", "f_lift_bytes", 24, UInt64()),
            FieldSpec("mapping_bytes", "f_mapping_bytes", 32, UInt64()),
            FieldSpec("omissions", "f_omissions", 40, UInt64()),
            FieldSpec("original_bytes", "f_original_bytes", 48, UInt64()),
            FieldSpec("route_memberships", "f_route_memberships", 56, UInt64()),
            FieldSpec("route_path_positions", "f_route_path_positions", 64, UInt64()),
            FieldSpec("routes", "f_routes", 72, UInt64()),
            FieldSpec("users", "f_users", 80, UInt64()),
        ),
    ),
    _TableSpec(
        12,
        "trace_limits",
        48,
        8,
        "object",
        (
            FieldSpec("events", "f_events", 0, UInt64()),
            FieldSpec("execution_callbacks", "f_execution_callbacks", 8, UInt64()),
            FieldSpec("frames", "f_frames", 16, UInt64()),
            FieldSpec("snapshot_bytes", "f_snapshot_bytes", 24, UInt64()),
            FieldSpec(
                "translated_instructions", "f_translated_instructions", 32, UInt64()
            ),
            FieldSpec("wire_bytes", "f_wire_bytes", 40, UInt64()),
        ),
    ),
    _TableSpec(
        13,
        "capture_limits",
        112,
        8,
        "object",
        (
            FieldSpec("events", "f_events", 0, UInt64()),
            FieldSpec("execution_callbacks", "f_execution_callbacks", 8, UInt64()),
            FieldSpec("frames", "f_frames", 16, UInt64()),
            FieldSpec("full_plan_bytes", "f_full_plan_bytes", 24, UInt64()),
            FieldSpec("full_plan_sites", "f_full_plan_sites", 32, UInt64()),
            FieldSpec("guarded_instructions", "f_guarded_instructions", 40, UInt64()),
            FieldSpec("receipt_bytes", "f_receipt_bytes", 48, UInt64()),
            FieldSpec("route_entries", "f_route_entries", 56, UInt64()),
            FieldSpec("scope_bytes", "f_scope_bytes", 64, UInt64()),
            FieldSpec("snapshot_bytes", "f_snapshot_bytes", 72, UInt64()),
            FieldSpec("thunk_neutral_bytes", "f_thunk_neutral_bytes", 80, UInt64()),
            FieldSpec(
                "thunk_neutral_instructions",
                "f_thunk_neutral_instructions",
                88,
                UInt64(),
            ),
            FieldSpec(
                "translated_instructions", "f_translated_instructions", 96, UInt64()
            ),
            FieldSpec("wire_bytes", "f_wire_bytes", 104, UInt64()),
        ),
    ),
    _TableSpec(
        14,
        "import_id",
        48,
        8,
        "object",
        (
            FieldSpec(
                "needed_library", "f_needed_library", 0, Option(TextSlice("text"))
            ),
            FieldSpec("symbol", "f_symbol", 16, TextSlice("text")),
            FieldSpec("version", "f_version", 24, Option(TextSlice("text"))),
            FieldSpec("version_hidden", "f_version_hidden", 40, Boolean64()),
        ),
    ),
    _TableSpec(
        15,
        "import_binding",
        152,
        8,
        "object",
        (
            FieldSpec(
                "address_proof_sha256", "f_address_proof_sha256", 0, TextSlice("digest")
            ),
            FieldSpec("binary_sha256", "f_binary_sha256", 8, TextSlice("digest")),
            FieldSpec("function", "f_function", 16, Option(UInt64())),
            FieldSpec("gap", "f_gap", 32, Option(TextSlice("text"))),
            FieldSpec("identity", "f_identity", 48, Option(TableSlice(14, "record"))),
            FieldSpec("lift_sha256", "f_lift_sha256", 64, TextSlice("digest")),
            FieldSpec(
                "relocation_file_offset",
                "f_relocation_file_offset",
                72,
                Option(UInt64()),
            ),
            FieldSpec("relocation_kind", "f_relocation_kind", 88, Option(UInt64())),
            FieldSpec("relocation_slot", "f_relocation_slot", 104, Option(UInt64())),
            FieldSpec("site", "f_site", 120, UInt64()),
            FieldSpec("symbol_index", "f_symbol_index", 128, Option(UInt64())),
            FieldSpec("thunk_path", "f_thunk_path", 144, TableSlice(2, "array")),
        ),
    ),
    _TableSpec(
        16,
        "call",
        40,
        8,
        "object",
        (
            FieldSpec("continuation", "f_continuation", 0, UInt64()),
            FieldSpec("import_gaps", "f_import_gaps", 8, TableSlice(3, "array")),
            FieldSpec("imported", "f_imported", 16, Option(TableSlice(15, "record"))),
            FieldSpec(
                "kind",
                "f_kind",
                32,
                TextSlice("literal", ("direct_call", "indirect_call")),
            ),
        ),
    ),
    _TableSpec(
        17,
        "jump",
        8,
        4,
        "object",
        (FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("indirect_jump",))),),
    ),
    _TableSpec(
        18,
        "return",
        8,
        4,
        "object",
        (FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("return",))),),
    ),
    _TableSpec(
        19,
        "trace_site",
        72,
        8,
        "object",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec(
                "continuation_of", "f_continuation_of", 8, TableSlice(2, "array")
            ),
            FieldSpec("entry", "f_entry", 16, Boolean64()),
            FieldSpec("owner", "f_owner", 24, UInt64()),
            FieldSpec("transfer", "f_transfer", 32, Variant(True, (16, 17, 18))),
            FieldSpec("witness_hex", "f_witness_hex", 64, TextSlice("witness")),
        ),
    ),
    _TableSpec(
        20,
        "trace_plan",
        72,
        8,
        "object",
        (
            FieldSpec(
                "address_proof_sha256", "f_address_proof_sha256", 0, TextSlice("digest")
            ),
            FieldSpec("binary_sha256", "f_binary_sha256", 8, TextSlice("digest")),
            FieldSpec("gaps", "f_gaps", 16, TableSlice(5, "array")),
            FieldSpec("lift_sha256", "f_lift_sha256", 24, TextSlice("digest")),
            FieldSpec("limits", "f_limits", 32, TableSlice(12, "record")),
            FieldSpec("registers", "f_registers", 40, TableSlice(4, "array")),
            FieldSpec("schema", "f_schema", 48, ExactNumber(2)),
            FieldSpec("scope", "f_scope", 56, TableSlice(2, "array")),
            FieldSpec("sites", "f_sites", 64, TableSlice(19, "array")),
        ),
    ),
    _TableSpec(
        21,
        "lift_main",
        24,
        8,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("lift_main",))),
            FieldSpec("lift_sha256", "f_lift_sha256", 8, TextSlice("digest")),
            FieldSpec("main_elf", "f_main_elf", 16, UInt64()),
        ),
    ),
    _TableSpec(
        22,
        "explicit_entry",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("explicit_entry",))),
            FieldSpec("request_sha256", "f_request_sha256", 8, TextSlice("digest")),
        ),
    ),
    _TableSpec(
        23,
        "requested_scope",
        48,
        8,
        "object",
        (
            FieldSpec(
                "policy", "f_policy", 0, TextSlice("literal", ("main-window-six-v1",))
            ),
            FieldSpec("root", "f_root", 8, UInt64()),
            FieldSpec("root_evidence", "f_root_evidence", 16, Variant(False, (21, 22))),
            FieldSpec("users", "f_users", 40, TableSlice(2, "array")),
        ),
    ),
    _TableSpec(
        24,
        "user",
        16,
        8,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("user",))),
            FieldSpec("owner", "f_owner", 8, UInt64()),
        ),
    ),
    _TableSpec(
        25,
        "transit",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("transit",))),
            FieldSpec("route_ids", "f_route_ids", 8, TableSlice(3, "array")),
        ),
    ),
    _TableSpec(
        26,
        "omitted",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("omitted",))),
            FieldSpec(
                "reason",
                "f_reason",
                8,
                TextSlice(
                    "literal",
                    ("outside_requested_users", "runtime_lifecycle_outside_window"),
                ),
            ),
        ),
    ),
    _TableSpec(
        27,
        "omitted_site",
        40,
        8,
        "object",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec("full_roles", "f_full_roles", 8, TableSlice(3, "array")),
            FieldSpec("owner", "f_owner", 16, UInt64()),
            FieldSpec(
                "reason",
                "f_reason",
                24,
                TextSlice(
                    "literal",
                    ("outside_requested_users", "runtime_lifecycle_outside_window"),
                ),
            ),
            FieldSpec("witness_sha256", "f_witness_sha256", 32, TextSlice("digest")),
        ),
    ),
    _TableSpec(
        28,
        "transit_route",
        56,
        8,
        "object",
        (
            FieldSpec("binding_sha256", "f_binding_sha256", 0, TextSlice("digest")),
            FieldSpec("call_site", "f_call_site", 8, UInt64()),
            FieldSpec("entries", "f_entries", 16, TableSlice(2, "array")),
            FieldSpec(
                "instruction_path", "f_instruction_path", 24, TableSlice(2, "array")
            ),
            FieldSpec("request", "f_request", 32, TableSlice(14, "record")),
            FieldSpec("slot", "f_slot", 40, UInt64()),
            FieldSpec("terminal", "f_terminal", 48, UInt64()),
        ),
    ),
    _TableSpec(
        29,
        "ordinary",
        16,
        8,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("ordinary",))),
            FieldSpec("successor", "f_successor", 8, UInt64()),
        ),
    ),
    _TableSpec(
        30,
        "local_direct",
        16,
        8,
        "object",
        (
            FieldSpec("destination", "f_destination", 0, UInt64()),
            FieldSpec("kind", "f_kind", 8, TextSlice("literal", ("local_direct",))),
        ),
    ),
    _TableSpec(
        31,
        "local_conditional",
        24,
        8,
        "object",
        (
            FieldSpec("fallthrough", "f_fallthrough", 0, UInt64()),
            FieldSpec(
                "kind", "f_kind", 8, TextSlice("literal", ("local_conditional",))
            ),
            FieldSpec("taken", "f_taken", 16, UInt64()),
        ),
    ),
    _TableSpec(
        32,
        "planned_roles",
        48,
        8,
        "object",
        (
            FieldSpec("continuation", "f_continuation", 0, Option(UInt64())),
            FieldSpec("destination", "f_destination", 16, Option(UInt64())),
            FieldSpec("kind", "f_kind", 32, TextSlice("literal", ("planned_roles",))),
            FieldSpec(
                "transfer_kind",
                "f_transfer_kind",
                40,
                TextSlice(
                    "literal",
                    ("direct_call", "indirect_call", "indirect_jump", "return"),
                ),
            ),
        ),
    ),
    _TableSpec(
        33,
        "transit_instruction",
        16,
        4,
        "object",
        (
            FieldSpec(
                "kind", "f_kind", 0, TextSlice("literal", ("transit_instruction",))
            ),
            FieldSpec("positions", "f_positions", 8, TableSlice(6, "array")),
        ),
    ),
    _TableSpec(
        34,
        "reject",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("reject",))),
            FieldSpec("reason", "f_reason", 8, TextSlice("text")),
        ),
    ),
    _TableSpec(
        35,
        "guard_instruction",
        88,
        8,
        "object",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec("full_roles", "f_full_roles", 8, TableSlice(3, "array")),
            FieldSpec("owner", "f_owner", 16, UInt64()),
            FieldSpec("rule", "f_rule", 24, Variant(False, (29, 30, 31, 32, 33, 34))),
            FieldSpec("witness_hex", "f_witness_hex", 80, TextSlice("witness")),
        ),
    ),
    _TableSpec(
        36,
        "dormant_outside_window",
        16,
        4,
        "object",
        (
            FieldSpec(
                "kind", "f_kind", 0, TextSlice("literal", ("dormant_outside_window",))
            ),
            FieldSpec("reason", "f_reason", 8, TextSlice("text")),
        ),
    ),
    _TableSpec(
        37,
        "guard_reject",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("guard_reject",))),
            FieldSpec("reason", "f_reason", 8, TextSlice("text")),
        ),
    ),
    _TableSpec(
        38,
        "local_branch_guard",
        40,
        8,
        "object",
        (
            FieldSpec("destination", "f_destination", 0, UInt64()),
            FieldSpec("fallthrough", "f_fallthrough", 8, Option(UInt64())),
            FieldSpec(
                "kind", "f_kind", 24, TextSlice("literal", ("local_branch_guard",))
            ),
            FieldSpec(
                "rule",
                "f_rule",
                32,
                TextSlice("literal", ("local_direct", "local_conditional")),
            ),
        ),
    ),
    _TableSpec(
        39,
        "metadata_only",
        16,
        4,
        "object",
        (
            FieldSpec("kind", "f_kind", 0, TextSlice("literal", ("metadata_only",))),
            FieldSpec("reason", "f_reason", 8, TextSlice("text")),
        ),
    ),
    _TableSpec(
        40,
        "gap_record",
        88,
        8,
        "object",
        (
            FieldSpec("address", "f_address", 0, UInt64()),
            FieldSpec(
                "disposition", "f_disposition", 8, Variant(False, (36, 37, 38, 39))
            ),
            FieldSpec("domain", "f_domain", 48, TextSlice("literal", ("ghidra",))),
            FieldSpec("elf", "f_elf", 56, Option(UInt64())),
            FieldSpec("index", "f_index", 72, UInt64()),
            FieldSpec("reason", "f_reason", 80, TextSlice("text")),
        ),
    ),
    _TableSpec(
        41,
        "exit_from_supported_bits",
        24,
        8,
        "object",
        (
            FieldSpec("register", "f_register", 0, TextSlice("text")),
            FieldSpec("transform", "f_transform", 8, TextSlice("text")),
            FieldSpec("width", "f_width", 16, UInt64()),
        ),
    ),
    _TableSpec(
        42,
        "exact_signal",
        8,
        8,
        "object",
        (FieldSpec("signal", "f_signal", 0, UInt64()),),
    ),
    _TableSpec(
        43,
        "termination_contract",
        128,
        8,
        "object",
        (
            FieldSpec(
                "behavior",
                "f_behavior",
                0,
                TextSlice("literal", ("process-termination",)),
            ),
            FieldSpec("binary_sha256", "f_binary_sha256", 8, TextSlice("digest")),
            FieldSpec("call_site", "f_call_site", 16, UInt64()),
            FieldSpec(
                "callbacks", "f_callbacks", 24, TextSlice("literal", ("forbidden",))
            ),
            FieldSpec(
                "cleanup",
                "f_cleanup",
                32,
                TextSlice("literal", ("no-unobserved-main-reentry",)),
            ),
            FieldSpec(
                "full_plan_sha256", "f_full_plan_sha256", 40, TextSlice("digest")
            ),
            FieldSpec(
                "import_binding_sha256",
                "f_import_binding_sha256",
                48,
                Option(TextSlice("digest")),
            ),
            FieldSpec(
                "permitted_physical_route_sha256",
                "f_permitted_physical_route_sha256",
                64,
                TextSlice("digest"),
            ),
            FieldSpec(
                "provider_evidence_sha256",
                "f_provider_evidence_sha256",
                72,
                TextSlice("digest"),
            ),
            FieldSpec("rule_sha256", "f_rule_sha256", 80, TextSlice("digest")),
            FieldSpec(
                "runtime_manifest_base_sha256",
                "f_runtime_manifest_base_sha256",
                88,
                TextSlice("digest"),
            ),
            FieldSpec("schema", "f_schema", 96, ExactNumber(1)),
            FieldSpec(
                "termination_rule", "f_termination_rule", 104, Variant(False, (41, 42))
            ),
        ),
    ),
    _TableSpec(
        44,
        "scope_selection",
        184,
        8,
        "object",
        (
            FieldSpec(
                "active_unlisted",
                "f_active_unlisted",
                0,
                TextSlice("literal", ("reject",)),
            ),
            FieldSpec(
                "address_proof_sha256", "f_address_proof_sha256", 8, TextSlice("digest")
            ),
            FieldSpec("binary_sha256", "f_binary_sha256", 16, TextSlice("digest")),
            FieldSpec(
                "claim",
                "f_claim",
                24,
                TextSlice("literal", ("requested-main-activation",)),
            ),
            FieldSpec("contracts", "f_contracts", 32, TableSlice(43, "array")),
            FieldSpec("dispositions", "f_dispositions", 40, TableSlice(7, "array")),
            FieldSpec(
                "full_plan_sha256", "f_full_plan_sha256", 48, TextSlice("digest")
            ),
            FieldSpec(
                "gap_dispositions", "f_gap_dispositions", 56, TableSlice(40, "array")
            ),
            FieldSpec(
                "guard_instructions",
                "f_guard_instructions",
                64,
                TableSlice(35, "array"),
            ),
            FieldSpec(
                "lazy_resolver",
                "f_lazy_resolver",
                72,
                TextSlice("literal", ("unsupported",)),
            ),
            FieldSpec("lift_sha256", "f_lift_sha256", 80, TextSlice("digest")),
            FieldSpec("limits", "f_limits", 88, TableSlice(13, "record")),
            FieldSpec("omitted", "f_omitted", 96, TableSlice(27, "array")),
            FieldSpec(
                "outside_window",
                "f_outside_window",
                104,
                TextSlice("literal", ("all-sites-outside-frame-capture",)),
            ),
            FieldSpec(
                "policy", "f_policy", 112, TextSlice("literal", ("main-window-six-v1",))
            ),
            FieldSpec(
                "policy_implementation_sha256",
                "f_policy_implementation_sha256",
                120,
                TextSlice("digest"),
            ),
            FieldSpec("registers", "f_registers", 128, TableSlice(4, "array")),
            FieldSpec("request", "f_request", 136, TableSlice(23, "record")),
            FieldSpec("root", "f_root", 144, UInt64()),
            FieldSpec("routes", "f_routes", 152, TableSlice(28, "array")),
            FieldSpec("schema", "f_schema", 160, ExactNumber(1)),
            FieldSpec(
                "transit_profile",
                "f_transit_profile",
                168,
                TextSlice("literal", ("eager-only",)),
            ),
            FieldSpec("users", "f_users", 176, TableSlice(2, "array")),
        ),
    ),
    _TableSpec(
        45,
        "load_segment",
        56,
        8,
        "object",
        (
            FieldSpec("alignment", "f_alignment", 0, UInt64()),
            FieldSpec("file_offset", "f_file_offset", 8, UInt64()),
            FieldSpec("file_size", "f_file_size", 16, UInt64()),
            FieldSpec("flags", "f_flags", 24, UInt64()),
            FieldSpec("index", "f_index", 32, UInt64()),
            FieldSpec("memory_size", "f_memory_size", 40, UInt64()),
            FieldSpec("va", "f_va", 48, UInt64()),
        ),
    ),
    _TableSpec(
        46,
        "elf_image",
        32,
        8,
        "object",
        (
            FieldSpec("dynamic", "f_dynamic", 0, TableSlice(8, "array")),
            FieldSpec("entry", "f_entry", 8, UInt64()),
            FieldSpec("kind", "f_kind", 16, UInt64()),
            FieldSpec("segments", "f_segments", 24, TableSlice(45, "array")),
        ),
    ),
    _TableSpec(
        47,
        "collector_data",
        112,
        4,
        "object",
        (
            FieldSpec(
                "address_proof_sha256", "f_address_proof_sha256", 0, TextSlice("digest")
            ),
            FieldSpec(
                "c_data_schema",
                "f_c_data_schema",
                8,
                TextSlice("literal", ("phoenix-eager-c-data-1",)),
            ),
            FieldSpec("full_plan", "f_full_plan", 16, TableSlice(20, "record")),
            FieldSpec(
                "full_plan_sha256", "f_full_plan_sha256", 24, TextSlice("digest")
            ),
            FieldSpec("geometry", "f_geometry", 32, TableSlice(10, "record")),
            FieldSpec("image", "f_image", 40, TableSlice(46, "record")),
            FieldSpec("lift_sha256", "f_lift_sha256", 48, TextSlice("digest")),
            FieldSpec("original", "f_original", 56, TableSlice(9, "record")),
            FieldSpec(
                "policy_implementation_sha256",
                "f_policy_implementation_sha256",
                64,
                TextSlice("digest"),
            ),
            FieldSpec(
                "profile",
                "f_profile",
                72,
                TextSlice("literal", ("main-window-six-v1",)),
            ),
            FieldSpec(
                "schema",
                "f_schema",
                80,
                TextSlice("literal", ("phoenix-eager-collector-data-1",)),
            ),
            FieldSpec("scope", "f_scope", 88, TableSlice(44, "record")),
            FieldSpec("scope_sha256", "f_scope_sha256", 96, TextSlice("digest")),
            FieldSpec(
                "transport_limits", "f_transport_limits", 104, TableSlice(11, "record")
            ),
        ),
    ),
)


def _geometry(descriptor: Descriptor) -> tuple[int, int, int]:
    match descriptor:
        case UInt64() | Boolean64() | ExactNumber() | EndFrom():
            return 8, 8, 3
        case Signed64():
            return 16, 8, 52
        case TextSlice():
            return 8, 4, 5
        case TableSlice(target_tag=tag):
            return 8, 4, tag + 4
        case Option(payload=payload):
            return 8 + _geometry(payload)[0], 8, 0
        case Variant(target_tags=tags):
            return 8 + 8 * len(tags), 8, 0
    raise TypeError("Invalid installed descriptor.")


def _leaf_cells(descriptor: Descriptor, base: int) -> tuple[tuple[int, int], ...]:
    match descriptor:
        case UInt64() | Boolean64() | ExactNumber() | EndFrom():
            return ((base, 8),)
        case Signed64():
            return ((base, 8), (base + 8, 8))
        case TextSlice() | TableSlice():
            return ((base, 4), (base + 4, 4))
        case Option(payload=payload):
            return ((base, 8), *_leaf_cells(payload, base + 8))
        case Variant(target_tags=tags):
            return (
                (base, 8),
                *((base + 8 + 4 * i, 4) for i in range(2 * len(tags))),
            )
    raise TypeError("Invalid installed descriptor.")


def _candidate_types() -> tuple[TypeLayout, ...]:
    return (
        TypeLayout(1, "uint8_t", 1, 1),
        TypeLayout(2, "uint32_t", 4, 4),
        TypeLayout(3, "uint64_t", 8, 8),
        TypeLayout(4, "const void *", 8, 8),
        *(
            TypeLayout(t.tag + 4, f"phoenix_{t.name}_slice_v1", 8, 4)
            for t in _TABLE_SPECS
        ),
        TypeLayout(52, "phoenix_signed_v1", 16, 8),
        *(
            TypeLayout(t.tag + 51, f"phoenix_{t.name}_v1", t.bytes, t.alignment)
            for t in _TABLE_SPECS[1:]
        ),
        TypeLayout(99, "phoenix_table_directory_entry_v1", 56, 8),
        TypeLayout(100, "phoenix_data_directory_v1", 2728, 8),
    )


def _candidate_tables() -> tuple[TableLayout, ...]:
    return tuple(
        TableLayout(
            t.tag,
            t.name,
            1 if t.tag == 1 else t.tag + 51,
            t.bytes,
            t.record_kind,
            tuple(
                TableField(f.logical_name, f.native_name, f.descriptor)
                for f in t.fields
            ),
        )
        for t in _TABLE_SPECS
    )


def _expand_members(definition: LayoutDefinition) -> tuple[MemberLayout, ...]:
    members: list[MemberLayout] = []

    def emit(
        owner: int,
        path: str,
        offset: int,
        size: int,
        alignment: int,
        type_code: int,
        extent: int = 1,
    ) -> None:
        members.append(
            MemberLayout(
                len(members) + 1,
                owner,
                path,
                offset,
                size,
                alignment,
                type_code,
                extent,
            )
        )

    def expand(owner: int, path: str, base: int, descriptor: Descriptor) -> None:
        size, alignment, code = _geometry(descriptor)
        emit(owner, path, base, size, alignment, code)
        match descriptor:
            case TextSlice() | TableSlice():
                emit(owner, path + ".offset", base, 4, 4, 2)
                emit(owner, path + ".count", base + 4, 4, 4, 2)
            case Signed64():
                emit(owner, path + ".negative", base, 8, 8, 3)
                emit(owner, path + ".magnitude", base + 8, 8, 8, 3)
            case Option(payload=payload):
                emit(owner, path + ".tag", base, 8, 8, 3)
                expand(owner, path + ".payload", base + 8, payload)
            case Variant(target_tags=tags):
                emit(owner, path + ".tag", base, 8, 8, 3)
                for index, tag in enumerate(tags):
                    name = definition.tables[tag - 1].name
                    expand(
                        owner,
                        path + ".payload_" + name,
                        base + 8 + 8 * index,
                        TableSlice(tag, "record"),
                    )

    for owner in range(5, 52):
        emit(owner, "offset", 0, 4, 4, 2)
        emit(owner, "count", 4, 4, 4, 2)
    emit(52, "negative", 0, 8, 8, 3)
    emit(52, "magnitude", 8, 8, 8, 3)
    for table, specs in zip(
        definition.tables[1:], definition.field_specs[1:], strict=True
    ):
        for spec in specs:
            expand(table.element_type, spec.native_name, spec.offset, spec.descriptor)
    for index, name in enumerate(
        (
            "tag",
            "count",
            "logical_element_bytes",
            "logical_bytes",
            "element_bytes",
            "storage_bytes",
        )
    ):
        emit(99, name, index * 8, 8, 8, 3)
    emit(99, "table", 48, 8, 8, 4)
    for index, name in enumerate(
        ("logical_data_sha256", "renderer_sha256", "native_source_sha256")
    ):
        emit(100, name, index * 32, 32, 1, 1, 32)
    emit(100, "tables", 96, 2632, 8, 99, 47)
    return tuple(members)


def _make_definition(machine: Machine) -> LayoutDefinition:
    if type(machine) is not int or machine not in (62, 183):
        raise ValueError("Invalid candidate machine.")
    definition = LayoutDefinition(
        "linux-x86_64-lp64-le-rela-1"
        if machine == 62
        else "linux-aarch64-lp64-le-rela-1",
        machine,
        _DECLARATIONS_SHA256,
        "phoenix-eager-c-data-1",
        _candidate_types(),
        (),
        _candidate_tables(),
        tuple(t.fields for t in _TABLE_SPECS),
        5021,
        40168,
        "collector-elf-sysv-rela-1",
    )
    return replace(definition, members=_expand_members(definition))


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def _check_descriptor(descriptor: Descriptor, active: set[int]) -> tuple[int, ...]:
    _require(id(descriptor) not in active, "Descriptor cycle.")
    active.add(id(descriptor))
    targets: tuple[int, ...] = ()
    if type(descriptor) in (UInt64, Boolean64, Signed64):
        pass
    elif isinstance(descriptor, ExactNumber) and type(descriptor) is ExactNumber:
        _require(
            type(descriptor.value) is int and 0 <= descriptor.value < 1 << 64,
            "Invalid fixed number.",
        )
    elif isinstance(descriptor, EndFrom) and type(descriptor) is EndFrom:
        _require(
            type(descriptor.prior_name) is str and bool(descriptor.prior_name),
            "Invalid endpoint source.",
        )
    elif isinstance(descriptor, TextSlice) and type(descriptor) is TextSlice:
        _require(
            type(descriptor.kind) is str
            and descriptor.kind in ("text", "digest", "witness", "literal"),
            "Invalid text kind.",
        )
        _require(
            type(descriptor.literals) is tuple
            and all(
                type(s) is str and bool(s) and s.isascii() for s in descriptor.literals
            ),
            "Invalid literals.",
        )
        _require(
            len(set(descriptor.literals)) == len(descriptor.literals)
            and bool(descriptor.literals) == (descriptor.kind == "literal"),
            "Invalid literal alternatives.",
        )
    elif isinstance(descriptor, TableSlice) and type(descriptor) is TableSlice:
        _require(
            type(descriptor.mode) is str and descriptor.mode in ("array", "record"),
            "Invalid slice mode.",
        )
        targets = (descriptor.target_tag,)
    elif isinstance(descriptor, Option) and type(descriptor) is Option:
        targets = _check_descriptor(descriptor.payload, active)
    elif isinstance(descriptor, Variant) and type(descriptor) is Variant:
        _require(
            type(descriptor.nullable) is bool
            and type(descriptor.target_tags) is tuple
            and bool(descriptor.target_tags),
            "Invalid variant.",
        )
        targets = descriptor.target_tags
        _require(
            all(type(t) is int for t in targets) and len(set(targets)) == len(targets),
            "Invalid variant targets.",
        )
    else:
        raise TypeError("Invalid installed descriptor.")
    _require(
        all(type(t) is int and 2 <= t <= 47 for t in targets), "Invalid table target."
    )
    active.remove(id(descriptor))
    return targets


def _check_graph(specs: tuple[tuple[FieldSpec, ...], ...]) -> None:
    edges: dict[int, tuple[int, ...]] = {}
    for tag, fields in enumerate(specs, 1):
        targets: list[int] = []
        _require(type(fields) is tuple, "Mutable field inventory.")
        previous: dict[str, Descriptor] = {}
        native_names: set[str] = set()
        for field in fields:
            _require(
                type(field) is FieldSpec
                and type(field.logical_name) is str
                and bool(field.logical_name)
                and type(field.native_name) is str
                and bool(field.native_name)
                and type(field.offset) is int
                and field.offset >= 0,
                "Invalid field specification.",
            )
            _require(
                field.logical_name not in previous
                and field.native_name not in native_names,
                "Duplicate field name.",
            )
            targets.extend(_check_descriptor(field.descriptor, set()))
            if isinstance(field.descriptor, EndFrom):
                _require(
                    type(previous.get(field.descriptor.prior_name)) is UInt64,
                    "Endpoint source must precede the endpoint.",
                )
            previous[field.logical_name] = field.descriptor
            native_names.add(field.native_name)
        edges[tag] = tuple(targets)
    active: set[int] = set()
    done: set[int] = set()

    def visit(tag: int) -> None:
        _require(tag not in active, "Table descriptor cycle.")
        if tag in done:
            return
        active.add(tag)
        for target in edges[tag]:
            visit(target)
        active.remove(tag)
        done.add(tag)

    for tag in edges:
        visit(tag)


def _check_member_tree(definition: LayoutDefinition) -> None:
    types = {t.id: t for t in definition.types}
    groups: dict[tuple[int, str], list[MemberLayout]] = {}
    paths: dict[tuple[int, str], MemberLayout] = {}
    for member in definition.members:
        _require(
            type(member) is MemberLayout
            and all(
                type(n) is int
                for n in (
                    member.id,
                    member.owner,
                    member.offset,
                    member.bytes,
                    member.alignment,
                    member.type_code,
                    member.extent,
                )
            )
            and type(member.path) is str
            and bool(member.path),
            "Invalid member record.",
        )
        _require(
            member.owner in types
            and member.owner >= 5
            and (member.owner, member.path) not in paths,
            "Invalid member owner or path.",
        )
        owner = types[member.owner]
        _require(
            member.offset >= 0
            and member.bytes > 0
            and member.extent > 0
            and member.alignment in (1, 4, 8)
            and member.offset % member.alignment == 0
            and member.offset + member.bytes <= owner.bytes
            and owner.alignment >= member.alignment,
            "Invalid member geometry.",
        )
        if member.type_code:
            _require(member.type_code in types, "Unknown member type.")
            target = types[member.type_code]
            _require(
                member.bytes == target.bytes * member.extent
                and member.alignment == target.alignment,
                "Wrong member type geometry.",
            )
        else:
            _require(
                member.extent == 1 and member.alignment == 8,
                "Invalid anonymous aggregate.",
            )
        parent_path = member.path.rpartition(".")[0]
        if parent_path:
            parent = paths.get((member.owner, parent_path))
            _require(parent is not None, "A member precedes its parent.")
            assert parent is not None
            _require(
                parent.extent == 1
                and parent.offset <= member.offset
                and member.offset + member.bytes <= parent.offset + parent.bytes
                and parent.alignment >= member.alignment,
                "Invalid composite containment.",
            )
        paths[member.owner, member.path] = member
        groups.setdefault((member.owner, parent_path), []).append(member)
    for owner in definition.types[4:]:
        _require((owner.id, "") in groups, "Missing owner members.")
    for (owner_id, parent_path), siblings in groups.items():
        parent = paths.get((owner_id, parent_path))
        start = parent.offset if parent is not None else 0
        end = start + (parent.bytes if parent is not None else types[owner_id].bytes)
        for sibling in siblings:
            _require(sibling.offset == start, "Sibling overlap, gap, or wrong order.")
            start += sibling.bytes
        _require(start == end, "Incomplete semantic leaf coverage.")
    for (owner_id, path), member in paths.items():
        composite = member.extent == 1 and (
            member.type_code == 0 or member.type_code >= 5
        )
        _require(
            ((owner_id, path) in groups) == composite,
            "Missing or unexpected composite children.",
        )


def _validate_definition(definition: LayoutDefinition) -> None:
    _require(type(definition) is LayoutDefinition, "Invalid definition type.")
    _require(
        type(definition.machine) is int and definition.machine in (62, 183),
        "Invalid candidate machine.",
    )
    expected_id = (
        "linux-x86_64-lp64-le-rela-1"
        if definition.machine == 62
        else "linux-aarch64-lp64-le-rela-1"
    )
    _require(
        type(definition.id) is str
        and definition.id == expected_id
        and definition.declarations_sha256 == _DECLARATIONS_SHA256
        and definition.c_data_schema == "phoenix-eager-c-data-1"
        and definition.elf_contract == "collector-elf-sysv-rela-1",
        "Invalid definition identity.",
    )
    _require(
        type(definition.witness_words) is int
        and definition.witness_words == 5021
        and type(definition.witness_bytes) is int
        and definition.witness_bytes == 40168,
        "Invalid witness dimensions.",
    )
    for rows, count in (
        (definition.types, 100),
        (definition.members, 653),
        (definition.tables, 47),
        (definition.field_specs, 47),
    ):
        _require(type(rows) is tuple and len(rows) == count, "Invalid inventory count.")
    for t in definition.types:
        _require(
            type(t) is TypeLayout
            and type(t.name) is str
            and bool(t.name)
            and all(type(n) is int for n in (t.id, t.bytes, t.alignment)),
            "Invalid type record.",
        )
    _require(
        tuple(t.id for t in definition.types) == tuple(range(1, 101))
        and len({t.name for t in definition.types}) == 100
        and definition.types == _candidate_types(),
        "Invalid type inventory.",
    )
    for table in definition.tables:
        _require(
            type(table) is TableLayout
            and type(table.name) is str
            and type(table.record_kind) is str
            and type(table.fields) is tuple
            and all(
                type(n) is int
                for n in (table.tag, table.element_type, table.logical_element_bytes)
            ),
            "Invalid table record.",
        )
        for field in table.fields:
            _require(
                type(field) is TableField
                and type(field.logical_name) is str
                and type(field.native_name) is str,
                "Invalid table field.",
            )
            _check_descriptor(field.descriptor, set())
    _check_graph(definition.field_specs)
    _require(sum(len(f) for f in definition.field_specs) == 214, "Invalid field count.")
    _require(
        tuple(t.tag for t in definition.tables) == tuple(range(1, 48))
        and len({t.name for t in definition.tables}) == 47
        and definition.tables == _candidate_tables(),
        "Invalid table inventory.",
    )
    _require(
        definition.field_specs == tuple(t.fields for t in _TABLE_SPECS),
        "Invalid field inventory.",
    )
    _check_member_tree(definition)
    _require(
        tuple(m.id for m in definition.members) == tuple(range(1, 654))
        and definition.members == _expand_members(definition),
        "Invalid expanded member inventory.",
    )
    for table, fields in zip(
        definition.tables[1:], definition.field_specs[1:], strict=True
    ):
        cells = tuple(
            cell for f in fields for cell in _leaf_cells(f.descriptor, f.offset)
        )
        end = 0
        for offset, width in cells:
            _require(offset == end, "Incomplete record leaf coverage.")
            end += width
        _require(
            end == definition.types[table.element_type - 1].bytes,
            "Incomplete record leaf coverage.",
        )


def _expected_witness(definition: LayoutDefinition) -> tuple[int, ...]:
    return (
        0x50484F454E49584C,
        1,
        definition.machine,
        8,
        8,
        1,
        100,
        653,
        47,
        *(n for t in definition.types for n in (t.id, t.bytes, t.alignment)),
        *(
            n
            for m in definition.members
            for n in (
                m.owner,
                m.id,
                m.offset,
                m.bytes,
                m.alignment,
                m.type_code,
                m.extent,
            )
        ),
        *(
            n
            for t in definition.tables
            for n in (t.tag, t.element_type, definition.types[t.element_type - 1].bytes)
        ),
    )


def _install() -> tuple[LayoutDefinition, LayoutDefinition]:
    definitions = (_make_definition(62), _make_definition(183))
    for definition in definitions:
        _validate_definition(definition)
    return definitions


_DEFINITIONS = _install()


def _definition(profile_id: str) -> LayoutDefinition:
    if type(profile_id) is not str:
        raise TypeError("The candidate profile ID must be an exact string.")
    for definition in _DEFINITIONS:
        if profile_id == definition.id:
            return definition
    raise ValueError("Unknown candidate profile ID.")


TRANSPORT_MAXIMA = (
    ("data_bytes", 16777216),
    ("elf_segments", 1024),
    ("gap_records", 65536),
    ("lift_bytes", 67108864),
    ("mapping_bytes", 67108864),
    ("omissions", 4096),
    ("original_bytes", 16777216),
    ("route_memberships", 1179648),
    ("route_path_positions", 1179648),
    ("routes", 4096),
    ("users", 4096),
)
TRACE_MAXIMA = (
    ("events", 10000),
    ("execution_callbacks", 1000000),
    ("frames", 64),
    ("snapshot_bytes", 8),
    ("translated_instructions", 1000000),
    ("wire_bytes", 8388608),
)
CAPTURE_MAXIMA = (
    ("events", 10000),
    ("execution_callbacks", 1000000),
    ("frames", 64),
    ("full_plan_bytes", 524288),
    ("full_plan_sites", 4096),
    ("guarded_instructions", 65536),
    ("receipt_bytes", 65536),
    ("route_entries", 32),
    ("scope_bytes", 8388608),
    ("snapshot_bytes", 8),
    ("thunk_neutral_bytes", 32),
    ("thunk_neutral_instructions", 8),
    ("translated_instructions", 1000000),
    ("wire_bytes", 8388608),
)
IMAGE_DYNAMIC_MAXIMUM = 65536
