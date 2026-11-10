from hashlib import sha256
from pathlib import Path
from struct import pack_into

import pytest

from phoenix.ingest import (
    BinaryMetadata,
    InputRejected,
    RejectionReason,
    inspect_binary,
)

_INTERP = 0x140
_LOAD = 64 + 56
_DYNAMIC = 0x200
_DYNAMIC_HEADER = 64 + 3 * 56
_DYNSTR = 0x280
_SHSTR = 0x310
_COMMENT = 0x360
_SECTIONS = 0x400
_NAMES = b"\0.shstrtab\0.comment\0.dynsym\0.dynstr\0.debug_info\0"


def _elf(
    *,
    pie: bool = True,
    osabi: int = 0,
    comment: bytes = b"\0GCC: example\0clang version example\0",
    loader: bytes = b"/lib64/ld-linux-x86-64.so.2\0",
    library: bytes = b"libc.so.6\0",
) -> bytearray:
    data = bytearray(0x600)
    base = 0 if pie else 0x400000
    ident = b"\x7fELF\x02\x01\x01" + bytes([osabi])
    pack_into(
        "<16sHHIQQQIHHHHHH",
        data,
        0,
        ident,
        3 if pie else 2,
        62,
        1,
        base + 0x180,
        64,
        _SECTIONS,
        0,
        64,
        56,
        4,
        64,
        5,
        1,
    )
    programs = [
        (3, 4, _INTERP, base + _INTERP, len(loader), len(loader), 1),
        (1, 5, 0, base, 0x200, 0x200, 0x1000),
        (1, 6, 0x200, base + 0x1200, 0x200, 0x240, 0x1000),
        (2, 6, _DYNAMIC, base + 0x1200, 64, 64, 8),
    ]
    for index, (kind, flags, offset, address, file_size, mem_size, align) in enumerate(
        programs
    ):
        pack_into(
            "<IIQQQQQQ",
            data,
            64 + index * 56,
            kind,
            flags,
            offset,
            address,
            address,
            file_size,
            mem_size,
            align,
        )
    data[_INTERP : _INTERP + len(loader)] = loader
    data[_SHSTR : _SHSTR + len(_NAMES)] = _NAMES
    data[_COMMENT : _COMMENT + len(comment)] = comment
    data[_DYNSTR + 1 : _DYNSTR + 1 + len(library)] = library
    for index, (tag, value) in enumerate(
        [(1, 1), (5, base + 0x1280), (10, 1 + len(library)), (0, 0)]
    ):
        pack_into("<qQ", data, _DYNAMIC + index * 16, tag, value)
    sections = [
        (b".shstrtab", 3, _SHSTR, len(_NAMES), 0, 0, 1, 0),
        (b".comment", 1 if comment else 0, _COMMENT, len(comment), 0, 0, 1, 0),
        (b".dynsym", 11, 0x2A0, 24, 4, 1, 8, 24),
        (b".dynstr", 3, _DYNSTR, 1 + len(library), 0, 0, 1, 0),
    ]
    for index, (name, kind, offset, size, link, info, align, entry_size) in enumerate(
        sections, 1
    ):
        pack_into(
            "<IIQQQQIIQQ",
            data,
            _SECTIONS + index * 64,
            _NAMES.index(name),
            kind,
            0,
            0,
            offset,
            size,
            link,
            info,
            align,
            entry_size,
        )
    return data


@pytest.mark.parametrize(("pie", "osabi"), [(True, 0), (False, 3)])
def test_inspect_stripped_glibc_elf(tmp_path: Path, pie: bool, osabi: int) -> None:
    data = _elf(pie=pie, osabi=osabi)
    path = tmp_path / "program"
    path.write_bytes(data)
    assert inspect_binary(path) == BinaryMetadata(
        sha256(data).hexdigest(),
        0x180 if pie else 0x400180,
        ("GCC: example", "clang version example"),
    )


def test_comment_is_optional(tmp_path: Path) -> None:
    path = tmp_path / "program"
    path.write_bytes(_elf(comment=b""))
    assert inspect_binary(path).compiler_evidence == ()


@pytest.mark.parametrize(
    ("loader", "library"),
    [
        (b"/lib/ld-musl-x86_64.so.1\0", b"libc.so.6\0"),
        (b"/lib64/ld-linux-x86-64.so.2\0", b"libc.so.60\0"),
    ],
)
def test_rejects_non_glibc_linkage(
    tmp_path: Path, loader: bytes, library: bytes
) -> None:
    path = tmp_path / "program"
    path.write_bytes(_elf(loader=loader, library=library))
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.NOT_GLIBC


@pytest.mark.parametrize(
    ("offset", "encoding", "value", "reason"),
    [
        (0, "<B", 0, RejectionReason.UNSUPPORTED_ELF),
        (4, "<B", 1, RejectionReason.UNSUPPORTED_ELF),
        (5, "<B", 2, RejectionReason.UNSUPPORTED_ELF),
        (7, "<B", 9, RejectionReason.UNSUPPORTED_ELF),
        (18, "<H", 183, RejectionReason.UNSUPPORTED_ELF),
        (16, "<H", 1, RejectionReason.NOT_EXECUTABLE),
        (24, "<Q", 0x1200, RejectionReason.NOT_EXECUTABLE),
        (64, "<I", 0, RejectionReason.NOT_DYNAMIC),
        (_DYNAMIC_HEADER, "<I", 0, RejectionReason.NOT_DYNAMIC),
        (_DYNAMIC + 48, "<q", 1, RejectionReason.MALFORMED_ELF),
        (
            _SECTIONS + 2 * 64,
            "<I",
            _NAMES.index(b".debug_info"),
            RejectionReason.NOT_STRIPPED,
        ),
        (_SECTIONS + 3 * 64 + 4, "<I", 2, RejectionReason.NOT_STRIPPED),
        (62, "<H", 0, RejectionReason.STRIPPING_UNVERIFIED),
        (_SECTIONS + 2 * 64, "<I", 0, RejectionReason.STRIPPING_UNVERIFIED),
        (_DYNAMIC, "<q", 21, RejectionReason.NOT_GLIBC),
    ],
)
def test_rejects_input_outside_contract(
    tmp_path: Path, offset: int, encoding: str, value: int, reason: RejectionReason
) -> None:
    data = _elf()
    pack_into(encoding, data, offset, value)
    path = tmp_path / "program"
    path.write_bytes(data)
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is reason


@pytest.mark.parametrize(
    ("offset", "encoding", "value"),
    [
        (20, "<I", 0),
        (32, "<Q", 1 << 63),
        (40, "<Q", 64),
        (54, "<H", 55),
        (56, "<H", 64),
        (58, "<H", 63),
        (62, "<H", 5),
        (64 + 32, "<Q", 0),
        (_INTERP + 27, "<B", 1),
        (_LOAD + 32, "<Q", 0x700),
        (_LOAD + 40, "<Q", 0x100),
        (_LOAD + 56 + 16, "<Q", 0),
        (_DYNAMIC_HEADER + 8, "<Q", 0x210),
        (_DYNAMIC_HEADER + 32, "<Q", 63),
        (_DYNAMIC + 8, "<Q", 10),
        (_DYNAMIC + 24, "<Q", 0x1400),
        (_DYNAMIC + 24, "<Q", 0x1230),
        (_DYNAMIC + 40, "<Q", 0x200),
        (_DYNAMIC + 48, "<q", 5),
        (_DYNSTR + 10, "<B", 1),
        (_SECTIONS + 64 + 4, "<I", 8),
        (_SECTIONS + 2 * 64, "<I", len(_NAMES)),
        (_SECTIONS + 2 * 64 + 24, "<Q", _SHSTR),
        (_SECTIONS + 2 * 64 + 32, "<Q", 0x400),
        (_SHSTR + len(_NAMES) - 1, "<B", 1),
    ],
)
def test_rejects_malformed_tables(
    tmp_path: Path, offset: int, encoding: str, value: int
) -> None:
    data = _elf()
    pack_into(encoding, data, offset, value)
    path = tmp_path / "program"
    path.write_bytes(data)
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.MALFORMED_ELF


def test_rejects_unterminated_comment(tmp_path: Path) -> None:
    path = tmp_path / "program"
    path.write_bytes(_elf(comment=b"GCC: example"))
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.MALFORMED_ELF


def test_rejects_truncated_header(tmp_path: Path) -> None:
    path = tmp_path / "program"
    path.write_bytes(b"\x7fELF")
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.MALFORMED_ELF


def test_rejects_sectionless_elf(tmp_path: Path) -> None:
    data = _elf()
    pack_into("<Q", data, 40, 0)
    pack_into("<HHH", data, 58, 0, 0, 0)
    path = tmp_path / "program"
    path.write_bytes(data)
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.STRIPPING_UNVERIFIED


def test_rejects_unreadable_input(tmp_path: Path) -> None:
    for path in (tmp_path, tmp_path / "missing", tmp_path / "bad\0path"):
        with pytest.raises(InputRejected) as failure:
            inspect_binary(path)
        assert failure.value.reason is RejectionReason.UNREADABLE


def test_rejects_oversize_file(tmp_path: Path) -> None:
    path = tmp_path / "program"
    with path.open("wb") as stream:
        stream.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises(InputRejected) as failure:
        inspect_binary(path)
    assert failure.value.reason is RejectionReason.TOO_LARGE
