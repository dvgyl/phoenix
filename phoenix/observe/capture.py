"""Immutable capture evidence. Typed records do not authenticate saved bytes."""

from dataclasses import dataclass, field
from typing import Literal

from phoenix.observe.mapping import ExternalTarget, MappedObservation
from phoenix.observe.scope import ScopeSelection
from phoenix.observe.wire import TraceIdentity
from phoenix.recover.addresses import ElfVA
from phoenix_eval.outcome import Exited, Signaled


@dataclass(frozen=True, slots=True)
class RootAnchor:
    entry_sequence: int
    site: ElfVA
    predecessor_pc: int
    rsp: int
    stack_target: int


@dataclass(frozen=True, slots=True)
class ReturnExit:
    return_sequence: int
    transfer_sequence: int
    next_rsp: int


@dataclass(frozen=True, slots=True)
class ProcessExit:
    contract_sha256: str
    call_sequence: int
    outcome_sha256: str


@dataclass(frozen=True, slots=True)
class CaptureReceipt:
    wire_identity: TraceIdentity
    raw_trace_sha256: str
    scope_sha256: str
    runtime_manifest_sha256: str
    root: RootAnchor
    root_exit: ReturnExit | ProcessExit
    guard_profile_sha256: str
    guard_passed: bool
    emitted_events: int
    execution_callbacks: int
    translated_instructions: int
    selected_instruction_callbacks: int
    outside_window_callbacks: int
    opaque_external_callbacks: int
    omitted_active_hits: int
    plugin_status: Literal["complete"]
    schema: Literal["phoenix-frame-capture-1"] = field(
        init=False, default="phoenix-frame-capture-1"
    )


@dataclass(frozen=True, slots=True)
class _CheckedCapture:
    """Private input from the future exact-byte boundary, or synthetic tests."""

    mapped: MappedObservation
    selection: ScopeSelection
    receipt: CaptureReceipt
    receipt_sha256: str
    guard_profile_sha256: str
    root_predecessor: ExternalTarget
    root_stack_target: ExternalTarget
    raw_trace_bytes: int
    receipt_bytes: int
    actual_termination: Exited | Signaled
    full_outcome_sha256: str
