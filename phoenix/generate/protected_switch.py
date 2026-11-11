import re
from dataclasses import dataclass
from hashlib import sha256

from phoenix.generate.checked_switch import SwitchEmission
from phoenix.generate.switch_source import SwitchSourceError, parse_flat_switch
from phoenix.lift.index import LiftIndex
from phoenix.lift.mapping import MappingError
from phoenix.recover import Function
from phoenix.recover.addresses import AddressProof, ElfVA, checked_end
from phoenix.recover.imports import Relocation, read_dynamic_imports

_MAX_GLOBALS = 32
_DATA_NAME = re.compile(r"DAT_([0-9a-f]{6,16})")
_PROTECTED_PREFIX = "#include <stdint.h>\ntypedef uint32_t uint;"


@dataclass(frozen=True, slots=True)
class TypedGlobal:
    name: str
    address: ElfVA
    value: int

    @property
    def declaration(self) -> str:
        return f"static uint32_t {self.name} = {self.value}u;"


@dataclass(frozen=True, slots=True)
class ProtectedDefinition:
    entry: int
    signature: str
    source: str
    source_sha256: str
    evidence: str
    emission: SwitchEmission
    globals: tuple[TypedGlobal, ...]


def _typed_global(
    name: str,
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    emission: SwitchEmission,
    relocations: tuple[Relocation, ...],
) -> TypedGlobal:
    match = _DATA_NAME.fullmatch(name)
    if match is None:
        raise SwitchSourceError("A protected switch has an unsupported data name.")
    address = int(match[1], 16)
    end = checked_end(address, 4)
    uses = {
        (function.entry, operand.address.offset, operand.size)
        for function in lift.functions.values()
        for op in function.analyzed
        for operand in (*op.inputs, op.output)
        if operand is not None
        and operand.address.space == "ram"
        and operand.address.offset < end
        and address < operand.address.offset + operand.size
    }
    if (emission.function, address, 4) not in uses or any(
        start != address or width != 4 for _, start, width in uses
    ):
        raise SwitchSourceError("A protected switch data width is not proved.")
    elf = ElfVA(address - proof.ghidra_delta)
    elf_end = checked_end(elf, 4)
    owners = [
        segment
        for segment in proof.image.segments
        if segment.va <= elf and elf_end <= segment.va + segment.memory_size
    ]
    if len(owners) != 1 or owners[0].flags & 3 != 2:
        raise SwitchSourceError("A protected switch data location is not proved.")
    if any(
        item.slot < elf_end
        and item.write_size != 0
        and (item.write_size is None or item.slot + item.write_size > elf)
        for item in relocations
    ):
        raise SwitchSourceError("A relocation can change protected switch data.")
    owner = owners[0]
    file_end = owner.va + owner.file_size
    if elf_end <= file_end:
        offset = proof.image.offset(elf, 4)
        initial = int.from_bytes(binary[offset : offset + 4], "little")
    elif elf >= file_end:
        initial = 0
    else:
        raise SwitchSourceError("A protected switch initializer crosses a file span.")
    return TypedGlobal(name, elf, initial)


def protect_switch(
    emission: SwitchEmission,
    function: Function,
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
) -> ProtectedDefinition:
    if (
        function.entry != emission.function
        or function.entry == lift.main
        or function.name != f"fn_{function.entry:x}"
        or sha256(function.raw_c.encode("utf-8")).hexdigest()
        != emission.input_source_sha256
        or sha256(emission.source).hexdigest() != emission.output_source_sha256
        or sha256(binary).hexdigest() != lift.binary_sha256
        or (proof.binary_sha256, proof.lift_sha256, proof.sha256)
        != (lift.binary_sha256, lift.lift_sha256, emission.address_proof_sha256)
    ):
        raise SwitchSourceError(
            "The protected switch has a conflicting source identity."
        )
    parsed = parse_flat_switch(emission.source)
    name = parsed.function_name
    if emission.source[name.start : name.end] != function.ghidra_name.encode("utf-8"):
        raise SwitchSourceError("The protected function name differs from the lift.")
    if len(parsed.external_names) > _MAX_GLOBALS:
        raise SwitchSourceError("The protected switch exceeds its global limit.")
    relocations = (
        read_dynamic_imports(binary, proof.image) if parsed.external_names else ()
    )
    globals_ = tuple(
        _typed_global(symbol, binary, lift, proof, emission, relocations)
        for symbol in parsed.external_names
    )
    if len({item.address for item in globals_}) != len(globals_):
        raise SwitchSourceError("Protected switch data names alias the same location.")
    source = (
        emission.source[: name.start]
        + function.name.encode("ascii")
        + emission.source[name.end :]
    )
    checked = parse_flat_switch(source)
    signature = source[checked.signature.start : checked.signature.end].decode("utf-8")
    return ProtectedDefinition(
        function.entry,
        signature,
        source.decode("utf-8"),
        sha256(source).hexdigest(),
        "The original switch and lift support the selector, labels, and signature.",
        emission,
        globals_,
    )


def protected_prefix(definitions: tuple[ProtectedDefinition, ...]) -> str:
    globals_: dict[int, TypedGlobal] = {}
    names: dict[str, int] = {}
    for definition in definitions:
        if (
            sha256(definition.source.encode("utf-8")).hexdigest()
            != definition.source_sha256
        ):
            raise MappingError(
                "A protected definition changed before project emission."
            )
        for item in definition.globals:
            if (
                globals_.setdefault(item.address, item) != item
                or names.setdefault(item.name, item.address) != item.address
            ):
                raise MappingError("Protected switch data declarations conflict.")
    return "\n".join(
        (
            _PROTECTED_PREFIX,
            *(item.declaration for _, item in sorted(globals_.items())),
        )
    )
