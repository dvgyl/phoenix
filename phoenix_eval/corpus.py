import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from phoenix_eval.case import Invocation
from phoenix_eval.toolchain import Compiler
from phoenix_eval.wire import decode_invocation
from phoenix_eval.worker import MAX_PROGRAM_BYTES

_NAME = re.compile(r"[a-z][a-z0-9-]{2,31}")
_HASH = re.compile(r"[0-9a-f]{64}")
_ARCHIVE_LIMIT = 64 * 1024 * 1024
_CASE_FILE_LIMIT = 8 * 1024 * 1024
_CASE_COUNT_LIMIT = 4096


class Tier(StrEnum):
    T0 = "T0"
    T1 = "T1"

    @property
    def flags(self) -> tuple[str, ...]:
        return ("-O0", "-O2") if self is Tier.T0 else ("-O0", "-O2", "-Os")

    @property
    def programs(self) -> int:
        return 10 if self is Tier.T0 else 15


class CorpusError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    compiler: Compiler
    flag: str
    sha256: str
    category: str

    @property
    def key(self) -> str:
        return f"{self.name}-{self.compiler}-{self.flag[1:]}"

    def executable(self, release: Path) -> Path:
        return release / self.name / self.compiler / f"{self.flag[1:]}.elf"


def _read_file(path: Path, limit: int) -> bytes:
    if path.resolve() != path or not path.is_file():
        raise CorpusError("The corpus file must be a regular file inside its release.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise CorpusError("The corpus file exceeds its size limit.")
    return data


def t0_manifest(release: Path) -> tuple[tuple[Variant, ...], str]:
    return release_manifest(release, Tier.T0)


def release_manifest(release: Path, tier: Tier) -> tuple[tuple[Variant, ...], str]:
    data = _read_file(release / "manifest.json", 64 * 1024)
    variants = manifest_variants(data, tier)
    for variant in variants:
        binary = _read_file(variant.executable(release), MAX_PROGRAM_BYTES)
        if hashlib.sha256(binary).hexdigest() != variant.sha256:
            raise CorpusError("A release binary does not match the manifest hash.")
    return variants, hashlib.sha256(data).hexdigest()


def manifest_variants(data: bytes, tier: Tier) -> tuple[Variant, ...]:
    count = tier.programs * len(Compiler) * len(tier.flags)
    try:
        entries = json.loads(data, object_pairs_hook=_unique_fields)
        if not isinstance(entries, list) or len(entries) != count:
            raise CorpusError(f"The {tier} manifest must have {count} variants.")
        variants = []
        for record in entries:
            if not isinstance(record, dict) or set(record) != {
                "name",
                "tier",
                "compiler",
                "flags",
                "sha256",
                "category",
            }:
                raise CorpusError(f"The {tier} manifest contains unexpected fields.")
            name = record["name"]
            flags = record["flags"]
            digest = record["sha256"]
            category = record["category"]
            compiler = record["compiler"]
            if (
                not _NAME.fullmatch(name)
                or record["tier"] != tier
                or compiler not in (Compiler.GCC, Compiler.CLANG)
                or flags not in ([flag] for flag in tier.flags)
                or not _HASH.fullmatch(digest)
                or not isinstance(category, str)
                or not 0 < len(category) <= 128
                or not category.isprintable()
            ):
                raise CorpusError(f"The {tier} manifest contains invalid metadata.")
            variants.append(
                Variant(name, Compiler(compiler), flags[0], digest, category)
            )
    except CorpusError:
        raise
    except (TypeError, UnicodeError, ValueError):
        raise CorpusError(f"The {tier} manifest is invalid.") from None
    expected = {
        (name, compiler, flag)
        for name in {variant.name for variant in variants}
        for compiler in Compiler
        for flag in tier.flags
    }
    if (
        len(expected) != count
        or {(variant.name, variant.compiler, variant.flag) for variant in variants}
        != expected
    ):
        raise CorpusError(
            f"The {tier} manifest does not contain every required variant."
        )
    return tuple(sorted(variants, key=lambda item: item.key))


def committed_hash(commitments: Path, filename: str) -> str:
    text = commitments.read_text(encoding="utf-8")
    matches = list(
        re.finditer(rf"(?m)^\| `{re.escape(filename)}` \| `([0-9a-f]{{64}})` \|$", text)
    )
    if len(matches) != 1:
        raise CorpusError("The archive has no unique hash commitment.")
    return matches[0].group(1)


def heldout_cases(
    archive: Path, digest: str, names: set[str], *, tier: Tier = Tier.T0
) -> dict[str, tuple[Invocation, ...]]:
    if not names or any(not _NAME.fullmatch(name) for name in names):
        raise CorpusError("The held-out archive requires valid program names.")
    data = _read_file(archive, _ARCHIVE_LIMIT)
    if hashlib.sha256(data).hexdigest() != digest:
        raise CorpusError("The held-out archive does not match its commitment.")
    prefix = tier.lower()
    expected = {f"{prefix}/cases/{name}.jsonl": name for name in names}
    cases = {}
    seen: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r|gz") as package:
            for member in package:
                if member.name in seen:
                    raise CorpusError("The held-out archive repeats a member.")
                seen.add(member.name)
                if member.isdir() and member.name in (prefix, f"{prefix}/cases"):
                    continue
                name = expected.get(member.name)
                if (
                    name is None
                    or name in cases
                    or not member.isfile()
                    or not 0 < member.size <= _CASE_FILE_LIMIT
                ):
                    raise CorpusError("The held-out archive contains an invalid entry.")
                stream = package.extractfile(member)
                if stream is None:
                    raise CorpusError("Cannot read a held-out archive entry.")
                with stream:
                    lines = stream.read().decode("ascii").splitlines()
                if not 0 < len(lines) <= _CASE_COUNT_LIMIT:
                    raise CorpusError("A held-out case set has an invalid size.")
                cases[name] = tuple(_case(line) for line in lines)
    except (OSError, EOFError, tarfile.TarError, UnicodeError, KeyError, ValueError):
        raise CorpusError("The held-out archive has an invalid case set.") from None
    if set(cases) != names:
        raise CorpusError("The held-out archive omits a required case set.")
    return cases


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("The case contains a repeated field.")
        result[key] = value
    return result


def _case(line: str) -> Invocation:
    data = json.loads(line, object_pairs_hook=_unique_fields)
    if not isinstance(data, dict) or set(data) != {
        "args",
        "stdin",
        "tree",
        "environment",
    }:
        raise ValueError("The case fields are invalid.")
    tree = data["tree"]
    if not isinstance(tree, dict) or set(tree) != {"mode", "entries"}:
        raise ValueError("The case tree fields are invalid.")
    if not isinstance(tree["entries"], list) or any(
        not isinstance(entry, dict) or set(entry) != {"path", "kind", "mode", "data"}
        for entry in tree["entries"]
    ):
        raise ValueError("The case entry fields are invalid.")
    return decode_invocation(line)
