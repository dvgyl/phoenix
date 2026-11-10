from dataclasses import dataclass

MAX_TRACE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class CodeTrace:
    start: int
    end: int
    hits: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.start < self.end:
            raise ValueError("The trace image addresses are invalid.")
        if not self.hits or tuple(sorted(set(self.hits))) != self.hits:
            raise ValueError("The trace must contain sorted, unique hits.")
        if self.hits[0] < self.start or self.hits[-1] >= self.end:
            raise ValueError("A hit is outside the original code range.")


def parse_trace(data: bytes) -> CodeTrace:
    if len(data) > MAX_TRACE_BYTES:
        raise ValueError("The trace exceeds the byte limit.")
    lines = data.decode("ascii").splitlines()
    if len(lines) < 3:
        raise ValueError("The code trace is incomplete.")
    header, *body, footer = (line.split() for line in lines)
    if len(header) != 3 or header[0] != "image" or footer != ["done", str(len(body))]:
        raise ValueError("The code trace is incomplete.")
    hits = []
    for record in body:
        if len(record) != 2 or record[0] != "hit":
            raise ValueError("Invalid trace record.")
        hits.append(int(record[1], 16))
    start, end = (int(address, 16) for address in header[1:])
    return CodeTrace(start, end, tuple(hits))
