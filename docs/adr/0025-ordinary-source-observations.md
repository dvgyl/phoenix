# Ordinary source observations and C token proof

The ordinary source companion records exporter observations. Its reader
checks binary and lift identity, the exact successful ordinary C source,
UTF-8 byte spans, operation references, block ownership, and record limits.
A declared marker role is a claim. The reader does not prove a C token.

Retain the exact immutable source bytes in `OrdinarySourceObservation`.
Use `SourceMarkerObservation` for its marker records. Reject source or
identity changes, malformed records, overlapping spans, and spans that
split UTF-8 characters. Keep wire schema 1 and existing public files.

The generation layer owns C syntax. It must parse the whole function
with the bounded flat C parser. It must compare the complete ordered
marker list with the parsed roles, values, and exact byte spans. Only
then can the switch validator use those links. A source hash alone
cannot establish token boundaries or control-flow correspondence.

Unsupported syntax gives a per-function gap. A complete parse with
conflicting markers gives a visible conflict. Invalid artifact identity
remains an artifact error. The original wire body and gap rules remain
unchanged. Do not attach a derived syntax gap to the original wire body.

The former adjacent ASCII check could accept partial tokens and text
inside comments or strings. Expanding its character set would retain
that defect. A separate general C lexer would duplicate the existing
bounded parser. The lower observation contract avoids both errors.
