# Public test programs

These programs have source code in the repository. They test the Phoenix
harness and are separate from Phoenix-Bench.

- `bitstats` reads binary stdin and reports a byte count or sum. Its
  mutations change stdout, stderr, exit codes, or environment handling.
- `filemarks` reads a file and writes a new directory and file. Its
  mutations change paths, bytes, permissions, or file retention.
- `runprobe` tests process isolation and failure reporting.
