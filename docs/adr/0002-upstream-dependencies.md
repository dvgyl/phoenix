# Use upstream tools as separate dependencies

Use Colima, Lima, and the Docker CLI for the Linux VM. These tools support
an external VM disk and an AArch64 guest with Rosetta. Use the versions
already present on this host.

Use Python 3.12 and uv for the local environment. Use Ruff, mypy, pytest,
Hypothesis, pytest-cov, and pre-commit for the local quality checks. These
tools provide formatting, type checks, property tests, coverage, and
repeatable hooks. Use the lock file for package versions and hashes.

Use pinned upstream packages and keep their license files with installed
copies. The Phoenix checkout contains its own code and documentation.
The notices file lists the upstream projects and licenses. If a later
change copies or modifies upstream code, review that change separately
before it enters the public repository.
