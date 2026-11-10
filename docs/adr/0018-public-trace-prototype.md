# ADR 0018. Public trace calibration with a separate observer

Date: 2026-11-10. Status: prototype only. Public calibration passed.
Additional runtime controls and independent review remain pending.

Phoenix needs ordered call observations before M2 analysis can use them.
Use a separate QEMU 9.2.0 arm64-host observer for public development cases.
Keep the accepted QEMU 8.2.2 and Rosetta oracle unchanged. Do not connect
this experiment to recovery, repair, evaluation, or pipeline entry points.

The wire shape is named `PhoenixPublicTraceV1`. Its specification is in
`experiments/m2_trace/FORMAT.md`. Define it before observer code. Use a
small fixed plan, ordered events, explicit gaps, and a checked footer.
A trace run must match the full agreed oracle outcome. A trace mismatch
rejects its evidence and keeps the case in oracle accounting.

Reuse QEMU 9.2.0 plugin API 4. The official archive is
https://download.qemu.org/qemu-9.2.0.tar.xz.
Its measured SHA-256 is
`f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894`.
The release tag commit is `ae35f033b874c627d81d51070187fbf55f0bf1a7`.
The archive plugin header SHA-256 is
`e4c5bf7e92075d7c1e6b1dcb6164bca6c549b2912a62b56ce1a777be4c7b8788`.
The primary release page, archive LICENSE, and header were checked.
The combined emulator is GPLv2. The header is GPL-2.0-or-later.
The original Phoenix plugin is GPL-2.0-or-later. No upstream plugin
implementation is copied. The MIT Python package does not link this code.
Retain attribution, COPYING, component notices, build instructions, and
corresponding source when distributing the observer. The recipe retains
the source archive and plugin source. Distributors must meet the applicable
GPL source-availability duties. A license check proves no runtime property.

Build only `x86_64-linux-user` on arm64. Use the pinned Ubuntu image,
snapshot packages, QEMU archive, and two build jobs. Use a separate tag.
Do not update worker or integrity tags. No Docker command or target
execution is permitted in this implementation task. The parent must check
image construction, instruction mechanisms, callback timing, PIE mapping,
sandbox compatibility, exact outcomes, controls, and three repetitions.

The fixture has two translation units, two stack nodes, an eight-byte
buffer, and runtime-selected increment or XOR operations. Freeze source
and case hashes before runtime tests. Preserve actual indirect calls at
O0 and O2 without LTO. Fail the static precondition if a compiler removes
them. This fixture is development-only and is never Phoenix-Bench.

The experiment supports call attempts, observed next-PC transfers,
planned returns, continuation register values, and bounded fread/fwrite
samples. Samples are observations. Type solving, allocation tracking,
localization, Ghidra schema changes, and production integration are deferred.
