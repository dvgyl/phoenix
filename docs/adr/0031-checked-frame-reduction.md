# Checked frame reduction

Use the required Astra algorithm to reduce a checked capture into one bounded
call tree. Process transfer confirmation, continuation, entry, and the current
transfer in that order. Use one stack. Give each activation a new frame ID.
Never search older frames to repair a contradictory continuation.

Call entry must preserve the five captured registers other than RSP.
The entry RSP must equal the pre-call RSP minus eight. A C3 return must use
its own entry RSP and the top call continuation. The matching continuation
must restore the pre-call RSP and preserve the returned RAX bits.

Root entry requires an independent stack-word read and an external predecessor.
Root return requires that saved target and a transfer confirmation. It does
not prove the process exit code. Full outcome association belongs to the
exact-byte admission boundary.

The immutable input is private. Typed receipt records do not authenticate saved
bytes. The parent must parse and bind the raw wire, runtime manifest, receipt,
canonical scope, root addresses, and accepted full outcome before construction.
This unit adds no public adapter or runtime collector.

An admitted tree has no provider or ABI type claim. Raw local observations
contain six register bit fields. Local observations require complete frame
admission. Every rejected capture exports an empty local tuple from both
`admit_frames` and `local_registers`. Questioned shared snapshots stay out.

The Astra correction task explicitly revises the original retention contract.
Local retention after a frame-only error is now unsupported. Independent review
found two errors in that earlier contract's implementation. Structural transit
errors shared the `transit` code with unsupported destinations. An early semantic
error also stopped reduction before later structural errors. The shared-value
scan did not prove that required roles and frames were complete.

The correction preserves the first rejection. It makes no completeness claim
after a semantic error. Only the existing reducer's successful closure authorizes
local facts. A separate structural reducer would duplicate the grammar and need
rules for continuation after disputed control evidence. This correction removes
the incomplete retention scan and adds no second frame algorithm.

`Rejected.local` retains its field position and narrows to `tuple[()]`.
Successful captures retain the six raw fields from `Entry`, `CallAttempt`, and
`Continuation`, with their exact provenance. Return-attempt values remain outside
the local API. This change does not alter tree admission or authenticate capture.
The original design and review records remain unchanged in the external audit.
The revised contract and permanent controls are recorded in
`audit/m2-frame-retention-correction-astra/` under the workspace root.

Synthetic reducer controls pass. The final exact scope snapshot matches the
separate scope compiler. Independent source review, the raw boundary, and live
collector controls remain required. Eager-only transit is a declared limit.
Lazy resolver paths and nonreturn contracts remain unsupported. Do not change
an invocation to hide that limit. The agent-sealed corpus is unchanged.
