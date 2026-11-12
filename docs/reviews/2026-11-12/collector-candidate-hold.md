# Collector transport design report

The verdict is **HOLD**. The preferred candidate is a generated typed `const` C header, compiled with fixed native source. A trusted worker build receipt binds the source inputs to the actual plugin. The candidate has no required Astra design verdict, implementation, or live result.

[design.md](design.md) defines the algorithm, transport decision, trust boundary, and identity dependencies. [api.md](api.md) defines immutable records, bounds, receipt fields, failure rules, and integration paths.

The separate full capture review remains open. This task does not certify `9672a0f`, replace that review, approve the parent options proposal, or complete SPEC section 9.

## Required role and task boundary

The fresh Astra process was requested with `-m gpt-6-astra -c 'service_tier="default"'`. The installed CLI configuration also used `service_tier="default"`. These are requested launch settings for Standard service. They do not independently attest model routing or service tier.

The process returned HOLD. Its file-access error was `sandbox-exec: sandbox_apply: Operation not permitted`. It reported that it could not read the required inputs or confirm artifact writes. Its shell exit was zero, but its response was a failure result. No design approval follows from that exit code. The process was not retried. Safety settings were not changed.

The parent read the required public sources and wrote these candidate documents. They are not an Astra verdict. The direct Astra task prohibited further agents. This task did not delegate corpus work.

The owner resumed this task on 2026-11-12. No earlier interrupted run, old event file, or session history was read. Existing dispatch and event files in the destination directory were not used or changed. The current failed process's final response is saved in [astra-final.md](/Volumes/PhoenixWork/tmp/m2-collector-transport-design-astra-resume-20261112/astra-final.md).

The [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md) supplied the Investigation workflow. Its applicable explanation and prose guidance was used. The latest user restrictions excluded history access, repository progress edits, source changes, and nested work. ASD-STE100 remains the writing standard. `throughput checkpoint: n/a, read-only investigation`.

## Work performed

The parent read AGENTS.md and SPEC.md in full, including after context compaction. It read every named public design and report. It read the exact scope, frame, and capture source inputs through their Git revisions. It read the tracked archived observer, recipe, public fixtures, and controls. It read the specified main wire, mapping, plan, physical-transfer, runtime, and tool-pin inputs.

[Source identities](/Volumes/PhoenixWork/tmp/m2-collector-transport-design-astra-resume-20261112/source-identities.json) record the exact main revision, source revisions, file lengths, and SHA-256 values for the core input set. The archived files in that manifest matched their tracked bytes at `c76cc598add3e5e74ca208fcceb95badafab13fc`. This is an input-identity check. It is not a test of collector behavior.

Main was clean at `3939fbc0d928d7701b289d559835bb466497a69c`. No source or tool pin was changed. No target, Docker command, Ghidra command, compiler, test suite, or runtime control ran. No commit or push occurred. The private Author retained the VM. No sealed source, held-out input, or private Author output was read.

Only the task's authorized audit and temporary directories received task artifacts. No accepted oracle image or archived v1 file was modified. No Phoenix result count or runtime success is reported.

## Decisive evidence

| Evidence | Design consequence |
| --- | --- |
| `main-window-six-v1` baseline, lifecycle and first-live-gate sections | Preserve every-position guards, exact next PC, root anchoring, six-field snapshots, role order, limits, callbacks, and complete outcomes. A transport change cannot reduce this algorithm. |
| `09e984b`, `ScopeSelection`, `TransitRoute`, and `TransitInstruction.positions` | The header must retain complete routes and every route-position membership. A selected-address list is insufficient. |
| `09e984b`, `_user_rule`, plus its review | Ordinary raw translation must be complete and faithful. Positive operation shapes and exact NOP forms do not independently prove semantics. Keep those assumptions visible. |
| `b85feba`, `_reduce`, `_local`, and corrected review | Every rejection has empty local output. The older local-salvage rule is not current. The frame bound counts closed nodes as well as active nodes. |
| `9672a0f`, `RuntimeManifest`, `guard_profile_sha256`, and raw admission interface | Source and plugin digests enter the runtime digest. That digest cannot be compiled into the same plugin. Use the acyclic build receipt and separate deployment record. Treat these files only as interface inputs. |
| Narrow data-format report | Runtime bytes must be canonical. The existing receipt parser permits equivalent JSON encodings. Hash exact saved bytes and preserve that parser distinction. |
| Archived `observer.c`, `translate`, `initialize`, `read_guest`, and `finish` | API 4 supports instruction callbacks, size/byte checks, six register handles, bounded reads, and atexit. Archived v1 behavior does not establish a production schema 2 collector. |
| Loader report, pinned QEMU header and `cpu_memory_rw_debug` read path | Preceding-write visibility is not guaranteed by the public memory-read contract. Fresh eight-byte control reads need separate evidence. Production remains HOLD until that requirement is resolved. |
| Loader report, TaskState queries and mapping survey | Eager external classification can remain outside the checked original-image envelope. It supplies no provider identity. The separate lazy map requirement must not be imposed on this narrower baseline. |
| Main `Invocation.environment`, overlay checks, launcher, and worker | Keep the fixed environment and complete-outcome runner. Do not add `LD_BIND_NOW`. Use an already eager original or retain the lazy rejection. |
| SPEC sections 5 and 6.1 | Keep original-byte evidence, collector source, and plugin outside the reconstructed C project. Preserve the agent-sealed process. |

Bounded text remains possible, but it needs a second complete native grammar and allocator. No supplied proposal proves that this parser preserves all scope semantics. The typed-header candidate removes that large runtime parser. It adds a bounded renderer and a worker compilation contract. The build limits remain unmeasured.

The worker, renderer, compiler, plugin, QEMU, launcher, and supervisor remain trusted components. The receipt proves a checked relationship only under that process boundary. A matching digest supplied by an untrusted caller is not process attestation.

## Executable host-control plan

The following commands are a future control plan. They were not run in this task. The first block is read-only and can check the exact fixed inputs now. It does not run Python package imports or targets.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
cd "/Volumes/PhoenixWork/phoenix"
test "$(git rev-parse HEAD)" = 3939fbc0d928d7701b289d559835bb466497a69c
test -z "$(git status --porcelain=v1)"
git show 09e984b8608743d87ce9b323a9f6a4a2fad9785b:phoenix/observe/scope.py | shasum -a 256
git show b85febaa4735c9916a526598b8ba06d0db07919d:phoenix/observe/frames.py | shasum -a 256
git show 9672a0f414e6fe128f8a1763c66694f551f2e2f5:phoenix/observe/admission.py | shasum -a 256
```

Expected source hashes, in that order, are:

```text
0cb93cadb4657dfeb776293fe823da439eb186c71978f9c74a7d0c1533867ef4
08a60db74fdc7d03445b11bfe85ae6f7945d68f8acc8a5bbab042a211030c54b
9fab8a358b5f7181bcab69bf7c7a00f7274ccb44c0658a7a6d9348908efd9082
```

The next block requires a later authorized integration worktree. It must contain the exact reviewed scope files, corrected frame files, separately reviewed capture files, and the new implementation. Those conditions are not met by fixed main. Set `PHOENIX_COLLECTOR_CHECKOUT` to that worktree. Use its existing locked Python 3.12 environment. Do not install or update dependencies as part of these commands.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
: "${PHOENIX_COLLECTOR_CHECKOUT:?Set the reviewed integration worktree}"
cd "$PHOENIX_COLLECTOR_CHECKOUT"
export TMPDIR="/Volumes/PhoenixWork/tmp/m2-collector-transport-design-astra-resume-20261112/host-controls"
export PYTHONDONTWRITEBYTECODE=1
export HYPOTHESIS_STORAGE_DIRECTORY="$TMPDIR/hypothesis"
export MYPY_CACHE_DIR="$TMPDIR/mypy"
mkdir -p "$TMPDIR"
test -x .venv/bin/python
test -f tests/test_observe_collector_data.py
test -f tests/test_observe_collector_build.py
test -f tests/test_observe_collector_binding.py
.venv/bin/python -B -m pytest --rootdir="$PWD" --confcutdir="$PWD/tests" \
  -c "$PWD/pyproject.toml" -p no:cacheprovider --basetemp="$TMPDIR/pytest" \
  tests/test_observe_plan.py tests/test_observe_wire.py \
  tests/test_observe_mapping.py tests/test_transfer_evidence.py \
  tests/test_observe_scope.py tests/test_observe_frames.py \
  tests/test_observe_admission.py tests/test_observe_collector_data.py \
  tests/test_observe_collector_build.py tests/test_observe_collector_binding.py
.venv/bin/ruff check --no-cache phoenix/observe tests/test_observe_collector_data.py \
  tests/test_observe_collector_build.py tests/test_observe_collector_binding.py
.venv/bin/ruff format --check --no-cache phoenix/observe \
  tests/test_observe_collector_data.py tests/test_observe_collector_build.py \
  tests/test_observe_collector_binding.py
.venv/bin/mypy --strict --cache-dir "$MYPY_CACHE_DIR" phoenix/observe \
  tests/test_observe_collector_data.py tests/test_observe_collector_build.py \
  tests/test_observe_collector_binding.py
```

Before execution, review imported test fixtures for target or VM use. The three new host modules must use synthetic records and fake worker responses. Their host commands must not start the live runner. The later repository quality gate must also pass. The focused command does not replace coverage, the full source-port checks, or the missing capture review.

Required host matrix:

| Group | Positive control | Negative control and required result |
| --- | --- | --- |
| Exact source ports | Reviewed scope and corrected frame hashes remain exact | Older scope dependency, changed file, or changed source closure fails identity checks. |
| Full data | Independently decode rendered tables and recover every source field | Delete a site, role, guard, route position, route user, gap, root field, witness byte, geometry field, or limit. Reject. |
| Shared routes | Two calls retain all shared-prefix and shared-suffix memberships | Deduplicate by terminal or symbol, swap position, or authorize an inactive route. Reject. |
| Canonical data | Same validated inputs produce identical data and header bytes | Duplicate/unknown JSON key, Boolean address, float, overflow, reordered canonical tuple, or unsupported variant rejects. |
| Generated C | Fixed declarations represent valid text and byte values | Quotes, backslashes, newlines, Unicode, comment markers, and source directives remain inert byte initializers. No generated code appears. |
| Bounds | Exact lower and maximum limits apply before work | One extra byte, record, frame, callback, route step, or generated byte rejects before the bounded operation. Fake compiler is not called after a preflight refusal. |
| Identity order | Build graph has no reference to its own output | Embed G in its header, Q or T in compiled source, or final deployment in its calibration evidence. Reject the schema/dependency check. |
| Existing identities | Existing policy and admission functions retain their encodings | Replace them with new source-manifest hashes. Reject. |
| Worker build | Independently rebuilt sources and pinned compiler produce a complete mocked receipt | Wrong binary, lift, proof, plan, scope, renderer, fixed C, header, flags, compiler, sysroot, image, or API hash rejects. |
| Build output | Expected native shared-object metadata and exports | Wrong architecture, link, extra dependency, missing export, nonzero exit, timeout, oversized diagnostics, or output cap rejects. |
| Cache | Trusted K and matching actual plugin can be reused | Caller-selected trust pin, stale plugin, changed scope, corrupt file, or different output for one K rejects. |
| Multiple cases | Same K/plugin serves different invocation digests | Carry a root anchor, sequence, pending route, or counter across cases. Reject. Target environment must be byte-equivalent. |
| Trust boundary | Controller supplies independent deployment and execution pins | Fully self-consistent caller-authored receipts without trusted provenance reject. |
| Raw reconstruction | Raw original/lift/mapping rebuild exact full plan and scope | Forged checked dataclass or regenerated checksums on changed source cannot bypass the raw boundary. |
| Runtime association | M contains the installed admission, scope policy, C, and Q identities | Swap observer QEMU, accepted image, guest runtime, launcher, worker, production boundary, or launch record. Reject. |
| Capture formats | Current runtime canonicalization and receipt parser behavior remain explicit | Treat an alternative receipt encoding as the same saved bytes. Reject its execution-receipt digest. |
| Case association | Exact invocation and all complete-outcome bytes match | Swap case/repetition, drop result, duplicate result, or alter termination, stream, path, data, or mode. Reject. |
| Failure export | Corrected frame failures export no local facts | Restore local salvage after a frame failure, or admit a partial artifact. Reject. |
| Scope limits | Eager-only profile and empty contracts | Lazy resolver profile, provider assertion, invented branch condition, new ABI claim, or nonreturn contract rejects. |
| Packaging | Collector artifacts remain auxiliary | Put original code witnesses, collector C, or plugin in the reconstructed project. Packaging/integrity control fails. |

Property tests must generate nested records, boundary values, shared-route memberships, invalid slices, and independent single-field mutations. Use an independent decoder or specification oracle. A test that merely calls the renderer twice is insufficient.

A later compiler control must compile representative generated headers against fixed declarations. It must inspect the resulting typed data through a test-only host tool. Run that tool only in its authorized build environment. Test compiler-resource refusals independently. This task supplies no compiled result.

## Live-control plan

Live work must wait until the private Author releases the VM and separate authorization permits it. Freeze a public case manifest, public source identities, original binary identities, and expected controls first. Production addresses must come from stripped binaries and checked lifts. Public source can define expected behavior; it cannot replace missing address proof.

The required new gate driver is proposed as `phoenix.observe.public_gate`. It is not present or implemented. Its future CLI contract is:

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
: "${PHOENIX_COLLECTOR_CHECKOUT:?Set the reviewed integration worktree}"
: "${PHOENIX_PUBLIC_GATE_MANIFEST:?Set the frozen public manifest path}"
: "${PHOENIX_PUBLIC_GATE_OUTPUT:?Set a new external-drive result directory}"
cd "$PHOENIX_COLLECTOR_CHECKOUT"
.venv/bin/python -B -m phoenix.observe.public_gate \
  --manifest "$PHOENIX_PUBLIC_GATE_MANIFEST" \
  --output "$PHOENIX_PUBLIC_GATE_OUTPUT" --repetitions 3
```

The command must reject an existing output directory, an unfrozen manifest, unknown fields, missing cases, or changed pins. The manifest binds every public case, expected supported/rejection status, source and binary identities, build receipt, candidate runtime, fixed invocation, accepted oracle identities, and control implementation. No image tag is an identity. The driver uses the accepted sandbox and complete-outcome runner. It saves raw and partial artifacts before parsing. It never reads held-out inputs.

Calibration trials use their own explicitly test-only context. They cannot create production evidence for recovery. The completed calibration report binds the candidate runtime and exact trial artifacts. It then becomes an input to the final production deployment record. This order prevents a calibration/deployment digest cycle.

The gate must retain all nine groups in the baseline's “First live gate and capability ledger” section:

1. Use the unchanged archived public fixture mechanisms for GCC and Clang at O0 and O2. Cover original and unchanged variants, both operations, and lengths 0, 1, 2, 7, 8, and 9. Retain wrong-target and wrong-count controls. Generate fresh schema 2 captures.
2. Include every actual main call, selected user, return, continuation, and required import route. Include `strcmp` and `ferror` when emitted. Record compiler-emitted helpers, including an unsupported route, explicitly. Do not shrink the scope to the old selected sites. Report optimized-away mechanisms.
3. Cover invalid arguments, early return, empty input, cap input, and stdio errors. Retain oracle-sensitive cases, unsupported paths, and collector failures in the frozen accounting.
4. Add a separate non-tail recursive public fixture. Verify recursion in each compiled control. Use repeated call/continuation addresses, a caller stack frame, four distinct integer parameters, and distinct RAX bits. This checks six captured fields. It does not establish six argument registers.
5. Cover direct and indirect internal calls, shared role sites, exact entries, direct GOT imports, and supported eager PLT routes. Retain default lazy resolution as a rejection. Use an already eager original for the positive. Do not modify the fixed invocation environment.
6. Cover omitted startup and teardown outside the root window. Then execute an omitted function during Active and require rejection. Reenter a selected function from an opaque external interval and require `unknown_callback`.
7. Build separately identified collector mutations for missing role emission, duplicate entry, wrong snapshots, wrong root anchor, disabled omission guards, missed callback reentry, and wrong shared-role order. Delete a complete leaf activation and recompute its wire/receipt digests. The native control must still fail its independent expected behavior. A parser-only check cannot detect every coherent omission.
8. Compare the full observer outcome with the unchanged accepted QEMU 8.2.2/Rosetta outcome. Independently alter stdout, stderr, exit, signal, path, bytes, and mode. Require rejection. Repeat supported comparable cases three times. Compare stable frame relations and counts; do not require relocated pointer values to match across processes.
9. Run archived v1 wrong-API and missing-register controls unchanged. Add corresponding schema 2 controls with separate identities. Preserve partial outcome and wire artifacts. A v1 PASS proves only preservation of that v1 control.

Add these production-specific paired controls:

| Mechanism | Required positive and negative |
| --- | --- |
| Eight-byte freshness | Store a distinct stack word immediately before the sampled root/return boundary. Check the actual collector read. Change a return word after root entry. The independent anchor comparison must reject. Clear scratch before each attempt. Test unreadable and page-crossing words; partial bytes must not be reused. |
| Register API | All six handles return exactly eight bytes. Missing, duplicate, wrong-width, or failed reads reject. One visit reuses one snapshot for its full role bundle. |
| Exact next PC | Transfer confirmation is the immediately next executed callback, including external destinations and translation boundaries. An intervening or missing T rejects. |
| Active guard | Ordinary fallthrough, both conditional outcomes, local direct branches, and route positions agree with exact bytes. Wrong successor, another route's position, unsupported active opcode, and original-image holes reject. |
| Dormant translation | QEMU can translate a dormant unsupported or mismatched position without executing it. Do not reject it solely for translation. Execute it during Active and require rejection. |
| Lifecycle | One root closes through R/T and independent post-return RSP. Missing T, wrong anchor, open child, second root activation, or exit-only closure rejects. Post-root monitoring remains enabled. |
| Counters and limits | Exercise exact boundaries and one over. Include many closed sequential frames, external loops, post-root loops, retranslations, and wire/footer space. No silent truncation or reclassification is allowed. |
| Native omission | Disable an entire activation or ordinary guard in a mutated collector. Independent control expectations must catch the missing behavior, even when all declared digests and counters are recomputed. |
| Build association | Correct plugin serves several fresh cases. Swap a same-binary/different-scope plugin, header, receipt, launch file, or runtime and require refusal before activation. |
| Termination and output | Normal complete return yields retained complete artifacts. Timeout, supervisor kill, missing atexit, write failure, duplicate response, malformed outcome, and unfinished wire reject. |
| Architecture | Native x86-64 and AArch64 CI run the public controls. Each architecture has its own plugin/toolchain identity. Emulation evidence is not native verification. |

Retain baseline paired rows 01–48. Rows 41–42 use the corrected no-local-export rule. Rows 39–40 are future nonreturn-contract controls; this eager profile has an empty table and must reject attempts to enable them. Do not count an unavailable contract as a positive capability.

Finite read controls are necessary but do not establish a universal freshness guarantee. The exact missing evidence is ordering between prior guest stores, the pre-instruction callback, and `cpu_memory_rw_debug`. Establish a sufficient contract from the pinned source or retain HOLD. If unavailable, separately design the minimal synchronized eight-byte read extension described in design.md. Do not silently change QEMU or tools.lock.

Each capability is labelled `exercised-positive`, `exercised-rejection`, `not-exercised`, or `unsupported`. All production live capabilities in this task are `not-exercised`. Lazy resolver transit, callbacks, tails, nonlocal returns, extra registers/ABI facts, provider identity, and general memory claims remain unsupported by this baseline.

## Integration order and remaining gates

1. Finish the current source ports and their full host checks. Preserve the exact reviewed scope files. Keep corrected frame semantics. The parent has not run those checks here.
2. Obtain the separate missing full capture review. The narrow parser report cannot close it. No blocked review was retried in this task.
3. Obtain a completed required Astra collector/build-binding design verdict. The fresh process's file-access failure leaves this gate open.
4. Implement and review the pure data renderer, source closure, build receipt, cache, and outer production admission gate. Prove the identity graph remains acyclic.
5. Implement the fixed native collector and worker adapter. Establish the eight-byte freshness contract. Keep eager and lazy identities separate.
6. After VM release, run the complete frozen public live matrix. Retain every rejection. Establish actual build limits, calibration identities, oracle equality, and native CI evidence.
7. Review the complete production diff and its integrity controls before recovery or localization consumes admitted trees. Preserve raw/default behavior and the accepted oracle/archive pins.
8. Continue the remaining milestone work with its required evaluation. SPEC section 9 still requires M4, the T0–T3 report with every baseline, costs and failure categories, publication, and replay of each headline number through `phoenix-eval`.

This report supplies a concrete candidate under HOLD. It supplies no runtime success, full capture verdict, milestone acceptance, or verified Phoenix completion.
