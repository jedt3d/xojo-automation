# Xojo Automation

Tools and a Codex skill for developing Xojo applications with version-aware
documentation, text project editing, Agentic Mode, and IDE diagnostics.

The first milestone evaluates **XMCP 1.11.0** and **XDOX 0.2.0** with **Xojo
2026r3 on an Apple Silicon Mac**. It is an evaluation, not cross-platform
qualification or a production MCP replacement.

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

Important limits: synchronization needs an explicit barrier, documentation
version/platform selection needs stronger guarantees, and cross-platform execution
has not been qualified.
Read the [evaluation report](docs/milestone-1-evaluation.md) for the complete
results, including model/index completion status and untested surfaces.

## Start here

1. Read the [user guide](docs/user-guide.md) for setup, daily workflow, and recovery.
2. Read the [developer reference](docs/developer-reference.md) to reproduce or
   extend the evaluation.
3. Inspect [recorded evidence](evidence/2026-10-29/) and [pinned upstream versions](upstreams.json).
4. Use the [next-milestone backlog](docs/roadmap.md) to choose follow-up work.

## Repository contents

| Path | Purpose |
| --- | --- |
| `skills/xojo-automation/` | Packaged existing skill, references, Python harness, and tests |
| `scripts/mcp_probe.py` | Explicit stdio MCP evaluation client; does not register a server |
| `scripts/inspect_xdox.py` | Read-only index, model, and service readiness inspection |
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
python3 -m unittest discover -s skills/xojo-automation/tests -v
python3 skills/xojo-automation/scripts/xojo_harness.py --help
python3 scripts/mcp_probe.py --help
```

IDE operations require a running, licensed Xojo installation and a suitable
project. Models, Xojo documentation, MBS plugins, and third-party binaries are
not included. No persistent Codex MCP configuration was changed by the evaluation.

## License

This repository uses the [MIT license](LICENSE). XMCP, XDOX, their dependencies,
Xojo documentation, and generated vendor instructions retain their own terms.
Upstream links and provenance are in [sources](docs/sources.md).
