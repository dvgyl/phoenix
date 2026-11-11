from hashlib import sha256

import pytest

from phoenix.generate.switch_source import SwitchSourceError, parse_flat_switch

SOURCE = b"""uint f(uint v, unsigned int second)
{
    uint scratch;
    switch(v & 0x7) {
        case 0: case 0x1:
            /* A marker: case 5: { } */
            total = total + second;
            break;
        case 2:
            total = (total ^ second) << 1;
            break;
        default:
            total = ~second;
    }
    return total;
}
"""


def test_flat_switch_delimits_exact_source_with_stacked_labels() -> None:
    parsed = parse_flat_switch(SOURCE)
    assert parsed.source_sha256 == sha256(SOURCE).hexdigest()
    assert parsed.mask == 7 and parsed.parameter == "v" and parsed.parameter_index == 0
    assert SOURCE[parsed.switch.start : parsed.switch.end] == b"switch"
    assert SOURCE[parsed.expression.start : parsed.expression.end] == b"v & 0x7"
    assert (
        SOURCE[parsed.parameter_reference.start : parsed.parameter_reference.end]
        == b"v"
    )
    assert [[label.value for label in arm.labels] for arm in parsed.arms] == [
        [0, 1],
        [2],
        [None],
    ]
    first = parsed.arms[0]
    assert SOURCE[first.body.start : first.body.end] == (
        b"\n            /* A marker: case 5: { } */\n"
        b"            total = total + second;"
    )
    assert [
        SOURCE[label.marker.start : label.marker.end] for label in first.labels
    ] == [b"0", b"0x1"]
    assert first.break_statement is not None
    assert SOURCE[first.break_statement.start : first.break_statement.end] == b"break;"
    assert parsed.arms[-1].break_statement is None
    assert (
        SOURCE[parsed.continuation.start : parsed.continuation.end] == b"return total;"
    )


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b"switch(v", b"switch(scratch"),
        (b"v & 0x7", b"v + 0x7"),
        (b"uint v", b"int v"),
        (b"uint scratch;", b"uint scratch = 0;"),
        (b"case 2:", b"case 0x1:"),
        (b"case 2:", b"case 4096:"),
        (b"case 2:", b"case 02:"),
        (b"case 2:", b"case 2 ... 4:"),
        (b"default:", b"case 3:"),
        (b"case 2:", b"default:"),
        (b"break;\n        case 2:", b"case 2:"),
        (b"total + second", b"total++ + second"),
        (b"total + second", b"some_call(second)"),
        (b"total + second", b"*ptr + second"),
        (b"total + second", b"second && total"),
        (b"total + second", b"second ? total : 1"),
        (b"total + second", b"(second, total)"),
        (b"total + second", b"0x1e+2"),
        (b"total + second", b"0xFE-1"),
        (b"return total;", b"return 0x1E-2;"),
        (b"uint f(", b"uint _Pragma("),
        (b"total = ~second;", b"/* no statement */"),
        (b"total + second", b"(" * 32 + b"second" + b")" * 32),
        (b"A marker:", b"??/\n A marker:"),
        (b"return total;", b"return total; return 0;"),
        (b"return total;", b"#pragma ignored\n return total;"),
    ],
)
def test_flat_switch_rejects_unproved_source_shapes(
    before: bytes, after: bytes
) -> None:
    assert before in SOURCE
    with pytest.raises(SwitchSourceError):
        parse_flat_switch(SOURCE.replace(before, after))


def test_flat_switch_uses_byte_positions_after_utf8_comment() -> None:
    source = SOURCE.replace(b"A marker:", "Café:".encode())
    result = parse_flat_switch(source)
    (label,) = result.arms[1].labels
    assert source[label.source.start : label.source.end] == b"case 2:"


@pytest.mark.parametrize(
    "selector",
    [b"(v & 0x7)", b"(v) & (0x7)", b"(unsigned int)v & 0x7", b"(uint32_t)(v & 0x7)"],
)
def test_flat_switch_accepts_unsigned_casts_and_parentheses(selector: bytes) -> None:
    source = SOURCE.replace(b"v & 0x7", selector).replace(
        b"total + second", b"(uint)(total + second)"
    )
    parsed = parse_flat_switch(source)
    assert source[parsed.expression.start : parsed.expression.end] == selector
    assert parsed.mask == 7 and parsed.parameter == "v"
    assert (
        source[parsed.parameter_reference.start : parsed.parameter_reference.end]
        == b"v"
    )
