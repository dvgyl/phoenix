# Prior art and dependencies

Phoenix measures whole-program behavior and portability within the
limits in [SPEC.md](../SPEC.md). The list below records the upstream
projects used in the workspace and the local quality checks.

| Project | Use in Phoenix | Upstream source |
| --- | --- | --- |
| Colima and Lima | Linux VM on macOS | [Colima](https://github.com/abiosoft/colima), [Lima](https://github.com/lima-vm/lima) |
| Docker CLI | Run isolated Linux containers | [Docker CLI](https://github.com/docker/cli) |
| Rosetta 2 | Independent x86-64 execution on Apple Silicon | [Apple Virtualization](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Python and uv | Orchestration and locked Python environments | [CPython](https://github.com/python/cpython), [uv](https://github.com/astral-sh/uv) |
| Ruff and mypy | Formatting, lint, and static type checks | [Ruff](https://github.com/astral-sh/ruff), [mypy](https://github.com/python/mypy) |
| pytest, Hypothesis, and pytest-cov | Test execution, generated test cases, and Python line coverage | [pytest](https://github.com/pytest-dev/pytest), [Hypothesis](https://github.com/HypothesisWorks/hypothesis), [pytest-cov](https://github.com/pytest-dev/pytest-cov) |
| pre-commit | Run the quality checks before a commit | [pre-commit](https://github.com/pre-commit/pre-commit) |

| Project | Use in Phoenix | Upstream source |
| --- | --- | --- |
| Ubuntu 24.04 | Pinned Linux image and package archive | [Ubuntu images](https://github.com/docker-library/official-images/blob/master/library/ubuntu), [Ubuntu Snapshot Service](https://snapshot.ubuntu.com/) |
| Docker Engine and Buildx | Isolated workers and architecture-specific images | [Moby](https://github.com/moby/moby), [Buildx](https://github.com/docker/buildx) |
| GCC, Clang, CMake, and GNU Binutils | Build and strip public test executables | [GCC](https://gcc.gnu.org/), [Clang](https://clang.llvm.org/), [CMake](https://cmake.org/), [GNU Binutils](https://www.gnu.org/software/binutils/) |
| Linux seccomp | Restrict system calls in the test process | [Linux kernel documentation](https://kernel.org/doc/html/latest/userspace-api/seccomp_filter.html) |
| QEMU user mode | Independent execution of x86-64 programs | [QEMU](https://www.qemu.org/docs/master/user/main.html) |
| Bubblewrap | Design comparison for per-test isolation | [Bubblewrap](https://github.com/containers/bubblewrap) |
| GitHub Actions and Astral setup-uv | Native CI and public report comparison | [Checkout](https://github.com/actions/checkout), [Artifact upload](https://github.com/actions/upload-artifact), [Artifact download](https://github.com/actions/download-artifact), [Setup uv](https://github.com/astral-sh/setup-uv) |
| QEMU TCG plugin interface | Observe original instruction execution | [QEMU 8.2 plugin API](https://qemu.readthedocs.io/en/v8.2.10/devel/tcg-plugins.html) |
| Meson, Ninja, pkgconf, and GLib | Build the pinned QEMU release | [Meson](https://github.com/mesonbuild/meson), [Ninja](https://github.com/ninja-build/ninja), [pkgconf](https://github.com/pkgconf/pkgconf), [GLib](https://github.com/GNOME/glib) |
| Ghidra 12.2 | Export program evidence and decompiled C | [Release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build), [headless analyzer guide](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.2_build/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md) |
| Temurin 25.0.5+8 | Run the pinned Ghidra release | [Official release](https://github.com/adoptium/temurin25-binaries/releases/tag/jdk-25.0.5%2B8) |
| Codex CLI and OpenAI Responses API | Standard-tier reconstruction and repair requests | [Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode), [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) |
| ELF specification | Validate file structure and dynamic linkage | [Section headers](https://gabi.xinuos.com/v42/elf/03-sheader.html), [dynamic linking](https://gabi.xinuos.com/v42/elf/08-dynamic.html) |
