from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from phoenix.generate import Candidate
from phoenix.verify import Verification
from phoenix_eval.build import ProjectSnapshot
from phoenix_eval.integrity import IntegrityReport


class Method(StrEnum):
    PHOENIX = "phoenix"
    GHIDRA_RAW = "ghidra-raw"


@dataclass(frozen=True, slots=True)
class Settings:
    images: dict[str, str]
    seed: int
    ghidra: Path
    java_home: Path
    repair_limit: int
    strongest_repair: bool
    checker_images: dict[str, str]
    method: Method = Method.PHOENIX
    cache_root: Path | None = None
    stage_versions: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.repair_limit <= 20:
            raise ValueError("Use a repair limit from 0 to 20.")


@dataclass(frozen=True, slots=True)
class Reconstruction:
    project: Path
    development_passed: bool


@dataclass(frozen=True, slots=True)
class Trial:
    candidate: Candidate
    project: ProjectSnapshot
    verification: Verification
    integrity: IntegrityReport | None

    @property
    def passed(self) -> bool:
        return (
            self.verification.passed
            and self.integrity is not None
            and self.integrity.passed
        )


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    run_id: str
    replayed: bool
    wall_seconds: float
