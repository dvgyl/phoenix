# Prove transfer kinds from original bytes

An original byte witness proves file and address identity. It does not
prove the instruction kind reported by p-code. A branch described as a
copy can also make a later thunk instruction unreachable.

Use one shared bounded byte classifier for physical calls, jumps, and
near returns. Check the complete instruction length and the selected
ModRM and SIB forms. Preserve supported prefixes and operand bits.
Unsupported encodings remain explicit gaps.

Each public recovery operation reconstructs and compares the complete
address proof before it derives import bindings or observation roles.
A caller-supplied typed binding cannot bypass this check.

A physical call with an unresolved import can retain its call evidence.
A wrong opcode cannot retain a call role or continuation origin. Calls
need a same-owner witness at the exact decoded continuation. Entry,
continuation, and transfer roles remain separate.

An import path must start at the exact thunk entry. Permit only the
listed neutral byte sequences before its terminal jump. Check every
hop, slot operand, relocation, symbol identity, and path bound. A static
symbol request does not identify the runtime library provider.

The combined integration retains the relocation write widths required
by the switch proof. The physical transfer correction and the width
metadata have separate checks. Their combined focused suite passes.

This static profile does not prove executed call frames, runtime
targets, ABI types, or behavior. Live capture and semantic trace
admission remain separate work. Conditional branches and halts outside
the profile remain visible plan gaps.
