# 0014. Bind development evidence to the delivered project

## Decision

Keep the tested source snapshot. Copy its exact bytes to the package.
Check the copied snapshot after writing separate reports.
The report records source and executable SHA-256 identities.

Each generated function keeps its `PHOENIX-UNVERIFIED` comment. The comment
states that tests were pending at generation. It directs the reader to the
report for final confidence. Passing cases determine the report's function
confidence. A failed case cannot give a function passing coverage.

## Designs considered

1. Preserve the tested snapshot and write reports separately. Source bytes
   stay fixed. This also preserves `__LINE__`. Comments record generation
   status, so the report must state final confidence.
2. Render final confidence comments and then verify that snapshot. Removing
   a comment can change `__LINE__`. A failed final test can change passing
   coverage and require different comments. Repeating this process might
   never stop. A bounded fallback would need immutable comments and another
   test, so it adds states without improving the selected design.

The first design removes this cycle. Each repair produces one snapshot.
Builds, verification, integrity checks, and the selected package use that
snapshot. Repair uses the existing round and cost limits. Resume derives
feedback from current observations. Replay uses the same rendering rules.

## Checkpoint contract

Store build observations. Derive differences with the existing mismatch
function. Bind ordered development inputs and expected
outcomes, including traces, with SHA-256. Require exactly the four expected
architecture/compiler configurations. A successful build needs one result
per case and matching executable bytes. A failed build needs no results or
executable identity. Missing or inconsistent evidence stops resume.

Checkpoint reuse requires the saved development identity and matching
source and executable identities. Inconsistent records stop resume. A
local actor with complete write access can replace records and hashes.
