# Open questions

- The workspace path contains an exFAT drive. Use the APFS mount required
  by AGENTS.md §6. The backing file stays in the requested workspace.
- The reuse guidance excludes sealed and held-out data from reused
  tooling. Keep all optional upstream research tools on public inputs.
  For the required runtime, restrict pinned execution and lifting tools to
  the inputs that SPEC.md permits for each stage. No tool in reconstruction
  may read sealed source or held-out inputs. Resolve any broader
  interpretation before the first sealed evaluation.
- Codex lists a Priority tier for explicit model overrides in its
  subagent tool. For Standard-only reviews, use a separate Codex CLI
  process with the requested model and an explicit default service tier.
- The optional test environment overlay can add values. Reject changes
  to the fixed environment and loader or emulator controls. This keeps
  the sandbox policy the same for the original and rebuild.
- The first M0 candidate review process used the Standard tier, but its
  reviewer reported a Priority-tier subreview. Do not use that review
  for the milestone gate. Disable nested agents, Fast mode, and
  Ultrafast mode in the replacement review process.
- The managed worktree tool has no per-call location. Create Phoenix
  agent worktrees with Git at the required external-drive path. Keep
  the desktop app's global worktree location for other projects.
