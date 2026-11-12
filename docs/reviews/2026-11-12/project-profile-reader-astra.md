Phoenix must complete every SPEC section 9 requirement. This review checks one prerequisite, the pure P1 project-profile reader. The verdict is **PASS for exact P1** at `6d00328bcb2a58cbf340b8275031995b83063aa2`. I found no blocking P1 implementation defect. Production v2 remains **HOLD**. No milestone, source admission, compiler evidence, semantic integrity, or build permission follows from this verdict.

The current P1 API is safe to use as the basis for the next bounded units. Those units must treat its result as untrusted consistency metadata. They must obtain source bytes, original inventory, installed policy, compiler records, and process authority independently. They must repeat validation at each external boundary. Neither a constructor nor a matching digest is an approval mechanism.

The review was direct. No agent, nested model, model CLI, API, provider, or model subprocess was used. No model or service setting was changed. The task dispatcher owns the requested Standard service setting. Session history and model configuration were not inspected. No concurrent Sol review or controls were read.

The source identities were verified before testing and again after testing.

| Identity | Exact value |
| --- | --- |
| Branch | `agent/m3-project-profile-reader` |
| Revision | `6d00328bcb2a58cbf340b8275031995b83063aa2` |
| Git tree | `01032e2d05a39e1a7a1f78bf1a7b4c8aeb6480a9` |
| Source | `phoenix_eval/project_profile.py`, 32,714 bytes |
| Source SHA-256 | `c6e57cdc80a51c932dbaf02e3ac0888c09e2375ad5909fce2b53a67a9701baa6` |
| Source Git blob | `3c9aba9c7e19e106ceb7baae51f1be0c21dcade2` |
| Tests | `tests/test_project_profiles.py`, 57,109 bytes |
| Test SHA-256 | `fff407471c9978b69dc4d726e8b781b37672545355b086b68f8bc1ebd695e766` |
| Test Git blob | `c3e1bf1dd9a010a5169aa2ccf3c62d2687ea6ff5` |
| ADR0039 SHA-256 | `e70a40330eeb42e461ac8df06da8842e89e38cbabc4ff8776f8457ebad9c9a85` |
| Old build module SHA-256 | `7bcf756f5e824dac383d9a08b9c82c70c138be2f0272e05bd31d7b63f7facba4` |
| Old CMake bytes SHA-256 | `d950cc94c3639acc3381102a5c3e7827c2e9465a472261aea055527c47d71773` |

[identities-before.json](identities-before.json) and [identities-after.json](identities-after.json) contain the complete named source identities. They are equal. [unchanged-source.json](unchanged-source.json) records the comparison. [identity_check.py](identity_check.py) is the repeatable local check.

The committed diff contains exactly five allowed files. It adds the module, its tests, and ADR0039. It appends to STATUS and LOG. All 223 other base files remain unchanged in the Git trees. Both complete progress prefixes remain. The STATUS prefix has 7,586 bytes and SHA-256 `ebe05a337051985b2d71b68cde52fa64bf134557d2319769521f3997f119c9a0`. The LOG prefix has 56,027 bytes and SHA-256 `a8ebc48f921e6f804702dcb8d894664398642113f449a4be495be869d092f793`. The parent added its final check entry to LOG after the worker report. The frozen committed LOG identity is recorded in the identity files.

The worktree was clean before and after the checks. No source edit, Git metadata command that changes history, commit, push, branch change, or tag was made. No old v1 implementation, schema, pin, caller, or report parser changes. A search of production source found no P1 caller outside the new module itself. These facts preserve the old entry points. They do not prove a future v2 integration correct.

I read AGENTS.md and SPEC.md completely. I also read the complete source, test module, ADR0039, public worker report, four authorized design documents, and the preserved output-scope exception. The named parent proofs were `final-scope.json`, `after-push.json`, `final-commit-push.json`, `parent-checks.sh`, `final-commit-push.log`, `parent-final-tests.exit`, and `parent-final-tests.log`. [public-input-identities.json](public-input-identities.json) binds these named public inputs. The parent proof reports a passing mandatory hook and a server-verified branch. I verified the local revision. I made no network check.

Current main `docs/QUESTIONS.md` places outcome comparison and isolation in `phoenix_eval`. Main resolved to `d736ef8728d474cf3bb7d050bb0a1d173f54a034` at the final identity read. The proposed coverage commands for absent `phoenix.diff` and `phoenix.sandbox` packages are stale. They supply no coverage evidence. The complete evaluator coverage gate remains 85 percent. I did not rerun the full gate because this task prohibits actual compilers and target execution.

The independent evidence is in [test_independent.py](test_independent.py). The fixture and expected CMake were authored in that file. No implementation serializer or validator supplies the expected wire, digest, CMake, or field values. The fixture files are [fixture-manifest.json](fixture-manifest.json), [fixture-correspondence.json](fixture-correspondence.json), [complete-expected-records.json](complete-expected-records.json), and [expected-CMakeLists.txt](expected-CMakeLists.txt). Owned public C and header bytes are under `fixture/`. They were never compiled or executed.

The independent fixture has three source files, one header, three function rows, two global rows, and two nominal type rows. It uses two internal functions with the same C name in different files. One global is external and one is internal. The two structure declarations have equal member text and different anchors. The fixture charges 16 serialized span occurrences and 48 reference edges. Its declared source-plus-CMake total is 938 bytes. The CMake file has 557 bytes. The manifest has 944 bytes. The correspondence has 4,558 bytes. These are fixture measurements, not Phoenix evaluation results.

The check results are as follows. The initial and expanded suites overlap. Do not add their case counts.

| Check | Result | Exit |
| --- | --- | ---: |
| Frozen source and exact diff check before tests | Passed. | 0 |
| Initial independent controls | 1,099 passed. | 0 |
| Initial affected host collection | Failed before test collection. The guard denied a sibling-directory metadata query. | 4 |
| Corrected affected host collection | 1,201 passed. This includes 1,163 P1 cases and 38 legacy build and submission cases. | 0 |
| Expanded independent controls | 1,178 passed. | 0 |
| Final independent controls | 1,185 passed. | 0 |
| Frozen source and exact diff check after tests | Passed. | 0 |
| Fixture export, named public input hashes, and before/after comparison | Passed. | 0 |

[commands.jsonl](commands.jsonl) retains exact pytest argument arrays and exits. [run_checks.py](run_checks.py), [run_host_corrected.py](run_host_corrected.py), and [run_final_controls.py](run_final_controls.py) retain the launch code. All shell commands sourced `/Volumes/Extreme Pro/Phoenix/env.sh`. Test children inherited the outer guard. TMPDIR, test logs, Hypothesis storage, bytecode prefix, and pytest basetemp were inside the assigned temporary directory. Bytecode writes were disabled. Pytest's cache provider was disabled.

Every audit test used the exact review directory for both `--rootdir` and `--confcutdir`. The repository-only host run used the repository for both options. [independent-initial.log](independent-initial.log), [independent-final.log](independent-final.log), and [affected-host-corrected.log](affected-host-corrected.log) retain successful output. The final independent log is from the final 1,185-case run. The intermediate 1,178-case observation is recorded in [independent-expanded-result.txt](independent-expanded-result.txt).

The initial host check setup was incorrect. It used the audit root while naming tests outside that root. Pytest attempted to inspect the `worktrees` ancestor and query metadata for a protected Author sibling. The outer guard refused that query. No test ran and no private data was read. [affected-host.log](affected-host.log) preserves the complete failure. The correction narrowed collection to the repository. It did not change or relax the guard. This check setup error is separate from the worker's prohibited event-data reads.

The controls establish the following P1 behavior.

| Requirement | Independent evidence and conclusion |
| --- | --- |
| Complete immutable records | Compare every wire field recursively, including exact scalar types, tuple lengths, record slots, frozen status, optional fields, anchors, and retained byte-object identities. The expected record keys come from the independent wire. |
| Closed wire | Remove, replace with Boolean, and duplicate every field. Add unknown fields across record shapes. Duplicate keys reject before ordinary JSON decoding. |
| Canonical wire | Reject alternate key order, whitespace, missing or repeated LF, escapes, Unicode metadata, BOM, NaN, Infinity, floats, exponent notation, and negative zero. |
| Input types | Reject non-byte inputs, bytes-like mutable objects, incorrect records, and subclasses. Exact integer checks reject Boolean aliases. |
| Resource limits | Verify all 16 exact defaults. Reject missing, raised, zero, negative, Boolean, and float limit fields before scanning. Accept the complete fixture at all reduced exact limits together. |
| Allocation order | Instrument JSON decoding, record creation, correspondence index creation, hashing, and rendering. Raw count and token limits reject before these later operations. Declared size sums reject before hashing, correspondence indexing, and rendering. |
| Hard bounds | Exercise hard byte, array, nesting, integer, string, span, and combined edge limits. Separate malformed raw cases from complete valid fixtures. Complete source-count, header-count, declared-total, identifier, and path fixtures cover their hard boundaries. |
| Paths and identifiers | Require full ASCII grammar matches. Reject suffix newlines, NUL, traversal, absolute paths, Unicode, uppercase aliases, nested paths, separators, and CMake text. Valid long paths and identifiers pass at their exact grammar limits. |
| Sorted rosters | Reject repeated and reversed source, function, global, type, declaration, user, and ID lists. Functions use numeric entry order. |
| Function ranges | Reject bad outer endpoints, signature/body overlap, out-of-file spans, header definitions, overlapping definitions, missing external main, repeated external names, and unresolved type references. |
| Nominal identity | Independently hash the exact domain, one actual NUL byte, canonical original identity, and complete anchor. Missing, textual, or repeated NUL separators fail. Equal member layouts retain different nominal IDs. |
| Declaration identity | Changes to any header row field invalidate the declaration-version digest. Two nominal types cannot own one definition range, even with different claimed span hashes. |
| Optional type definitions | Null definitions work for opaque struct, union, and enum proposals. A typedef without a definition fails. |
| CMake | The independent complete golden bytes equal the old template with exactly one executable-stanza replacement. The old literal was also checked at the design revision, the parent revision, and HEAD. Mutation of the legacy runtime constant cannot change v2 rendering. |
| Forged direct objects | Delete or mutate every manifest and correspondence field. Reject all inconsistent records. Reject direct path injection, subclasses, missing top-level bytes, and scalar subclasses. A complete independently constructed matching record can render only the fixed expected bytes. |
| Finite input errors | All observed malformed-input refusals use the finite category and phase sets. Details are bounded ASCII text. No partial parsed result is returned. |
| Programming errors | Inject ValueError, TypeError, RuntimeError, and OSError at each of seven hash calls and at JSON decoding. These faults remain visible. Only JSONDecodeError is converted at the decoder boundary. Canonical encoder faults also propagate. |

The missing-ProfileLimits correction is at `project_profile.py:191`. The independent controls delete each of its 16 fields separately. Each control fails with `profile_limit` in the parse phase before scanning. An entirely uninitialized limits record also fails. The correction does not catch hash or decoder programming errors.

The missing-optional-field correction is at `project_profile.py:919`. A record with an explicit null definition passes. Delete that field from the same direct record, and rendering fails with `profile_correspondence` in the correspondence phase. Every other direct record field also receives deletion and mutation controls. This verifies absence separately from null without a broad exception handler.

The raw scanner bounds the input before JSON tree creation. It still creates small bounded token strings and duplicate-key sets. The maximum input bytes, token sizes, nesting, arrays, records, spans, and references constrain work. They are not an exact Python heap bound. The source-size sum is a declared sum in P1. It becomes an actual-byte obligation in P2. Hard-bound malformed controls do not demonstrate acceptance of a complete valid project. The final controls label those cases separately.

No blocking P1 source finding was found. The following concerns remain concrete integration requirements or process findings. Their severity describes the risk if left unaddressed at the named later boundary.

| ID and severity | File and line | Reproducer | Practical effect | Recommended correction or obligation |
| --- | --- | --- | --- | --- |
| R1. High at production admission. Not a P1 defect. | `phoenix_eval/project_profile.py:581`, `:741`, and `:879`. | `test_semantic_counterexamples_are_only_consistency_metadata`, `test_no_source_byte_or_original_authority_from_matching_hashes`, and `test_stale_declared_users_cannot_change_parser_obligation`. | A false span hash, a prototype represented as a body, a wrong origin entry, a wrong claimed type kind, or an omitted function can pass P1. Empty or stale user lists also pass. Treating this as source or compiler authority would remove required checks. | P2 must check actual bytes and expected identities. P4/P5 must derive complete compiler facts and users independently, check the trusted original inventory, and check real abstract syntax tree associations. No omitted user or reference list may suppress a compiler duty. |
| R2. Low API integration risk. Not a P1 defect. | `phoenix_eval/project_profile.py:942` and `:956`. | Parse with the complete reduced limits in `test_all_reduced_bounds_together_on_complete_valid_fixture`. Inspect the public record fields and renderer signature. | ParsedProjectV2 does not retain the caller's reduced limits or their provenance. Rendering checks hard defaults. A caller cannot infer its own policy from the record's type. | P2 filesystem and byte adapters must carry evaluator-owned limits and expected policy separately. Recheck them on each admission and reload. Do not use a constructor or prior renderer success as a policy receipt. No v1 wire change is needed. |
| R3. Medium process finding. Pre-existing and disclosed. | `docs/adr/0039-independent-project-profile-reader.md:207` and the public worker report. | The worker report states that two checksum-generation passes and one verification pass read its unowned dispatcher event file. This review did not repeat those reads. | The worker violated its read scope. Its checks cannot support an unqualified process-assurance claim. This does not, by itself, establish a defect in the frozen reader. | Retain the incident, failed checks, and prior evidence. Use explicit artifact lists and the v5 outer guard. Keep independent code acceptance separate from worker process assurance. Do not treat the accepted design-output exception as approval of this incident. |
| R4. Low review check setup error. Corrected here. | `run_checks.py`, initial affected-host argv in `commands.jsonl`. | Run repository tests with the unrelated audit root. The preserved log shows pytest's denied sibling metadata query. | The initial host suite did not collect. It is not a passing result or a product defect. | Use the repository root for repository-only collection. Keep the required audit root for audit tests. The corrected host run passed without a guard change. |

R1 counterexamples are positive parser controls with explicitly false semantic claims. The prototype example binds actual bytes `int main(void);` and supplies a one-byte body range. The parser accepts the arithmetic. A compiler association check must reject it. The wrong-origin example changes entries without an authoritative inventory. Another example changes both original identities and recomputes nominal IDs. Agreement still grants no original authority. The false source hashes pass because P1 receives no source bytes. These controls prove the authority limit, not an integrity bypass in an enabled production route.

The accepted interface choices have long-term costs.

| Choice | Benefit | Cost and action |
| --- | --- | --- |
| Exact supplied canonical CMake | The delivered file and the evaluator's expected file are identical. Safe source paths are the only variable text. | This intentionally limits build features. Keep template bytes in installed v2 policy. Change version or explicit policy identity for future semantics. Never silently follow a new v1 constant. |
| Complete records plus retained canonical bytes | Reviewers and later adapters can inspect every declaration. Direct-object forgery is detected through reparse and complete comparison. | Rendering repeats bounded parsing and hashing. Keep this boundary check until a reviewed internal authority type exists. Do not remove it based on frozen dataclasses alone. |
| Strict raw scanner plus JSON decoder | Limits and duplicate checks occur before tree allocation. The final byte comparison defines one wire representation. | Grammar and resource logic exist in two stages. Any later field or array needs matching raw-count and reduced-limit controls. A new wire version must not bypass the scanner. |
| Nominal anchor IDs | Equal-layout types remain distinct. Identity does not vary with native structure size. | Anchor truth and actual compatible declarations remain separate work. A future tag/typedef alias feature needs an explicit reviewed schema. Do not merge identities by spelling or layout. |
| Fixed hard limits with caller reductions | P1 has a bounded public grammar and repeatable refusal behavior. | Some hard limits cannot all be reached by one complete valid input because byte limits bind first. Retain reduced valid controls and separate hard raw controls. Publish any later limit change through versioned policy. |
| Separate v2 adapters | Historical v1 callers and recorded formats remain exact. | Later units must carry several explicit types and discriminators. This cost is justified by replay integrity. Avoid a default parameter that silently broadens v1 admission. |

Boundary Discipline shaped the distinction between parser consistency and later evaluator authority. Model the Domain shaped the complete-field comparison against the independent record tree. Both leaf skills were read. The installed poteto-mode Investigation workflow was applied directly. The user prohibited nested models, source edits, commits, and publication. Those instructions replace conflicting skill steps. No comment deletion is recommended. The source comments explain authority limits, frozen policy data, and allocation order. I found no defect reason to remove them.

All remaining P2 through P9 units remain open.

| Unit | Required completion |
| --- | --- |
| P2a | Validate the complete actual source-byte roster, sizes, hashes, span contents, declaration identity, expected original and origin, installed policy, deterministic source digest, and canonical archive. Derive the archive from owned bytes. Reject forged tuple/archive combinations. |
| P2b | Add descriptor-based physical path checks, no-follow and regular-file checks, parent/link/hard-link checks, bounded enumeration, race detection, atomic publication, and idempotent conflict handling. Preserve v1 snapshots. |
| P3a | Add strict versioned receipt and transport readers. Bind context, project, source roster, archive, object, executable, and evidence identities. Bound complete responses and diagnostics. A process exit is not a receipt. |
| P3b | Review and implement the fixed native compiler launcher. Pin toolchains and system inventories. Use fresh build roots, read-only inputs, fixed environment and argv, fixed probes, exact object and link rosters, and complete actual invocation records. |
| P4a | Add native Clang source evidence under a new policy. Cover active source closure, declarations, storage, literals, calls, locations, and all units. Preserve `m1-v1`. |
| P4b | Complete the separate native GCC interface review and implementation. Prove the required frontend hooks, preprocessing, storage, and location coverage. Do not substitute Clang-only evidence or compiler exit status. |
| P4c | After the Author releases the VM, bind actual inputs, preprocessing, dependencies, objects, linking, and executable bytes in all four native compiler/architecture contexts. |
| P5a | Independently parse the frozen origin inventory. Check exact function completeness, main identity, address space, definition/signature/body association, symbols, complete actual users, nominal declarations, and shared-global compatibility. Hashes remain identity evidence only. |
| P5b | Apply every integrity rule to all frozen source and header bytes, all required active compiler facts, and all four tested executables. Retain original-text, storage, output-memorization, call, control-flow, and unsupported-evidence failures. Incomplete evidence cannot yield PASS. |
| P6a | Add explicit v2 selection and SubmissionV2. Freeze complete source and package evidence before evaluation-input access. Bind exact returned checkpoint bytes. Retain costs, failures, atomic retry, and durable contradictions. |
| P6b | Add versioned configuration, result, capture, and replay readers. Verify all stable identities, ancestors, ledger, receipts, failures, and tested artifacts. Preserve exact M1 and M2 formats. Missing evidence must not regenerate. |
| P7a | Add versioned pipeline records and explicit selection. Reject conflicting resume/replay overrides before provider or runtime work. Keep the module producer disabled. |
| P7b | Retain the exact tested project snapshot through trial, verification, final packaging, reports, and development capture. Test with a fake module supplier before enabling a producer. |
| P8a | Freeze and commit the public positive and negative fixture matrix before live execution. Record every required result stage. Keep failed and blocked controls. Reject protected inputs. |
| P8b | After the Author releases the VM, run four builds, independent oracles, public behavior and corruption controls, native x86-64 and AArch64 CI, exact outcome comparisons, default-preservation checks, and replay on the integrated revision. |
| P9 | Separately review type recovery, shared declarations, modules, generation, scheduling where needed, and producer enablement. Require the preceding gates and an explicit method policy before any opt-in production route. |

The full capture review remains **OPEN after provider screening**. This P1 review did not retry, rephrase, replace, or certify it. Production capture, build issuance, live collector checks, source admission, native compiler evidence, and semantic integrity remain open. The private Author retains the VM. No VM lease or guard change occurred.

M2 still needs its measured acceptance and portability evidence. M3 still needs no M2 regression, whole-program types and modules, at least 70 percent non-default T1 function types, and the required independent readability review. M4 still needs the frozen T0-T3 evaluation, every baseline and ablation, complete costs and failure categories, limitations, and verified commitments. T2 private qualification and T3 runtime qualification are not supplied by this review.

SPEC section 9 remains open. Phoenix must complete M4, publish the complete held-out report against every baseline, publish the required harness and benchmark artifacts through the sealing process, and reproduce every headline with `phoenix-eval --replay`. No software-test count in this report is a held-out result or a fully-successful binary count.

No compiler, Ghidra, Docker, VM operation, target execution, real provider, network call, image change, credential action, or installation ran. Existing local .venv tools were used. No sealed source, held-out input, source archive from another task, private run, Author data or history, session history, existing events, stderr, or summary data was read. The initial denied metadata query is disclosed above. No dispatcher output file was hashed. Only named public inputs and this review's explicit output list were hashed.

All review writes are inside `/Volumes/PhoenixWork/audit/m3-project-profile-reader-review-astra-20261112` or its matching temporary directory. All local check children completed. No model child was started. The exact P1 PASS does not authorize the remaining work to skip a gate.
