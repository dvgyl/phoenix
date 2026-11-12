#ifndef PHOENIX_COLLECTOR_DATA_V1_H
#define PHOENIX_COLLECTOR_DATA_V1_H
#include <stdint.h>
#include <stddef.h>
#if defined(__GNUC__) || defined(__clang__)
#define PHOENIX_DATA_EXPORT __attribute__((visibility("default"), used, retain))
#else
#error Unsupported collector declaration compiler.
#endif
_Static_assert(sizeof(void *) == 8, "The collector requires 64-bit pointers.");
struct phoenix_signed_v1 { uint64_t negative; uint64_t magnitude; };
enum { PHOENIX_TABLE_BYTES_V1 = 1 };
struct phoenix_bytes_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_UINTS_V1 = 2 };
struct phoenix_uints_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_STRINGS_V1 = 3 };
struct phoenix_strings_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_REGISTERS_V1 = 4 };
struct phoenix_registers_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_PLAN_GAPS_V1 = 5 };
struct phoenix_plan_gaps_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_POSITIONS_V1 = 6 };
struct phoenix_positions_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_DISPOSITIONS_V1 = 7 };
struct phoenix_dispositions_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_DYNAMIC_V1 = 8 };
struct phoenix_dynamic_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_ORIGINAL_V1 = 9 };
struct phoenix_original_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_GEOMETRY_V1 = 10 };
struct phoenix_geometry_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRANSPORT_LIMITS_V1 = 11 };
struct phoenix_transport_limits_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRACE_LIMITS_V1 = 12 };
struct phoenix_trace_limits_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_CAPTURE_LIMITS_V1 = 13 };
struct phoenix_capture_limits_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_IMPORT_ID_V1 = 14 };
struct phoenix_import_id_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_IMPORT_BINDING_V1 = 15 };
struct phoenix_import_binding_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_CALL_V1 = 16 };
struct phoenix_call_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_JUMP_V1 = 17 };
struct phoenix_jump_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_RETURN_V1 = 18 };
struct phoenix_return_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRACE_SITE_V1 = 19 };
struct phoenix_trace_site_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRACE_PLAN_V1 = 20 };
struct phoenix_trace_plan_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_LIFT_MAIN_V1 = 21 };
struct phoenix_lift_main_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_EXPLICIT_ENTRY_V1 = 22 };
struct phoenix_explicit_entry_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_REQUESTED_SCOPE_V1 = 23 };
struct phoenix_requested_scope_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_USER_V1 = 24 };
struct phoenix_user_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRANSIT_V1 = 25 };
struct phoenix_transit_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_OMITTED_V1 = 26 };
struct phoenix_omitted_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_OMITTED_SITE_V1 = 27 };
struct phoenix_omitted_site_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRANSIT_ROUTE_V1 = 28 };
struct phoenix_transit_route_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_ORDINARY_V1 = 29 };
struct phoenix_ordinary_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_LOCAL_DIRECT_V1 = 30 };
struct phoenix_local_direct_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_LOCAL_CONDITIONAL_V1 = 31 };
struct phoenix_local_conditional_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_PLANNED_ROLES_V1 = 32 };
struct phoenix_planned_roles_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TRANSIT_INSTRUCTION_V1 = 33 };
struct phoenix_transit_instruction_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_REJECT_V1 = 34 };
struct phoenix_reject_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_GUARD_INSTRUCTION_V1 = 35 };
struct phoenix_guard_instruction_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_DORMANT_OUTSIDE_WINDOW_V1 = 36 };
struct phoenix_dormant_outside_window_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_GUARD_REJECT_V1 = 37 };
struct phoenix_guard_reject_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_LOCAL_BRANCH_GUARD_V1 = 38 };
struct phoenix_local_branch_guard_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_METADATA_ONLY_V1 = 39 };
struct phoenix_metadata_only_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_GAP_RECORD_V1 = 40 };
struct phoenix_gap_record_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_EXIT_FROM_SUPPORTED_BITS_V1 = 41 };
struct phoenix_exit_from_supported_bits_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_EXACT_SIGNAL_V1 = 42 };
struct phoenix_exact_signal_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_TERMINATION_CONTRACT_V1 = 43 };
struct phoenix_termination_contract_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_SCOPE_SELECTION_V1 = 44 };
struct phoenix_scope_selection_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_LOAD_SEGMENT_V1 = 45 };
struct phoenix_load_segment_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_ELF_IMAGE_V1 = 46 };
struct phoenix_elf_image_slice_v1 { uint32_t offset; uint32_t count; };
enum { PHOENIX_TABLE_COLLECTOR_DATA_V1 = 47 };
struct phoenix_collector_data_slice_v1 { uint32_t offset; uint32_t count; };
struct phoenix_uints_v1 {
    uint64_t f_value;
};
struct phoenix_strings_v1 {
    struct phoenix_bytes_slice_v1 f_value;
};
struct phoenix_registers_v1 {
    struct phoenix_bytes_slice_v1 f_name;
    uint64_t f_width;
};
struct phoenix_plan_gaps_v1 {
    uint64_t f_address;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_positions_v1 {
    struct phoenix_bytes_slice_v1 f_route_sha256;
    uint64_t f_position;
};
struct phoenix_dispositions_v1 {
    uint64_t f_address;
    struct {
        uint64_t tag;
        struct phoenix_user_slice_v1 payload_user;
        struct phoenix_transit_slice_v1 payload_transit;
        struct phoenix_omitted_slice_v1 payload_omitted;
    } f_disposition;
};
struct phoenix_dynamic_v1 {
    struct phoenix_signed_v1 f_tag;
    uint64_t f_value;
};
struct phoenix_original_v1 {
    uint64_t f_bytes;
    struct phoenix_bytes_slice_v1 f_sha256;
};
struct phoenix_geometry_v1 {
    uint64_t f_executable_file_start;
    uint64_t f_executable_file_size;
    uint64_t f_load_memory_start;
    uint64_t f_load_memory_size;
};
struct phoenix_transport_limits_v1 {
    uint64_t f_data_bytes;
    uint64_t f_elf_segments;
    uint64_t f_gap_records;
    uint64_t f_lift_bytes;
    uint64_t f_mapping_bytes;
    uint64_t f_omissions;
    uint64_t f_original_bytes;
    uint64_t f_route_memberships;
    uint64_t f_route_path_positions;
    uint64_t f_routes;
    uint64_t f_users;
};
struct phoenix_trace_limits_v1 {
    uint64_t f_events;
    uint64_t f_execution_callbacks;
    uint64_t f_frames;
    uint64_t f_snapshot_bytes;
    uint64_t f_translated_instructions;
    uint64_t f_wire_bytes;
};
struct phoenix_capture_limits_v1 {
    uint64_t f_events;
    uint64_t f_execution_callbacks;
    uint64_t f_frames;
    uint64_t f_full_plan_bytes;
    uint64_t f_full_plan_sites;
    uint64_t f_guarded_instructions;
    uint64_t f_receipt_bytes;
    uint64_t f_route_entries;
    uint64_t f_scope_bytes;
    uint64_t f_snapshot_bytes;
    uint64_t f_thunk_neutral_bytes;
    uint64_t f_thunk_neutral_instructions;
    uint64_t f_translated_instructions;
    uint64_t f_wire_bytes;
};
struct phoenix_import_id_v1 {
    struct {
        uint64_t tag;
        struct phoenix_bytes_slice_v1 payload;
    } f_needed_library;
    struct phoenix_bytes_slice_v1 f_symbol;
    struct {
        uint64_t tag;
        struct phoenix_bytes_slice_v1 payload;
    } f_version;
    uint64_t f_version_hidden;
};
struct phoenix_import_binding_v1 {
    struct phoenix_bytes_slice_v1 f_address_proof_sha256;
    struct phoenix_bytes_slice_v1 f_binary_sha256;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_function;
    struct {
        uint64_t tag;
        struct phoenix_bytes_slice_v1 payload;
    } f_gap;
    struct {
        uint64_t tag;
        struct phoenix_import_id_slice_v1 payload;
    } f_identity;
    struct phoenix_bytes_slice_v1 f_lift_sha256;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_relocation_file_offset;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_relocation_kind;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_relocation_slot;
    uint64_t f_site;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_symbol_index;
    struct phoenix_uints_slice_v1 f_thunk_path;
};
struct phoenix_call_v1 {
    uint64_t f_continuation;
    struct phoenix_strings_slice_v1 f_import_gaps;
    struct {
        uint64_t tag;
        struct phoenix_import_binding_slice_v1 payload;
    } f_imported;
    struct phoenix_bytes_slice_v1 f_kind;
};
struct phoenix_jump_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
};
struct phoenix_return_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
};
struct phoenix_trace_site_v1 {
    uint64_t f_address;
    struct phoenix_uints_slice_v1 f_continuation_of;
    uint64_t f_entry;
    uint64_t f_owner;
    struct {
        uint64_t tag;
        struct phoenix_call_slice_v1 payload_call;
        struct phoenix_jump_slice_v1 payload_jump;
        struct phoenix_return_slice_v1 payload_return;
    } f_transfer;
    struct phoenix_bytes_slice_v1 f_witness_hex;
};
struct phoenix_trace_plan_v1 {
    struct phoenix_bytes_slice_v1 f_address_proof_sha256;
    struct phoenix_bytes_slice_v1 f_binary_sha256;
    struct phoenix_plan_gaps_slice_v1 f_gaps;
    struct phoenix_bytes_slice_v1 f_lift_sha256;
    struct phoenix_trace_limits_slice_v1 f_limits;
    struct phoenix_registers_slice_v1 f_registers;
    uint64_t f_schema;
    struct phoenix_uints_slice_v1 f_scope;
    struct phoenix_trace_site_slice_v1 f_sites;
};
struct phoenix_lift_main_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_lift_sha256;
    uint64_t f_main_elf;
};
struct phoenix_explicit_entry_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_request_sha256;
};
struct phoenix_requested_scope_v1 {
    struct phoenix_bytes_slice_v1 f_policy;
    uint64_t f_root;
    struct {
        uint64_t tag;
        struct phoenix_lift_main_slice_v1 payload_lift_main;
        struct phoenix_explicit_entry_slice_v1 payload_explicit_entry;
    } f_root_evidence;
    struct phoenix_uints_slice_v1 f_users;
};
struct phoenix_user_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    uint64_t f_owner;
};
struct phoenix_transit_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_strings_slice_v1 f_route_ids;
};
struct phoenix_omitted_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_omitted_site_v1 {
    uint64_t f_address;
    struct phoenix_strings_slice_v1 f_full_roles;
    uint64_t f_owner;
    struct phoenix_bytes_slice_v1 f_reason;
    struct phoenix_bytes_slice_v1 f_witness_sha256;
};
struct phoenix_transit_route_v1 {
    struct phoenix_bytes_slice_v1 f_binding_sha256;
    uint64_t f_call_site;
    struct phoenix_uints_slice_v1 f_entries;
    struct phoenix_uints_slice_v1 f_instruction_path;
    struct phoenix_import_id_slice_v1 f_request;
    uint64_t f_slot;
    uint64_t f_terminal;
};
struct phoenix_ordinary_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    uint64_t f_successor;
};
struct phoenix_local_direct_v1 {
    uint64_t f_destination;
    struct phoenix_bytes_slice_v1 f_kind;
};
struct phoenix_local_conditional_v1 {
    uint64_t f_fallthrough;
    struct phoenix_bytes_slice_v1 f_kind;
    uint64_t f_taken;
};
struct phoenix_planned_roles_v1 {
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_continuation;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_destination;
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_transfer_kind;
};
struct phoenix_transit_instruction_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_positions_slice_v1 f_positions;
};
struct phoenix_reject_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_guard_instruction_v1 {
    uint64_t f_address;
    struct phoenix_strings_slice_v1 f_full_roles;
    uint64_t f_owner;
    struct {
        uint64_t tag;
        struct phoenix_ordinary_slice_v1 payload_ordinary;
        struct phoenix_local_direct_slice_v1 payload_local_direct;
        struct phoenix_local_conditional_slice_v1 payload_local_conditional;
        struct phoenix_planned_roles_slice_v1 payload_planned_roles;
        struct phoenix_transit_instruction_slice_v1 payload_transit_instruction;
        struct phoenix_reject_slice_v1 payload_reject;
    } f_rule;
    struct phoenix_bytes_slice_v1 f_witness_hex;
};
struct phoenix_dormant_outside_window_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_guard_reject_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_local_branch_guard_v1 {
    uint64_t f_destination;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_fallthrough;
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_rule;
};
struct phoenix_metadata_only_v1 {
    struct phoenix_bytes_slice_v1 f_kind;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_gap_record_v1 {
    uint64_t f_address;
    struct {
        uint64_t tag;
        struct phoenix_dormant_outside_window_slice_v1 payload_dormant_outside_window;
        struct phoenix_guard_reject_slice_v1 payload_guard_reject;
        struct phoenix_local_branch_guard_slice_v1 payload_local_branch_guard;
        struct phoenix_metadata_only_slice_v1 payload_metadata_only;
    } f_disposition;
    struct phoenix_bytes_slice_v1 f_domain;
    struct {
        uint64_t tag;
        uint64_t payload;
    } f_elf;
    uint64_t f_index;
    struct phoenix_bytes_slice_v1 f_reason;
};
struct phoenix_exit_from_supported_bits_v1 {
    struct phoenix_bytes_slice_v1 f_register;
    struct phoenix_bytes_slice_v1 f_transform;
    uint64_t f_width;
};
struct phoenix_exact_signal_v1 {
    uint64_t f_signal;
};
struct phoenix_termination_contract_v1 {
    struct phoenix_bytes_slice_v1 f_behavior;
    struct phoenix_bytes_slice_v1 f_binary_sha256;
    uint64_t f_call_site;
    struct phoenix_bytes_slice_v1 f_callbacks;
    struct phoenix_bytes_slice_v1 f_cleanup;
    struct phoenix_bytes_slice_v1 f_full_plan_sha256;
    struct {
        uint64_t tag;
        struct phoenix_bytes_slice_v1 payload;
    } f_import_binding_sha256;
    struct phoenix_bytes_slice_v1 f_permitted_physical_route_sha256;
    struct phoenix_bytes_slice_v1 f_provider_evidence_sha256;
    struct phoenix_bytes_slice_v1 f_rule_sha256;
    struct phoenix_bytes_slice_v1 f_runtime_manifest_base_sha256;
    uint64_t f_schema;
    struct {
        uint64_t tag;
        struct phoenix_exit_from_supported_bits_slice_v1 payload_exit_from_supported_bits;
        struct phoenix_exact_signal_slice_v1 payload_exact_signal;
    } f_termination_rule;
};
struct phoenix_scope_selection_v1 {
    struct phoenix_bytes_slice_v1 f_active_unlisted;
    struct phoenix_bytes_slice_v1 f_address_proof_sha256;
    struct phoenix_bytes_slice_v1 f_binary_sha256;
    struct phoenix_bytes_slice_v1 f_claim;
    struct phoenix_termination_contract_slice_v1 f_contracts;
    struct phoenix_dispositions_slice_v1 f_dispositions;
    struct phoenix_bytes_slice_v1 f_full_plan_sha256;
    struct phoenix_gap_record_slice_v1 f_gap_dispositions;
    struct phoenix_guard_instruction_slice_v1 f_guard_instructions;
    struct phoenix_bytes_slice_v1 f_lazy_resolver;
    struct phoenix_bytes_slice_v1 f_lift_sha256;
    struct phoenix_capture_limits_slice_v1 f_limits;
    struct phoenix_omitted_site_slice_v1 f_omitted;
    struct phoenix_bytes_slice_v1 f_outside_window;
    struct phoenix_bytes_slice_v1 f_policy;
    struct phoenix_bytes_slice_v1 f_policy_implementation_sha256;
    struct phoenix_registers_slice_v1 f_registers;
    struct phoenix_requested_scope_slice_v1 f_request;
    uint64_t f_root;
    struct phoenix_transit_route_slice_v1 f_routes;
    uint64_t f_schema;
    struct phoenix_bytes_slice_v1 f_transit_profile;
    struct phoenix_uints_slice_v1 f_users;
};
struct phoenix_load_segment_v1 {
    uint64_t f_alignment;
    uint64_t f_file_offset;
    uint64_t f_file_size;
    uint64_t f_flags;
    uint64_t f_index;
    uint64_t f_memory_size;
    uint64_t f_va;
};
struct phoenix_elf_image_v1 {
    struct phoenix_dynamic_slice_v1 f_dynamic;
    uint64_t f_entry;
    uint64_t f_kind;
    struct phoenix_load_segment_slice_v1 f_segments;
};
struct phoenix_collector_data_v1 {
    struct phoenix_bytes_slice_v1 f_address_proof_sha256;
    struct phoenix_bytes_slice_v1 f_c_data_schema;
    struct phoenix_trace_plan_slice_v1 f_full_plan;
    struct phoenix_bytes_slice_v1 f_full_plan_sha256;
    struct phoenix_geometry_slice_v1 f_geometry;
    struct phoenix_elf_image_slice_v1 f_image;
    struct phoenix_bytes_slice_v1 f_lift_sha256;
    struct phoenix_original_slice_v1 f_original;
    struct phoenix_bytes_slice_v1 f_policy_implementation_sha256;
    struct phoenix_bytes_slice_v1 f_profile;
    struct phoenix_bytes_slice_v1 f_schema;
    struct phoenix_scope_selection_slice_v1 f_scope;
    struct phoenix_bytes_slice_v1 f_scope_sha256;
    struct phoenix_transport_limits_slice_v1 f_transport_limits;
};
struct phoenix_table_directory_entry_v1 {
    uint64_t tag;
    uint64_t count;
    uint64_t logical_element_bytes;
    uint64_t logical_bytes;
    uint64_t element_bytes;
    uint64_t storage_bytes;
    const void *table;
};
struct phoenix_data_directory_v1 {
    uint8_t logical_data_sha256[32];
    uint8_t renderer_sha256[32];
    uint8_t native_source_sha256[32];
    struct phoenix_table_directory_entry_v1 tables[47];
};
extern const struct phoenix_data_directory_v1 phoenix_collector_data_v1;
#endif
