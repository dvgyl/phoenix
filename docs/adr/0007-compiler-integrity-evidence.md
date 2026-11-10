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
