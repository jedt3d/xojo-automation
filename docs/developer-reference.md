# Developer reference

## Milestone-2 coordination layer

`scripts/xojo_coordinator.py` is the client/worker entrypoint. `coordination.py`
owns profiles, source snapshots, stamp barriers, identity guards, runtime event
validation and cleanup. `mcp_session.py` owns one persistent, serial stdio
connection. It refuses a normal close while a response is pending.

The worker reuses `GuiLease` from the existing skill. It keeps all child pipes
open after the foreground client returns. Compiler diagnostics are matched by
MCP request ID and attached to a UUID/project/source revision. The runtime probe
adds the same identities to per-job events. The coordinator does not parse a
global IDE error/log file.

The source digest normalizes only `CoordinationStamp`; it includes managed code
and pinned inputs. Xojo tag attributes require `=` to be serialized as `\x3D`.
Unescaped Base64 padding was truncated in the first live attempt. IDE version
guards compare formatted strings, avoiding float-comparison warning text in
data replies. Both discoveries are retained in the milestone-2 evidence.

Use the [coordination guide](coordination.md) for the profile/runtime contract and
the [milestone-2 report](milestone-2-coordination.md) for actual test coverage.
New tests live under `tests/`; the original harness tests remain under the skill.
Never induce a live pending-IPC failure before validating the transport/worker
behavior with mocks. A permanent unresolved reply requires operator recovery;
there is no verified forced-cancellation API.

## Architecture and ownership

```text
Agent -- reads --> skill and project instructions
      -- edits --> .xojo_code / other text project items
                         |
                    Agentic Mode
                         |
                    Running Xojo IDE
                         ^
                         | IDE IPC v2
MCP client -- stdio --> XMCP
                         | reads
                         +---- installed docs (read-only)
                         +---- XDOX SQLite database
                         +---- loopback embedding/rerank services

XDOX owns indexing, database writes, notes, models, and model-server lifecycle.
```

The Python harness is an existing alternative IPC client. It does not share
XMCP's transport code. Serialize all IDE clients under the same GUI lease.
Agentic Mode's asynchronous watcher remains active alongside them, so holding
a lease alone does not establish source synchronization.

## Dependencies and source provenance

- Python scripts in this repository use the standard library.
- Xojo 2026r3 is a licensed external application, not a repository dependency.
- XMCP's exact tested source commit and XDOX's tested release/digest are recorded
  in `upstreams.json`. Review current source and the pinned version separately.
- XMCP source was built unchanged. The IDE emitted an older-project version
  warning while opening its 2026r2.1 project; compilation succeeded on 2026r3.
- XDOX 0.2.0 is the runtime tested here. Current `main` was inspected, but was
  not rebuilt because this IDE has only the default database plugins and no MBS
  WebKit/Cocoa development plugins.
- The initial skill copy comes from the user's existing local skill. Its
  generated indexes retain local snapshot paths; they are metadata, not bundled
  third-party examples. The personal historical learning journal is excluded.

Download upstream source into an ignored work folder, then use the exact pins:

```sh
mkdir -p work
git clone https://github.com/o3jvind/XMCP.git work/XMCP
git -C work/XMCP checkout 32200c34809e2ae7e218854ac60038a09df30851
git clone https://github.com/o3jvind/XDOX.git work/XDOX
git -C work/XDOX checkout 7b906d28d0099092207d44de4a7163777bbeaa8d
```

XDOX's release archive digest is in `upstreams.json`. Keep signed binaries and
their libraries together. Do not copy embedded upstream licensing material or
personal Keychain data into repository source/evidence.

## Fixture creation and variants

The checked-in fixture was created through Xojo's new-project chooser:
Console, application name `AgenticSmoke`, **for AI (Agentic Mode)** checked.
Xojo saved `AgenticMode=True` in its manifest and generated the instruction files.
Its generated `AGENTS.md` references `CLAUDE.md`, which the IDE did not create;
`XOJO-CODING.md` was present and read. That missing optional pointer did not
block the observed workflow.

The committed `App.xojo_code` is the restored, valid baseline. Variants under
`fixtures/variants/` are complete alternative App files:

| Variant | Purpose | Observable result |
| --- | --- | --- |
| baseline | Immediate successful run | Temporary marker `agentic-reloaded-v2` |
| compile-error | Missing type in Run | Compiler error names `MissingMilestoneType` |
| runtime-error | Deliberate unhandled RuntimeException | Sentinel message and stack in `/tmp/xmcp_debug.log` |
| hold | Event loop for up to 60 seconds | Marker `agentic-hold-v3`, live debug process, then stop |

Use a disposable copy when reproducing tests. Preserve any pre-existing global
debug log before running the exception variant. Its logger uses a shared path;
project/run isolation is a future requirement, not implemented here.

For each source variant:

1. Confirm the exact fixture project and IDE; acquire the shared GUI lease.
2. Verify no fixture debug process is running.
3. Replace only the fixture's `App.xojo_code` with the selected variant.
4. Wait for a new `Reloaded App` entry in Messages. Record the entry and edit.
5. Analyze, Run, or create the Agentic trigger as the test requires.
6. Wait for a fresh result, not just an IPC acknowledgment.
7. Capture the evidence, stop the debug process, and restore baseline source.
8. Verify the restore reloaded before closing the disposable project.

`SpecialFolder.Temporary` resolved to this user's per-user temporary directory
in the run; it was not `/tmp`. Discover/record its actual path when checking the
marker on another host. Runtime exception logging uses `/tmp` deliberately to
match the tested XMCP tool contract.

## The MCP evaluation client

`scripts/mcp_probe.py` launches an explicitly supplied executable, initializes
MCP over newline-delimited stdio JSON-RPC, sends a list of requests sequentially,
and writes responses and timings. It does not install or register a server.

Example request file:

```json
[
  {"method": "tools/list"},
  {"method": "tools/call", "params": {
    "name": "lookup_class", "arguments": {"class_name": "DesktopButton"}
  }}
]
```

Run from the repository root, after building XMCP:

```sh
python3 scripts/mcp_probe.py \
  --requests /absolute/path/to/requests.json \
  --output work/probe-result.json \
  --timeout 240 \
  -- /absolute/path/to/XMCP \
  --docs-path "/absolute/path/to/Xojo 2026r3/Documentation"
```

Run `--help` for the complete interface. `--timeout` is in seconds per request;
XMCP tool timeout arguments are in **milliseconds**. The server defaults for
build/run are much longer than this probe default, so choose compatible limits.

This is a bounded diagnostic client, **not the production orchestration layer**:
it does not acquire the GUI lease, validate expected project identity, or prove
reload completion. The live IDE tests were run while a separate shared lease
was held and identity/reload checks were performed. Use the existing harness
for guarded workflows until the next milestone implements an equivalent MCP
boundary.

XMCP documents that abandoning a connection while an IDE operation is pending
can crash the IDE. Do not use this evaluation client to provoke IDE timeout
failures. All recorded IDE requests completed before the process was stopped.
The probe terminates the server at normal completion because upstream documents
that closing stdin alone does not reliably terminate XMCP.

Early evidence requests offered protocol `2024-11-05`, and XMCP selected
`2025-06-18`; the final probe offers `2025-06-18`. This is not a protocol
conformance suite or a native Codex attachment test.

## Evidence contract

`scripts/inspect_xdox.py` captures read-only chunk/embedding counts, selected-version
metadata, model sizes, and loopback service health. It does not read personal
note contents. Its default data path is macOS-specific; pass `--data-dir` for a
different location. Health inspection alone is not a functional retrieval test.

Read `evidence/2026-10-29/manifest.json` for the case list and status. The
individual records retain requests, replies, elapsed durations, and retries.

- `mcp-baseline.json`: handshake, tool schemas, identity, Analyze, Run.
- `agentic-trigger.json`: trigger consumption plus changed runtime marker.
- `agentic-messages.txt`: reload/run log observed through the IDE's Accessibility tree.
- `agentic-compile-error.txt`: Agentic Mode error-file contents.
- `mcp-compile-error.json`: early Analyze/Run around a watcher transition.
- `mcp-analyze-known-error.json`: analysis after source/error synchronization.
- `mcp-runtime*.json`: stale attempt, synchronized launch, and later log read.
- `mcp-stop.json`: stopping the live hold variant.
- `mcp-release-build.json` and `artifact.json`: build response, architecture,
  execution, initial executable-only signature failure, and successful bundle verification.
- `docs-*.json`: compact retrieval evidence. Full vendor pages are not published.
- `docs-reranked.json`, `docs-after-quit.json`: reranker/no-match smoke and keyword fallback.
- `xdox-index*.json`: version, chunk counts, embedding counts, service readiness,
  and model/download state.
- `environment.json` and `cleanup.json`: host scope and final process/lease state.

Search response summaries record lengths, hashes, labels, and a short opening
excerpt. They demonstrate what was returned, not universal API correctness.
Do not interpret database-version labels as introduction dates for APIs or
historical release-note excerpts.

## Validation

```sh
python3 -m unittest discover -s skills/xojo-automation/tests -v
python3 -m py_compile scripts/mcp_probe.py
python3 scripts/mcp_probe.py --help
```

The original 10 tests plus two new path regressions cover IPC completion,
missing responses, identity checks,
script errors, and GUI leases. They do not test an actual IDE, XDOX retrieval,
Windows IPC, signing, or mobile/Web execution. Those claims require separate
live evidence.

Before publishing a change, inspect staged filenames/diff and search for
credentials, private notes, model files, databases, and generated binaries.
Preserve source revision pins and failures that explain the resulting guidance.
