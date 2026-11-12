# Collector architecture verdict

Phoenix needs verified v1 completion through SPEC.md section 9. This review approves one design prerequisite. It does not establish v1 completion.

**PASS-to-implement for the corrected design specified here. Production admission remains HOLD.** Select the generated typed `const` header and the trusted worker build receipt. Apply corrections F1 through F4 below as part of that design. The earlier candidate is not approved verbatim.

The pinned QEMU implementation supplies sufficient ordering for the narrow pre-instruction eight-byte read contract below. No QEMU extension is required for that contract. This is a source-based conclusion. It is not a live result or an unrestricted promise from the public API.

The full capture review of `9672a0f414e6fe128f8a1763c66694f551f2e2f5` remains OPEN. This task used that revision only as an interface input. It did not retry or replace the separately blocked full review. All production, live, native-hardware, and recovery-integration gates remain open.

The reviewed candidate files are [design.md](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/design.md), [api.md](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/api.md), and [report.md](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/report.md). I read all three in full. Exact revisions and hashes are in [read-inputs.json](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/read-inputs.json).

The transport decision is as follows.

| Choice | Benefit | Cost that affects this decision | Verdict |
| --- | --- | --- | --- |
| Typed constant header with fixed collector code | One pure renderer carries the complete plan and scope. The native collector needs no general plan parser. | Requires a trusted compiler, retained tables, build issuance records, and bounded compilation. | Select. Implement the corrections below. |
| Bounded text | One reusable plugin can accept many static plans. | Requires a complete native grammar, allocation rules, reference checks, and an independent decoder. It does not remove worker provenance or launch checks. | Keep as a later alternative if compilation cost proves unacceptable. |
| Generated collector control flow | Can specialize the collector for each input. | Changes executable logic for each binary. Makes source closure and independent review larger. | Reject. Generate data only. |

The existing archived text parser is not an alternative implementation of the new contract. It carries a small selected-site plan and schema 1 behavior. Its controls remain useful preservation tests. They do not establish schema 2 collection.

**F1. A consistent build receipt is not an issued build receipt.**

The candidate correctly requires trusted provenance. Its proposed `validate_build_receipt` signature supplies only a `TrustedBuildContext`. That context identifies expected build inputs. It does not identify an output issued by the worker. Thus the signature does not express the separate provenance check needed for a cache hit. See the candidate [API](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/api.md:24) and its compilation and cache contract.

Use a controller-owned build registry. A successful trusted build transaction records `K`, the exact receipt digest `B`, the plugin digest `Q`, and the build context identity. The registry entry follows successful worker completion and output checks. A caller's artifact directory cannot create that entry. A later cache hit requires the entry and fresh hashes of the stored bytes. Loss of the registry requires a new trusted build. Matching untrusted digests are insufficient.

Make the API distinction explicit.

```text
check_build_consistency(prepared, receipt_raw, plugin_raw, context)
    -> ConsistentBuild | CollectorRejection

validate_issued_build(prepared, receipt_raw, plugin_raw,
                      context, issued: TrustedIssuedBuildPin)
    -> CheckedBuild | CollectorRejection

TrustedIssuedBuildPin = {build_key, receipt_sha256, plugin_sha256,
                        build_context_sha256}
```

Only the second result can authorize cache reuse or deployment. The installed controller obtains `issued` from its trusted registry. Production artifacts cannot supply it. These are authority rules, not Python constructor protections. The worker, controller, compiler, and supervisor remain trusted components.

Keep a second registry for completed executions. Bind each expected case and repetition before launch. Save the returned execution receipt through that transaction after process completion. An output cannot nominate its own trusted execution pin. Reject duplicate, missing, extra, or late responses. Preserve the same rule on replay.

**F2. Calibration needs identities for each trial and a separate applicability rule.**

The candidate builds one plugin per binary and static build key. Its calibration paragraph instead binds one runtime digest `T` and one build receipt `B` to the whole public matrix. See [design.md line 82](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/design.md:82) and [api.md line 355](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/api.md:355). The matrix contains different compiler outputs, public fixtures, scopes, and collector mutations. They cannot all use one binary-bound plugin or one `T`.

Replace the singular calibration record with the following structure.

```text
CalibrationSuiteEvidence = {
    schema, common_context_sha256, freshness_contract_sha256,
    frozen_public_case_manifest_sha256,
    applicability_rule_sha256,
    trials: tuple[CalibrationTrial, ...],
    complete_artifact_manifest_sha256, reviewer_decision
}

CalibrationTrial = {
    case_key, repetition, expected_status,
    binary_sha256, full_plan_sha256, scope_sha256,
    build_key, build_receipt_sha256, runtime_manifest_sha256,
    exact_launch_spec_sha256, actual_status,
    saved_artifact_manifest_sha256
}
```

Each trial uses its own actual `B`, `Q`, and `T`. Mutations have distinct identities. An expected rejection has its retained partial artifacts and actual result. It does not require a fabricated complete capture receipt.

Each mutation trial records its exact declared change from the baseline context. Only the unmodified approved context can authorize ordinary production deployment. A successful test of an intentionally changed collector never approves that collector for production.

The common context binds the fixed collector and type declarations, renderer, source-policy and admission implementations, builder, compiler inputs, launch profile, observer QEMU, runtime dependencies, architecture, and limit policy. The applicability rule is installed code in the production boundary. It compares these fields exactly. It cannot be selected by the submitted suite.

For an ordinary production build, require the approved common context, its issued build receipt, complete regenerated data, and compiled-table validation. Label reuse of the public calibration as implementation calibration. Do not claim that the new binary's plugin or invocation was a public trial. The new execution still needs every live guard, independent root read, complete outcome comparison, and raw admission check. If a deployment claims exact-artifact calibration, require an exact matching trial instead.

This correction changes how evidence is recorded. It does not remove a public case, mutation control, repetition, or independent review. No production deployment is authorized until the complete public matrix passes. Test-only trial results cannot enter recovery.

**F3. Retain complete data in the compiled artifact.**

The candidate retains complete records in the generated header. It does not define how the compiler must retain tables which the callback does not read. A source header containing an unused `static const` table does not itself require that table to remain in the shared object. The candidate also leaves the required output exports unnamed. See [design.md lines 47 through 57](/Volumes/PhoenixWork/audit/m2-collector-transport-design-astra-resume-20261112/design.md:47).

Use one fixed, exported constant table directory, named `phoenix_collector_data_v1`. It must reference every generated table, with its type tag, count, and length. Keep `qemu_plugin_install` and `qemu_plugin_version` as the required QEMU exports. Put the export and retention declarations in the fixed native schema. Do not derive an identifier or source fragment from an input symbol.

The fixed installation routine must traverse the directory and check all table tags, counts, slices, and references. Its operational indexes must refer to those tables. Do not make a second hand-written selected-site list. Preserve complete unused metadata as data. Keep the compiler and linker flags fixed. Reject an output whose required data or exports are absent.

Add a build-output inspection record. It binds the actual plugin digest to the represented logical data digest and table inventory. An independent compiled-data reader must recover the complete logical record using the declared target layout. Validate that reader against representative compiled headers in the later authorized Linux build environment. Do not use the renderer as its own decoder. Do not hash C padding or invent field offsets. Read the layout from the fixed declarations and checked build output. The receipt must bind this inspection record.

The retained data must include every `TraceSite` role, every `continuation_of` user, complete optional `ImportBinding` fields, and all import gaps. Keep `needed_library=None`. Keep every omission reason and gap's original index and Ghidra address. Preserve the checked ELF address as a separate optional field.

For routes, retain the call-specific binding and every `(route_sha256, position)` membership. Two calls which share a terminal or suffix still have separate route identities. At execution, the pending call selects one route and one next position. Membership in another route grants no permission. The exact [scope source](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/sources/09e984b8608743d87ce9b323a9f6a4a2fad9785b/phoenix/observe/scope.py:483) establishes this requirement.

**F4. Bind the actual launch and close the new source manifest.**

The small launch line is suitable as bounded plugin input. Its labels do not record the complete command which the supervisor executed. The candidate execution receipt has no exact launch-spec digest. Add `launch_profile_sha256` to the deployment record. Add `exact_launch_spec_sha256` and `accepted_case_record_sha256` to the execution receipt. Retain both corresponding records.

The fixed launch profile describes the accepted launcher, observer command template, target paths, working directory, environment rule, descriptors, runtime tree, sandbox options, and resource limits. The exact launch spec records the actual expanded argument vector, environment, case-root association, and applied limits. It includes the binary, invocation, deployment, and launch-line identities. The worker checks the spec against the fixed profile before it starts the process. The supervisor records the actual result from that process.

The accepted case record binds the original binary, invocation, complete accepted outcome, and existing independent oracle evidence. On this Mac, retain both accepted QEMU 8.2.2 and Rosetta identities. The candidate's one accepted worker image field cannot identify both oracle executions. Add this association in the outer record. Do not change the strict existing runtime manifest to carry it.

Keep the exact target environment from `Invocation.environment()`. Keep `/program`, the existing arguments, stdin, and initial tree. Preserve the accepted launcher's sandbox and complete filesystem snapshot rules. Add no `LD_BIND_NOW`, `QEMU_*`, or hidden target overlay. An eager positive must use an already eager original under an independently accepted invocation. Default lazy cases remain visible rejections.

The plugin can compare the supplied `D` with its compiled data identity. It can check its tables and hash the immutable original path supplied by QEMU. `C`, `Q`, `B`, `T`, and the invocation digest are worker-supplied labels at that plugin boundary. They become checked associations through the worker and controller. Do not embed `C` into the header to make it self-verifying. `C` depends on that header's hash and would create a cycle.

Preserve the nine-file scope-policy hash and the ten-file admission hash exactly. They identify declared file sets. They are not complete process attestations. The new source manifest must cover the new producer, renderer, table reader, receipt validators, applicability rule, runner, worker adapter, launcher recipe, and their local dependencies. Include the existing policy and admission file sets. Include import initializers and the actual sandbox, case, wire, outcome, and tree code. The current runner lives in `phoenix_eval/worker.py` and `phoenix_eval/docker.py`. There is no `phoenix/sandbox/` directory at the fixed main revision.

Freeze the new manifest's exact relative-name allowlist before implementation review. Derive its transitive local imports from the implemented files. Reject missing or extra compilation inputs. Bind the Python interpreter and installed dependencies through the immutable execution image. Control import paths and loaded bytecode. `-B` alone prevents bytecode writes but does not establish which code was loaded. A stale bytecode file cannot become an unrecorded implementation. The same rule applies to the native compiler, linker, headers, startup objects, libraries, QEMU header, and runtime shared libraries.

The corrected digest order remains acyclic.

```text
original inputs -> P, S -> D
fixed source manifests -> R, N
D, R, N -> generated header G -> source manifest C
C, fixed build context -> request K -> actual plugin Q -> issued receipt B
P, S, C, Q, installed admission and runtime pins -> M -> T
public trial B_i, T_i, launch specs, outcomes -> calibration suite
T, B, common-context approval, freshness contract -> deployment
deployment, accepted case -> exact launch spec -> actual capture and outcome
completed trusted transaction -> execution receipt -> saved replay pin
```

Build and observer base images contain fixed tools and source. They must not contain a final per-binary runtime manifest or deployment record which refers to that same image. Calibration records must not refer to a future production deployment digest.

**Pre-instruction freshness decision.**

Accept the following source contract for QEMU 9.2.0, commit `ae35f033b874c627d81d51070187fbf55f0bf1a7`, plugin API 4. The verified release archive hash is `f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894`.

An eight-byte read occurs synchronously inside an instruction execution callback registered with `QEMU_PLUGIN_CB_R_REGS`. The guest is x86-64 Linux-user under TCG, QEMU's Tiny Code Generator. There is one guest thread and one vCPU. The sampled stack bytes are ordinary guest memory. No other agent writes those bytes during the callback. No signal handler, asynchronous writer, device memory, or concurrent mapping change participates. These conditions limit the claim. They are not a newly inferred property of an arbitrary target.

Under those conditions, a successful read returns the backing-memory bytes after completed preceding guest instructions and before the current instruction. It does not promise global store-buffer drainage, persistence, an atomic snapshot against concurrent writers, or a write history. It does not prove that a word was never changed and restored between samples.

The source evidence is as follows. Line ranges refer to exact saved source files.

| Source location | Evidence |
| --- | --- |
| [translator.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/accel/tcg/translator.c:150), lines 150 through 181 | The instruction-start plugin marker is generated before `ops->translate_insn`. The preceding instruction's generated operations precede the next marker. |
| [plugin-gen.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/accel/tcg/plugin-gen.c:280), lines 280 through 340, and lines 111 through 118 and 158 through 173 | Injection replaces each marker in place. Regular and conditional callbacks use a synchronous TCG helper call. They are not dispatched to another thread. |
| [plugins/core.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/plugins/core.c:370), lines 370 through 425 | Both callback forms map `QEMU_PLUGIN_CB_R_REGS` to `TCG_CALL_NO_WG`. They do not mark the callback as having no side effects. |
| [tcg.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/tcg/tcg.c:5410), lines 5410 through 5435 | The helper call synchronizes TCG globals before calling a helper which can read them. This supplies the current RSP and other captured registers. It is separate from guest-memory ordering. |
| [optimize.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/tcg/optimize.c:1506), lines 1506 through 1540 and 2071 through 2095 | The callback invalidates memory-copy optimization state and stops barrier merging across the call. Guest stores remain guest-store operations. |
| [tcg-opc.h](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/include/tcg/tcg-opc.h:203), lines 203 through 241, and [tcg.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/tcg/tcg.c:6190), lines 6190 through 6240 | Guest stores have side effects. Code generation visits the operation list in order. The liveness pass also retains side-effect operations at lines 3826 through 3837. |
| [AArch64 backend](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/tcg/aarch64/tcg-target.c.inc:1823), lines 1823 through 1847, 1885 through 1935, and 1718 through 1729 | Linux-user addresses use the guest base and guest address. Fast stores emit native stores. A slow store calls its helper before returning to the following generated code. |
| [x86 backend](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/tcg/i386/tcg-target.c.inc:2434), lines 2434 through 2479 and 2544 through 2558 | The 64-bit host backend also emits stores to the guest backing address. This is source evidence only for the later native x86-64 profile. |
| [user-exec.c](/Volumes/PhoenixWork/tmp/m2-guest-loader-static-sol/sources/qemu-9.2.0/accel/tcg/user-exec.c:1058), lines 1058 through 1130, and [ldst_atomicity.c.inc](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/accel/tcg/ldst_atomicity.c.inc:985), lines 985 through 1033 | Store helpers write the translated host backing memory before returning. They do not enqueue a later guest-memory write. |
| [plugins/api.c](/Volumes/PhoenixWork/tmp/m2-guest-loader-static-sol/sources/qemu-9.2.0/plugins/api.c:563), lines 563 through 580 | The read API sets the requested byte count and calls `cpu_memory_rw_debug` on `current_cpu`. A negative result fails the read. |
| [cpu-target.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/cpu-target.c:377), lines 377 through 395 and 431 through 462 | The Linux-user read checks page validity, copies each readable page portion, and returns success only after the entire range. |
| [uaccess.c](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/linux-user/uaccess.c:8), lines 8 through 24, and [cpu_ldst.h](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/include/exec/cpu_ldst.h:85), lines 85 through 93 | The copy uses the same guest-address-plus-guest-base mapping as the store path. There is no separate memory snapshot cache. |
| [x86 CALL generation](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/target/i386/tcg/emit.c.inc:1551), lines 1551 through 1560, and [push generation](/Volumes/PhoenixWork/tmp/m2-collector-architecture-direct-astra-20261112/qemu-9.2.0/target/i386/tcg/translate.c:1957), lines 1957 through 1969 | A near CALL stores the return word and updates RSP before the transfer. The destination callback therefore follows that store. |

The conclusion uses ordinary same-thread read-after-write behavior for the same backing bytes. It does not depend on another core observing the store. The source paths above establish the operation order and address association. Finite positive tests alone would not establish either property.

The public [header warning](/Volumes/PhoenixWork/tmp/m2-guest-loader-static-sol/sources/qemu-9.2.0/include/qemu/qemu-plugin.h:897), lines 897 through 916, still applies. The API does not flush arbitrary writes and does not promise freshness in every callback. In particular, the current instruction has not executed at an instruction-start callback. This review supports completed prior instructions under the stated profile. It does not remove that warning or extend the claim to translation callbacks, concurrent threads, or system emulation.

Use one actual eight-byte API call for the root anchor and a separate call for each return attempt. Clear scratch before each call. Check arithmetic, the Boolean result, and the exact eight-byte length. On failure, discard the entire sample, including any copied first-page prefix. A page-crossing read is acceptable only when all eight bytes succeed. Decode little-endian bytes explicitly. Count every attempted read. Never reconstruct the entry anchor from the later return.

The debug path can try `/proc/self/mem` for a non-readable guest page at `cpu-target.c` lines 439 through 449. The accepted QEMU case root has no such proc mount. Preserve that launch profile. Do not treat debug-read success as a general proof of guest read permission in a different environment.

Add a canonical freshness-contract record for this restricted profile and source closure. Pin it in deployment and calibration. The record must not claim live calibration before that work runs. If the source, backend, callback mode, concurrency contract, or memory model changes, this conclusion no longer applies automatically. Reassess that profile. A broader synchronized-read extension would need its own source contract and review. A fence alone would not create an atomic snapshot against concurrent writers.

**Rules which the implementation must preserve.**

Use the complete canonical plan from fixed main. Use scope `09e984b8608743d87ce9b323a9f6a4a2fad9785b` and only the corrected frame files from `b85febaa4735c9916a526598b8ba06d0db07919d`. Do not import the frame branch's older scope dependency. Reconstruct root evidence, users, binary identity, proof, source-policy identity, all limits, and the ordered register profile from raw inputs.

The six fields are RDI, RSI, RDX, RCX, RAX, and RSP. Only four are argument registers. No additional argument, type, provider, branch-condition, or complete indirect-target fact follows.

For each executed position, check limits and classify the visit. Confirm the previous attempt with immediate `T`. Check the pending ordinary successor, branch destinations, or route position and the current witness. Then emit `C`, all applicable `E` roles, and the current `A`, `J`, or `R`. Use one snapshot for shared roles. Root activation must pass its current guard before it can produce an admitted role bundle. A failure may retain diagnostic bytes but exports no local facts.

Count the root activation and valid continuation resumption as selected visits. Count the root-return confirmation as opaque external. Count other pre-root and post-root visits outside the window. Keep counting and detecting root reentry after closure. Bound total frame nodes, including closed nodes. Keep pending transfer and route state per process. Never reuse them across cases.

Check translated instruction size and bytes for each relevant execution. Keep validation with that translation's callback data. A dormant translated mismatch does not reject merely because translation ran ahead. A later relevant execution must reject it. Do not reuse the archived collector's per-site `checked` Boolean as proof for a different translation.

Use the complete PT_LOAD memory envelope to exclude holes and non-executable original-image positions from external classification. QEMU's start and end code fields can support the existing checked executable-file bias. Its entry field can describe the interpreter. The pinned [loader source](/Volumes/PhoenixWork/tmp/m2-guest-loader-static-sol/sources/qemu-9.2.0/linux-user/elfload.c:3903) makes that distinction explicit. An external position still has unknown provider identity. The separate lazy-transit profile remains unimplemented.

Keep all candidate bounds, including caller-supplied lower bounds. The 16 MiB worker binary bound wins over the static parser's 64 MiB bound. The 32 MiB observed-outcome cap can reject an otherwise valid sandbox result. Report that refusal. Check source, table, header, diagnostic, plugin, and compiler resource limits before the corresponding work. The proposed compiler limits remain unmeasured.

Keep original-code witnesses, generated observer headers, collector sources, plugins, and receipts outside reconstructed C and package archives. Preserve SPEC section 5 checks. Keep the QEMU 9.2 observer separate from the accepted QEMU 8.2.2 and Rosetta oracles. Do not change archived v1 files or their meaning.

**Implementation order.**

1. Port the exact scope and corrected frame files into a later implementation worktree. Run their combined host checks. Keep the missing full capture review open.
2. Implement complete data reconstruction, fixed native declarations, the pure header renderer, and an independent decoder. Add retention and exact lower-bound controls.
3. Implement build consistency checks, trusted issuance, cache rules, source closure, and compiled-table inspection. Mock worker transactions in pure host tests. No mock result can authorize production.
4. Implement the fixed native collector and launch adapter against the approved contracts. Preserve the raw/default APIs. Add the outer production entry point and explicit test-only calibration types.
5. After the Author releases the VM, compile and run the full frozen public matrix. Use per-trial identities. Complete independent implementation, source-closure, capture, and native-platform reviews before recovery or localization can consume the result.

The pure units in steps 2 and 3 can proceed while full capture review is blocked. The collector state machine can be developed against synthetic contracts. Production integration cannot bypass that review. This design approval closes only the transport architecture decision.
