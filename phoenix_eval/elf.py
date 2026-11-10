from dataclasses import dataclass
from struct import Struct, unpack_from

_SECTION = Struct("<IIQQQQIIQQ")


@dataclass(frozen=True, slots=True)
class Section:
    address: int
    data: bytes


def elf_sections(program: bytes, *names: str) -> dict[str, Section]:
    """Read named file-backed sections from a little-endian ELF64 file."""
    if len(program) < 64 or not program.startswith(b"\x7fELF\x02\x01\x01"):
        raise ValueError("Use a little-endian ELF64 file.")
    (table,) = unpack_from("<Q", program, 40)
    width, count, string_index = unpack_from("<HHH", program, 58)
    table_end = table + width * count
    if (
        table < 64
        or width != _SECTION.size
        or not 0 < string_index < count < 0xFF00
        or table_end > len(program)
    ):
        raise ValueError("The ELF section table is invalid.")
    string_header = _SECTION.unpack_from(program, table + width * string_index)
    _, kind, flags, _, start, size, *_ = string_header
    if (
        kind != 3
        or flags & 0x800
        or not size
        or start + size > len(program)
        or (start < table_end and table < start + size)
    ):
        raise ValueError("The ELF section names are invalid.")
    strings = program[start : start + size]
    if strings[0] != 0 or strings[-1] != 0:
        raise ValueError("The ELF section name table must start and end with zero.")
    wanted = {name.encode("ascii"): name for name in names}
    sections = {}
    for index in range(1, count):
        name_index, kind, flags, address, start, size, *_ = _SECTION.unpack_from(
            program, table + width * index
        )
        if name_index >= len(strings):
            raise ValueError("An ELF section name is out of bounds.")
        name = wanted.get(strings[name_index : strings.index(0, name_index)])
        if name is None:
            continue
        if (
            name in sections
            or kind != 1
            or flags & 0x800
            or start + size > len(program)
            or (size and start < table_end and table < start + size)
        ):
            raise ValueError(f"The ELF {name} section is invalid.")
        sections[name] = Section(address, program[start : start + size])
    return sections
