"""Classify the supported physical transfers from checked x86-64 witnesses."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from phoenix.lift.index import LiftIndex, Operation
from phoenix.lift.mapping import GhidraVA, LiftMapping, MappingError
from phoenix.recover.addresses import (
    AddressProof,
    ElfVA,
    InstructionWitness,
    prove_addresses,
)

type TransferKind = Literal[
    "direct_call", "indirect_call", "direct_jump", "indirect_jump", "return"
]

_OPCODES: dict[TransferKind, str] = {
    "direct_call": "CALL",
    "indirect_call": "CALLIND",
    "direct_jump": "BRANCH",
    "indirect_jump": "BRANCHIND",
    "return": "RETURN",
}
_TRANSFER_OPCODES = frozenset(_OPCODES.values()) | {"CBRANCH", "CALLOTHER"}
_REX = frozenset((0x40, 0x41, 0x42, 0x43, 0x48, 0x49, 0x4A, 0x4B))


@dataclass(frozen=True, slots=True)
class IndirectOperand:
    mod: int
    rm: int
    sib: int | None
    rex_w: bool
    rex_x: bool
    rex_b: bool
    displacement: int
    rip_slot: ElfVA | None


@dataclass(frozen=True, slots=True)
class PhysicalTransfer:
    kind: TransferKind
    length: int
    prefix: int | None = None
    destination: ElfVA | None = None
    operand: IndirectOperand | None = None

    @property
    def import_slot(self) -> ElfVA | None:
        if self.operand is None or self.prefix not in (None, 0xF2, 0x3E):
            return None
        return self.operand.rip_slot


def _relative(end: int, displacement: int) -> ElfVA | None:
    destination = end + displacement
    if 0 <= end < 1 << 64 and 0 <= destination < 1 << 64:
        return ElfVA(destination)
    return None


def _decode_indirect(data: bytes, end: int) -> PhysicalTransfer | None:
    prefix = None if data[0] == 0xFF else data[0]
    opcode = 0 if prefix is None else 1
    cursor = opcode + 2
    if len(data) < cursor or data[opcode] != 0xFF:
        return None
    modrm = data[opcode + 1]
    mod, group, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    if group not in (2, 4):
        return None
    if (
        prefix not in _REX
        and prefix is not None
        and (prefix not in (0xF2, 0x3E) or modrm not in (0x15, 0x25))
    ):
        return None

    sib = None
    if mod != 3 and rm == 4:
        if cursor == len(data):
            return None
        sib = data[cursor]
        cursor += 1
    rip_relative = mod == 0 and rm == 5
    if mod == 2 or rip_relative or (mod == 0 and sib is not None and sib & 7 == 5):
        width = 4
    else:
        width = 1 if mod == 1 else 0
    if cursor + width != len(data):
        return None
    displacement = int.from_bytes(data[cursor:], "little", signed=True)
    slot = _relative(end, displacement) if rip_relative else None
    if rip_relative and slot is None:
        return None
    return PhysicalTransfer(
        "indirect_call" if group == 2 else "indirect_jump",
        len(data),
        prefix,
        operand=IndirectOperand(
            mod,
            rm,
            sib,
            bool(prefix in _REX and prefix & 8),
            bool(prefix in _REX and prefix & 2),
            bool(prefix in _REX and prefix & 1),
            displacement,
            slot,
        ),
    )


def decode_transfer(data: bytes, address: ElfVA) -> PhysicalTransfer | None:
    if not 0 < len(data) <= 15 or not 0 <= address < 1 << 64:
        return None
    opcode = data[0]
    end = address + len(data)
    if end > 1 << 64:
        return None
    if opcode in (0xE8, 0xE9, 0xEB):
        if len(data) != (2 if opcode == 0xEB else 5):
            return None
        displacement = int.from_bytes(data[1:], "little", signed=True)
        destination = _relative(end, displacement)
        if destination is None:
            return None
        return PhysicalTransfer(
            "direct_call" if opcode == 0xE8 else "direct_jump",
            len(data),
            destination=destination,
        )
    if data == b"\xc3":
        return PhysicalTransfer("return", 1)
    return _decode_indirect(data, end)


@dataclass(frozen=True, slots=True)
class TransferEvidence:
    physical: PhysicalTransfer | None
    operation: Operation | None
    continuation: InstructionWitness | None = None
    gap: str | None = None


@dataclass(frozen=True, slots=True)
class CheckedTransfers:
    proof: AddressProof
    sites: Mapping[GhidraVA, TransferEvidence]
    rule: Literal["phoenix-x86-64-transfer-v1"] = "phoenix-x86-64-transfer-v1"


def check_transfers(
    binary: bytes, lift: LiftIndex, supplied: AddressProof
) -> CheckedTransfers:
    mapping = LiftMapping(
        supplied.binary_sha256,
        supplied.lift_sha256,
        lift.image_base,
        lift.startup,
        supplied.spans,
    )
    proof = prove_addresses(binary, lift, mapping)
    if proof != supplied:
        raise MappingError("The supplied address proof differs from the derived proof.")

    witnesses = {w.ghidra: w for w in proof.witnesses}
    sites: dict[GhidraVA, TransferEvidence] = {}
    for address, instruction in lift.instructions.items():
        witness = witnesses.get(address)
        physical = decode_transfer(witness.data, witness.elf) if witness else None
        raw = [op for op in instruction.pcode if op.opcode in _TRANSFER_OPCODES]
        if physical is None and not raw:
            continue
        operation = raw[0] if len(raw) == 1 else None
        gap = None
        continuation = None
        if witness is None:
            gap = "unavailable_site"
        elif len(raw) > 1:
            gap = "conflicting_transfer_roles"
        elif physical is None:
            gap = "unsupported_transfer_encoding"
        elif operation is None or operation.opcode != _OPCODES[physical.kind]:
            gap = "conflicting_transfer_bytes"
        elif physical.kind in ("direct_call", "indirect_call"):
            adjacent = witnesses.get(GhidraVA(address + physical.length))
            if adjacent is not None and adjacent.owner == witness.owner:
                continuation = adjacent
        sites[address] = TransferEvidence(physical, operation, continuation, gap)
    return CheckedTransfers(proof, MappingProxyType(sites))
