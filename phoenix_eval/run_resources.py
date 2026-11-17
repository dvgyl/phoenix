"""Sample evaluator memory, active container memory, and workspace storage."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread

from phoenix_eval.docker import docker_cli


def _container_bytes(text: str) -> float:
    total = 0.0
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([0-9.]+)([KMGT]?i?B)\s*/.*", line)
        if match is None:
            raise ValueError("Docker returned an invalid memory sample.")
        unit = match[2]
        exponent = "BKMGT".index(unit[0]) if unit != "B" else 0
        total += float(match[1]) * (1024 if "i" in unit else 1000) ** exponent
    return total


def _process_bytes(text: str, parent: int) -> int:
    processes = [tuple(map(int, line.split())) for line in text.splitlines()]
    children = {parent}
    while True:
        found = {pid for pid, ppid, _ in processes if ppid in children}
        if found <= children:
            break
        children.update(found)
    return sum(rss * 1024 for pid, _, rss in processes if pid in children)


@dataclass
class Resources:
    workspace: Path
    peak_memory_gib: float = 0.0
    peak_storage_gib: float = 0.0
    samples: int = 0
    failed_samples: int = 0
    _stop: Event = field(default_factory=Event)
    _lock: Lock = field(default_factory=Lock)
    _thread: Thread | None = None

    def sample(self) -> None:
        storage = shutil.disk_usage(self.workspace)
        with self._lock:
            self.peak_storage_gib = max(self.peak_storage_gib, storage.used / 2**30)
        try:
            host = subprocess.run(
                ("ps", "-A", "-o", "pid=,ppid=,rss="),
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            containers = subprocess.run(
                (*docker_cli(), "stats", "--no-stream", "--format", "{{.MemUsage}}"),
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            memory = (
                _process_bytes(host.stdout, os.getpid())
                + _container_bytes(containers.stdout)
            ) / 2**30
        except (OSError, ValueError, subprocess.SubprocessError):
            with self._lock:
                self.failed_samples += 1
            return
        with self._lock:
            self.samples += 1
            self.peak_memory_gib = max(self.peak_memory_gib, memory)

    def _monitor(self) -> None:
        while not self._stop.is_set():
            self.sample()
            self._stop.wait(2)

    def start(self) -> None:
        self._thread = Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def finish(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.sample()
