# Public switch control

This public source forces a masked switch with a shared state variable.
The case manifest fixes 56 verification cases. Its development subset
omits selector 11. The checked reconstruction must retain that selector.

The reconstruction caller receives only the compiled binary and its
Ghidra evidence. The control uses a fixed cleanup response for the ordinary
main function. The checked emitter supplies the switch definition.
This control does not measure language-model reconstruction quality.

Run `scripts/check-m2-public U2 --run-id <id>` from the repository after
its source is committed and reviewed. Source the workspace environment.
Set `PHOENIX_VM_LEASE=public-u2` only when the private Corpus Author has
released the Linux VM. The command rejects a closed lease before any
external command. It requires current pinned worker and integrity images.

For GCC and Clang originals, the driver calls the actual reconstruction
pipeline with `checked_switches=True`. It verifies the development cases,
replays the fixed response, compares the exact source archive, and runs
all 56 public cases on all four compiler and architecture combinations.
Both oracle engines must agree. No case can be excluded from this gate.

The driver also replaces the protected function with a constant-zero body.
It retains the package metadata. The source contract must reject this copy.
All four builds must compile and show only the expected stdout difference
on the three selector-11 cases. A compiler error does not pass this control.

Artifacts are under `$PHOENIX_ROOT/audit/public-gates/<id>`. The preflight
records the source, cases, tool identities, runtime, commit, and image IDs.
An incomplete report has `complete=false` and `passed=false`. Failed work
remains available for inspection. Use a fresh run ID for each attempt.
This command uses no live model. Its zero model usage is a software-control
property. It is not a reconstruction cost result or a held-out result.

The source check proves byte retention. It does not prove that the compiler
uses those bytes. For example, an inactive definition can retain them.
The positive and negative behavior checks must both pass to establish the
complete control result. Keep both checks mandatory.
