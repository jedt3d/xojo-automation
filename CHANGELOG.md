# Changelog

## Unreleased — 2026-10-29

### Milestone 2 — coordinated Console jobs

- Add a lease-owning worker over persistent XMCP stdio sessions, with guarded
  project/IDE checks and one request in flight.
- Add opt-in item revision stamps and loaded-constant probes for Agentic reload
  synchronization, including correct escaping of Base64 padding in Xojo defaults.
- Isolate compiler/runtime diagnostics by run ID, project ID and source revision;
  reject stale events and capture instrumented exceptions.
- Drain late replies after client deadlines/cancellation; quarantine unresolved
  IPC rather than disconnecting a live IDE. Normal worker termination signals
  request cancellation.
- Retry cleanup only for explicitly undelivered, absent-socket attempts; retain
  uncertain partial writes even when a caller deadline has expired.
- Stop owned debug runs, compare PID/start/executable before OS termination,
  restore only unchanged stamped files, and verify their reload before release.
- Add a separate Console fixture/profile, mocked transport/state tests, live
  validation suite, coordination guide and milestone report.
- Preserve the milestone-1 evidence and fixture; no global MCP registration or
  installed skill replacement is performed.

### Milestone 1 — evaluation

- Establish the first milestone repository with user and developer documentation.
- Package the existing Xojo automation skill, its release/migration references,
  scripts, and 10 harness tests; omit the personal historical journal.
- Pin XMCP 1.11.0 source and XDOX 0.2.0 release/archive digest for evaluation.
- Add a stdio MCP probe, read-only XDOX readiness inspector, and disposable
  Agentic Mode fixture with error variants.
- Record live 2026r3 results for external reload/run, compile diagnostics,
  application-side exception logging, debug stopping, documentation lookup,
  and a universal Console build.
- Preserve stale-result attempts and the initially mis-targeted signature check as
  evidence; document synchronization and packaging boundaries.
- Keep cross-platform validation and production integration as future work.
- Correct project identity comparison for shell-escaped `ProjectShellPath`
  results; add two regression tests while retaining wrong-project rejection.
- Route MCP work to the evaluated tool schema and evidence-backed integration notes.
