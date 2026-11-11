# First observation plan

The observer must admit the same site as a function entry, a previous
call's continuation, and a transfer when the original listing proves
those roles. The static adapter already holds witness bytes and a
checked address conversion. Keep it independent from observation and
the evaluator.

A single kind per site would lose a role at a shared address. Use one
site per ELF address with independent entry and continuation fields.
The transfer field has one of four kinds. Only a call has a continuation
and optional verified import identity. Represent missing or contradictory
roles as explicit gaps. Never turn a runtime target list into a static
closure.

The plan builder takes the binary bytes, typed lift, and address proof.
It checks the binary and derives imports at the same boundary. It
retains the six calibrated register names and widths, original
instruction witness, static scope, and capture limits. Its canonical
JSON is the input identity for future observer wire records. No runtime
claim follows from a plan. The accepted Rosetta and QEMU oracles remain
unchanged.

Host gate: build a plan from each saved public compiler lift. Confirm
shared roles, call continuation bytes, function scope, and supported
import identity. Reject mismatched binary and proof. Test an incomplete
continuation and a contradictory transfer kind. Live capture, runtime
mapping, trace admission, and return evidence belong to subsequent
units. Do not execute a target in this unit.

The initial profile requires a call and its continuation to have the
same function owner. Keep a different owner as a gap. A planned call
can share its address with an entry. A continuation can share its
address with a return. These role combinations do not prove frames.

Keep import gaps separate from physical call roles. Verify supported
original call and thunk operands before attaching an import identity.
An unknown import does not erase a witnessed call. A contradictory
raw transfer count prevents use of that transfer.
