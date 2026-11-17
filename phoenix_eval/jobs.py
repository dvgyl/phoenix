import ctypes
import fcntl
import os
import platform
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Literal

SlotClass = Literal["compile", "execution", "llm"]


def physical_cores() -> int:
    if platform.system() == "Darwin":
        count = ctypes.c_uint()
        size = ctypes.c_size_t(ctypes.sizeof(count))
        library = ctypes.CDLL(None, use_errno=True)
        if library.sysctlbyname(
            b"hw.physicalcpu", ctypes.byref(count), ctypes.byref(size), None, 0
        ):
            raise OSError(ctypes.get_errno(), "Cannot read the physical core count.")
        return max(1, count.value)
    topology = Path("/sys/devices/system/cpu")
    cores = {
        (
            (path / "physical_package_id").read_text().strip(),
            (path / "core_id").read_text().strip(),
        )
        for path in topology.glob("cpu[0-9]*/topology")
        if (path / "core_id").is_file()
    }
    return len(cores) or 1


@dataclass(frozen=True)
class Slots:
    root: Path
    jobs: int
    llm: int = 8

    def __post_init__(self) -> None:
        if self.jobs < 1 or self.llm < 1:
            raise ValueError("Resource slot counts must be positive.")

    @classmethod
    def from_environment(cls) -> "Slots":
        workspace = os.environ.get("PHOENIX_ROOT")
        if not workspace:
            raise ValueError("Source the Phoenix workspace environment.")
        jobs = os.environ.get("PHOENIX_JOBS")
        return cls(
            Path(workspace).resolve() / "slots",
            int(jobs) if jobs is not None else max(1, physical_cores() // 2),
            int(os.environ.get("PHOENIX_LLM_SLOTS", "8")),
        )

    def count(self, kind: SlotClass) -> int:
        compile_slots = max(1, self.jobs // 2)
        return {
            "compile": compile_slots,
            "execution": max(1, self.jobs - compile_slots),
            "llm": self.llm,
        }[kind]

    @contextmanager
    def acquire(self, kind: SlotClass) -> Iterator[None]:
        directory = self.root / kind
        if directory.resolve() != directory:
            raise ValueError(
                "The resource slot directory cannot contain symbolic links."
            )
        directory.mkdir(parents=True, exist_ok=True)
        while True:
            for number in range(self.count(kind)):
                descriptor = os.open(
                    directory / f"{number}.lock",
                    os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                    0o600,
                )
                try:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    try:
                        yield
                    finally:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                    return
                finally:
                    os.close(descriptor)
            time.sleep(0.05)


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    if path.parent.resolve() != path.parent:
        raise ValueError("The cache lock directory cannot contain symbolic links.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def limited[**P, T](kind: SlotClass) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorate(function: Callable[P, T]) -> Callable[P, T]:
        @wraps(function)
        def call(*args: P.args, **kwargs: P.kwargs) -> T:
            with Slots.from_environment().acquire(kind):
                return function(*args, **kwargs)

        return call

    return decorate
