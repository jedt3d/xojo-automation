# Xojo Automation

Tools and a Codex skill for developing Xojo applications with version-aware
documentation, text project editing, Agentic Mode, and IDE diagnostics.

Milestone 2 adds a coordination worker over **XMCP 1.11.0**, tested with **Xojo
2026r3 on macOS ARM64**. It verifies project/revision identity, waits for Agentic
reloads, isolates run diagnostics, and cleans up after success, failure, or
cancellation. The current adapter supports opt-in local Console projects.

See the [coordination guide](docs/coordination.md) and
[milestone-2 report](docs/milestone-2-coordination.md).

## What works in the local evaluation

- Build XMCP from its pinned source with Xojo 2026r3.
- Discover its MCP tools and identify the open project and IDE version.
- Automatically reload external edits and run through `XojoRunProject.txt`.
- Retrieve compile errors, analyze synchronized source, and stop a live debug app.
- Retrieve an intentional runtime exception and stack using application-side
  exception logging.
- Index installed 2026r3 documentation with XDOX and query it through XMCP.
- Build and execute a universal macOS Console fixture; both architectures are
  present, with execution tested on ARM64.

Important limits: documentation version/platform selection needs stronger
guarantees, and other target/profile combinations remain unqualified. A stuck
IPC request is drained or quarantined, not forcibly disconnected.
The [milestone-1 evaluation](docs/milestone-1-evaluation.md) retains the original
XMCP/XDOX findings and documentation-search results.

## Start here

1. Read the [user guide](docs/user-guide.md) for setup, daily workflow, and recovery.
2. Read the [developer reference](docs/developer-reference.md) to reproduce or
   extend the evaluation.
3. Inspect [coordination evidence](evidence/2026-10-29-milestone-2/validation.json),
   [original evaluation evidence](evidence/2026-10-29/), and [pinned upstream versions](upstreams.json).
4. Use the [next-milestone backlog](docs/roadmap.md) to choose follow-up work.

## Repository contents

| Path | Purpose |
| --- | --- |
| `skills/xojo-automation/` | Packaged existing skill, references, Python harness, and tests |
| `scripts/mcp_probe.py` | Explicit stdio MCP evaluation client; does not register a server |
| `scripts/inspect_xdox.py` | Read-only index, model, and service readiness inspection |
| `scripts/xojo_coordinator.py` | Guarded Analyze/Run jobs, status, waiting and cancellation |
| `fixtures/coordinated-smoke/` | Opt-in runtime probe, profile and milestone-2 Console fixture |
| `fixtures/agentic-smoke/` | IDE-created, Agentic Mode Console test project |
| `fixtures/variants/` | Baseline, deliberate compiler/runtime errors, and long-running source |
| `evidence/` | Test inputs/results and environment records |
| `docs/` | User guide, developer reference, evaluation, sources, and roadmap |

The skill's example/doc indexes describe the original local snapshot; they do
not contain the example files and are not a portable SDK. Rebuild them for
another machine. Personal historical journal contents are excluded.

## Quick check

Requires Python 3.9+; this evaluation uses the interpreter recorded in
`evidence/2026-10-29/environment.json`.

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/xojo-automation/tests -v
python3 skills/xojo-automation/scripts/xojo_harness.py --help
python3 scripts/mcp_probe.py --help
python3 scripts/xojo_coordinator.py --help
```

IDE operations require a running, licensed Xojo installation and a suitable
project. Models, Xojo documentation, MBS plugins, and third-party binaries are
not included. No persistent Codex MCP configuration was changed by the evaluation.

## License

This repository uses the [MIT license](LICENSE). XMCP, XDOX, their dependencies,
Xojo documentation, and generated vendor instructions retain their own terms.
Upstream links and provenance are in [sources](docs/sources.md).
