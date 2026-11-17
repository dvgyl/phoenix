import re
import tarfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from phoenix_eval.docker import Engine
from phoenix_eval.jobs import limited
from phoenix_eval.toolchain import SOURCE_TOOL_OPTIONS, Compiler, ToolTimeout, run_tool

_SOURCE_LIMIT = 4 * 1024 * 1024
_EXECUTABLE_LIMIT = 16 * 1024 * 1024
PROJECT_CMAKE = """cmake_minimum_required(VERSION 3.22)
project(phoenix_rebuild LANGUAGES C)
add_executable(program src/program.c)
target_include_directories(program PRIVATE include)
target_compile_definitions(program PRIVATE _POSIX_C_SOURCE=200809L)
target_compile_options(program PRIVATE -Wall -Wextra -O2 -fstack-protector-all)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(program PRIVATE LINKER:-z,relro,-z,now)
endif()
set_target_properties(program PROPERTIES
    C_STANDARD 11 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
"""
_BUILD_SCRIPT = f"""
tar -xf -
status=0
{{
    cmake -S project -B build -DCMAKE_C_COMPILER="$1" -DCMAKE_C_STANDARD=11 \
        -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_C_EXTENSIONS=OFF \
        '-DCMAKE_C_FLAGS=-Wall -Wextra' &&
    cmake --build build --parallel 2
}} >build.log 2>&1 || status=$?
if [ "$(wc -c <build.log)" -gt 1048576 ]; then
    printf '%s\\n' 'The build log exceeds its size limit.' >&2
    exit 1
fi
cat build.log >&2
[ "$status" -eq 0 ]
head -c {_EXECUTABLE_LIMIT + 1} build/program
"""


@dataclass(frozen=True)
class BuildResult:
    engine: Engine
    compiler: Compiler
    executable: Path | None
    warnings: int
    diagnostics: str


@dataclass(frozen=True)
class ProjectSnapshot:
    files: tuple[tuple[str, bytes], ...]
    archive: bytes


def project_files(project: Path) -> dict[str, bytes]:
    source = project / "src"
    include = project / "include"
    if not source.is_dir() or source.is_symlink():
        raise ValueError("The project needs a regular source directory.")
    if include.is_symlink() or (include.exists() and not include.is_dir()):
        raise ValueError("The header path must be a regular directory.")
    sources = sorted(source.glob("*.c"))
    if not sources:
        raise ValueError("The project needs at least one C source file.")
    files = [project / "CMakeLists.txt", *sources, *sorted(include.glob("*.h"))]
    contents = {}
    remaining = _SOURCE_LIMIT
    for file in files:
        if file.is_symlink() or not file.is_file():
            raise ValueError("Project inputs must be regular files.")
        with file.open("rb") as stream:
            data = stream.read(remaining + 1)
        remaining -= len(data)
        if remaining < 0:
            raise ValueError("The source archive exceeds the build limit.")
        contents[file.relative_to(project).as_posix()] = data
    return contents


def snapshot_project(project: Path) -> ProjectSnapshot:
    files = tuple(project_files(project).items())
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, data in files:
            entry = tarfile.TarInfo(f"project/{name}")
            entry.size = len(data)
            entry.mode = 0o644
            entry.mtime = 1794268800
            archive.addfile(entry, BytesIO(data))
    return ProjectSnapshot(files, output.getvalue())


def project_archive(project: Path | ProjectSnapshot) -> bytes:
    snapshot = snapshot_project(project) if isinstance(project, Path) else project
    return snapshot.archive


@limited("compile")
def build_project(
    project: Path | ProjectSnapshot,
    destination: Path,
    engine: Engine,
    compiler: Compiler,
    *,
    image: str | None = None,
) -> BuildResult:
    if engine is Engine.QEMU_X86_64:
        raise ValueError("Use a compiler image to build the program.")
    payload = project_archive(project)
    try:
        finished = run_tool(
            engine.platform,
            image or f"phoenix-worker:{engine.platform}",
            _BUILD_SCRIPT,
            "build-project",
            compiler,
            options=(
                *SOURCE_TOOL_OPTIONS,
                "--pids-limit=64",
                "--memory=1536m",
                "--memory-swap=1536m",
                "--tmpfs=/work:rw,exec,nosuid,nodev,size=256m,uid=19704,gid=19704,mode=0700",
            ),
            input=payload,
            timeout=180,
            check=False,
            timeout_error=ToolTimeout(),
        )
    except ToolTimeout:
        return BuildResult(
            engine, compiler, None, 0, "The build exceeded its time limit."
        )
    diagnostics = finished.stderr.decode("utf-8", errors="replace")
    warnings = len(re.findall(r"(?m)^.*?\bwarning:", diagnostics))
    program = finished.stdout
    machine = 62 if engine.platform == "amd64" else 183
    if (
        finished.returncode
        or not 20 <= len(program) <= _EXECUTABLE_LIMIT
        or not program.startswith(b"\x7fELF\x02\x01")
        or int.from_bytes(program[18:20], "little") != machine
    ):
        return BuildResult(
            engine,
            compiler,
            None,
            warnings,
            diagnostics or "The build did not emit a valid ELF.",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as scratch:
        temporary = Path(scratch) / "program"
        temporary.write_bytes(program)
        temporary.chmod(0o600)
        temporary.replace(destination)
    return BuildResult(engine, compiler, destination, warnings, diagnostics)
