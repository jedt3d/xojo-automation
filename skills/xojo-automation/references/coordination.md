# Coordinated Console workflow

When working in a checkout of `jedt3d/xojo-automation`, prefer its
`scripts/xojo_coordinator.py` for an existing opt-in coordination profile.
The worker lives in the repository, not in this installable skill folder.
Copying the skill alone does not install the coordinator or XMCP.

Read the repository's `docs/coordination.md` for commands and profile setup;
the [published guide](https://github.com/jedt3d/xojo-automation/blob/main/docs/coordination.md)
is the fallback when the checkout is not present. Evidence is in the repository's
`evidence/2026-10-29-milestone-2/` and milestone-2 report.

- Current adapter: local macOS Console, flat managed code items, 2026r3 Agentic
  Mode, evaluated XMCP 1.11.0. Other targets/profiles remain unqualified.
- Managed items explicitly opt in with a public `CoordinationStamp` constant.
  Save/reconcile human IDE edits before handing those files to automation.
- The worker polls loaded constants and verifies identity/stamps in the action
  script. It does not reopen, revert, force reload, or change Agentic Mode.
- Compiler replies and instrumented runtime events belong to a UUID/project/
  source revision. Shared stale error files and logs are not accepted as evidence.
- After client exit code 2, inspect the worker. It retains the lease and backend
  while draining a pending reply. Use `cancel`; do not terminate it or XMCP to
  hurry the IDE. A quarantined request may require preserving work and closing
  that IDE before resources can be safely released.
- Restore conflicts preserve the edited file and fail cleanup. Resolve them
  before another job. Direct XMCP/harness clients still need the shared lease;
  they do not automatically gain this worker's synchronization guarantees.
