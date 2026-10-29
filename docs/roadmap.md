# Remaining work

These are proposed follow-up milestones. This repository's first milestone
evaluates existing tools; it does not implement all of the following.

## Milestone 2 delivered: bounded Console coordination

The [worker and profile](coordination.md) implement project/IDE guards, loaded
revision stamps, serial XMCP operations, run-specific diagnostics and cleanup.
The current adapter is local macOS Console/flat code items on 2026r3. Read the
[milestone-2 report](milestone-2-coordination.md) for mock/live coverage and limits.

Remaining integration work: native MCP attachment/proxy in a fresh agent chat,
adapters for other project layouts/targets, and recovery after an OS crash or
force-kill. A permanently pending IDE reply is quarantined, not automatically
cancelled. These are not implied by successful Console jobs.

## Next: documentation precision

- Keep existing member-specific lookup, including the tested inherited property;
  add explicit source/anchor and version/platform labels in returned results.
- Per-request version/platform selection, independent of a global XDOX picker.
- Distinguish runtime target from IDE host and API availability from historical
  release-note evidence.
- Source-backed API1/API2 migration and tutorial assessment, using the existing
  skill's history rather than automatic name replacement.
- A curated retrieval benchmark spanning Desktop, Web, iOS, Android, Console,
  inherited members, deprecated APIs, and no-match questions.

Acceptance: every benchmark answer identifies its selected version/target,
contains inspectable source evidence, and marks unresolved availability as unknown.
Evaluate XMCP/XDOX extensions before implementing a parallel search engine.

## Packaging and target execution

- Keep the verified Console bundle target for signature checks. Establish
  Developer ID signing/notarization separately from the passing ad-hoc local check.
- Inventory existing Windows/Linux hosts, Xcode/iOS devices, Android SDK/devices,
  browser tooling, Xojo licenses, and plugin architectures.
- Add target adapters incrementally. Record built, launched, functional, UI,
  signed, and packaged states separately, including native/emulated execution.
- Evaluate XojoUnit for shared logic and target-specific smoke fixtures; Android
  coverage requires its own check.

Acceptance: a small vertical slice executes on each claimed target with retained
evidence. Neither a cross-compiled binary nor an upstream support claim counts
as a target runtime pass.

## Later: reusable recipes and packaging

Create tested UI/data/network recipes with target-specific views and shared
business logic where useful. Keep one main skill with focused references until
separate workflows justify additional skills. Package the proven tools as a
plugin only when installation and update behavior are reproducible.
