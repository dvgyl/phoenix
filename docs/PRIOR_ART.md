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
