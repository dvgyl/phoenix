# Measure recovered x86-64 block entries

Use a QEMU Tiny Code Generator plugin to mark each executed x86-64
instruction address in the original program. The plugin records the
loaded entry address. Subtract the difference between the loaded entry
address and the ELF entry address to get file addresses.

Use GNU Binutils to recover a static inventory of block entries in
`.text`. Use function entries from unwind records when present. Add
direct branch targets and instruction addresses that follow transfers
of control. Treat this as a recovered inventory. Its coverage is
separate from source branch coverage and from QEMU translation-block
coverage.

Run the original with and without the plugin. Require identical
behavior before using the trace. Keep cases that add a new recovered
block to the development set. Keep the full public case set for the
mutation check.

Build the plugin against the pinned QEMU plugin header. The plugin
source uses the header's GPL-2.0-or-later license. The repository
contains no copy of the QEMU header or binary.

The Ubuntu QEMU executable reports that it does not support the plugin
option. Build the official QEMU 8.2.2 source release with plugin support.
Check the source archive hash before the image build uses it. Use the
same QEMU executable for traced and untraced runs.
