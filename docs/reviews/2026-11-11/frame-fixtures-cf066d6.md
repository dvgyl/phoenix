The owner requires verified Phoenix completion through SPEC.md section 9 and a current GitHub handoff. This review checks the corrected public source checkpoint. The agent-sealed corpus remains outside this review.

**PASS for the corrected public source checkpoint.** F1 is closed at `cf066d69162de8657563f087b491995ca5c0a63f`. No blocking finding remains in this small correction. This verdict gives no milestone approval. It does not establish Linux behavior, SPEC.md section 9 completion, or a current GitHub handoff.

The worktree is `/Volumes/PhoenixWork/worktrees/m1-submission-recovery`. The branch is `agent/m2-frame-calibration`. The frozen revision file names `cf066d69162de8657563f087b491995ca5c0a63f`. HEAD matches that full SHA. Its direct parent is `cd59f7f6ff4fdbbdae65fcdded33b06d1dadf45c`, the revision reviewed in the complete prior independent HOLD. The correction is one commit. Initial and final status checks are empty.

The request specifies GPT-6.1 Sol and Standard as launch settings. This report does not attest model routing or service routing. This review used no nested agents and did not inspect session histories.

The complete [prior HOLD](/Volumes/PhoenixWork/audit/m2-frame-fixtures-final-sol/report.md) identifies F1 as its only blocking finding. Its `before.json`, `after.json`, `checks.json`, `final.json`, and compiler command records were read. The prior source identities and case checks agree with the unchanged bytes checked here. The [correction commit log](/Volumes/PhoenixWork/audit/m2-frame-fixture-preparation/claim-correction-commit.log) records a passed quality hook and a three-file commit. This review read that record. It did not rerun or independently attest the hook.

The complete [correction diff](review-evidence/correction.diff) changes only the fixture README, `docs/LOG.md`, and `docs/STATUS.md`. The C sources, case file, manifest, ADR 0034, compiler flags, source and case hashes, and live control code are unchanged from the parent revision. The full changed-path check establishes that this correction changes no other tracked artifact. No private file was opened to make this check.

The README no longer says that recursion changes local stack state. It states, "The live gate must verify a caller stack frame in each required build." It retains the requirement to inspect compiler output for shared roles. It also states that source shape alone cannot establish a machine instruction pattern. This closes the unsupported assertion and retains the live requirement.

The LOG addition records the prior HOLD, the text correction, and the open Linux checks. The STATUS correction keeps Linux execution and exact correction review open. These changed passages claim no execution or milestone acceptance. Historical results elsewhere in STATUS were not re-evaluated by this review.

All SHA-256 values below refer to exact file bytes. Every file matches its frozen HEAD blob. The unchanged files also match their parent blobs and the prior review's recorded hashes. Full old and new Git blob identities are in [before.json](review-evidence/before.json).

| File | Current SHA-256 | Relation to parent |
| --- | --- | --- |
| `corpus_public/mechanisms/frame-calibration/recursive.c` | `64acaea4f51059f4bf32b6ecef62ab472d375f16405e5e362241fe6aebc04fa4` | Unchanged |
| `corpus_public/mechanisms/frame-calibration/callback.c` | `f5ad05530417ee79917fd28194794c97c9aeb558d06bb6b4f5e86d4f38ac9fec` | Unchanged |
| `corpus_public/mechanisms/frame-calibration/cases.json` | `184767b8a89c741c6d7a8c0e3553efc02a19bf19b0c04ad58dfdc7fe7803a069` | Unchanged |
| `corpus_public/mechanisms/frame-calibration/manifest.json` | `53cf83e6c6d72cba2ed3deb4048a70b10e85e2761ebadc6a830c0ab7a60f12d9` | Unchanged |
| `corpus_public/mechanisms/frame-calibration/README.md` | `e04ce057fc9de496a5627f3ce9382c75d6742d2af277ca1b8dd0d89b0bfa9b61` | Corrected |
| `docs/adr/0034-public-frame-calibration.md` | `6fdf757e0fb92b4ee5baf41b7fdce7a624c1cc3986f8d76a656da969be461aa8` | Unchanged |
| `docs/STATUS.md` | `09c75074f872a0cb5d07841d306075e741591357feca0109842d82035adfdf27` | Corrected |
| `docs/LOG.md` | `46c1befb6acd81f3306c476f4f2ed40fe2c3f52786b9d1b90ec1bee34566fc6a` | Corrected |
| `AGENTS.md` | `5dc37aed176f6a9990979b29df9b771bfaedcf07df6e09c1d34a5b851216bc3c` | Unchanged |
| `SPEC.md` | `dbc3ec8aab2fb74e5bab303017208a2ed93169acc7d2fb3e5938b88b2c073671` | Unchanged |

The previous README SHA-256 was `c4b674ef4eeb66fb1e646a10596c9a4b999e263169f24e6ed4fd635c6d0bff4c`. Its Git blob was `257667f62b63b06a8d9d52ef9e02cef7d7ad3533`. The corrected Git blob is `256399eb915d9526bbab893ad961531578d71b8b`.

The complete roster was compared with an independently stated expected roster. The check rejects duplicate JSON keys. It checks fields, string arguments without NUL, canonical input hex, unique IDs, and unique fixture, argument, and input tuples. It compares every manifest field and recalculates each declared source and case hash.

| Case group | Declared cases | Checked roster |
| --- | --- | --- |
| Explicit depths | 20 | Depths 0, 1, 2, 4, and 8 each use EOF, `00`, `ff`, and `41`. |
| Default depth | 4 | No argument, with the same four input forms. |
| Early return | 5 | `9`, `bad`, empty argument, `-1`, and `2 extra`, each with EOF. |
| Callback rejection | 4 | No argument, with EOF, `00`, `ff`, and `41`. |
| Total | 33 | 29 expected supported cases and 4 expected callback rejections. |

These counts describe declared cases. They are not execution results or Phoenix success rates. Both selected-comparator and omitted-comparator scopes remain declared in the manifest. The [case roster](review-evidence/case-roster.json) contains all checked cases.

The manifest retains GCC and Clang at O0 and O2. Its common flags remain `-std=c11 -Wall -Wextra -Werror -fno-lto -fno-optimize-sibling-calls -Wl,-z,now`. Its strip flag remains `--strip-all`. The profile remains `eager-only-new-calibration`. The `archived_v1_changed` field remains false. These declarations do not prove the effects of a Linux compiler or linker.

The source-level limits remain in force. The volatile function pointer supplies an indirect recursive call. The caller uses the child result after the call. This establishes a non-tail call in the source. Scalar locals do not require a machine stack frame. Source review cannot establish register values, saved stack contents, final call instructions, or shared instruction roles.

The source uses four `uint64_t` arguments and defined unsigned arithmetic. The declared depth limit requests at most nine recursive activations. That bound follows from source analysis. It is not a measured trace. Four arguments do not test six argument registers. The parser does not declare a digits-only grammar. Do not infer rejection of every negative spelling. EOF and NUL are separate input cases but request the same numeric input value. The programs do not check stream errors.

The callback source supplies a `qsort` comparator candidate. It does not implement or prove capture rejection. The roster omits numeric overflow text, whitespace and sign variants, intermediate depths 3, 5, 6, and 7, comparator ties, and stream-error injection. These omissions limit later coverage claims. The full public gate remains larger than this roster.

The prior compiler command records contain eight successful syntax invocations. Both `/usr/bin/gcc --version` and `/usr/bin/clang --version` report Apple Clang 21.0.0, build `clang-2100.4.1.1`. They name one host compiler family. They do not establish separate GNU GCC and Clang checks, a Linux build, linking, stripping, optimizer output, or runtime behavior. This correction review ran no compiler or target check.

The exact automated verification command was run from the reviewed worktree. It exited with code 0 under Python 3.14.6.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
export TMPDIR=/Volumes/PhoenixWork/tmp/m2-frame-fixture-claim-sol
export PYTHONDONTWRITEBYTECODE=1
python3 /Volumes/PhoenixWork/tmp/m2-frame-fixture-claim-sol/verify.py
```

The verification result was as follows.

```json
{"result":"PASS","F1":"closed","unchanged_artifact_identities":"PASS","complete_case_roster":{"total":33,"expected_supported":29,"expected_callback_rejected":4},"compiler_invocations":0,"target_executions":0,"live_gates":"not-exercised"}
```

The full result is in [checks.json](review-evidence/checks.json). The [verification script](/Volumes/PhoenixWork/tmp/m2-frame-fixture-claim-sol/verify.py) is retained. [commands.json](review-evidence/commands.json) records exact Git argument arrays, working directories, exit codes, and results. For `git show` content checks, it records byte counts and SHA-256 values. The script compares those bytes in memory.

The principal Git commands were `git rev-parse HEAD`, `git branch --show-current`, and `git status --porcelain=v1 --untracked-files=all`. The script also checked the parent revision, ancestry, one-commit count, full changed-path list, full diff, and `git diff --check`. All exited with code 0. Both status checks were empty. The diff check emitted no output. The source and documentation comparisons pass in [before.json](review-evidence/before.json) and [after.json](review-evidence/after.json).

The remaining Linux and live requirements below are retained from the prior independent HOLD and the unchanged public fixture documents. The underlying design audit was not opened in this review. None of these requirements was exercised here.

1. Build both fixtures with pinned Linux GNU GCC and Clang at O0 and O2 with the declared flags. Record compiler, linker, container image, source, manifest, symbol-bearing binary, and stripped binary identities. Verify immediate binding and stripping. Preserve archived inputs, environments, default lazy-resolution rejection controls, and the sealed compiler matrix.
2. Inspect every required build for an actual caller stack frame, indirect non-tail recursion, repeated nested call and continuation addresses, four distinct argument patterns, and a distinct RAX result. Record any mechanism removed by optimization. Establish empty-function and shared-role patterns from machine evidence.
3. Obtain accepted full outcomes from unchanged QEMU 8.2.2 and Rosetta oracle engines. Use the production QEMU 9.2.0 observer with exact plugin and runtime identities. Use stripped inputs and checked lifts for production plans. Keep symbol truth separate from address derivation. Preserve raw wire, scope certificates, root anchors, receipts, partial outcomes, and rejection records.
4. Run every declared case, including early returns and rejections. Run each callback case with the comparator selected and omitted. Require capture rejection in both scopes. Admit no tree and export no local register facts. Confirm selected-entry `unknown_callback` behavior and omitted-entry guard rejection. Let each process finish. Compare stdout, stderr, exit or signal, paths, file bytes, and modes with accepted oracle outcomes.
5. Repeat comparable supported captures three times. Do not treat relocated pointers as stable values. Exercise actual collector mutations for missing roles, duplicate entry, incorrect snapshots, incorrect root anchor, disabled omission guard, missed callback reentry, and incorrect shared-site order. Give each mutation a separate plugin identity. Host parser mutations do not replace collector mutations.
6. Complete the other public gate groups. Retain archived mechanisms across required operations and lengths, all emitted main calls, error and boundary paths, internal calls, import transit, startup and teardown omissions, omitted active execution, and full-outcome mutations. Preserve v1 wrong-API and missing-register controls. Add schema 2 controls with separate identities. Retain rejected and unsupported cases in the accounting. The prior HOLD identifies public paired controls 01 through 48 as part of that wider gate.

General callbacks remain unsupported by the first profile. No source or syntax check closes these live requirements. M2 and later acceptance, real-hardware cross-checks, and SPEC.md section 9 remain outside this PASS. Section 9 still requires M4, the T0 through T3 held-out report with all baselines and costs, artifact publication, and replay of every headline result. GitHub state was not queried or changed. This review cannot establish a current GitHub handoff.

AGENTS.md and SPEC.md were read in full. The requested [Poteto mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.135/skills/poteto-mode/SKILL.md), its Codex mapping, Investigation playbook, and applicable review and writing skills were read. The Prove It Works principle required checks against committed bytes and current Git state. The user prohibits nested agents, source edits, and external actions. Those limits take priority over skill delegation and edit steps. The [task checklist](/Volumes/PhoenixWork/tmp/m2-frame-fixture-claim-sol/todo.md) records the exceptions. Unslop and Technical Writing guided the report prose.

The external volumes are mounted. `df -h / "/Volumes/Extreme Pro" /Volumes/PhoenixWork` showed 16 GiB, 83 GiB, and 23 GiB available. STATUS records an internal baseline of 14,432,616 KiB. The current internal free space exceeds that baseline. All review writes stayed in the two permitted external directories.

This review made no repository change, commit, push, or milestone tag. It ran no Docker command, linker, target, Ghidra process, provider call, pipeline, or phoenix-eval. It read no sealed source, held-out input, private Author output, session history, or unrelated audit directory. Input identities are in [inputs.json](review-evidence/inputs.json). The final state check is in [final.json](review-evidence/final.json). Review output hashes are in [review-artifacts.sha256](review-evidence/review-artifacts.sha256).
