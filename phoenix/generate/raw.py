import re
from pathlib import Path

from phoenix.recover import Function, Program
from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.coverage import read_executable_bounds
from phoenix_eval.elf import elf_sections

_COMPATIBILITY = """#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef uint8_t byte;
typedef uint8_t undefined;
typedef uint8_t undefined1;
typedef uint16_t undefined2;
typedef uint32_t undefined4;
typedef uint64_t undefined8;
typedef unsigned char uchar;
typedef unsigned short ushort;
typedef unsigned int uint;
typedef unsigned long ulong;
typedef long long longlong;
typedef unsigned long long ulonglong;
typedef void code(void);

extern int __printf_chk(int, const void *, ...);
extern int __fprintf_chk(FILE *, int, const void *, ...);
extern char **environ;
"""

_DATA_NAME = re.compile(r"\b(?:DAT_|s_[A-Za-z0-9_]*_)([0-9a-fA-F]{6,16})\b")


class RawBaselineError(ValueError):
    pass


def _signature(function: Function) -> tuple[str, str, str]:
    pattern = re.compile(
        rf"(?m)^([^\n;{{}}]+?)\s+({re.escape(function.ghidra_name)})"
        r"\s*\(([^()]*)\)\s*\{"
    )
    signature = pattern.search(function.raw_c)
    if signature is None:
        raise RawBaselineError(f"Cannot declare raw function {function.entry:#x}.")
    return signature[1].strip(), signature[2], signature[3].strip()


def _entry_wrapper(return_type: str, name: str, parameters: str) -> str:
    types = []
    for parameter in parameters.split(",") if parameters not in ("", "void") else ():
        match = re.fullmatch(r"([A-Za-z0-9_\s*]+?)\b[A-Za-z_]\w*", parameter.strip())
        if match is None or not match[1].strip():
            raise RawBaselineError(
                "The raw main function has an unsupported parameter."
            )
        types.append(match[1].strip())
    if len(types) > 3:
        raise RawBaselineError("The raw main function has more than three parameters.")
    arguments = []
    for type_name, value in zip(types, ("argc", "argv", "environ")):
        if value != "argc" and "*" not in type_name:
            value = f"(uintptr_t){value}"
        arguments.append(f"({type_name}){value}")
    call = f"{name}({', '.join(arguments)})"
    body = (
        f"{call};\n    return 0;" if return_type == "void" else f"return (int){call};"
    )
    declaration = "int main(int argc, char **argv)" if arguments else "int main(void)"
    return f"{declaration}\n{{\n    {body}\n}}\n"


def _literal(value: bytes) -> str:
    return '"' + "".join(f"\\{byte:03o}" for byte in value) + '"'


def _data_declarations(program: Program, original: bytes, raw_c: str) -> list[str]:
    sections = elf_sections(original, ".rodata")
    rodata = sections.get(".rodata")
    entry, _ = read_executable_bounds(original)
    bias = program.startup - entry
    strings = dict(program.strings)
    declarations = []
    data_names = {match[0]: int(match[1], 16) for match in _DATA_NAME.finditer(raw_c)}
    for name, address in sorted(data_names.items()):
        if address in strings:
            value = strings[address].encode("utf-8")
        elif rodata is not None:
            index = address - bias - rodata.address
            if not 0 <= index < len(rodata.data):
                continue
            value, terminator, _ = rodata.data[index : index + 256].partition(b"\0")
            if not terminator or any(
                byte not in b"\t\n\r" and not 32 <= byte < 127 for byte in value
            ):
                continue
        else:
            continue
        declarations.append(f"static const char {name}[] = {_literal(value)};")
    return declarations


def write_raw_project(project: Path, program: Program, original: Path) -> None:
    functions = {function.entry: function for function in program.functions}
    signatures = {
        address: _signature(function) for address, function in functions.items()
    }
    return_type, entry_name, parameters = signatures[program.main]
    alias = ""
    if entry_name == "main":
        entry_name = "phoenix_raw_main"
        signatures[program.main] = return_type, entry_name, parameters
        alias = f"#define main {entry_name}\n"
    prototypes = [
        f"{return_type} {name}({parameters or 'void'});"
        for return_type, name, parameters in signatures.values()
    ]
    raw_c = "\n".join(function.raw_c for function in program.functions)
    declarations = _data_declarations(program, original.read_bytes(), raw_c)
    header = "\n".join(
        (
            _COMPATIBILITY,
            *declarations,
            *prototypes,
            _entry_wrapper(return_type, entry_name, parameters),
            alias,
        )
    )
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "include").mkdir(exist_ok=True)
    (project / "CMakeLists.txt").write_text(PROJECT_CMAKE, encoding="utf-8")
    (project / "include/compat.h").write_text(header, encoding="utf-8")
    (project / "src/program.c").write_text(
        '#include "compat.h"\n' + raw_c, encoding="utf-8"
    )
