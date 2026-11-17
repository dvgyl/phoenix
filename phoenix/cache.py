import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from phoenix.jobs import file_lock
from phoenix_eval.artifacts import atomic_bytes as atomic_bytes


class CacheError(ValueError):
    pass


def default_root() -> Path:
    workspace = os.environ.get("PHOENIX_ROOT")
    if not workspace:
        raise CacheError("Source the Phoenix workspace environment.")
    return Path(workspace).resolve() / "cache/phoenix"


def identity_hash(identity: object) -> str:
    return sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


def stage_versions(
    pipeline_version: str, tools: dict[str, str], images: dict[str, str]
) -> dict[str, str]:
    return {
        "lift": identity_hash({"source": pipeline_version, "tools": tools}),
        "devset": identity_hash({"source": pipeline_version, "images": images}),
    }


def read_entry(directory: Path, name: str, identity: object) -> bytes:
    try:
        if directory.resolve() != directory:
            raise ValueError
        artifact = directory / name
        manifest = directory / "stage.json"
        if artifact.is_symlink() or manifest.is_symlink():
            raise ValueError
        data = artifact.read_bytes()
        record = json.loads(manifest.read_bytes())
        if record != {"identity": identity, "sha256": sha256(data).hexdigest()}:
            raise ValueError
        return data
    except (OSError, ValueError, TypeError, RecursionError):
        raise CacheError(
            f"The cache entry is corrupt or mismatched at {directory}."
        ) from None


def publish_entry(directory: Path, name: str, identity: object, data: bytes) -> None:
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".cache-", dir=directory.parent) as temporary:
        staging = Path(temporary) / "entry"
        staging.mkdir()
        (staging / name).write_bytes(data)
        (staging / "stage.json").write_text(
            json.dumps(
                {"identity": identity, "sha256": sha256(data).hexdigest()},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        staging.replace(directory)


@dataclass(frozen=True)
class StageIdentity:
    binary_sha256: str
    version: str
    seed: int | None = None

    def __post_init__(self) -> None:
        for value in (self.binary_sha256, self.version):
            if len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value
            ):
                raise CacheError("Cache identities require SHA-256 values.")


@dataclass(frozen=True)
class StageCache:
    root: Path

    def materialize(
        self,
        stage: Literal["lift", "devset"],
        identity: StageIdentity,
        destination: Path,
        produce: Callable[[Path], object],
        *,
        recorded: Path | None = None,
    ) -> None:
        record = asdict(identity)
        directory = (
            self.root.resolve() / stage / identity.binary_sha256 / identity.version
        )
        if identity.seed is not None:
            directory /= str(identity.seed)
        with file_lock(directory.with_suffix(".lock")):
            if recorded is not None:
                data = read_entry(recorded.parent, recorded.name, record)
                if destination.exists():
                    if read_entry(destination.parent, destination.name, record) != data:
                        raise CacheError(
                            "The replay stage differs from its recorded artifact."
                        )
                    return
            elif destination.exists():
                read_entry(destination.parent, destination.name, record)
                return
            elif directory.exists():
                data = read_entry(directory, destination.name, record)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with TemporaryDirectory(
                    prefix=".stage-", dir=destination.parent
                ) as temporary:
                    output = Path(temporary) / destination.name
                    produce(output)
                    data = output.read_bytes()
                publish_entry(directory, destination.name, record, data)
            atomic_bytes(destination, data)
            atomic_bytes(
                destination.parent / "stage.json",
                json.dumps(
                    {"identity": record, "sha256": sha256(data).hexdigest()},
                    sort_keys=True,
                ).encode()
                + b"\n",
            )
