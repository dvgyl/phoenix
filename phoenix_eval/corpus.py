import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
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
    data = _read_file(release / "manifest.json", 64 * 1024)
    try:
        entries = json.loads(data)
        if not isinstance(entries, list) or len(entries) != 40:
            raise CorpusError("The T0 manifest must have 40 variants.")
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
                raise CorpusError("The T0 manifest contains unexpected fields.")
            name = record["name"]
            flags = record["flags"]
            digest = record["sha256"]
            category = record["category"]
            compiler = record["compiler"]
            if (
                not _NAME.fullmatch(name)
                or record["tier"] != "T0"
                or compiler not in (Compiler.GCC, Compiler.CLANG)
                or flags not in (["-O0"], ["-O2"])
                or not _HASH.fullmatch(digest)
                or not isinstance(category, str)
                or not 0 < len(category) <= 128
                or not category.isprintable()
            ):
                raise CorpusError("The T0 manifest contains invalid metadata.")
            variants.append(
                Variant(name, Compiler(compiler), flags[0], digest, category)
            )
    except (TypeError, UnicodeError, json.JSONDecodeError):
        raise CorpusError("The T0 manifest is invalid.") from None
    expected = {
        (name, compiler, flag)
        for name in {variant.name for variant in variants}
        for compiler in Compiler
        for flag in ("-O0", "-O2")
    }
    if (
        len(expected) != 40
        or {(variant.name, variant.compiler, variant.flag) for variant in variants}
        != expected
    ):
        raise CorpusError("The T0 manifest does not contain every required variant.")
    for variant in variants:
        binary = _read_file(variant.executable(release), MAX_PROGRAM_BYTES)
        if hashlib.sha256(binary).hexdigest() != variant.sha256:
            raise CorpusError("A release binary does not match the manifest hash.")
    ordered = tuple(sorted(variants, key=lambda item: item.key))
    return ordered, hashlib.sha256(data).hexdigest()


def committed_hash(commitments: Path, filename: str) -> str:
    text = commitments.read_text(encoding="utf-8")
    matches = list(
        re.finditer(rf"(?m)^\| `{re.escape(filename)}` \| `([0-9a-f]{{64}})` \|$", text)
    )
    if len(matches) != 1:
        raise CorpusError("The archive has no unique hash commitment.")
    return matches[0].group(1)


def heldout_cases(
    archive: Path, digest: str, names: set[str]
) -> dict[str, tuple[Invocation, ...]]:
    if not names or any(not _NAME.fullmatch(name) for name in names):
        raise CorpusError("The held-out archive requires valid program names.")
    data = _read_file(archive, _ARCHIVE_LIMIT)
    if hashlib.sha256(data).hexdigest() != digest:
        raise CorpusError("The held-out archive does not match its commitment.")
    expected = {f"t0/cases/{name}.jsonl": name for name in names}
    cases = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r|gz") as package:
            for member in package:
                if member.isdir() and member.name in ("t0", "t0/cases"):
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
                cases[name] = tuple(decode_invocation(line) for line in lines)
    except (OSError, EOFError, tarfile.TarError, UnicodeError, KeyError, ValueError):
        raise CorpusError("The held-out archive has an invalid case set.") from None
    if set(cases) != names:
        raise CorpusError("The held-out archive omits a required case set.")
    return cases
