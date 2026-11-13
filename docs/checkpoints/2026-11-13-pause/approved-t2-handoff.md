T2 is complete. Updated at 2026-11-13T00:48:17.017610+00:00.

The batch has ten programs and 60 stripped compiler variants. All variants passed the fixed input set under both emulators. The batch has 43,276 fixed inputs. All 20 generator replays passed. All 60 final rebuilds reproduced the validated binary hashes.

Each program passed at least 85 percent source branch coverage and 90 percent detection of non-equivalent mutants. Aggregate branch coverage is 18590/21685. Aggregate mutant detection is 305/310. The held-out set did not detect 5 non-equivalent mutants. Separate witnesses proved their non-equivalence. These witnesses did not count as held-out kills. The minimum program coverage is 2742/3225. The minimum program mutant detection is 29/32. C source sizes range from 1,502 to 4,036 lines. These are corpus adequacy counts, not reconstruction scores.

1 mutant confirmation used a declared rule for an emulator diagnostic. All raw evidence is preserved. Original-program comparisons used no normalization.

The corpus is agent-sealed on the honor system. No reconstruction results were used. Astra and Standard were launch settings. They are not independent routing attestation.

Release manifest: `/Volumes/PhoenixWork/sealed/release/t2/manifest.json`.

Release manifest SHA-256: `cd60cf5a1bdc7106c02bfad3c0ab7820fd6a3d7a8aaab757e234fe958b63e78f`.

Source archive SHA-256: `5f3b67cce71ad1ec6e7876889ff1e609a4072b2feb833fb23f2ba2f072fd8788`.

Held-out archive SHA-256: `27ea3363f4cd1ef284db6b3ec0ff24c5d7bb7cf3ca8fcfc20e5cd6f4211e6574`.

The source archive is `/Volumes/PhoenixWork/sealed/t2-source.tar.gz`. The held-out archive is `/Volumes/PhoenixWork/holdout/t2-inputs.tar.gz`. Keep both private until the specified publication stage.

The evaluator needs capacity for 9,216 inputs and 30,700,244 encoded input bytes per program. The Author used caps of 16,384 inputs and 32 MiB. The per-case sandbox limits did not change. No pipeline code changed.

Colima is stopped. The VM lease is released. The accepted M1 image identities and tags are unchanged. No owner blocker remains. T3 did not start. No commit or push was made.

Apply only the T2 addition below. This older worktree document does not contain the accepted T1 entry. Keep the accepted T0 and T1 entries. The exact worktree diff follows.

```diff
--- a/docs/corpus_commitments.md
+++ b/docs/corpus_commitments.md
@@ -4,3 +4,12 @@
 | --- | --- |
 | `t0-source.tar.gz` | `0ec88f1de7ce2577f4ab9d23bcfdf08c1795e9582984c0f5a3455483dd242b99` |
 | `t0-inputs.tar.gz` | `1d57dce417990d2092f758b8812adfa9f83cfc352d99e694c27dca0814922ee5` |
+
+# T2
+
+| Archive | SHA-256 |
+| --- | --- |
+| `t2-source.tar.gz` | `5f3b67cce71ad1ec6e7876889ff1e609a4072b2feb833fb23f2ba2f072fd8788` |
+| `t2-inputs.tar.gz` | `27ea3363f4cd1ef284db6b3ec0ff24c5d7bb7cf3ca8fcfc20e5cd6f4211e6574` |
+
+The corpus is agent-sealed on the honor system.
```
