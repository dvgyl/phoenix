import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from phoenix_eval import worker
from phoenix_eval.case import (
    GLIBC_TUNABLES,
    QEMU_CPU,
    Invocation,
    WorkerRuntime,
)
from phoenix_eval.docker import Engine, docker_args, docker_cli, run_cases
from phoenix_eval.outcome import Exited, Outcome


def test_case_cannot_override_oracle_pins() -> None:
    assert Invocation().environment()["GLIBC_TUNABLES"] == GLIBC_TUNABLES
    for name in ("GLIBC_TUNABLES", "QEMU_CPU"):
        with pytest.raises(ValueError, match="protected"):
            Invocation(overlay=((name, "override"),))
    case = Invocation(overlay=(("CASE_VALUE", "unchanged"),))
    assert case.environment()["CASE_VALUE"] == "unchanged"
    command = worker.worker_args(WorkerRuntime.QEMU, ())
    assert command[command.index("-cpu") + 1] == QEMU_CPU


@pytest.mark.parametrize("engine", tuple(Engine))
def test_container_restrictions_apply_to_each_mode(engine: Engine) -> None:
    command = docker_args(engine, "test")
    for option in (
        "--network=none",
        "--read-only",
        "--pids-limit=32",
        "--memory=1536m",
        "--memory-swap=1536m",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
    ):
        assert option in command
    assert "--privileged" not in command
    assert "--volume" not in command
    needs_proc = engine in (Engine.ROSETTA, Engine.TRUE_SOURCE_ARM64)
    assert ("--cap-add=SYS_ADMIN" in command) == needs_proc
    assert ("--security-opt=apparmor=unconfined" in command) == needs_proc
    assert (
        engine.runtime is WorkerRuntime.TRUE_SOURCE_ARM64
        if (engine is Engine.TRUE_SOURCE_ARM64)
        else engine.runtime is not WorkerRuntime.TRUE_SOURCE_ARM64
    )


@pytest.mark.parametrize("runtime", tuple(WorkerRuntime))
def test_sanitizer_options_are_fixed_only_for_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: WorkerRuntime
) -> None:
    monkeypatch.setattr(worker, "SCRATCH", tmp_path)
    case = Invocation(
        overlay=(
            ("ASAN_OPTIONS", "detect_leaks=1"),
            ("UBSAN_OPTIONS", "halt_on_error=0"),
        )
    )

    def launch(
        command: tuple[str, ...], *, env: dict[str, str], **_: object
    ) -> MagicMock:
        assert command[1] == runtime
        assert env["GLIBC_TUNABLES"] == GLIBC_TUNABLES
        if runtime is WorkerRuntime.TRUE_SOURCE_ARM64:
            assert env["ASAN_OPTIONS"] == "detect_leaks=0:halt_on_error=1:symbolize=0"
            assert env["UBSAN_OPTIONS"] == "halt_on_error=1:print_stacktrace=0"
        else:
            assert env == case.environment()
        result = MagicMock()
        result.__enter__.return_value.wait.return_value = 0
        return result

    monkeypatch.setattr(subprocess, "Popen", launch)
    with (tmp_path / "io").open("w+b") as stream:
        assert (
            worker._launch(tmp_path, case, runtime, stream, stream, stream, False) == 0
        )


# Set the prefix after building both images with scripts/build-worker.
IMAGE_PREFIX = os.environ.get("PHOENIX_VALIDATION_IMAGE_PREFIX")
container_test = pytest.mark.skipif(
    IMAGE_PREFIX is None,
    reason="Set PHOENIX_VALIDATION_IMAGE_PREFIX for container tests.",
)
CANONICAL_FLAGS = (
    "-std=c11",
    "-O2",
    "-Wall",
    "-Wextra",
    "-ffp-contract=off",
    "-fno-strict-aliasing",
    "-fwrapv",
    "-fsigned-char",
    "-fstack-protector-all",
    "-Wl,-z,relro,-z,now",
)


def compile_fixture(source: str, compiler: str, platform: str, sanitize: bool) -> bytes:
    flags = (*CANONICAL_FLAGS, *(("-fsanitize=address,undefined",) if sanitize else ()))
    result = subprocess.run(
        (
            *docker_cli(),
            "run",
            "--rm",
            "-i",
            "--pull=never",
            "--platform",
            f"linux/{platform}",
            "--network=none",
            "--read-only",
            "--pids-limit=32",
            "--memory=1536m",
            "--memory-swap=1536m",
            "--tmpfs",
            "/work:rw,exec,nosuid,nodev,size=64m",
            "--workdir",
            "/work",
            "--env",
            "TMPDIR=/work",
            "--entrypoint",
            "/bin/sh",
            f"{IMAGE_PREFIX}-worker:{platform}",
            "-ec",
            f"{compiler} -x c {' '.join(flags)} -o program - -lm -ldl; cat program",
        ),
        input=source.encode(),
        capture_output=True,
        check=True,
        timeout=60,
    )
    assert result.stdout.startswith(b"\x7fELF")
    return result.stdout


@container_test
@pytest.mark.parametrize("compiler", ("gcc", "clang"))
@pytest.mark.parametrize("defect", ("valid", "address", "undefined"))
def test_arm64_sanitizers_report_source_defects(compiler: str, defect: str) -> None:
    source = r"""
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    (void)argv;
    volatile int divisor = argc - 1;
    volatile int index = argc + 4;
    volatile int *values = calloc(2, sizeof(int));
    if (!values) return 2;
    BODY
    free((void *)values);
    puts("valid");
    return 0;
}
""".replace(
        "BODY",
        {
            "valid": "values[1] = divisor + index;",
            "address": "free((void *)values); values[0] = 1; return 0;",
            "undefined": 'printf("%d\\n", 1 / divisor);',
        }[defect],
    )
    binary = compile_fixture(source, compiler, "arm64", True)
    case = Invocation(
        overlay=(
            ("ASAN_OPTIONS", "halt_on_error=0"),
            ("UBSAN_OPTIONS", "halt_on_error=0"),
        )
    )
    results = run_cases(
        binary,
        (case,) * 3,
        Engine.TRUE_SOURCE_ARM64,
        image=f"{IMAGE_PREFIX}-worker:arm64",
    )
    for result in results:
        assert isinstance(result, Outcome), result
        if defect == "valid":
            assert result.termination == Exited(0)
            assert result.stdout == b"valid\n"
            assert result.stderr == b""
        else:
            assert result.termination != Exited(0)
            diagnostic = (
                b"AddressSanitizer: heap-use-after-free"
                if defect == "address"
                else b"runtime error: division by zero"
            )
            assert diagnostic in result.stderr, result


@container_test
@pytest.mark.parametrize("engine", tuple(Engine))
def test_linux_launcher_restrictions(engine: Engine) -> None:
    if engine is Engine.AMD64:
        native = subprocess.run(
            (*docker_cli(), "info", "--format", "{{.Architecture}}"),
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()
        if native not in ("x86_64", "amd64"):
            pytest.skip("The direct AMD64 mode requires an AMD64 Docker daemon.")
    source = r"""
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
int main(void) {
    struct rlimit as, cpu, file, core;
    getrlimit(RLIMIT_AS, &as);
    getrlimit(RLIMIT_CPU, &cpu);
    getrlimit(RLIMIT_FSIZE, &file);
    getrlimit(RLIMIT_CORE, &core);
    int failures = 0;
    int validation = VALIDATION;
    if (!validation && (as.rlim_cur != 1073741824 ||
                        as.rlim_max != 1073741824)) failures++;
    if (cpu.rlim_cur != 5 || cpu.rlim_max != 6) failures++;
    if (file.rlim_cur != 67108864 || file.rlim_max != 67108864) failures++;
    if (core.rlim_cur != 0 || core.rlim_max != 0) failures++;
    if (getuid() != 19704 || getgid() != 19704) failures++;
    if (fork() != -1 || errno != EPERM) return 20;
    if (setsid() != -1 || errno != EPERM) failures++;
    if (unshare(CLONE_NEWUSER) != -1 || errno != EPERM) failures++;
    if (open("/opt/phoenix/tools.lock", O_RDONLY) != -1) failures++;
    if (open("/etc/passwd", O_RDONLY) != -1) failures++;
    if (open("/proc/1/root/etc/passwd", O_RDONLY) != -1) failures++;
    if (open("/escape", O_WRONLY | O_CREAT, 0600) != -1) failures++;
    int fd = open("case-file", O_WRONLY | O_CREAT, 0600);
    if (fd < 0 || write(fd, "ok", 2) != 2) failures++;
    if (fd >= 0) close(fd);
    void *reservation = mmap(0, 2147483648ULL, PROT_NONE,
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if ((reservation != MAP_FAILED) != validation) failures++;
    if (reservation != MAP_FAILED) munmap(reservation, 2147483648ULL);
    printf("%d\n", failures);
    return failures != 0;
}
""".replace("VALIDATION", "1" if engine is Engine.TRUE_SOURCE_ARM64 else "0")
    platform = (
        "arm64"
        if engine.platform == "arm64" and engine is not Engine.QEMU_X86_64
        else "amd64"
    )
    binary = compile_fixture(source, "gcc", platform, False)
    (result,) = run_cases(
        binary,
        (Invocation(),),
        engine,
        image=f"{IMAGE_PREFIX}-worker:{engine.platform}",
    )
    assert isinstance(result, Outcome), result
    assert result.termination == Exited(0), result
    assert result.stdout == b"0\n", result
    assert result.tree.entries[0].path == "case-file"


@container_test
def test_x86_runners_select_the_same_glibc_functions() -> None:
    symbols = subprocess.run(
        (
            *docker_cli(),
            "run",
            "--rm",
            "--pull=never",
            "--platform",
            "linux/amd64",
            "--network=none",
            "--read-only",
            "--entrypoint",
            "/usr/bin/readelf",
            f"{IMAGE_PREFIX}-worker:amd64",
            "--dyn-syms",
            "--wide",
            "/usr/lib/x86_64-linux-gnu/libc.so.6",
            "/usr/lib/x86_64-linux-gnu/libm.so.6",
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    names = tuple(
        sorted(
            {
                line.split()[7].replace("@@", "@")
                for line in symbols.splitlines()
                if len(line.split()) >= 8
                and line.split()[3] == "IFUNC"
                and line.split()[7].split("@")[0]
                not in {"time", "gettimeofday", "__gettimeofday"}
            }
        )
    )
    assert len(names) >= 50
    source = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
    void *math = dlopen("libm.so.6", RTLD_NOW | RTLD_GLOBAL);
    if (!math) return 2;
    for (int i = 1; i < argc; i++) {
        char *version = strchr(argv[i], '@');
        if (!version) return 4;
        *version++ = '\0';
        void *function = dlvsym(RTLD_DEFAULT, argv[i], version);
        Dl_info info;
        if (!function || !dladdr(function, &info)) return 3;
        printf("%s %lx\n", argv[i],
               (unsigned long)((uintptr_t)function - (uintptr_t)info.dli_fbase));
    }
    return 0;
}
"""
    binary = compile_fixture(source, "gcc", "amd64", False)
    outputs = []
    for engine in (Engine.ROSETTA, Engine.QEMU_X86_64):
        results = run_cases(
            binary,
            (Invocation(args=names),) * 3,
            engine,
            image=f"{IMAGE_PREFIX}-worker:{engine.platform}",
        )
        for result in results:
            assert isinstance(result, Outcome), result
            assert result.termination == Exited(0), result
            assert result.stderr == b""
            assert len(result.stdout.splitlines()) == len(names)
            outputs.append(result.stdout)
    assert all(output == outputs[0] for output in outputs)


@pytest.mark.parametrize("runtime", tuple(WorkerRuntime))
def test_worker_selects_a_separate_validation_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: WorkerRuntime
) -> None:
    monkeypatch.setattr(worker, "SCRATCH", tmp_path)
    monkeypatch.setattr(worker, "TARGET_UID", os.getuid())
    monkeypatch.setattr(worker, "TARGET_GID", os.getgid())
    roots = {
        "NATIVE_RUNTIME": "ordinary",
        "QEMU_RUNTIME": "qemu",
        "VALIDATION_RUNTIME": "validation",
    }
    for attribute, marker in roots.items():
        directory = tmp_path / marker
        directory.mkdir()
        (directory / "marker").write_text(marker)
        monkeypatch.setattr(worker, attribute, directory)

    def launch(root: Path, *_: object) -> int:
        expected = (
            "validation"
            if runtime is WorkerRuntime.TRUE_SOURCE_ARM64
            else "qemu"
            if runtime is WorkerRuntime.QEMU
            else "ordinary"
        )
        assert (root / "marker").read_text() == expected
        return 0

    monkeypatch.setattr(worker, "_launch", launch)
    assert isinstance(worker.run_case(b"fixture", Invocation(), runtime), Outcome)


@pytest.mark.parametrize("engine", (Engine.ARM64, Engine.TRUE_SOURCE_ARM64))
def test_sanitizer_mode_does_not_enable_tracing(engine: Engine) -> None:
    with pytest.raises(ValueError, match="QEMU"):
        run_cases(b"fixture", (Invocation(),), engine, trace=True)
