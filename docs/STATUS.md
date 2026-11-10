# Phoenix status

M0 is in progress. The preliminary Apple Silicon run
`m0-4561081303ab4545b4c194d9f212922c` matched 16 public cases and
detected 20 of 20 mutation builds. The coverage check failed in that
run. A full run with the corrected collector is in progress.

The baseline for free space on the internal drive is 14,432,616 KiB.
The workspace uses the case-sensitive APFS mount at `/Volumes/PhoenixWork`.

## Next actions

1. Inspect the full Apple Silicon acceptance report and development set.
2. Verify both native CI jobs and their exact outcome hashes.
3. Compare the Mac outcome hashes with the native CI results.
4. Obtain an independent Astra review of the candidate milestone.
5. Tag M0 after all checks pass.
