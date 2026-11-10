"""Inspect ELF inputs for Phoenix without executing them."""

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from struct import Struct
from typing import NamedTuple

__all__ = ["BinaryMetadata", "InputRejected", "RejectionReason", "inspect_binary"]

_HEADER = Struct("<16sHHIQQQIHHHHHH")
_PROGRAM = Struct("<IIQQQQQQ")
_SECTION = Struct("<IIQQQQIIQQ")
_DYNAMIC = Struct("<qQ")

_PT_LOAD, _PT_DYNAMIC, _PT_INTERP = 1, 2, 3
_PF_X = 1
_SHT_PROGBITS, _SHT_SYMTAB, _SHT_STRTAB, _SHT_NOBITS = 1, 2, 3, 8
_SHF_ALLOC, _SHF_INFO_LINK, _SHF_COMPRESSED = 0x2, 0x40, 0x800
_DT_NULL, _DT_NEEDED, _DT_STRTAB, _DT_STRSZ, _DT_SONAME = 0, 1, 5, 10, 14
_GLIBC_INTERPRETERS = (
    b"/lib64/ld-linux-x86-64.so.2\0",
    b"/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2\0",
)
_DEBUG_PREFIXES = (b".debug_", b".zdebug_", b".stab", b".gnu.linkonce.wi.")
_DEBUG_NAMES = (b".gnu_debugdata\0", b".gdb_index\0", b".symtab\0")
_MAX_FILE_SIZE = 64 * 1024 * 1024
_MAX_COMMENT_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class BinaryMetadata:
    sha256: str
    entry_address: int
    compiler_evidence: tuple[str, ...]


class RejectionReason(StrEnum):
    UNREADABLE = "unreadable"
    TOO_LARGE = "too_large"
    UNSUPPORTED_ELF = "unsupported_elf"
    MALFORMED_ELF = "malformed_elf"
    NOT_EXECUTABLE = "not_executable"
    NOT_DYNAMIC = "not_dynamic"
    NOT_GLIBC = "not_glibc"
    STRIPPING_UNVERIFIED = "stripping_unverified"
    NOT_STRIPPED = "not_stripped"


class InputRejected(ValueError):
    def __init__(self, reason: RejectionReason, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


class _Program(NamedTuple):
    kind: int
    flags: int
    offset: int
    address: int
    physical_address: int
    file_size: int
    memory_size: int
    alignment: int


class _Section(NamedTuple):
    name: int
    kind: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_size: int


def _read_file(path: Path) -> bytes:
    try:
        # Nonblocking open lets the regular-file check reject pipes without waiting.
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise InputRejected(RejectionReason.UNREADABLE, "Use a regular file.")
            if info.st_size <= _MAX_FILE_SIZE:
                data = stream.read(_MAX_FILE_SIZE + 1)
                if len(data) <= _MAX_FILE_SIZE:
                    return data
    except InputRejected:
        raise
    except (OSError, ValueError) as exc:
        raise InputRejected(
            RejectionReason.UNREADABLE, "Cannot read the file."
        ) from exc
    raise InputRejected(RejectionReason.TOO_LARGE, "The file exceeds 64 MiB.")


def _malformed(detail: str) -> InputRejected:
    return InputRejected(RejectionReason.MALFORMED_ELF, detail)


def _end(data: bytes, offset: int, size: int, field: str) -> int:
    end = offset + size
    if end > len(data):
        raise _malformed(f"The {field} extends past the end of the file.")
    return end


def _table_end(
    data: bytes, offset: int, size: int, count: int, layout: Struct, field: str
) -> int:
    if offset < _HEADER.size or offset % 8 or size != layout.size or not count:
        raise _malformed(f"The {field} has an invalid offset, entry size, or count.")
    return _end(data, offset, size * count, field)


def _check_disjoint(spans: list[tuple[int, int]], detail: str) -> None:
    for (_, end), (start, _) in pairwise(sorted(spans)):
        if end > start:
            raise _malformed(detail)


def _check_strings(data: bytes, offset: int, size: int) -> None:
    end = _end(data, offset, size, "string table")
    if not size or data[offset] != 0 or data[end - 1] != 0:
        raise _malformed("The string table must start and end with a null byte.")


def _check_alignment(alignment: int) -> None:
    if alignment & (alignment - 1):
        raise _malformed("The ELF alignment is not a power of two.")


def _check_program(data: bytes, programs: list[_Program], entry: int) -> None:
    loads: list[_Program] = []
    dynamic: _Program | None = None
    interp: _Program | None = None
    for program in programs:
        if program.kind == 0:  # PT_NULL has no defined fields.
            continue
        _end(data, program.offset, program.file_size, "segment")
        _check_alignment(program.alignment)
        if program.kind == _PT_LOAD:
            if (
                program.file_size > program.memory_size
                or program.address + program.memory_size > 1 << 64
                or (program.address - program.offset) % max(4096, program.alignment)
            ):
                raise _malformed("The load segment has invalid sizes or alignment.")
            if loads and program.address < loads[-1].address + loads[-1].memory_size:
                raise _malformed("The load segments overlap or are out of order.")
            loads.append(program)
        elif program.kind == _PT_DYNAMIC:
            if dynamic is not None:
                raise _malformed("The ELF has more than one dynamic segment.")
            dynamic = program
        elif program.kind == _PT_INTERP:
            if interp is not None:
                raise _malformed("The ELF has more than one interpreter segment.")
            interp = program

    if not entry or not any(
        p.flags & _PF_X and p.address <= entry < p.address + p.file_size for p in loads
    ):
        raise InputRejected(
            RejectionReason.NOT_EXECUTABLE, "The entry is outside executable file data."
        )
    if interp is None or dynamic is None:
        raise InputRejected(
            RejectionReason.NOT_DYNAMIC,
            "The ELF needs an interpreter and dynamic data.",
        )

    if not 1 < interp.file_size <= 4096:
        raise _malformed("The interpreter path has an invalid length.")
    interpreter = data[interp.offset : interp.offset + interp.file_size]
    if interpreter[-1] != 0 or b"\0" in interpreter[:-1]:
        raise _malformed("The interpreter path must end with a single null byte.")
    if interpreter not in _GLIBC_INTERPRETERS:
        raise InputRejected(
            RejectionReason.NOT_GLIBC, "The ELF does not name a supported glibc loader."
        )
    _check_dynamic(data, loads, dynamic)


def _file_offset(loads: list[_Program], address: int, size: int) -> int:
    for load in loads:
        delta = address - load.address
        if 0 <= delta < load.file_size and delta + size <= load.file_size:
            return load.offset + delta
    raise _malformed("The dynamic data points outside file-backed load segments.")


def _check_dynamic(data: bytes, loads: list[_Program], dynamic: _Program) -> None:
    start = dynamic.offset
    size = dynamic.file_size
    if not size or size % _DYNAMIC.size or size > dynamic.memory_size:
        raise _malformed("The dynamic table has an invalid size.")
    if _file_offset(loads, dynamic.address, size) != start:
        raise _malformed("The dynamic table offset does not match its load segment.")

    fields: dict[int, int] = {}
    for offset in range(start, start + size, _DYNAMIC.size):
        tag, value = _DYNAMIC.unpack_from(data, offset)
        if tag == _DT_NULL:
            stop = offset
            break
        if tag in (_DT_STRTAB, _DT_STRSZ, _DT_SONAME):
            if tag in fields:
                raise _malformed("The dynamic table repeats a single-value tag.")
            fields[tag] = value
    else:
        raise _malformed("The dynamic table has no DT_NULL entry.")

    if _DT_STRTAB not in fields or _DT_STRSZ not in fields:
        raise _malformed("The dynamic table does not specify its string table.")
    string_size = fields[_DT_STRSZ]
    strings = _file_offset(loads, fields[_DT_STRTAB], string_size)
    _check_strings(data, strings, string_size)
    if start < strings + string_size and strings < start + size:
        raise _malformed("The dynamic table overlaps its string table.")

    has_libc = False
    for offset in range(start, stop, _DYNAMIC.size):
        tag, value = _DYNAMIC.unpack_from(data, offset)
        if tag in (_DT_NEEDED, _DT_SONAME):
            if not 0 < value < string_size or data[strings + value] == 0:
                raise _malformed("The dynamic library name is empty or out of bounds.")
            if tag == _DT_NEEDED:
                has_libc |= data.startswith(b"libc.so.6\0", strings + value)
    if _DT_SONAME in fields:
        raise InputRejected(
            RejectionReason.NOT_EXECUTABLE, "The ELF names a shared object."
        )
    if not has_libc:
        raise InputRejected(
            RejectionReason.NOT_GLIBC, "The ELF does not need libc.so.6."
        )


def _check_sections(
    data: bytes,
    sections: list[_Section],
    names_index: int,
    reserved: list[tuple[int, int]],
) -> tuple[str, ...]:
    if any(sections[0]):
        raise _malformed("The first section header must be empty.")
    spans = reserved.copy()
    for section in sections:
        if section.kind == 0:  # SHT_NULL has no defined fields after index zero.
            continue
        _check_alignment(section.alignment)
        if (
            section.link >= len(sections)
            or (section.flags & _SHF_INFO_LINK and section.info >= len(sections))
            or (section.entry_size and section.size % section.entry_size)
        ):
            raise _malformed("The section has an invalid link, index, or entry size.")
        if section.flags & _SHF_ALLOC and section.address + section.size > 1 << 64:
            raise _malformed("The allocated section exceeds the ELF address space.")
        if section.kind != _SHT_NOBITS:
            end = _end(data, section.offset, section.size, "section")
            if section.size:
                spans.append((section.offset, end))
    _check_disjoint(spans, "The ELF sections or header tables overlap.")

    if names_index == 0:
        raise InputRejected(
            RejectionReason.STRIPPING_UNVERIFIED, "The ELF has no section name table."
        )
    names = sections[names_index]
    if names.kind != _SHT_STRTAB or names.flags & _SHF_COMPRESSED:
        raise _malformed("The section name table has an invalid type or flags.")
    _check_strings(data, names.offset, names.size)

    comment = None
    names_end = names.offset + names.size
    for section in sections:
        if section.kind == 0:
            continue
        if section.name >= names.size:
            raise _malformed("The section name is out of bounds.")
        start = names.offset + section.name
        if section.kind == _SHT_SYMTAB or data.startswith(
            _DEBUG_PREFIXES + _DEBUG_NAMES, start, names_end
        ):
            raise InputRejected(
                RejectionReason.NOT_STRIPPED, "The ELF contains symbols or debug data."
            )
        if data[start] == 0:
            raise InputRejected(
                RejectionReason.STRIPPING_UNVERIFIED, "The ELF has an unnamed section."
            )
        if data.startswith(b".comment\0", start, names_end):
            if (
                comment is not None
                or section.kind != _SHT_PROGBITS
                or section.flags & _SHF_COMPRESSED
            ):
                raise _malformed("The ELF has an invalid .comment section.")
            comment = section

    if comment is None:
        return ()
    if comment.size > _MAX_COMMENT_SIZE:
        raise InputRejected(
            RejectionReason.TOO_LARGE, "The .comment section exceeds 64 KiB."
        )
    raw = data[comment.offset : comment.offset + comment.size]
    if raw and raw[-1] != 0:
        raise _malformed("The .comment section must end with a null byte.")
    return tuple(
        text.decode("utf-8", errors="replace") for text in raw.split(b"\0") if text
    )


def inspect_binary(path: Path) -> BinaryMetadata:
    """Check Linux ELF headers, glibc linkage evidence, and signs of stripping.

    This check reads files up to 64 MiB and compiler comments up to 64 KiB.
    It requires standard header numbering and section names to check stripping.

    Compiler comments are hints. This check cannot prove source language,
    compiler flags, or which libraries the loader will use. It cannot prove
    determinism or restrictions on threads, processes, or input and output.
    """
    data = _read_file(path)
    if not data.startswith(b"\x7fELF"):
        raise InputRejected(RejectionReason.UNSUPPORTED_ELF, "The file is not ELF.")
    if len(data) < _HEADER.size:
        raise _malformed("The ELF header is incomplete.")

    (
        ident,
        kind,
        machine,
        version,
        entry,
        phoff,
        shoff,
        _,
        ehsize,
        phsize,
        phnum,
        shsize,
        shnum,
        shstrndx,
    ) = _HEADER.unpack_from(data)
    if ident[4:7] != b"\x02\x01\x01" or ident[7] not in (0, 3) or machine != 62:
        raise InputRejected(
            RejectionReason.UNSUPPORTED_ELF, "Use little-endian Linux x86-64 ELF64."
        )
    if version != 1 or ehsize != _HEADER.size:
        raise _malformed("The ELF header has an invalid version or size.")
    if kind not in (2, 3):  # ET_EXEC or ET_DYN for position-independent executables.
        raise InputRejected(
            RejectionReason.NOT_EXECUTABLE, "The ELF type is not executable."
        )
    if (
        phnum == 0xFFFF
        or shnum >= 0xFF00
        or shstrndx >= 0xFF00
        or (shoff and not shnum)
    ):
        raise InputRejected(
            RejectionReason.UNSUPPORTED_ELF, "Extended ELF numbering is not supported."
        )

    phend = _table_end(data, phoff, phsize, phnum, _PROGRAM, "program header table")
    if not shoff and not shnum and not shstrndx and shsize in (0, _SECTION.size):
        raise InputRejected(
            RejectionReason.STRIPPING_UNVERIFIED, "The ELF has no section header table."
        )
    shend = _table_end(data, shoff, shsize, shnum, _SECTION, "section header table")
    if shstrndx >= shnum or (phoff < shend and shoff < phend):
        raise _malformed("The section name index or header table layout is invalid.")

    view = memoryview(data)
    programs = [_Program(*row) for row in _PROGRAM.iter_unpack(view[phoff:phend])]
    sections = [_Section(*row) for row in _SECTION.iter_unpack(view[shoff:shend])]
    _check_program(data, programs, entry)
    compiler_evidence = _check_sections(
        data, sections, shstrndx, [(0, _HEADER.size), (phoff, phend), (shoff, shend)]
    )
    return BinaryMetadata(sha256(data).hexdigest(), entry, compiler_evidence)
