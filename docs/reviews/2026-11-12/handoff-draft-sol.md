The goal is to preserve Phoenix for the timed pause. A new agent must then be able to resume the original goal through `SPEC.md` section 9.

**PASS for the exact public draft and its archival records at `8579da39c352c946dab60df11d7a4aba7feec544`.** No blocking draft or archival defect was found. The final pause is not certified. The principal agent must observe and record the final process, queue, private Author, VM, goal, checkpoint, and pending-file state itself. This draft review cannot establish those later facts.

This review used the requested GPT-6.1 Sol role and Standard service instruction. These are requested launch settings. I did not inspect session history or independently attest model routing. No nested model, agent, model CLI, API call, or dispatch wrapper ran. I did not query private process or VM state. This review gives no milestone approval or permission to resume.

The local identities passed these checks.

| Item | Exact identity or result |
| --- | --- |
| Frozen checkout | `/Volumes/PhoenixWork/worktrees/m1-preflight-review-2` |
| Draft commit | `8579da39c352c946dab60df11d7a4aba7feec544` |
| Draft Git tree | `f382618286ee5d018d2821b41a0e2976e22f2c55` |
| Implementation baseline | `2c9934a6b96004536c5db98e844dce180c958c25` |
| Earlier handoff | `e1f0fff2caee0c81056b29b5b759542eb697e29d` |
| Branch | `agent/thread-handoff` |
| Peeled `m0` | `4ef231a1bbdc8d572e06dd5a44efff620dda0e97` |
| Peeled `m1` | `6897e4753d8acedfae57af63e6426faf116bed2e` |
| Working state | Clean before and after reconstruction. |
| Non-documentation comparison | All 181 tracked paths outside `docs/` have the same Git blobs and modes as the baseline. |
| Real index | SHA-256 `c139ded4dbf354432b74c1195551163ea8c383180a173bd699f19bfb2cbb2ca3` before and after reconstruction. |

The local remote-tracking refs identify the named draft and main commits. No fetch or network operation ran. These observations do not establish current server state. The tag targets match the required immutable commits. No tag was changed.

The log preservation checks passed. The earlier handoff log has 55,004 bytes and 889 lines. It is an exact byte prefix of the draft log. Its SHA-256 is `872067964b73b71267af45efc75a702e689dbac526b693f10e7d2f537a1cadee`. All 948 main log lines remain in order in the 1,084-line draft log. The verification records the draft line position for every main line. Main's complete log is an ordered line sequence, not one contiguous byte block. The draft log has SHA-256 `30982fa91cc4510a609187a5d7fd50b6c59e92adc80e549ef585040fb9d960b5`. STATUS matches main exactly. All 27 earlier checkpoint and review files retain their earlier Git blobs and modes.

The independent archival reconstruction passed every file check.

| Patch | Recorded base | Files |
| --- | --- | ---: |
| `m1-analyze.patch` | `55626073e4693193e5e4a64e4317e31767c9d73a` | 2 |
| `m1-compiler-integrity.patch` | `80f4de0e3cc274602dd7dee7da6a7032e1080423` | 5 |
| `m1-heldout-pair.patch` | `80f4de0e3cc274602dd7dee7da6a7032e1080423` | 2 |
| `m1-immutable-inputs.patch` | `2ce518abd1548b9fd3f70f2d2530ab20c0f6fbc1` | 8 |
| `m1-ingest.patch` | `4f5e2e4d1f4fe61eaa7be0ad9107c16c49395fef` | 2 |
| `m1-integrity.patch` | `4f5e2e4d1f4fe61eaa7be0ad9107c16c49395fef` | 2 |
| `m1-lift.patch` | `4f5e2e4d1f4fe61eaa7be0ad9107c16c49395fef` | 4 |
| `m1-pipeline-identity.patch` | `2ce518abd1548b9fd3f70f2d2530ab20c0f6fbc1` | 4 |
| `m1-preflight-review.patch` | `b85febaa4735c9916a526598b8ba06d0db07919d` | 5 |
| `m1-development-evidence-fix.patch` | `9672a0f414e6fe128f8a1763c66694f551f2e2f5` | 5 |

For each patch, I created a separate temporary Git index and object directory under the assigned external temporary directory. The original object directory was read through `GIT_ALTERNATE_OBJECT_DIRECTORIES`. The real index and worktrees were not used as patch destinations. The procedure was:

1. Verify the patch SHA-256 against its manifest.
2. Set `GIT_INDEX_FILE` and `GIT_OBJECT_DIRECTORY` to that patch's temporary paths.
3. Run `git read-tree <recorded-base>` with those variables.
4. Run `git apply --cached --unidiff-zero --check <patch>`.
5. Run `git apply --cached --unidiff-zero <patch>`.
6. Require the changed path set to equal the complete manifest file set.
7. Read each result blob and mode from the temporary index.
8. Compare every byte count, SHA-256, and executable mode with the manifest. Save the reconstructed bytes in the temporary directory.

All eight old patches and all 29 old source files passed. Those 29 files also match the explicitly listed original public files and their executable modes. `scripts/build-integrity` has executable mode `100755`. The other 28 source files have mode `100644`. Both historical port patches and all 10 port files passed. The port files have mode `100644`. The two copies of the formerly untracked scope ADR are included. These ports are historical backups. The actual ports were later committed. No archival patch was applied to main. Existing scratch outputs were not moved or added to the public backups.

All 18 published review copies passed byte-count and SHA-256 checks against their manifests. Each copy is also byte-identical to its explicitly named original public report. This includes both earlier and later review manifests. All five interrupted collector records match their manifest and explicitly named originals. The collector manifest retains `state=interrupted`, `verdict=none`, and `approved=false`. File identity and a historical exit marker do not establish process authority or design approval. The exact source paths, expected hashes, actual hashes, file sizes, modes, and reconstruction paths are in [final-check.json](final-check.json).

The draft preserves the following limits.

| Requirement | Evidence and assessment |
| --- | --- |
| Original scope | HANDOFF lines 11-18 and 259-264 retain the full section 9 goal. M2 through M4, all baselines and ablations, publication, and headline replay remain open. SPEC itself is unchanged. |
| Accepted M1 | HANDOFF lines 60-69 and STATUS retain the exact original and replay run IDs. Phoenix retains 19/20 behavior passes, 18/20 integrity passes, and 17/20 fully successful variants. Both `embedded_text` failures and the behavior failure remain explicit. Ghidra-raw retains 8/20. STATUS retains its 12 compiler failures. Block-entry coverage is separate from source branch coverage. I checked these disclosures against public progress records. I did not open private runs or repeat the measurement. |
| Full capture | HANDOFF lines 147-157 retain OPEN after provider screening. The blocked task has no code verdict. The parser-only PASS does not replace full review, runtime association, calibration, or live acceptance. Screening must remain in effect. |
| P1 authority | HANDOFF lines 97-110 retain code-only acceptance, evaluator-owned reduced limits, complete source origins, actual shared users, four native compiler contexts, and the open P2-P9 work. Both public P1 reviews preserve the worker's prohibited checksum reads. The design output-directory exception is separate. Neither exception supplies process assurance. |
| Readers and hashes | HANDOFF line 81 rejects process, source-fact, and behavior authority from a pure reader. The verified review copies also distinguish identity from trusted build issuance and semantic admission. |
| U1 and complete byte production | HANDOFF lines 119-143 retain the incomplete producer and later U4/U5 HOLDs. U1's page-rounded alias and RELRO assumptions still require explicit treatment. The final record must carry any page-assumption HOLD explicitly. A passive reader or Darwin layout check cannot supply Linux compiler or runtime evidence. |
| Runtime and images | HANDOFF lines 175-204 distinguish native CI from the pending same-revision Mac comparison. The accepted M1 image and worker identities remain explicit. Every original or reconstructed target must run only in Linux containers. Host static checks do not establish target behavior. |
| Native parent evidence | The named `verified-summary.json` identifies workflow `43322747514`, exact main, the stated worker digest, two native run IDs, seed, public case counts, and outcome digests. It leaves the Mac comparison pending. I checked the summary's consistency with the draft. I did not read archives or repeat native checks. |
| Private corpus | HANDOFF lines 208-224 preserve private source, held-out, archive, run, and Author-output limits. T1's narrow 304-316 C LOC range remains explicit. T2 is an incomplete 23:04 UTC adequacy snapshot, not a Phoenix score or final commitment. T3 has five source-screened selections and five pending Linux runtime qualifications. The knowledge cutoff is not asserted to be an independently verified training completion date. |
| Model and service limits | HANDOFF lines 226-238 require at most four models including root, Standard service, Fast disabled, nested models disabled, and unchanged guards. Requested service is not routing attestation. This review started no additional model and did not measure the total active model count. |

The dated unit rows are acceptable draft snapshots. The table says "Current draft state". The text says "at this draft checkpoint" and requires actual final-state verification. The final pause section is explicitly pending. The P1, byte diagnostic, U1 writer, adapter design, and private Author status can change after this revision. Their stale draft values must not become final shutdown claims.

The final-update checklist remains mandatory for the principal agent.

1. Stop new dispatch at **2026-11-13 00:56:47 UTC**. Complete the pause by **2026-11-13 01:11:47 UTC**. Keep the date with both times. The watcher writes markers. It does not kill processes.
2. Stop and verify all model workers and queues. Include review processes, writers, adapter design tasks, and queued wrappers. Record actual end state. Do not infer it from an exit file, source reader, digest, or this report.
3. Stop the private Author safely through its allowed control path. Preserve its checkpoint and private storage. Read only approved aggregate status and handoff records. Do not inspect private contents to create a backup.
4. Stop Colima only after the Author has stopped safely. Record actual VM shutdown. Preserve the VM disk. This reviewer has made no such observation.
5. Inventory all final pending public files. Include staged, unstaged, and untracked files. Include every new ADR. Save exact bases, complete patches, hashes, sizes, and executable modes. Independently reconstruct those new backups. Keep scratch outputs outside public backups. Do not publish private material.
6. Replace stale work-unit rows with exact final tips and review verdicts. Preserve every original HOLD and setup failure. Carry U1's page-assumption HOLD and the complete-byte-producer HOLD until their exact gates pass. Do not convert a diagnostic PASS into complete-production approval.
7. Update HANDOFF, STATUS, and LOG with observed final facts. Record public commits and actual push results. Preserve both log sequences and immutable M0/M1 tags. Keep the full capture review OPEN and all source, compiler, live, and semantic authority limits explicit.
8. Publish the canonical resume checkpoint with the installed checkpoint tool. Read it back through the canonical project lookup. Check exact identities and completeness. This draft's checkpoint-read command is not proof that publication has occurred.
9. Disable the one-time automation `pause-phoenix-and-prepare-handoff`. Record its observed disabled state. Keep DRAINING and PAUSED effective. A new user instruction is required before resume. Replace the old timer configuration before any later dispatch.
10. Set the existing goal to `paused` last. Do this only after shutdown, backups, public records, and checkpoint readback are verified. Never mark the goal complete for this pause. Section 9 remains incomplete.

One review setup error occurred. The first reconstruction command omitted `--unidiff-zero`. Git rejected the zero-context immutable-input patch before the complete check could finish. The failed command and partial results remain in [commands.json](commands.json) and [verification.json](verification.json). The first script remains in `verify_archives-first-attempt.py`. The corrected command reconstructed all 39 files. No archival file or guard was changed. A manually entered timestamp in the first decision row was also wrong. An appended correction preserves that error. Command records contain actual timestamps.

I read AGENTS.md, SPEC.md, HANDOFF.md, STATUS.md, the complete LOG.md, the named parent JSON evidence, archival manifests, patches, and the installed [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md). The Prove It Works principle led to direct file comparisons. The Build the Lever principle led to the retained reconstruction script. The required leaf skills were read. User limits replaced nested review and session-audit steps. ASD-STE100 Issue 9, technical-writing, and unslop guidance govern this report.

All review writes are confined to the assigned audit and temporary directories. No target, compiler, Ghidra, Docker, Colima, Lima, network, credential, or model command ran. No dispatcher event, dispatcher stderr, dispatcher summary, Codex history, private source, held-out input, source archive, private run, Author worktree, or Author output was read. Only marker existence was checked for the review stop condition. No process-state or VM-state claim follows from those marker checks.

The explicit output list is `report.md`, `final-check.json`, `verification.json`, `verification-second.json`, `commands.json`, `commands-second.json`, `commands-final.json`, `verify_archives.py`, `verify_archives-first-attempt.py`, `finalize.py`, `todo.md`, and `decisions.tsv`. The temporary index, object, and reconstructed-file paths are listed individually in final-check.json. Pre-existing dispatcher files in this review directory are excluded from the output checksum list and were not read.
