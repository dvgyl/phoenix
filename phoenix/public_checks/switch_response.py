import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from struct import unpack_from

from phoenix.generate import raw
from phoenix.generate.protected_switch import ProtectedDefinition
from phoenix.lift.index import LiftIndex
from phoenix.llm.provider import Completion, Model, Request, Usage
from phoenix.recover import Program
from phoenix.recover.addresses import AddressProof, ElfVA
from phoenix.recover.imports import read_dynamic_imports

_STDIN = re.compile(r"\*\(FILE \*\*\)PTR_stdin_([0-9a-f]+)")
_ZERO_USAGE = Usage(0, 0, 0)


@dataclass(frozen=True, slots=True)
class PublicResponse:
    response: str
    binary_sha256: str
    lift_sha256: str
    main_source_sha256: str
    protected_source_sha256: str
    protected_source: str
    protected_signature: str
    transformations: tuple[str, ...]


class FixedPublicProvider:
    name = "fixed-public-cleanup"

    def __init__(self, prepare: Callable[[], PublicResponse]) -> None:
        self.prepare = prepare
        self.prepared: PublicResponse | None = None
        self.calls = 0

    def maximum_usage(self, request: Request) -> Usage:
        return _ZERO_USAGE

    def complete(self, request: Request) -> Completion:
        if request.model is not Model.SOL:
            raise ValueError("The public control requires the Sol request profile.")
        self.calls += 1
        if self.prepared is None:
            self.prepared = self.prepare()
        return Completion(self.prepared.response, _ZERO_USAGE, Model.SOL)


def _stdin_symbol(binary: bytes, proof: AddressProof, slot_name: str) -> None:
    slot = ElfVA(int(slot_name, 16) - proof.ghidra_delta)
    records = [
        record
        for record in read_dynamic_imports(binary, proof.image)
        if record.slot == slot
    ]
    if len(records) != 1 or records[0].kind != 6:
        raise ValueError("The public stdin slot has no unique object relocation.")
    record = records[0]
    tags = dict(proof.image.dynamic)
    symbol = ElfVA(tags[6] + record.symbol_index * 24)
    label, flags, _, section, _, _ = unpack_from(
        "<IBBHQQ", binary, proof.image.offset(symbol, 24)
    )
    if flags & 15 != 1 or section != 0 or label >= tags[10]:
        raise ValueError("The public stdin slot has conflicting symbol evidence.")
    offset = proof.image.offset(ElfVA(tags[5]), tags[10])
    if binary[offset + label :].split(b"\0", 1)[0] != b"stdin":
        raise ValueError("The public object relocation does not request stdin.")


def prepare_response(
    program: Program,
    binary: bytes,
    lift: LiftIndex,
    proof: AddressProof,
    protected: ProtectedDefinition,
) -> PublicResponse:
    if (
        len(program.functions) != 2
        or program.main != lift.main
        or sha256(binary).hexdigest() != lift.binary_sha256
        or proof.lift_sha256 != lift.lift_sha256
        or protected.entry == program.main
        or {item.entry for item in program.functions} != {program.main, protected.entry}
    ):
        raise ValueError("The public control needs main and one protected switch.")
    main = next(item for item in program.functions if item.entry == program.main)
    target = next(item for item in program.functions if item.entry == protected.entry)
    if main.raw_c != lift.functions[lift.main].raw_c:
        raise ValueError("The public main source differs from its lift.")
    definition = re.search(
        rf"\b{re.escape(main.ghidra_name)}\s*\(([^()]*)\)\s*\{{",
        main.raw_c,
    )
    if definition is None or not main.raw_c.rstrip().endswith("}"):
        raise ValueError("The public main declaration is unsupported.")
    parameters = definition[1].strip()
    if parameters != "int param_1,long param_2":
        raise ValueError(
            "The public main needs its fixed decompiler parameter profile."
        )
    body = main.raw_c[definition.end() : main.raw_c.rfind("}")]
    if body.count("*(char **)(param_2 + 8)") != 1:
        raise ValueError("The public main has an unsupported argv access.")
    body = body.replace("*(char **)(param_2 + 8)", "param_2[1]")
    changes = ["Use the standard main argv pointer."]
    calls = re.compile(rf"\b{re.escape(target.ghidra_name)}\s*\(")
    if len(calls.findall(body)) != 1:
        raise ValueError("The public main must call the protected function once.")
    body = calls.sub(target.name + "(", body)
    changes.append("Use the retained function name.")
    declarations = raw._COMPATIBILITY
    data = raw._data_declarations(program, binary, main.raw_c)
    declarations += "\n" + "\n".join(data)
    for declaration in data:
        match = re.fullmatch(
            r"static const char (DAT_[0-9a-f]+)\[\] = .*;", declaration
        )
        if match is not None:
            body = re.sub(rf"&{re.escape(match[1])}\b", match[1], body)
    if "&DAT_" in body:
        raise ValueError("The public main has an unbound address expression.")
    changes.append("Use typed original string arrays.")
    for match in tuple(_STDIN.finditer(body)):
        _stdin_symbol(binary, proof, match[1])
    body = _STDIN.sub("stdin", body)
    if "PTR_stdin_" in body:
        raise ValueError("The public main has an unsupported stdin expression.")
    changes.append("Use the proved stdin object request.")
    widened = 'printf("%u\\n",(ulong)uVar1)'
    if widened in body:
        if body.count(widened) != 1 or re.search(r"\buint\s+uVar1\s*;", body) is None:
            raise ValueError("The public printf value has no uint declaration.")
        body = body.replace(widened, 'printf("%u\\n",uVar1)')
        changes.append("Use the declared uint value for the uint format.")
    response = json.dumps(
        {
            "declarations": declarations,
            "functions": {
                hex(program.main): {
                    "signature": "int main(int param_1, char **param_2)",
                    "body": body,
                    "evidence": "The startup evidence identifies argc and argv.",
                },
            },
        }
    )
    return PublicResponse(
        response,
        lift.binary_sha256,
        lift.lift_sha256,
        sha256(main.raw_c.encode("utf-8")).hexdigest(),
        protected.source_sha256,
        protected.source,
        protected.signature,
        tuple(changes),
    )
