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
contain six register bit fields. Missing events, capture errors, and incomplete
frames export no local facts. A frame-only error rejects the whole tree and
can retain independent local snapshots. Questioned shared snapshots stay out.

Synthetic reducer controls pass. The final exact scope snapshot matches the
separate scope compiler. Independent source review, the raw boundary, and live
collector controls remain required. Eager-only transit is a declared limit.
Lazy resolver paths and nonreturn contracts remain unsupported. Do not change
an invocation to hide that limit. The agent-sealed corpus is unchanged.
