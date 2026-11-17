"""Publish complete artifact bytes with atomic replacement."""

import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile


def atomic_bytes(
    path: Path, data: bytes, *, before_publish: Callable[[], None] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            if before_publish is not None:
                before_publish()
            staged.replace(path)
            descriptor = os.open(
                path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            staged.unlink(missing_ok=True)
