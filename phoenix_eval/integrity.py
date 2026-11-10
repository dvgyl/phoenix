import hashlib
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from phoenix_eval.build import ProjectSnapshot, snapshot_project
from phoenix_eval.docker import docker_cli
from phoenix_eval.elf import elf_sections

_TEXT_WINDOW = 64
_MAX_TEXT = 512 * 1024
_EVIDENCE_LIMIT = 32 * 1024 * 1024
_HEX = re.compile(r"[a-f0-9]*")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED_C = re.compile(
    r"""/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' """, re.S | re.X
)
_TARGETS = {"amd64": "x86_64-linux-gnu", "arm64": "aarch64-linux-gnu"}
_ALLOWED_CALLS = frozenset(
    """
    abort abs access atexit atoi atol atoll bsearch calloc chdir chmod clearerr
    close closedir creat dup dup2 exit fchmod fclose fcntl fdopen feof ferror
    fflush fgetc fgetpos
    fgets fileno fopen fprintf fputc fputs fread free freopen fscanf fseek fseeko
    fsetpos fstat ftell ftello ftruncate fwrite getc getchar getenv getline
    getdelim getopt isalnum isalpha isascii isblank iscntrl isdigit isgraph
    islower isprint ispunct isspace isupper isxdigit labs llabs lseek lstat
    malloc memchr memcmp memcpy memmove memset mkdir open opendir perror printf
    putc putchar puts qsort read readdir realloc remove rename rewind rmdir scanf
    setbuf setvbuf snprintf sprintf sscanf stat strcat strchr strcmp strcpy
    strcspn strdup strerror strlen strncat strncmp strncpy strnlen strpbrk strrchr
    strspn strstr strtod strtof strtok strtok_r strtol strtold strtoll strtoul
    strtoull tolower toupper truncate umask ungetc unlink vfprintf vprintf
    vsnprintf vsprintf write __ctype_b_loc __ctype_tolower_loc __ctype_toupper_loc
    __assert_fail __errno_location __fprintf_chk __isoc99_fscanf __isoc99_scanf
    __isoc99_sscanf __printf_chk
    """.split()
)


@dataclass(frozen=True, slots=True)
class Storage:
    kind: str
    artifact: str
    offset: int
    data: bytes
    canonical_type: str
    origin: bytes | None = None


@dataclass(frozen=True, slots=True)
class Call:
    kind: str
    name: str


@dataclass(frozen=True, slots=True)
class FunctionShape:
    name: str
    branches: int
    loops: int
    switches: int


@dataclass(frozen=True, slots=True)
class CompilerEvidence:
    target: str
    version: str
    storage: tuple[Storage, ...]
    calls: tuple[Call, ...]
    functions: tuple[FunctionShape, ...] = ()


@dataclass(frozen=True, slots=True)
class BlobJustification:
    target: str
    artifact: str
    offset: int
    sha256: str
    size: int
    reason: str


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    passed: bool
    categories: dict[str, int]
    checked_storage_records: int
    checked_executables: int
    targets: tuple[str, ...]
    clang_versions: tuple[str, ...]
    justifications: tuple[BlobJustification, ...]


class IntegrityError(ValueError):
    def __init__(self, message: str, category: str = "incomplete_source_check") -> None:
        super().__init__(message)
        self.category = category


def original_shapes(data: bytes, *, raw: bool) -> tuple[FunctionShape, ...]:
    try:
        document = json.loads(data)
        functions = []
        for item in document["functions"]:
            name = item["ghidra_name" if raw else "name"]
            if not _IDENTIFIER.fullmatch(name):
                raise ValueError
            if raw and name == "main":
                name = "phoenix_raw_main"
            code = _QUOTED_C.sub(" ", item["raw_c"])
            functions.append(
                FunctionShape(
                    name,
                    len(re.findall(r"\bif\s*\(|\?|&&|\|\|", code)),
                    len(re.findall(r"\b(?:while|for)\s*\(|\bdo\s*\{", code)),
                    len(re.findall(r"\bswitch\s*\(", code)),
                )
            )
        if not functions:
            raise ValueError
        if raw:
            functions.append(FunctionShape("main", 0, 0, 0))
        return tuple(functions)
    except (OSError, KeyError, TypeError, ValueError, UnicodeError):
        raise IntegrityError(
            "The independent lift has no complete function evidence.",
            "incomplete_origin",
        ) from None


def _checker_category(raw: bytes) -> str:
    try:
        report = json.loads(raw)
        category = report["error"]["category"]
        if report["status"] == "unchecked" and re.fullmatch(r"[a-z_]{1,40}", category):
            return f"compiler_{category}"
    except (KeyError, TypeError, ValueError, UnicodeError):
        pass
    return "incomplete_source_check"


def compiler_evidence(
    raw: bytes, target: str, artifact: str, files: dict[str, bytes]
) -> CompilerEvidence:
    try:
        document = json.loads(raw)
        if (
            type(document["schema"]) is not int
            or document["schema"] != 1
            or document["policy"] != "m1-v1"
            or document["status"] != "complete"
            or document["target"] != target
            or document["translation_unit"] != artifact
            or "18.1.3" not in document["clang_version"]
            or type(document["record_count"]) is not int
            or len(document["records"]) != document["record_count"]
        ):
            raise IntegrityError("Clang source evidence is incomplete.")
        storage = []
        for item in document["records"]:
            kind = item["kind"]
            name = item["file"]
            offset = item["offset"]
            data = item["bytes_hex"]
            type_name = item.get("canonical_type", "")
            origin_hex = item.get("origin_hex")
            if (
                kind
                not in (
                    "literal",
                    "literal_storage",
                    "storage",
                    "constant_output",
                )
                or name not in files
                or not name.endswith((".c", ".h"))
                or type(offset) is not int
                or not 0 <= offset < len(files[name])
                or not isinstance(type_name, str)
                or not _HEX.fullmatch(data)
                or (origin_hex is not None and not _HEX.fullmatch(origin_hex))
            ):
                raise IntegrityError(
                    "Clang source evidence contains an invalid record."
                )
            origin = bytes.fromhex(origin_hex) if origin_hex is not None else None
            storage.append(
                Storage(kind, name, offset, bytes.fromhex(data), type_name, origin)
            )
        calls = []
        for item in document["calls"]:
            kind = item["kind"]
            name = item.get("name", "")
            if kind not in (
                "builtin",
                "external_linkage",
                "external_reference",
                "indirect",
                "project",
            ) or not isinstance(name, str):
                raise IntegrityError("Clang source evidence contains an invalid call.")
            calls.append(Call(kind, name))
        functions = []
        for item in document["functions"]:
            name = item["name"]
            counts = (item["branches"], item["loops"], item["switches"])
            if not _IDENTIFIER.fullmatch(name) or any(
                type(count) is not int or count < 0 for count in counts
            ):
                raise IntegrityError(
                    "Clang source evidence contains an invalid function."
                )
            functions.append(FunctionShape(name, *counts))
        return CompilerEvidence(
            target,
            str(document["clang_version"]),
            tuple(storage),
            tuple(calls),
            tuple(functions),
        )
    except (KeyError, TypeError, AttributeError, ValueError, UnicodeError):
        raise IntegrityError("Clang did not supply complete source evidence.") from None


def inspect_project(
    project: Path | ProjectSnapshot, images: dict[str, str]
) -> tuple[CompilerEvidence, ...]:
    snapshot = snapshot_project(project) if isinstance(project, Path) else project
    files = dict(snapshot.files)
    translation_units = tuple(name for name in files if name.endswith(".c"))
    if translation_units != ("src/program.c",):
        raise IntegrityError("The M1 checker requires one fixed C translation unit.")
    artifact = translation_units[0]
    payload = snapshot.archive
    evidence = []
    docker = docker_cli()
    for architecture, target in _TARGETS.items():
        image = images.get(architecture, "")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise IntegrityError("The source checker requires pinned image IDs.")
        name = f"phoenix-c-check-{uuid4().hex}"
        command = (
            *docker,
            "run",
            "--rm",
            "--interactive",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=32",
            "--memory=768m",
            "--memory-swap=768m",
            "--user=19704:19704",
            "--tmpfs=/work:rw,noexec,nosuid,nodev,size=64m,uid=19704,gid=19704,mode=0700",
            "--workdir=/work",
            "--env=TMPDIR=/work",
            "--env=HOME=/nonexistent",
            "--env=SOURCE_DATE_EPOCH=1794268800",
            "--entrypoint=/bin/sh",
            f"--platform=linux/{architecture}",
            f"--name={name}",
            image,
            "-ec",
            'tar -xf -; status=0; /opt/phoenix/bin/phoenix-c-integrity "$@" '
            f"> evidence.json 2> checker.log || status=$?; "
            f'head -c {_EVIDENCE_LIMIT + 1} evidence.json; exit "$status"',
            "check-source",
            "--project=/work/project",
            f"/work/project/{artifact}",
            "--",
            f"--target={target}",
            "-std=c11",
            "-pedantic-errors",
            "-Wall",
            "-Wextra",
            "-I/work/project/include",
        )
        try:
            result = subprocess.run(
                command, input=payload, capture_output=True, check=False, timeout=60
            )
        except subprocess.TimeoutExpired:
            subprocess.run(
                (*docker, "rm", "-f", name),
                capture_output=True,
                check=False,
                timeout=10,
            )
            raise IntegrityError(
                "The Clang source check exceeded its time limit."
            ) from None
        if len(result.stdout) > _EVIDENCE_LIMIT:
            raise IntegrityError("The Clang source check could not complete.")
        if result.returncode:
            raise IntegrityError(
                "The Clang source check could not complete.",
                _checker_category(result.stdout),
            )
        evidence.append(compiler_evidence(result.stdout, target, artifact, files))
    return tuple(evidence)


def _matches_text(windows: set[bytes], data: bytes) -> bool:
    return bool(windows) and any(
        data[index : index + _TEXT_WINDOW] in windows
        for index in range(len(data) - _TEXT_WINDOW + 1)
    )


def check_integrity(
    original: bytes,
    source: dict[str, bytes],
    executables: tuple[bytes, ...],
    evidence: tuple[CompilerEvidence, ...],
    dev_outputs: frozenset[bytes],
    origin: tuple[FunctionShape, ...],
) -> IntegrityReport:
    sections = elf_sections(original, ".text", ".rodata", ".data")
    text = sections.get(".text")
    if text is None or not 0 < len(text.data) <= _MAX_TEXT:
        raise IntegrityError(
            "The original text section exceeds the source check scope."
        )
    rodata = sections[".rodata"].data if ".rodata" in sections else b""
    data_sections = tuple(
        sections[name].data for name in (".rodata", ".data") if name in sections
    )
    windows = {
        text.data[index : index + _TEXT_WINDOW]
        for index in range(len(text.data) - _TEXT_WINDOW + 1)
    }
    categories: Counter[str] = Counter()
    if len(executables) != 4:
        categories["missing_build"] += 1
    targets = tuple(item.target for item in evidence)
    if set(targets) != set(_TARGETS.values()) or len(targets) != 2:
        categories["incomplete_source_check"] += 1
    for artifact in (*source.values(), *executables):
        if _matches_text(windows, artifact):
            categories["embedded_text"] += 1

    justifications = []
    expected = {function.name: function for function in origin}
    if not expected or len(expected) != len(origin):
        categories["incomplete_origin"] += 1
    for item in evidence:
        names = {function.name for function in item.functions}
        if names != set(expected) or len(names) != len(item.functions):
            categories["unproven_functions"] += 1
        else:
            for function in item.functions:
                prior = expected[function.name]
                if (
                    function.branches > prior.branches
                    or function.loops > prior.loops
                    or function.switches > prior.switches
                ):
                    categories["unproven_control_flow"] += 1
        for call in item.calls:
            if call.kind == "indirect":
                categories["unresolved_call"] += 1
            elif call.kind != "project" and call.name not in _ALLOWED_CALLS:
                categories["unapproved_call"] += 1
        for record in item.storage:
            payload = record.data
            if _matches_text(windows, payload):
                categories["embedded_text"] += 1
            if record.kind == "literal":
                if payload and not any(payload in section for section in data_sections):
                    categories["unproven_literal"] += 1
            if record.kind in ("literal", "constant_output"):
                if (
                    len(payload) > 32
                    and payload in dev_outputs
                    and (record.origin or payload) not in rodata
                ):
                    categories["memorized_output"] += 1
                continue
            table = record.kind == "storage" and "[" in record.canonical_type
            large = len(payload) > 4096
            if not (table or large):
                continue
            zeroes = not any(payload)
            in_original = any(payload in section for section in data_sections)
            if table and not (zeroes or in_original):
                categories["unproven_constant_table"] += 1
            if large:
                if not (zeroes or in_original):
                    categories["unjustified_blob"] += 1
                else:
                    justifications.append(
                        BlobJustification(
                            item.target,
                            record.artifact,
                            record.offset,
                            hashlib.sha256(payload).hexdigest(),
                            len(payload),
                            "The typed initializer contains only zero bytes."
                            if zeroes
                            else "The original data section contains these bytes.",
                        )
                    )
    return IntegrityReport(
        not categories,
        dict(categories),
        sum(len(item.storage) for item in evidence),
        len(executables),
        targets,
        tuple(item.version for item in evidence),
        tuple(justifications),
    )
