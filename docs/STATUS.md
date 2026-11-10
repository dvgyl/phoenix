# Phoenix status

M0 is in progress. Apple Silicon run
`m0-b4ff3a1a02104fc1bb49bd9057262c4c` matched 16 public cases and
detected all 20 mutation builds. It reached 30 of 45 recovered block
entries in `bitstats` and 30 of 51 in `filemarks`. The earlier candidate
failed independent review. The replacement adds checks for emulator
identity, image provenance, and QEMU sandbox behavior.

The baseline for free space on the internal drive is 14,432,616 KiB.
The workspace uses the case-sensitive APFS mount at `/Volumes/PhoenixWork`.

## Next actions

1. Run Apple Silicon acceptance on the replacement candidate.
2. Verify native x86-64 and AArch64 CI on the same commit.
3. Save the comparison of all three reports.
4. Obtain an independent Standard-tier Astra verdict.
5. Tag M0 after all checks pass.
