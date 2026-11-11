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

## Optional graph publication

Switch graphs require the mapping companion. Export the graphs in a
separate post-script within the same read-only analysis. Limit export
to 32 functions, 4 MiB per graph and 16 MiB total graph data. Record
unsupported normalized graphs as gaps. The manifest binds the binary
and lift digests to each graph digest and function address.

A switch-enabled generation uses commit schema 2. The commit binds the
switch manifest as well as the lift and mapping. The reader verifies
all three before exposing a generation. The mapping-only profile still
writes commit schema 1. A malformed switch bundle cannot select a new
generation. An exported graph is a proposal, not a checked dispatch.

The exporter limits each operation to 256 inputs, as the reader does.
A schema 1 directory cannot contain switch evidence. Each switch
file must have one link. Reject the new generation if either
publication check fails.
