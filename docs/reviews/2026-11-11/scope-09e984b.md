The owner requires verified Phoenix completion through SPEC.md section 9. This review checks one static prerequisite. Corpus sealing remains in force.

**PASS for the explicit, stricter static scope contract at `09e984b8608743d87ce9b323a9f6a4a2fad9785b`.** No new defect was found within that contract. This verdict depends on complete, faithful raw translation and checked instruction starts. It does not establish independent machine instruction semantics. It gives no target execution, runtime capture, frame admission, recovery, or milestone approval. SPEC.md section 9 remains incomplete.

The branch is `agent/m2-observation-scope`. The checkout was clean before and after review. All 13 recorded repository file hashes match their exact HEAD objects and remain unchanged. These include the source, tests, ADR0030, eight policy dependencies, and both instruction files. [before.json](before.json), [after.json](after.json), and [verify_state.py](verify_state.py) retain the checks. Local `main` and `origin/main` both point to `3939fbc0d928d7701b289d559835bb466497a69c`. Neither local ref has `phoenix/observe/scope.py`. No remote fetch ran.

The complete static block is `f0c61f2..HEAD`. Its three reviewed paths are `scope.py`, `test_observe_scope.py`, and ADR0030. The focused correction is `b42a7a2..HEAD`. [full.patch](full.patch) and [correction.patch](correction.patch) preserve those exact diffs. Their SHA-256 values are `05f234cc1ddf0ce9875feded0c316541716a23e4583e35694a37b4647c650e42` and `6541a55874e9180fbdc7ad43e0d002f47f6754146fbfdd84ae64b4532aedbb80`. The complete branch also changes `docs/STATUS.md` and `docs/LOG.md`. Their session history was excluded from this review.

The evidence supports the following results. Counts describe synthetic controls and public static comparisons. They are not Phoenix success measurements or `phoenix-eval` results.

| Check | Actual result | Child command exit |
| --- | --- | --- |
| Original independent suite, unchanged | 177 passed. Two withdrawn positives failed. | 1 |
| Prior fresh independent suite, unchanged | 517 passed. One withdrawn positive failed. | 1 |
| Original supported subset | 177 passed. Two deselected. | 0 |
| Prior fresh supported subset | 517 passed. One deselected. | 0 |
| Expanded scope, U1, plan, transfer, and wire tests | 898 passed. | 0 |
| New independent suite | 713 passed. The final run also passed 713. | 0 |
| Exact saved defect inputs | All nine have the required corrected outcomes. | 0 |
| Saved public reconstruction | 16 exact plans. 16 certificates match except for policy identity. | 0 |
| Official operation tables and policy identity | All 55 accepted operation shapes match. | 0 |
| Ruff lint, format check, strict mypy, and diff check | All passed. | 0 each |
| Audit input identities and final source state | All matched. The checkout remained clean. | 0 each |

The unchanged broad suites are still red. Their failures are intentional restrictions under the new contract. They must not be reported as all passing. [original.log](original.log) and [fresh.log](fresh.log) preserve the exact assertion differences.

| Original assertion | Old expected guard | Current guard |
| --- | --- | --- |
| `test_ordinary_bytes_have_exact_successor[4889c0]` | `Ordinary(264)` with empty raw translation. | `Reject("missing_ordinary_evidence")` |
| `test_ordinary_bytes_have_exact_successor[31c0]` | `Ordinary(263)` with empty raw translation. | `Reject("missing_ordinary_evidence")` |
| `test_c6_mov_is_ordinary` | `Ordinary(264)` with empty raw translation. | `Reject("missing_ordinary_evidence")` |

The supported subset commands exclude only those named assertions. The old reviewer files were not edited. A small [pytest plugin](audit_plugin.py) redirects the prior fresh suite's identity output to this audit directory. It does not change its assertions. Separate permanent and new controls supply explicit MOV data operations. The permanent revised XOR control supplies its data and defined flag operations. The prior [mismatch record](/Volumes/PhoenixWork/audit/m2-scope-control-root-astra/preserved-contract-mismatches.json) remains intact.

The positive ordinary-flow rule is explicit at [scope.py line 681](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:681). Empty raw translation is accepted only for the nine exact shared NOP encodings. Exact ENDBR64 is also accepted at the proved owner entry. The compiler compares complete bytes. It does not remove prefixes to obtain a neutral match. Every accepted ordinary instruction still needs an exact same-owner successor at line 698. ADR0030 records the same restriction at [line 41](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/docs/adr/0030-requested-observation-scope.md:41).

Nonempty ordinary translation uses the closed operation table at [scope.py line 38](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:38). Line 687 checks input count and output presence. STORE has three inputs and no output. Other accepted operations have one or two inputs and an output. Independently neutral bytes permit only register identity COPY operations at line 691. Unknown, analysis-only, pseudo, and malformed operation shapes reject. Multiple identity COPY operations remain permitted. The tests cover valid shapes and incorrect counts or output presence for every accepted operation.

The official [Ghidra core operation tables](https://ghidra.re/ghidra_docs/languages/html/pcodedescription.html) confirm all 55 shapes. The [raw p-code reference](https://ghidra.re/ghidra_docs/languages/html/pcoderef.html) defines direct instruction translation. The [pseudo-operation reference](https://ghidra.re/ghidra_docs/languages/html/pseudo-ops.html) describes effects that need not be fully explicit. [check_references.py](check_references.py) downloads these three public pages and extracts the tables. [references.json](references.json) binds their exact bytes. [primary-operation-shapes.json](primary-operation-shapes.json) records the result.

This shape check has a specific limit. It checks names, counts, and output presence. It does not prove operand semantics, arithmetic effects, or completeness. Some [new shape controls](test_independent.py) deliberately attach data operations to generic test bytes. Those controls test the shape boundary only. They do not establish faithful translation of those bytes. The two new normal MOV controls use explicit matching data operations. A forged or incomplete translation can still satisfy a supported shape. ADR0030 states this limit at [line 52](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/docs/adr/0030-requested-observation-scope.md:52). The verdict does not remove that precondition.

The control-byte veto remains separate from positive ordinary evidence. [scope.py line 715](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:715) rejects both C6 F8 and C7 F8 after the existing prefix scan. Thus XABORT and XBEGIN reject even with a supplied identity COPY. The permanent suite covers all 256 XABORT immediate values and paired prefix and raw-evidence cases. The new suite adds independent transaction controls. No transaction state at root entry is assumed.

All prior findings were checked against their actual controls. The float aliases now reject. The recursive [exact comparison at line 392](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:392) checks every proof dataclass field and tuple element. It includes image records, spans, witnesses, gaps, and cached start indexes. [Line 784](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:784) compares the reconstructed proof and then uses it for certificate output. The prior fresh suite retains its nested float, bool, integer-subclass, bytearray, and list controls. The new malformed raw-input controls also reject invalid numeric types, null operands, duplicate operation identities, and incorrect instruction sites at parsing.

Root requests retain exact integer addresses, sorted distinct users, a selected root, unique executable entries, and checked evidence at [scope.py line 421](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:421). Direct incoming root calls reject at line 810. Reported incoming root targets at physically checked direct or indirect call sites reject at line 818. The checked witness determines the caller owner. True root recursion remains supported. An unrelated reported target or a record at an unavailable noncall site does not become a proved incoming call. The unchanged prior controls cover those distinctions. Static root selection does not establish an external runtime predecessor.

[reproduce_prior.py](reproduce_prior.py) reads the nine exact saved defect inputs. It verifies their binary, lift, proof, and full-plan identities against the original defect records. It reapplies the two saved float mutations. The malformed proof, malformed main evidence, and incoming root caller now return typed rejections. Both XBEGIN inputs and all four XABORT inputs now receive rejecting instruction guards. [prior-findings-results.json](prior-findings-results.json) records each result. All full plans remain unchanged. No old input or certificate was overwritten.

Physical transfer evidence and local branch evidence remain separate. [_branch at line 572](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:572) accepts only exact unprefixed supported branch forms. It requires one compatible raw machine branch, exact length, signed displacement agreement, and same-owner instruction witnesses. Conditional branches also need the exact fallthrough witness. Raw p-code local targets do not become machine addresses. The unchanged controls cover every supported conditional opcode, negative displacement, wrong domains, bounds, instruction interiors, absent raw evidence, conflicting transfer roles, and missing successors. The branch guard certifies destinations. It does not prove branch conditions.

Import routes are rebuilt at [scope.py line 483](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:483). They preserve call-specific binding identities, exact slots, import requests, physical thunk entries, and complete instruction paths. Shared suffixes retain all route positions. Conflicting shared successors and user-transit ownership reject. Synthetic external aliases do not become physical entries. Direct GOT calls have no fabricated thunk entry. The prior independent controls retain exact neutral limits, the 32-entry route boundary, unsupported thunk cases, shared paths, and distinct suffix entry positions. The certificate declares eager-only transit. Static construction cannot establish a resolved runtime slot or a provider identity. Lazy resolver transit remains unsupported.

The compiler preserves every full-plan site and gap. The site partition and omission records at [scope.py line 944](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:944) retain owners, all roles, witness digests, and omission reasons. Gap records retain their index, original Ghidra address, reason, and checked ELF conversion at line 882. Supported branch discharges retain the original gap. Active uncertainty gets a rejecting guard or unlisted-start rejection. Unmappable selected gaps block selection. Unrelated omitted gaps stay dormant. The existing and prior independent controls cover these paths.

All declared capture limit fields remain positive exact integers within policy maxima at [scope.py line 752](/Volumes/PhoenixWork/worktrees/m1-integrity-text-design/phoenix/observe/scope.py:752). The stack word is exactly eight bytes. Static site, witness, plan, route, neutral-instruction, neutral-byte, and scope-byte bounds are checked. Exact-capacity and one-less controls pass. Lower runtime counters bind the certificate. These checks establish static limits and bounded output. They do not prove live enforcement of counters. Nonreturn contracts remain unsupported.

[check_public.py](check_public.py) rebuilds all 16 saved public scopes. It opens only exact public inputs from the prior identity manifest. It checks binary, lift, mapping, and publication identities. Each full plan matches its saved hash and the root-cause audit's before and final bytes. Each new certificate matches the root-cause audit's final bytes exactly. Comparison with the prior corrected Sol certificate removes only `policy_implementation_sha256`. Every other field matches. Comparator mutation controls cover users, routes, omissions, dispositions, gaps, guards, limits, registers, and plan identity. No new public rejection appeared. All 12 existing selected-code Reject guards remain visible. Certificate construction does not prove that a particular execution can pass them.

The rebuilt plans and certificates are in [public](public). [public-results.json](public-results.json) records every comparison. [public-input-identities.json](public-input-identities.json) binds every read input. [check_inputs.py](check_inputs.py) verifies 180 recorded audit and public input identities. It also compares the selected original reviewer files with their saved artifact manifests. The original controls remain unchanged.

The exact handoff identities are below.

| Artifact | SHA-256 |
| --- | --- |
| `phoenix/observe/scope.py` | `0cb93cadb4657dfeb776293fe823da439eb186c71978f9c74a7d0c1533867ef4` |
| `tests/test_observe_scope.py` | `2a2ba8c115aeb852834b69e82da9a82a2303dbdf40e0a620a0ca7188a138bd6b` |
| `docs/adr/0030-requested-observation-scope.md` | `66ee8af0d38c090f9edab0e9165c60d84f28d45085a663a7412ce1dfb21e9905` |
| Policy implementation identity | `d958b7093004c7688813a350b8a24f0f1be7010fb781bf7da8c044f2dae855c0` |

The policy identity was recomputed independently from canonical JSON containing all nine relative source names and their hashes. It matches the implementation and the root-cause handoff. [policy-source-manifest.json](policy-source-manifest.json) preserves the exact input bytes. Original independent controls also verify that each individual source change changes the policy digest. No absolute workspace path enters that manifest.

[commands.json](commands.json) records actual argument vectors, working directories, environments, output paths, and child exit codes. The following commands reproduce the checks. The runner retains prior logs. The first command returns exit 1 for the three preserved old-contract failures. The second returns exit 0 when every supported check passes.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-integrity-text-design
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/python -B /Volumes/PhoenixWork/audit/m2-observation-scope-positive-sol/run_checks.py original fresh
.venv/bin/python -B /Volumes/PhoenixWork/audit/m2-observation-scope-positive-sol/run_checks.py before original-supported fresh-supported existing-retry independent-final prior-findings public references-public ruff format mypy diff-check inputs after
```

Two review-tool failures remain visible. The initial repository-suite command used an audit root outside the repository. Pytest attempted a directory metadata check at `/Volumes/PhoenixWork/worktrees/m1-corpus-author` and received a permission error. It read no private content. [existing.log](existing.log) preserves that failed collection. The corrected repository root and test configuration produced 898 passes in [existing-retry.log](existing-retry.log). The initial reference command passed the operation and policy checks, then failed because GitHub CLI authentication was unavailable. [references.log](references.log) preserves that failure. The public GitHub API fallback succeeded. A web fetch of the issue returned a cache miss. One auxiliary file patch was rejected because it named the same output file twice. That rejected patch changed no file.

[Issue 8](https://github.com/dvgyl/phoenix/issues/8) remains open. The public API result is saved in [issue-8.json](issue-8.json). The issue was not changed. A PASS for this exact static contract does not close that issue or certify integration on main.

The full requested project instructions, specification, poteto-mode skill, prior Astra design and report, both prior Sol reports and controls, and root-cause contract and checks were read. The user restrictions override broader session, delegation, editing, and shipping steps. [todo.md](todo.md) records those limits. The Prove It Works principle led to actual control runs, exact saved-input reconstruction, and final identity checks. Its leaf skill was read. Technical-writing and unslop guidance was applied with ASD-STE100 prose. The requested GPT-6.1 Sol role and Standard service are launch settings. This interface does not independently attest either setting. No model or service setting changed.

All new files are within the two permitted output directories. No repository source edit, commit, push, tag, Docker command, target execution, Ghidra process, model-provider call, or nested agent occurred. No sealed material, held-out input, private Author log, or session history was read. The failed pytest metadata check above is retained as a review process limit. No claim of runtime or native hardware verification is made.

All production gates remain open. Admission must reconstruct the certificate from original inputs and check the exact runtime manifest, raw schema 2 bytes, mapping, receipt, and complete process outcome. A supplied dataclass or matching digest cannot authenticate capture. Root predecessor and stack-word calibration, instruction size and next-PC guards, omitted-code and callback rejection, role order, recursion, import transit, limits, root closure, and reentry still need live evidence. Every rejected capture must export no local facts. The revised frame rule takes precedence over the original Astra salvage text.

The complete public GCC and Clang matrix at O0 and O2 remains required. It must retain both operations, all specified lengths, every emitted main call, invalid arguments, early returns, empty and cap input, stdio errors, and all rejection cases. Actual collector mutations must test missing activations and disabled guards. Separate recursion and four-argument patterns, three repetitions, archived v1 preservation, unchanged accepted oracles, and native architecture checks remain required. Default lazy-resolution rejection stays visible. An eager positive requires its own accepted development invocation.

The six captured registers are RDI, RSI, RDX, RCX, RAX, and RSP. Only four are argument registers in this profile. Provider identity, types, branch conditions, complete indirect target sets, general callbacks, tails, nonlocal returns, signal handlers, threads, extra argument registers, vector registers, stack arguments, aggregate values, memory snapshots, and automatic ABI inference remain unsupported or unproved. Recovery and localization must wait for integration and live approval.

SPEC.md section 9 still requires M4, held-out T0 through T3 results against every baseline, costs, a failure taxonomy, publication of the required artifacts, and replay of every headline number. This static PASS closes none of those completion requirements. Corpus sealing remains preserved.
