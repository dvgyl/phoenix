"""Reconstruct complete static data. This unit issues no runtime authority."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field, fields, is_dataclass
from hashlib import sha256
from typing import Literal, cast

from phoenix.lift.index import parse_lift
from phoenix.lift.mapping import MappingError, parse_mapping
from phoenix.observe.plan import TracePlan, build_trace_plan
from phoenix.observe.scope import (
    CaptureLimits,
    ExplicitEntry,
    LiftMain,
    Rejection,
    RequestedScope,
    ScopeSelection,
    TransitInstruction,
    select_scope,
)
from phoenix.recover.addresses import ElfImage, ElfVA, checked_end, prove_addresses


@dataclass(frozen=True, slots=True)
class TransportLimits:
    original_bytes: int = 16 * 1024 * 1024
    lift_bytes: int = 64 * 1024 * 1024
    mapping_bytes: int = 64 * 1024 * 1024
    users: int = 4096
    routes: int = 4096
    omissions: int = 4096
    gap_records: int = 65536
    elf_segments: int = 1024
    route_path_positions: int = 4096 * 32 * 9
    route_memberships: int = 4096 * 32 * 9
    data_bytes: int = 16 * 1024 * 1024


type RejectionReason = Literal[
    "input_type",
    "input_limit",
    "static_reconstruction",
    "scope_identity",
    "render_limit",
]


@dataclass(frozen=True, slots=True)
class CollectorRejected:
    reason: RejectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class Original:
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class Geometry:
    executable_file_start: ElfVA
    executable_file_end_exclusive: int
    load_memory_start: ElfVA
    load_memory_end_exclusive: int


type RecordValue = None | bool | int | str | tuple[RecordValue, ...] | FrozenRecord


@dataclass(frozen=True, slots=True)
class FrozenRecord:
    """Keep all logical object fields without mutable children."""

    entries: tuple[tuple[str, RecordValue], ...]


class _Refusal(Exception):
    def __init__(self, reason: RejectionReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail[:512]


def _object_fields(value: object) -> tuple[tuple[str, object], ...] | None:
    if isinstance(value, FrozenRecord):
        return value.entries
    if is_dataclass(value) and not isinstance(value, type):
        return tuple(
            (item.name, cast(object, getattr(value, item.name)))
            for item in sorted(fields(value), key=lambda item: item.name)
        )
    return None


def _tokens(value: object) -> Iterator[str]:
    members = _object_fields(value)
    if members is not None:
        yield "{"
        for index, (name, child) in enumerate(members):
            if index:
                yield ","
            yield json.dumps(name, ensure_ascii=True)
            yield ":"
            yield from _tokens(child)
        yield "}"
    elif type(value) is tuple:
        yield "["
        for index, child in enumerate(cast(tuple[object, ...], value)):
            if index:
                yield ","
            yield from _tokens(child)
        yield "]"
    elif value is None or type(value) in (bool, int, str):
        yield json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    else:
        raise TypeError("Unsupported collector record value.")


def _canonical(value: object, limit: int) -> bytes:
    output = bytearray()
    for token in _tokens(value):
        # All tokens are ASCII. Reserve the final LF before each append.
        if len(output) + len(token) + 1 > limit:
            raise _Refusal("render_limit", "The collector data exceeds its byte limit.")
        output.extend(token.encode("ascii"))
    output.append(10)
    return bytes(output)


def _freeze(value: object) -> RecordValue:
    members = _object_fields(value)
    if members is not None:
        return FrozenRecord(tuple((name, _freeze(child)) for name, child in members))
    if type(value) is tuple:
        return tuple(_freeze(child) for child in cast(tuple[object, ...], value))
    if value is None or type(value) in (bool, int, str):
        return cast(None | bool | int | str, value)
    raise TypeError("Unsupported collector record value.")


@dataclass(frozen=True, slots=True)
class CollectorData:
    original: Original
    lift_sha256: str
    address_proof_sha256: str
    full_plan_sha256: str
    scope_sha256: str
    policy_implementation_sha256: str
    full_plan: TracePlan
    scope: ScopeSelection
    image: ElfImage
    geometry: Geometry
    transport_limits: TransportLimits
    schema: Literal["phoenix-eager-collector-data-1"] = field(
        init=False, default="phoenix-eager-collector-data-1"
    )
    profile: Literal["main-window-six-v1"] = field(
        init=False, default="main-window-six-v1"
    )
    c_data_schema: Literal["phoenix-eager-c-data-1"] = field(
        init=False, default="phoenix-eager-c-data-1"
    )

    def to_bytes(self) -> bytes:
        """Encode every field with a byte bound and one final LF."""
        return _canonical(self, self.transport_limits.data_bytes)

    @property
    def sha256(self) -> str:
        return sha256(self.to_bytes()).hexdigest()

    def record(self) -> FrozenRecord:
        """Return the complete immutable logical record for a later renderer."""
        self.to_bytes()
        record = _freeze(self)
        assert isinstance(record, FrozenRecord)
        return record


def _require(condition: bool, reason: RejectionReason, detail: str) -> None:
    if not condition:
        raise _Refusal(reason, detail)


def _limits(supplied: object, maximum: CaptureLimits | TransportLimits) -> None:
    _require(
        type(supplied) is type(maximum), "input_type", "Invalid limit record type."
    )
    for item in fields(maximum):
        value: object = getattr(supplied, item.name)
        _require(
            type(value) is int and 0 < value <= getattr(maximum, item.name),
            "input_limit",
            f"Invalid limit for {item.name}.",
        )
    if isinstance(supplied, CaptureLimits):
        _require(
            supplied.snapshot_bytes == 8,
            "input_limit",
            "The snapshot width must be eight bytes.",
        )


def _digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _request(requested: RequestedScope, limits: TransportLimits) -> None:
    _require(type(requested) is RequestedScope, "input_type", "Invalid request type.")
    _require(
        type(requested.policy) is str and requested.policy == "main-window-six-v1",
        "scope_identity",
        "Unsupported scope policy.",
    )
    _require(
        type(requested.users) is tuple
        and type(requested.root) is int
        and 0 <= requested.root < 1 << 64,
        "input_type",
        "The request needs an integer root and a tuple of users.",
    )
    _require(
        0 < len(requested.users) <= limits.users,
        "input_limit",
        "The requested users exceed their bound.",
    )
    _require(
        all(type(user) is int and 0 <= user < 1 << 64 for user in requested.users),
        "input_type",
        "Each requested user must be an unsigned 64-bit integer.",
    )
    evidence = requested.root_evidence
    if type(evidence) is LiftMain:
        valid = (
            _digest(evidence.lift_sha256)
            and type(evidence.main_elf) is int
            and 0 <= evidence.main_elf < 1 << 64
            and evidence.kind == "lift_main"
        )
    elif type(evidence) is ExplicitEntry:
        valid = _digest(evidence.request_sha256) and evidence.kind == "explicit_entry"
    else:
        valid = False
    _require(valid, "input_type", "Invalid root evidence.")


def _geometry(image: ElfImage) -> Geometry:
    executable = tuple(segment for segment in image.segments if segment.flags & 1)
    _require(bool(executable), "static_reconstruction", "No executable load segment.")
    return Geometry(
        min(segment.va for segment in executable),
        max(checked_end(segment.va, segment.file_size) for segment in executable),
        min(segment.va for segment in image.segments),
        max(checked_end(segment.va, segment.memory_size) for segment in image.segments),
    )


def prepare_collector_data(
    binary: bytes,
    lift_raw: bytes,
    mapping_raw: bytes,
    full_plan_raw: bytes,
    scope_raw: bytes,
    requested: RequestedScope,
    *,
    limits: CaptureLimits = CaptureLimits(),
    transport_limits: TransportLimits = TransportLimits(),
) -> CollectorData | CollectorRejected:
    """Rebuild raw static evidence. A matching hash is not process attestation."""
    try:
        _limits(limits, CaptureLimits())
        _limits(transport_limits, TransportLimits())
        inputs = (
            ("original", binary, transport_limits.original_bytes),
            ("lift", lift_raw, transport_limits.lift_bytes),
            ("mapping", mapping_raw, transport_limits.mapping_bytes),
            ("full plan", full_plan_raw, limits.full_plan_bytes),
            ("scope", scope_raw, limits.scope_bytes),
        )
        for name, raw, bound in inputs:
            _require(
                type(raw) is bytes, "input_type", f"The {name} must be exact bytes."
            )
            _require(
                0 < len(raw) <= bound,
                "input_limit",
                f"The {name} byte length exceeds its bound or is zero.",
            )
        _request(requested, transport_limits)
        lift = parse_lift(lift_raw, binary)
        mapping = parse_mapping(mapping_raw, binary, lift_raw)
        proof = prove_addresses(binary, lift, mapping)
        _require(
            len(proof.image.segments) <= transport_limits.elf_segments,
            "input_limit",
            "The ELF load segments exceed their bound.",
        )
        plan = build_trace_plan(binary, lift, proof)
        _require(
            len(plan.sites) <= limits.full_plan_sites
            and len(plan.gaps) <= transport_limits.gap_records,
            "input_limit",
            "The full-plan inventory exceeds its bound.",
        )
        _require(
            plan.to_bytes() == full_plan_raw,
            "static_reconstruction",
            "The full plan differs from its complete canonical reconstruction.",
        )
        selection = select_scope(binary, lift, proof, plan, requested, limits=limits)
        if isinstance(selection, Rejection):
            raise _Refusal(
                "static_reconstruction", f"{selection.code}: {selection.detail}"
            )
        _require(
            selection.to_bytes() == scope_raw,
            "scope_identity",
            "The scope differs from its complete installed-policy reconstruction.",
        )
        inventories = (
            ("users", len(selection.users), transport_limits.users),
            ("routes", len(selection.routes), transport_limits.routes),
            ("omissions", len(selection.omitted), transport_limits.omissions),
            (
                "scope gaps",
                len(selection.gap_dispositions),
                transport_limits.gap_records,
            ),
            (
                "route path positions",
                sum(len(route.instruction_path) for route in selection.routes),
                transport_limits.route_path_positions,
            ),
            (
                "route memberships",
                sum(
                    len(guard.rule.positions)
                    for guard in selection.guard_instructions
                    if isinstance(guard.rule, TransitInstruction)
                ),
                transport_limits.route_memberships,
            ),
        )
        for name, count, bound in inventories:
            _require(count <= bound, "input_limit", f"The {name} exceed their bound.")
        data = CollectorData(
            Original(proof.binary_sha256, len(binary)),
            proof.lift_sha256,
            proof.sha256,
            plan.sha256,
            selection.sha256,
            selection.policy_implementation_sha256,
            plan,
            selection,
            proof.image,
            _geometry(proof.image),
            transport_limits,
        )
        data.to_bytes()
        return data
    except _Refusal as error:
        return CollectorRejected(error.reason, error.detail)
    except MappingError as error:
        return CollectorRejected("static_reconstruction", str(error)[:512])
