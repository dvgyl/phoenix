# Check C storage with compiler evidence

Use the pinned Clang frontend to check generated C before optimization.
The compiler resolves type aliases, literal concatenation, conversions,
and array bounds. The checker can examine declarations that the linker
would remove. Keep the separate byte scan of all four executables.

Start with a restricted set of initializers. Report an incomplete check
when the frontend cannot explain the stored bytes. Keep decoded literal
payloads separate from stored bytes. For example, an array can contain
padding beyond the end of its string literal. Bind any large blob
justification to the source and storage hashes.

Use Clang 18.1.3 and the corresponding LLVM development libraries from
the pinned Ubuntu snapshot. The libraries use the same license terms as
the Clang toolchain already in the repository notices. Run the checker
in a Linux container without the original ELF or evaluation inputs.

Keep the generated build configuration under evaluator control. The
source check and all builds must use the same project files. A byte
scan cannot establish the absence of a loader, emulator, or output
lookup table. Apply separate controls before using the integrity result
to score a binary.

Require original data evidence for nonzero initialized arrays, including
short arrays. Check literal data passed directly to output and buffer
copy functions. Record the newline that `puts` adds. Keep the source
literal separate so the evaluator can check its original data evidence.

Check external function references as well as direct calls. Require the
same function set and bound the source branch, loop, and switch counts
with a separate Ghidra lift. These bounds allow type cleanup and some
control flow changes. They can reject a valid rewrite that introduces
additional source control structure. The checks cover the stated source
facts. Held-out tests provide the behavior evidence.

Keep the original and project archive as fixed bytes throughout each
evaluation. Check the built executable hash again before its byte scan.
Freeze and validate the development invocations before the evaluator
opens the held-out archive. Both x86-64 engines must reproduce their
saved original outcomes.
