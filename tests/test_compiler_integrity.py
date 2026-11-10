import io
import json
import os
import subprocess
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

ARCHITECTURES = os.environ.get("PHOENIX_COMPILER_INTEGRITY_ARCHES", "")
TARGETS = {"amd64": "x86_64-linux-gnu", "arm64": "aarch64-linux-gnu"}
FLAGS = ("-std=c11", "-pedantic-errors", "-Wall", "-Wextra", "-I/snapshot/include")

pytestmark = pytest.mark.skipif(
    not ARCHITECTURES,
    reason="Set PHOENIX_COMPILER_INTEGRITY_ARCHES to run Docker checks.",
)


@pytest.fixture(params=ARCHITECTURES.split(","))
def arch(request: pytest.FixtureRequest) -> str:
    architecture = str(request.param)
    assert architecture in TARGETS
    return architecture


@contextmanager
def staged_snapshot(arch: str, snapshot: Path, image: str) -> Iterator[str]:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for child in sorted(snapshot.iterdir()):
            tar.add(child, arcname=child.name)
    volume = (
        subprocess.check_output(["docker", "volume", "create"], timeout=10)
        .decode()
        .strip()
    )
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--pull=never",
                f"--platform=linux/{arch}",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--user=0:0",
                f"--mount=type=volume,src={volume},dst=/snapshot",
                "--entrypoint=/bin/tar",
                image,
                "--no-same-owner",
                "--no-same-permissions",
                "-xf",
                "-",
                "-C",
                "/snapshot",
            ],
            input=archive.getvalue(),
            capture_output=True,
            check=True,
            timeout=30,
        )
        yield volume
    finally:
        subprocess.run(
            ["docker", "volume", "rm", volume],
            check=True,
            capture_output=True,
            timeout=10,
        )


def docker(
    arch: str, snapshot: Path, image: str, entrypoint: str, *args: str
) -> subprocess.CompletedProcess[bytes]:
    with staged_snapshot(arch, snapshot, image) as volume:
        return subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--pull=never",
                f"--platform=linux/{arch}",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit=64",
                "--memory=1536m",
                "--memory-swap=1536m",
                "--user=19704:19704",
                "--tmpfs=/work:rw,noexec,nosuid,nodev,size=32m,mode=1777",
                f"--mount=type=volume,src={volume},dst=/snapshot,readonly",
                "--env=TMPDIR=/work",
                "--env=HOME=/nonexistent",
                "--env=SOURCE_DATE_EPOCH=1794268800",
                f"--entrypoint={entrypoint}",
                image,
                *args,
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )


def checker(
    arch: str, snapshot: Path, *extra: str
) -> subprocess.CompletedProcess[bytes]:
    return docker(
        arch,
        snapshot,
        f"phoenix-c-integrity:{arch}",
        "/opt/phoenix/bin/phoenix-c-integrity",
        "--project=/snapshot",
        "/snapshot/case.c",
        "--",
        f"--target={TARGETS[arch]}",
        *FLAGS,
        *extra,
    )


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    tmp_path.chmod(0o755)
    (tmp_path / "include").mkdir()
    return tmp_path


def nums(values: list[int] | range) -> str:
    return ",".join(map(str, values))


def octal(values: range) -> str:
    return '"' + "".join(f"\\{value:03o}" for value in values) + '"'


def compiler_sections(arch: str, snapshot: Path) -> dict[str, bytes]:
    # Emit unused declarations so their bytes are available in the object file.
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format={{.Id}}", f"phoenix-worker:{arch}"],
        text=True,
        timeout=10,
    ).strip()
    result = docker(
        arch,
        snapshot,
        image,
        "/bin/sh",
        "-ec",
        r"""
        clang-18 "$@" -O0 -femit-all-decls -fdata-sections \
            -c /snapshot/case.c -o /work/case.o
        objdump -h /work/case.o |
            awk '$2 ~ /^\.(data|rodata)\./ { print $2 }' |
            while read -r section; do
                objcopy --dump-section "$section=/work/section" \
                    /work/case.o /work/copy.o
                printf '%s ' "$section"
                od -An -v -tx1 /work/section | tr -d ' \n'
                printf '\n'
            done
        """,
        "sh",
        f"--target={TARGETS[arch]}",
        *FLAGS,
    )
    assert result.returncode == 0, result.stderr.decode()
    return {
        name: bytes.fromhex(data)
        for name, data in (
            line.split(" ", 1) for line in result.stdout.decode().splitlines()
        )
    }


def test_compiler_storage_and_literals(arch: str, snapshot: Path) -> None:
    header = b"static const unsigned char header_value[] = {9, 0, 8};\n"
    (snapshot / "include" / "generated.h").write_bytes(header)
    values = range(128, 192)
    short = octal(range(128, 191))
    length_32 = "k" * 32
    length_33 = "m" * 33
    source = f"""
#include <stdint.h>
#include <inttypes.h>
#include "generated.h"
typedef unsigned char byte;
typedef byte byte_alias;
typedef char text_byte;
enum {{ first = 3 }};
_Static_assert(first == 3, "static assertion text");
static const byte_alias unused[2][32] = {{
    {{{nums(values[:32])}}}, {{{nums(values[32:])}}}
}};
unsigned char rows[2][3000] = {{{{42}},{{43}}}};
uint_least8_t least[] = {{{nums([value + 256 for value in values])}}};
uint_fast8_t fast[] = {{{nums([value + 256 for value in values])}}};
unsigned char wrapped[] = {{{nums([value + 256 for value in values])}}};
unsigned int wide[] = {{{nums(values)}}};
unsigned char separate_left[] = {{{nums(values[:32])}}};
unsigned char separate_right[] = {{{nums(values[32:])}}};
char payload_32[] = "{length_32}";
char payload_33[] = "{length_33}";
char padded_string[5000] = "a";
char padded_numeric[5000] = {{97}};
signed char from_char[] = {{'\\377'}};
signed char from_int[] = {{-1}};
text_byte exact[63] = {short};
char plus_null[64] = {short};
char inferred[] = {short};
char longer[65] = {short};
char translated[] = "A??/n" "B\\
C";
char utf8[] = u8"λ";
char embedded_null[] = "a\\0b";
const char blank[] = "";
unsigned int elided[3][4] = {{1,2,3,4,[2][3]=first}};
unsigned char designated[5][3] = {{[4] = {{[2] = (unsigned char)260}}}};
uint64_t integer = {{ UINT64_C(0x0102030405060708) }};
_Bool truth = 17;
int char_extension = (char)255;
char format[] = "%" PRId64;
char nested_strings[3][4] = {{"ab", [2] = "c"}};
char braced_fixed[5] = {{"abc"}};
char braced_inferred[] = {{"ab"}};
char braced_rows[2][4] = {{{{"a"}}, {{"bc"}}}};
static const unsigned char at_limit[4096] = {{1}};
static const unsigned char above_limit[4097] = {{2}};
extern void read_local(const unsigned char *);
extern void report(const char *);
static void uncalled(int n) {{
    const unsigned char local[] = {{5, 0, 7, 8, 1, 2, 3, 4}};
    int runtime = n + 3;
    read_local(local);
    if (runtime)
        report("Status: the requested " "file is available.\\n");
}}
""".encode()
    (snapshot / "case.c").write_bytes(source)
    result = checker(arch, snapshot)
    assert result.returncode == 0, (result.stdout.decode(), result.stderr.decode())
    report = json.loads(result.stdout)
    assert report["status"] == "complete"
    assert report["schema"] == 1
    assert report["policy"] == "m1-v1"
    assert report["translation_unit"] == "case.c"
    assert report["target"] == TARGETS[arch]
    assert "18.1.3" in report["clang_version"]
    records = report["records"]
    assert report["record_count"] == len(records)
    storage = {
        item["declaration"]: item for item in records if item["kind"] == "storage"
    }
    sections = compiler_sections(arch, snapshot)
    expected_objects = {
        "header_value",
        "unused",
        "rows",
        "least",
        "fast",
        "wrapped",
        "wide",
        "separate_left",
        "separate_right",
        "payload_32",
        "payload_33",
        "char_extension",
        "padded_string",
        "padded_numeric",
        "from_char",
        "from_int",
        "exact",
        "plus_null",
        "inferred",
        "longer",
        "translated",
        "utf8",
        "embedded_null",
        "blank",
        "elided",
        "designated",
        "integer",
        "truth",
        "format",
        "nested_strings",
        "braced_fixed",
        "braced_inferred",
        "braced_rows",
        "at_limit",
        "above_limit",
        "local",
    }
    assert storage.keys() == expected_objects
    for name in sorted(expected_objects):
        suffix = ".cst8" if name == "local" else "." + name
        matching = [
            data for section, data in sections.items() if section.endswith(suffix)
        ]
        assert len(matching) == 1, (name, sections.keys())
        assert bytes.fromhex(storage[name]["bytes_hex"]) == matching[0], name

    assert storage["header_value"]["file"] == "include/generated.h"
    assert storage["header_value"]["offset"] == header.index(b"header_value")
    assert storage["unused"]["offset"] == source.index(b"unused")
    assert storage["exact"]["bytes_hex"] == bytes(values[:-1]).hex()
    assert storage["inferred"]["bytes_hex"] == bytes(values[:-1]).hex() + "00"
    assert (
        storage["padded_string"]["bytes_hex"] == storage["padded_numeric"]["bytes_hex"]
    )
    assert storage["from_char"]["bytes_hex"] == storage["from_int"]["bytes_hex"] == "ff"
    assert bytes(values) not in bytes.fromhex(storage["wide"]["bytes_hex"])
    assert storage["separate_left"]["bytes_hex"] == bytes(values[:32]).hex()
    assert storage["separate_right"]["bytes_hex"] == bytes(values[32:]).hex()
    assert storage["char_extension"]["bytes_hex"] == (
        "ffffffff" if arch == "amd64" else "ff000000"
    )

    literals = {item["offset"]: item for item in records if item["kind"] == "literal"}
    assert bytes.fromhex(literals[source.index(b'"A??/')]["bytes_hex"]) == b"A\nBC"
    assert bytes.fromhex(literals[source.index(b'"a\\0b"')]["bytes_hex"]) == b"a\0b"
    assert literals[source.index(b'"static assertion text"')]["bytes_hex"] == (
        b"static assertion text".hex()
    )
    for payload in (length_32, length_33):
        offset = source.index(f'"{payload}"'.encode())
        assert literals[offset]["bytes_hex"] == payload.encode().hex()
    format_literal = literals[source.index(b'"%"')]
    assert format_literal["tokens"][0]["spelling"]["scope"] == "project"
    assert format_literal["tokens"][1]["spelling"]["scope"] == "system"
    assert format_literal["tokens"][1]["expansion"]["offset"] == source.index(b"PRId64")
    literal_storage = [item for item in records if item["kind"] == "literal_storage"]
    assert len(literal_storage) == 1
    message = b"Status: the requested file is available.\n\0"
    assert literal_storage[0]["bytes_hex"] == message.hex()
    assert any(message in data for name, data in sections.items() if ".str" in name)
    assert {item["name"] for item in report["calls"]} == {"report", "read_local"}


@pytest.mark.parametrize(
    ("source", "category"),
    [
        (
            '#define GAP\nchar a[] = "Status: the requested "'
            ' GAP "file is available.\\n";',
            "unsupported_preprocessing",
        ),
        ("#if 0\nchar a[5000];\n#endif\n", "unsupported_preprocessing"),
        ('#line 7 "spoofed.c"\nchar a[] = "literal";\n', "unsupported_preprocessing"),
        ("#pragma once\nint a = 1;\n", "unsupported_preprocessing"),
        ('#include "/etc/os-release"\n', "unapproved_file"),
        ("int broken = ;\n", "compiler_error"),
        ('#include <stddef.h>\nwchar_t a[] = L"wide";\n', "unsupported_string"),
        ('const char *a = "relocation";\n', "unsupported_storage"),
        ("struct S { int n; }; struct S a = {7};\n", "unsupported_storage"),
        ("int a = 1; void f(int n) { int b[n]; }\n", "unsupported_type"),
        ("void f(int n) { int a[] = {n}; }\n", "unresolved_initializer"),
        ('void f(void) { __asm__("nop"); }\n', "unsupported_assembly"),
        ("int f(void) { return *(int *)0x4000; }\n", "hardcoded_address"),
        ("unsigned char oversized[8388609] = {1};\n", "limit"),
    ],
)
def test_incomplete_source(
    arch: str, snapshot: Path, source: str, category: str
) -> None:
    (snapshot / "case.c").write_text(source + "\n")
    result = checker(arch, snapshot)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "unchecked"
    assert report["error"]["category"] == category, result.stderr.decode()
    assert "records" not in report


def test_rejects_extra_compiler_arguments(arch: str, snapshot: Path) -> None:
    (snapshot / "case.c").write_text("int a;\n")
    result = checker(arch, snapshot, "-include", "/etc/os-release")
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["category"] == "arguments"


def test_implicit_static_zero(arch: str, snapshot: Path) -> None:
    (snapshot / "case.c").write_text(
        "extern int repeated; int repeated; int repeated; extern int other;\n"
        "int inferred[];\n"
        "void f(void) { static unsigned char local_zero[2]; }\n"
    )
    result = checker(arch, snapshot)
    assert result.returncode == 0, (result.stdout.decode(), result.stderr.decode())
    report = json.loads(result.stdout)
    assert report["record_count"] == 3
    assert {item["declaration"]: item["bytes_hex"] for item in report["records"]} == {
        "repeated": "00000000",
        "inferred": "00000000",
        "local_zero": "0000",
    }


def test_include_cannot_escape_via_symlink(arch: str, snapshot: Path) -> None:
    (snapshot / "include" / "alias.h").symlink_to("/usr/include/stdint.h")
    (snapshot / "case.c").write_text('#include "alias.h"\n')
    result = checker(arch, snapshot)
    assert result.returncode == 1, (result.stdout.decode(), result.stderr.decode())
    assert json.loads(result.stdout)["error"]["category"] == "unapproved_file"


def test_accepts_runtime_values_and_reports_direct_calls(
    arch: str, snapshot: Path
) -> None:
    (snapshot / "case.c").write_text(
        "#include <stdio.h>\n#include <stdlib.h>\n"
        "int length(const char *text) { return atoi(text); }\n"
        "int main(void) {\n"
        '    const char *value = getenv("PUBLIC_TEST");\n'
        '    const char *fallback = "0";\n'
        "    const int count = length(value != NULL ? value : fallback);\n"
        "    return count;\n"
        "}\n"
    )
    result = checker(arch, snapshot)
    assert result.returncode == 0, (result.stdout.decode(), result.stderr.decode())
    report = json.loads(result.stdout)
    assert any(
        item["kind"] == "project" and item["name"] == "length"
        for item in report["calls"]
    )
    assert {
        item["bytes_hex"] for item in report["records"] if item["kind"] == "literal"
    } == {
        b"PUBLIC_TEST".hex(),
        b"0".hex(),
    }


def test_records_library_added_bytes_and_external_function_references(
    arch: str, snapshot: Path
) -> None:
    text = "This public output has a library-added newline."
    (snapshot / "case.c").write_text(
        "#include <stdio.h>\n#include <stdlib.h>\n"
        'int apply(int (*fn)(const char *)) { return fn("example"); }\n'
        f'int main(void) {{ if (0) apply(system); return puts("{text}"); }}\n'
    )
    result = checker(arch, snapshot)
    assert result.returncode == 0, (result.stdout.decode(), result.stderr.decode())
    report = json.loads(result.stdout)
    (output,) = [
        item for item in report["records"] if item["kind"] == "constant_output"
    ]
    assert bytes.fromhex(output["bytes_hex"]) == (text + "\n").encode()
    assert bytes.fromhex(output["origin_hex"]) == text.encode()
    assert any(
        item["kind"] == "external_reference" and item["name"] == "system"
        for item in report["calls"]
    )
