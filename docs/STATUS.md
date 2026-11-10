# Phoenix status

M0 is in progress. The local quality gate passes. No M0 acceptance run
has passed yet.

The baseline for free space on the internal drive is 14,432,616 KiB.
The workspace uses the case-sensitive APFS mount at `/Volumes/PhoenixWork`.

## Next actions

1. Complete the plugin-enabled QEMU build and check a real trace.
2. Run and inspect the Apple Silicon M0 acceptance report.
3. Verify the native x86-64 and AArch64 CI jobs and compare their reports.
4. Obtain an independent Astra review of the candidate milestone.
5. Tag M0 after all checks pass.
