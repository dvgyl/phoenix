# Use a separate normalized graph for checked switch evidence

Ghidra's normal decompiler output can replace a machine table address
expression with a selector. This happened in both public GCC and Clang
O2 fixtures. The normal lift remains the source of ordinary function
bodies and raw instruction evidence. Use a separate normalized graph
to recover the guarded table expression.

Bind the graph to the binary and ordinary lift digests. Retain normalized
block successors and operation identities separately from raw operations.
Require the graph's true edge to enter the dispatch and its false edge
to enter the default. Check that the original mask, compare and unsigned
branch bytes agree. Do not use printed instruction names to decide this.

The first profile admits a 32-bit masked selector, one unsigned bound,
and a signed 32-bit table entry added to its base. It admits at most 4,096
selectors. Require a read-only file-backed range and reject a relocation
that can reach it. Require every destination to be an exact instruction
owned by the dispatch function. Compare decoded destinations with the
lift proposals. Do not pair the proposed label and target arrays.

Preserve one case per selector. Two cases can share a target. Static cases
remain present even if development tests do not visit them. The result
does not establish that test coverage is complete.

This checkpoint only reads and checks evidence. The production graph
export and generation path must bind their artifacts separately. The
public runtime test must rebuild the checked switch in four compiler and
architecture configurations. A saved table or syntax check does not
satisfy that test.
