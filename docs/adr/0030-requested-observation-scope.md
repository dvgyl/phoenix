# Requested observation scope

The frame collector needs a bounded activation window. Full-program startup
includes callbacks and loader activity that the first frame profile cannot
admit. Keep the full static trace plan unchanged. Compile a separate scope
certificate for one requested main activation.

The certificate records every site disposition and original gap. It binds
exact user instruction bytes, same-owner local branch destinations, and
proved import transit routes. Unsupported active paths have rejecting guards.
An omitted path stays unsupported during active capture. Selection does not
prove that a complete execution can satisfy the certificate.

The first policy is `main-window-six-v1`. It captures RAX, RDI, RSI, RDX,
RCX, and RSP. These are six registers, including four argument registers.
Its import transit profile supports eager resolution only. Lazy resolution
and all nonreturn contracts remain unsupported. Do not change an invocation
to make a saved public fixture satisfy this profile.

Rebuild the certificate from the binary and checked lift at capture admission.
A supplied dataclass or digest cannot authenticate runtime capture. The
collector must check instruction guards, root entry, closure, limits, and
full outcome equality. Frame admission and live calibration are separate gates.

The supplied Astra design defines the algorithm. Static scope tests and all
16 saved public E1 comparisons pass. No target ran. Independent source review
and live capture remain required. The agent-sealed corpus is unchanged.

The first independent review held the implementation at `2cfce37`.
The correction requires exact proof field types and uses reconstructed proof
values for certificate output. It also rejects XBEGIN encodings and reported
incoming indirect callers from other proved owners. A reported target is
conservative selection evidence. It does not prove an executed destination.
The original HOLD and failing controls remain in the audit record.

The second independent review held `b42a7a2`. Four XABORT controls still
received Ordinary with empty raw p-code. Both fixes assumed that no match
in a finite control blacklist proved ordinary flow. That premise is false.
The direct control probe also found acceptance of unknown raw operation names.

Ordinary now needs positive evidence. Empty raw p-code is accepted only for
the nine exact NOP forms in the existing import proof, or exact ENDBR64 at
the proved owner entry. The compiler reuses the shared byte constants.
It does not change the shared proof or strip prefixes to find a match.
Nonempty raw p-code needs known core data operations with the documented
input count and output presence. Neutral bytes permit only identity COPY
operations. Unknown operation names, wrong input counts, and wrong output
presence reject. Analysis-only, pseudo, and conflicting neutral operations
also reject. Every ordinary guard still needs an exact same-owner
successor. All earlier transfer, branch, gap, and ownership checks remain.

The byte blacklist is an additional rejection rule. It includes XABORT and
XBEGIN, but is not a complete ISA classifier. Ordinary flow through core
raw operations remains conditional on a complete, faithful raw translation.
The compiler cannot prove that translation from nonempty p-code alone.
It does not repair missing operations or independently decode ordinary bytes.
The pinned lift, instruction-size checks, next-PC checks, and live gates
remain necessary. A static certificate does not authenticate a capture.

This contract explicitly removes empty-evidence support for other forms.
The original empty MOV and XOR positives now reject. Separate positive
controls supply valid raw data operations. The unchanged reviewer controls
and their exact mismatches remain in the audit record. This is a deliberate
capability restriction. No transaction-state precondition exists at root
entry. XABORT can transfer to an earlier transaction's fallback address.
Rejecting XBEGIN inside the window does not establish an inactive transaction.

The primary definitions are in the
[Intel instruction manual](https://cdrdv2-public.intel.com/671110/325383-sdm-vol-2abcd.pdf),
NOP page 4-169, ENDBR64 page 3-345, XABORT page 6-17, and XBEGIN page 6-25.
The [raw p-code reference](https://ghidra.re/ghidra_docs/languages/html/pcoderef.html)
and [core operations](https://ghidra.re/ghidra_docs/languages/html/pcodedescription.html)
define the bounded data-operation path.
[Pseudo operations](https://ghidra.re/ghidra_docs/languages/html/pseudo-ops.html)
do not supply that evidence.

The parent's revised frame rule also remains required. Every rejected
capture exports no local facts. Successful trees retain raw observations.
This static correction changes no frame or boundary API. Independent review,
production live gates, and recovery integration remain open.
