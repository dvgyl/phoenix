# Public draft checkpoints

These eight patches preserve old public source drafts from local worktrees.
They are archival records. They are not accepted production changes.
Current implementations are already in later commits on main.

`manifest.json` records each original base commit and each file hash.
Each patch applies to its recorded base. Do not apply a patch to main.
The source worktrees retain their original files.

Private corpus files, held-out inputs, binaries, caches, generated lifts,
and temporary logs are excluded. Public validation records remain under
`/Volumes/PhoenixWork/audit/` and the original worktree directories.
