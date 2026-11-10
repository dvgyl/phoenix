# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. The first sealed run scored zero fully successful
variants for both Phoenix and Ghidra-raw. The exact replay reproduced
that result.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 0/20 | 0/20 |
| Ghidra-raw | 8/20 | 0/20 | 0/20 |

The run is `m1-t0-ce6a34d` at commit `ce6a34d`. Its replay is
`m1-t0-replay-ce6a34d`. All 792 original cases per method were
eligible. There were zero emulator disagreements and evaluation errors.
The tests reached 790 of 1,079 recovered block entries. These counts
measure recovered blocks. Source branch adequacy is recorded separately.

Public `-O0` probes reproduced the exact-byte rejection in C runtime
startup code. A hardened build profile passed all four public variants
and the integrity checks in
`m1-public-hardened-e675da21dc2a43f4ba29dd132b067fd4`.
The copied-byte negative controls also passed.

The follow-up implementation adds development integrity repair,
checker identity binding, replay lineage preservation, and model log
identity checks. It also adds package-only Ubuntu download fallback.
The signed repository probe passed on both Linux worker images.
Full Linux integration and independent review of this candidate are
pending. There is no M1 tag.

Native ARM64 CI passed for `ce6a34d`. Three x86-64 attempts stopped on
Ubuntu package delivery. The first M0 native outcome comparison remains
green in [run 42794652145](https://github.com/dvgyl/phoenix/actions/runs/42794652145).

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has 2 GiB of memory.

## Next actions

1. Build and verify the follow-up worker and checker images.
2. Run the public optimization matrix and new public control programs.
3. Obtain the independent Astra preflight review of the exact candidate.
4. Run a new sealed M1 measurement with its own revision and run ID.
5. Replay and review that exact result before any M1 tag.
