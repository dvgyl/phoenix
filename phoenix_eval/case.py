import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from phoenix_eval.outcome import Outcome, TreeSnapshot


def _oracle_pins() -> tuple[str, str]:
    with (Path(__file__).resolve().parents[1] / "tools.lock").open("rb") as stream:
        pins = tomllib.load(stream)
    cpu, tunables = pins["qemu_cpu"], pins["glibc_tunables"]
    if (
        not isinstance(cpu, str)
        or not cpu
        or not isinstance(tunables, str)
        or not tunables
    ):
        raise ValueError("Oracle pins must be nonempty strings.")
    return cpu, tunables


QEMU_CPU, GLIBC_TUNABLES = _oracle_pins()
FIXED_ENVIRONMENT = (
    ("HOME", "/nonexistent"),
    ("LANG", "C.UTF-8"),
    ("TZ", "UTC"),
    ("GLIBC_TUNABLES", GLIBC_TUNABLES),
)
PROTECTED_PREFIXES = ("LD_", "QEMU_", "ROSETTA_", "DYLD_", "MALLOC_")


@dataclass(frozen=True)
class Invocation:
    args: tuple[str, ...] = ()
    stdin: bytes = b""
    tree: TreeSnapshot = TreeSnapshot()
    overlay: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if any("\0" in arg for arg in self.args):
            raise ValueError("An argument cannot contain a NUL byte.")
        names = set(dict(FIXED_ENVIRONMENT))
        for name, value in self.overlay:
            if not name or "=" in name or "\0" in name or "\0" in value:
                raise ValueError("Invalid environment entry.")
            if name in names or name.startswith(PROTECTED_PREFIXES):
                raise ValueError(
                    "An environment entry repeats or changes a protected value."
                )
            names.add(name)
        object.__setattr__(self, "overlay", tuple(sorted(self.overlay)))

    def environment(self) -> dict[str, str]:
        return dict((*FIXED_ENVIRONMENT, *self.overlay))


class WorkerRuntime(StrEnum):
    DIRECT = "direct"
    TRUE_SOURCE_ARM64 = "true-source-arm64"
    QEMU = "qemu"
    ROSETTA = "rosetta"


class FailureKind(StrEnum):
    LAUNCH = "launch"
    LIMIT = "limit"
    TIMEOUT = "timeout"
    SNAPSHOT = "snapshot"
    TRACE = "trace"


@dataclass(frozen=True)
class CaseFailure:
    kind: FailureKind
    detail: str


CaseResult = Outcome | CaseFailure
