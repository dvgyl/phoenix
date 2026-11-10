# Measure recovered x86-64 block entries

Use a QEMU Tiny Code Generator plugin to mark each executed x86-64
instruction address in the original program. The plugin records the
start address of the loaded executable segment. Subtract the difference
between that address and the first executable segment address in the
ELF file. QEMU's entry address can refer to the dynamic loader, so
the collector uses the segment address.

Use GNU Binutils to recover a static inventory of block entries in
`.text`. Use function entries from unwind records when present. Add
direct branch targets and instruction addresses that follow transfers
of control. Treat this as a recovered inventory. Its coverage is
separate from source branch coverage and from QEMU translation-block
coverage.

Run the original with and without the plugin. Require identical
behavior before using the trace. Keep cases that add a new recovered
block to the development set. Generate a seeded mutation for each
selected case. Keep a mutation only if the two emulators agree and the
mutation adds coverage. Keep the full public case set for the mutation
check.

Build the plugin against the pinned QEMU plugin header. The plugin
source uses the header's GPL-2.0-or-later license. The repository
contains no copy of the QEMU header or binary.

The Ubuntu QEMU executable reports that it does not support the plugin
option. Build the official QEMU 8.2.2 source release with plugin support.
Check the source archive hash before the image build uses it. Use the
same QEMU executable for traced and untraced runs.

Build QEMU with Meson, Ninja, pkgconf, and the GLib development package
from the pinned Ubuntu snapshot. Meson and Ninja support the upstream
build. pkgconf resolves the installed GLib package. The Ubuntu package
license files apply to these dependencies. Keep their source links in
the notices file.
