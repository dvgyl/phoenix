from struct import pack, pack_into

import pytest

from phoenix_eval.elf import Section, elf_sections


def _elf() -> bytes:
    names = b"\0.shstrtab\0.text\0.rodata\0"
    data = bytearray(64)
    data[:7] = b"\x7fELF\x02\x01\x01"
    pack_into("<Q", data, 40, 128)
    pack_into("<HHH", data, 58, 64, 4, 1)
    data.extend(names + b"codeconstant")
    data.extend(bytes(128 - len(data)))
    data.extend(bytes(64))
    for index, kind, address, offset, size in (
        (1, 3, 0, 64, len(names)),
        (11, 1, 0x1000, 64 + len(names), 4),
        (17, 1, 0x2000, 68 + len(names), 8),
    ):
        data.extend(
            pack("<IIQQQQIIQQ", index, kind, 0, address, offset, size, 0, 0, 1, 0)
        )
    return bytes(data)


def test_reads_exact_section_ranges() -> None:
    assert elf_sections(_elf(), ".text", ".rodata", ".data") == {
        ".text": Section(0x1000, b"code"),
        ".rodata": Section(0x2000, b"constant"),
    }


@pytest.mark.parametrize("offset", (4, 40, 58, 62, 128 + 2 * 64, 128 + 3 * 64 + 24))
def test_rejects_invalid_section_locations(offset: int) -> None:
    elf = bytearray(_elf())
    elf[offset] = 0xFF
    with pytest.raises(ValueError):
        elf_sections(bytes(elf), ".text", ".rodata")
