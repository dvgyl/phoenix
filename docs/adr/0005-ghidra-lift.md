# Export lifting evidence with pinned Ghidra

Use Ghidra 12.2 for M1. Its headless analyzer can inspect a stripped
binary without executing it. Its public Java API gives Phoenix the
decompiled text, p-code, addresses, symbols, and control-flow graph.
Keep the versioned export separate from generated C.

Use Temurin 25.0.5+8 on Apple Silicon. Ghidra 12.2 requires a Java 25
development kit. Keep both archives and installed tools on the external
drive. Verify the archive hashes in `tools.lock` before extraction.
Retain the upstream license files with the installed tools.

The headless process may read only the binary and its analysis inputs.
Use public fixtures for development. Keep sealed source and held-out
cases outside the lifting process.
