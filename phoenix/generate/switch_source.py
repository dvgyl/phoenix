import re
from dataclasses import dataclass
from hashlib import sha256

_MAX_SOURCE = 1024 * 1024
_MAX_TOKENS = 65_536
_MAX_CASES = 4096
_MAX_EXPRESSION_DEPTH = 32
_IDENTIFIER = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*")
_INTEGER = re.compile(rb"(?:0[xX][0-9A-Fa-f]+|0|[1-9][0-9]*)(?:[uU])?")
_SOURCE_TRANSFORM = re.compile(rb"\?\?[=/'()!<>-]|\\[ \t\v\f]*[\r\n]")
_TOKEN = re.compile(
    rb"(?P<space>[ \t\r\n\v\f]+)|(?P<comment>//[^\r\n]*|/\*.*?\*/)|"
    rb"(?P<token>[A-Za-z_][A-Za-z0-9_]*|(?:[0-9]|\.[0-9])(?:[eEpP][+-]|[A-Za-z0-9_.])*|"
    rb"\+\+|--|&&|\|\||<<|>>|<=|>=|==|!=|[(){}:;,=+*/%&|^<>~!-])",
    re.DOTALL,
)
_KEYWORDS = frozenset(
    b"auto break case char const continue default do double else enum extern float "
    b"for goto if inline int long register restrict return short signed sizeof static "
    b"struct switch typedef union unsigned void volatile while _Alignas _Alignof "
    b"_Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert "
    b"_Thread_local _Pragma uint uint32_t".split()
)
_UINT_TYPES = frozenset((b"uint", b"uint32_t", b"unsigned"))
_BINARY = frozenset(b"+ - * / % & | ^ << >> < > <= >= == !=".split())
_UNARY = frozenset(b"+ - ~ !".split())


class SwitchSourceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class CaseLabel:
    value: int | None
    marker: Span
    source: Span


@dataclass(frozen=True, slots=True)
class Arm:
    labels: tuple[CaseLabel, ...]
    body: Span
    break_statement: Span | None


@dataclass(frozen=True, slots=True)
class FlatSwitch:
    source_sha256: str
    switch: Span
    expression: Span
    parameter: str
    parameter_index: int
    parameter_reference: Span
    mask: int
    arms: tuple[Arm, ...]
    continuation: Span


@dataclass(frozen=True, slots=True)
class _Token:
    value: bytes
    span: Span


@dataclass(frozen=True, slots=True)
class _MaskedParameter:
    token: _Token
    mask: int


type _SelectorValue = _Token | int | _MaskedParameter


def _tokens(source: bytes) -> tuple[_Token, ...]:
    if (
        not 0 < len(source) <= _MAX_SOURCE
        or b"\0" in source
        or _SOURCE_TRANSFORM.search(source)
    ):
        raise SwitchSourceError("The source is outside the checked switch profile.")
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SwitchSourceError("The checked switch source is not UTF-8.") from error
    tokens: list[_Token] = []
    offset = 0
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if match is None:
            raise SwitchSourceError(f"Unsupported C token at byte {offset}.")
        if match.lastgroup == "token":
            if len(tokens) == _MAX_TOKENS:
                raise SwitchSourceError("The source exceeds the switch token limit.")
            tokens.append(_Token(match[0], Span(offset, match.end())))
        offset = match.end()
    return tuple(tokens)


class _Parser:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.tokens = _tokens(source)
        self.index = 0

    def next(self) -> bytes:
        return self.tokens[self.index].value if self.index < len(self.tokens) else b""

    def take(self, expected: bytes | None = None) -> _Token:
        if self.index == len(self.tokens):
            raise SwitchSourceError("The checked switch source ended too early.")
        token = self.tokens[self.index]
        if expected is not None and token.value != expected:
            raise SwitchSourceError(
                f"Unsupported switch syntax at byte {token.span.start}."
            )
        self.index += 1
        return token

    def identifier(self) -> _Token:
        token = self.take()
        if not _IDENTIFIER.fullmatch(token.value) or token.value in _KEYWORDS:
            raise SwitchSourceError("The switch source needs a simple identifier.")
        return token

    def uint32_type(self) -> None:
        if self.next() == b"unsigned":
            self.take()
            self.take(b"int")
        elif self.next() in (b"uint", b"uint32_t"):
            self.take()
        else:
            raise SwitchSourceError(
                "The switch profile requires an unsigned 32-bit type."
            )

    def integer(self, maximum: int) -> tuple[int, Span]:
        token = self.take()
        if _INTEGER.fullmatch(token.value) is None:
            raise SwitchSourceError(
                "The switch profile requires a bounded integer constant."
            )
        digits = token.value.rstrip(b"uU")
        hexadecimal = digits.lower().startswith(b"0x")
        if hexadecimal:
            digits = digits[2:].lstrip(b"0") or b"0"
        if len(digits) > (8 if hexadecimal else 10):
            raise SwitchSourceError(
                "The switch constant is outside its supported range."
            )
        number = int(digits, 16 if hexadecimal else 10)
        if number > maximum:
            raise SwitchSourceError(
                "The switch constant is outside its supported range."
            )
        return number, token.span

    def operand(self, depth: int) -> None:
        if depth == _MAX_EXPRESSION_DEPTH:
            raise SwitchSourceError("The switch expression exceeds its nesting limit.")
        if self.next() in _UNARY:
            self.take()
            self.operand(depth + 1)
        elif self.next() == b"(":
            self.take()
            if self.next() in _UINT_TYPES:
                self.uint32_type()
                self.take(b")")
                self.operand(depth + 1)
            else:
                self.expression(depth + 1)
                self.take(b")")
        elif _INTEGER.fullmatch(self.next()) is not None:
            self.integer(0xFFFF_FFFF)
        else:
            self.identifier()

    def expression(self, depth: int = 0) -> None:
        self.operand(depth)
        while self.next() in _BINARY:
            self.take()
            self.operand(depth)

    def selector_operand(self, depth: int) -> _SelectorValue:
        if depth == _MAX_EXPRESSION_DEPTH:
            raise SwitchSourceError("The switch expression exceeds its nesting limit.")
        if self.next() == b"(":
            self.take()
            if self.next() in _UINT_TYPES:
                self.uint32_type()
                self.take(b")")
                return self.selector_operand(depth + 1)
            value = self.selector(depth + 1)
            self.take(b")")
            return value
        if _INTEGER.fullmatch(self.next()) is not None:
            return self.integer(0xFFFF_FFFF)[0]
        return self.identifier()

    def selector(self, depth: int = 0) -> _SelectorValue:
        left = self.selector_operand(depth)
        if self.next() != b"&":
            return left
        self.take()
        right = self.selector_operand(depth)
        if not isinstance(left, _Token) or not isinstance(right, int):
            raise SwitchSourceError(
                "The selector must mask one parameter with a constant."
            )
        return _MaskedParameter(left, right)

    def label(self) -> CaseLabel:
        start = self.take()
        value, marker = (
            (None, start.span)
            if start.value == b"default"
            else self.integer(_MAX_CASES - 1)
        )
        end = self.take(b":")
        return CaseLabel(value, marker, Span(start.span.start, end.span.end))

    def arm(self) -> Arm:
        labels = [self.label()]
        while self.next() in (b"case", b"default"):
            if len(labels) > _MAX_CASES:
                raise SwitchSourceError("The switch exceeds its label limit.")
            labels.append(self.label())
        body_start = labels[-1].source.end
        while self.next() not in (b"break", b"case", b"default", b"}"):
            if self.next() != b";":
                self.identifier()
                self.take(b"=")
                self.expression()
            self.take(b";")
        exit_span = None
        body_end = self.tokens[self.index - 1].span.end
        if self.next() == b"break":
            start = self.take()
            end = self.take(b";")
            exit_span = Span(start.span.start, end.span.end)
        elif self.next() != b"}":
            raise SwitchSourceError("The switch arm can fall through to another arm.")
        elif body_start == body_end:
            raise SwitchSourceError("The final switch arm needs a statement.")
        return Arm(tuple(labels), Span(body_start, body_end), exit_span)

    def parse(self) -> FlatSwitch:
        self.uint32_type()
        self.identifier()
        self.take(b"(")
        parameters = []
        while True:
            self.uint32_type()
            parameters.append(self.identifier().value)
            if self.next() != b",":
                break
            self.take()
        self.take(b")")
        self.take(b"{")
        declared = set(parameters)
        if len(declared) != len(parameters):
            raise SwitchSourceError("The switch source repeats a parameter name.")
        while self.next() in _UINT_TYPES:
            self.uint32_type()
            name = self.identifier().value
            if name in declared:
                raise SwitchSourceError("The switch source repeats a local name.")
            declared.add(name)
            self.take(b";")
        switch = self.take(b"switch")
        self.take(b"(")
        expression_index = self.index
        selector = self.selector()
        if (
            not isinstance(selector, _MaskedParameter)
            or selector.token.value not in parameters
        ):
            raise SwitchSourceError(
                "The switch selector must use an original parameter."
            )
        parameter = selector.token
        expression = Span(
            self.tokens[expression_index].span.start,
            self.tokens[self.index - 1].span.end,
        )
        self.take(b")")
        self.take(b"{")
        arms = []
        seen: set[int | None] = set()
        while self.next() in (b"case", b"default"):
            arm = self.arm()
            for label in arm.labels:
                if label.value in seen:
                    raise SwitchSourceError(
                        "The switch repeats a case or default label."
                    )
                seen.add(label.value)
            arms.append(arm)
        self.take(b"}")
        if (
            len(seen) < 2
            or None not in seen
            or all(label.value is not None for label in arms[-1].labels)
        ):
            raise SwitchSourceError("The switch needs cases and a final default arm.")
        tail = self.take(b"return")
        self.expression()
        finish = self.take(b";")
        self.take(b"}")
        if self.next():
            raise SwitchSourceError(
                "Unexpected source after the checked switch function."
            )
        return FlatSwitch(
            sha256(self.source).hexdigest(),
            switch.span,
            expression,
            parameter.value.decode("ascii"),
            parameters.index(parameter.value),
            parameter.span,
            selector.mask,
            tuple(arms),
            Span(tail.span.start, finish.span.end),
        )


def parse_flat_switch(source: bytes) -> FlatSwitch:
    return _Parser(source).parse()
