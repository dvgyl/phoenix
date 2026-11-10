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
| libseccomp | Restrict Linux system calls in the test process | [libseccomp](https://github.com/seccomp/libseccomp) |
| QEMU user mode | Independent execution of x86-64 programs | [QEMU](https://www.qemu.org/docs/master/user/main.html) |
| Bubblewrap | Design comparison for per-test isolation | [Bubblewrap](https://github.com/containers/bubblewrap) |
