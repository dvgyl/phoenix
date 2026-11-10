# Export lifting evidence with pinned Ghidra

Use Ghidra 12.2 for M1. Its headless analyzer can inspect a stripped
binary without executing it. Its public Java API gives Phoenix the
decompiled text, p-code, addresses, symbols, and control-flow graph.
Keep the versioned export separate from generated C.

Use Temurin 25.0.5+8 on Apple Silicon. Ghidra 12.2 requires a Java 25
development kit. Keep both archives and installed tools on the external
drive. Verify the archive hashes in `tools.lock` before extraction.
Retain the upstream license files with the installed tools.

Use Gson 2.13.2 from the Ghidra archive to write JSON in the headless
script. The Ghidra archive pins this dependency. Gson uses the Apache
2.0 license. The repository includes the script and schema. The installed
tools retain the Ghidra and Gson license files.

The upstream archive has no macOS ARM64 decompiler. Build that
component with the upstream Makefile and the installed Xcode toolchain.
Run `scripts/build-ghidra-native` after you verify and extract the
archive. The script stages all build files on the external drive. The
first verified build used Xcode 27.2 (27B52) and Apple Clang 21.0.0.

The headless process may read only the binary and its analysis inputs.
Use public fixtures for development. Keep sealed source and held-out
cases outside the lifting process.
