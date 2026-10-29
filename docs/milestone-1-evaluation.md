# Milestone 1: XMCP, XDOX, and Xojo 2026r3

Evaluated on 2026-10-29. **Recommendation: adopt the existing XMCP/XDOX
capabilities and build a thin coordination layer around them.** A replacement
documentation engine or IDE bridge is not justified by these results.

This evaluation is scoped to one Apple Silicon macOS host and a disposable
Console project. It does not qualify every tool, target, or deployment workflow.
The case list and individual evidence files are in
[`evidence/2026-10-29`](../evidence/2026-10-29/).

## Environment and provenance

| Component | Evaluated version / scope |
| --- | --- |
| Xojo | 2026r3; bundle `26.3.0.3.68307`, version `26.3.0.68307` |
| Host | macOS ARM64; exact OS/Python versions in `environment.json` |
| XMCP | 1.11.0, source commit `32200c34809e2ae7e218854ac60038a09df30851` |
| XDOX runtime | Signed release 0.2.0; archive digest verified against the release asset |
| XDOX source review | Commit `7b906d28d0099092207d44de4a7163777bbeaa8d`; not rebuilt |
| Documentation | Installed `Xojo 2026r3/Documentation` |
| Project | IDE-created `AgenticSmoke`, Console, text format, `AgenticMode=True` |

Source/release pins are in [`upstreams.json`](../upstreams.json). The existing
global skill/client configuration was not replaced. The repository contains a
packaged skill copy and one narrow harness correction.

## Results

| Capability | Result | Evidence |
| --- | --- | --- |
| Build XMCP with 2026r3 | Passed; ARM64 executable built from unchanged source | `xmcp-open.json`, `xmcp-build.json` |
| MCP initialize and tools/list | Passed; 31 tools advertised with optional file tools disabled | `mcp-baseline.json` |
| Project and IDE identity | Correct path/version returned; paths are shell-escaped | `mcp-baseline.json` |
| Agentic Mode generation | Saved text project, mode flag, AGENTS/XOJO-CODING instructions | Checked-in fixture |
| External source reload | Passed without reopen or manual reload; Messages and changed runtime marker observed | `agentic-messages.txt`, `agentic-trigger.json` |
| Agentic run trigger | Consumed trigger and executed changed source; marker arrived in 4.061 seconds in this run | `agentic-trigger.json` |
| Compile diagnostics | Deliberate missing type reported by Agentic Mode and MCP | `agentic-compile-error.txt`, `mcp-compile-error.json` |
| Synchronized Analyze | Deliberate error and unused-local warning reported | `mcp-analyze-known-error.json` |
| Runtime exception details | Passed with application-side logger; message and stack retrieved later | `mcp-runtime-log.json`, runtime-error variant |
| Stop active debug process | Passed; hold-variant process existed and was gone after stop | `mcp-stop.json`, `environment.json` |
| Release build and execution | Universal Console artifact built; x86_64/ARM64 present; native ARM64 execution returned 0 and expected marker | `mcp-release-build.json`, `artifact.json` |
| Local signature check | Containing Console bundle passes strict verification; signature is ad-hoc | `artifact.json` |
| XDOX released app | Launched without installing MBS development plugins | `environment.json`, XDOX UI observation |
| Documentation indexing | 16,127 chunks, all embedded: 16,102 for 2026r3 plus 25 version-independent | `xdox-index.json` |
| Keyword retrieval | Agentic Mode and Android history returned version-labeled results | `docs-keyword.json` |
| Completed-index semantic retrieval | Agentic Mode found; natural-language string question located `String.Left` | `docs-full-semantic.json` |
| Class/member lookup | Summary and targeted entries work, including Enabled on DesktopButton/base class | `docs-members.json`, `docs-web-member.json` |
| Unknown API handling | Missing class/member returned explicit failure/available-member guidance | `docs-full-semantic.json`, `docs-members.json` |
| Reranker | Passed readiness and retrieval/no-match smoke; complete 4.28 GB model installed | `xdox-index-final.json`, `docs-reranked.json` |
| Harness checks | 12 unit tests pass, including two new shell-path regressions | `verification.json` |

Durations above are observations from one run, not performance estimates or a
general benchmark. Repeated searches, database warmup, model readiness, and
result expansion affect comparisons.

## Findings that change the workflow

### 1. Agentic Mode works, but needs a synchronization barrier

The initial file edit generated `Reloaded App` in Messages and the baseline
runtime marker. A second external edit changed the marker to
`agentic-reloaded-v2`; the Agentic trigger ran it while the project stayed open.
No manual reload/revert or close/reopen was used for the edit/run sequence.

Two earlier calls illustrate why a successful tool response is insufficient:

- Analyze requested around the compile-error edit first said clean; a subsequent
  Run reported the missing type. Analyze after the error/reload was established
  reported both the error and unused-local warning.
- A Run requested immediately after switching from the invalid source to the
  runtime-error variant still reported the previous missing type. After the new
  `Reloaded App` entry was observed, Run compiled the new variant successfully.

These observations establish a race in the combined workflow. They do not prove
that XMCP's diagnostic parser is faulty. The next layer must associate an edit
revision with completed reload before Analyze/Run/Build.

### 2. Runtime diagnostics require instrumentation and fresh-output polling

`get_debug_log` reads a file written by the application's exception handler. It
does not extract an exception directly from Xojo's paused debugger. The fixture
writes an intentional error message and stack from `UnhandledException`.

The first log read immediately after the synchronized Run returned “no log”; a
later read returned the sentinel and stack. A Run acknowledgment therefore needs
an application-start/completion or fresh-log check. Global `/tmp` logging also
needs project/run isolation before routine multi-project use.

Live locals, watches, stack-frame selection, and breakpoint/step behavior were
not tested. Their presence must not be inferred from the successful log test.

### 3. Existing member lookup already solves much of the documentation problem

The advertised schema has separate `class_name`, `member`, and `full` fields.
Default class lookup returns a summary. Targeted calls returned concise entries
for DesktopButton.Pressed, DesktopButton.Enabled, DesktopUIControl.Enabled,
String.Left, and WebSession.LazyLoadDependencies.

The initial `class_name: DesktopButton.Pressed` call used the wrong contract and
failed. The initial `LazyDependencies` spelling also failed and listed available
members, including the actual `LazyLoadDependencies`. Both failed attempts are
retained; neither is classified as a missing MCP capability.

Build on this existing API. Remaining needs are explicit source/anchor metadata,
per-request version/target guarantees, broader correctness tests, and migration
reasoning supported by release history.

### 4. A version-labeled search is not an API availability verdict

Keyword search for Android introspection retrieved a 2024r3 release-note section
inside the 2026r3 documentation corpus. That is valid history, but the corpus
label alone does not establish today's platform/API behavior.

Semantic search found the intended Agentic and String.Left material, but also
expanded results to unrelated members named Mode. A requested `max_results: 3`
can produce more displayed sections through expansion. Keep exact lookup as the
preferred path for known APIs and apply a response budget at the integration
layer. Once the reranker was ready, the Agentic query returned four relevant
sections without the unrelated Mode members; String.Left remained discoverable,
and an invented-API search returned no results. After quitting XDOX, keyword
retrieval still worked and both model servers stopped. These few prompts are
smoke tests, not a retrieval-quality benchmark.

XMCP's current database search reads XDOX's active-version setting. Passing a
2026r3 docs path does not independently pin database retrieval to that version.
Only one indexed version was exercised here; isolation across multiple active
projects/versions remains unqualified.

### 5. Validate signatures at the correct artifact boundary

The XDOX archive hash matched its published digest. Its initial extracted copy
failed strict verification because of Finder metadata on the framework. Removing
only that metadata from the disposable copy restored strict verification;
Gatekeeper assessment accepted the original Developer ID/notarized signature.
The app was not re-signed and system security settings were not changed.

The fixture's first signature command targeted the executable inside its generic
Console bundle and failed. Checking the containing bundle directory passed.
`artifact.json` retains both. Local ad-hoc signature validity and successful
execution do not establish Developer ID distribution or notarization readiness.

### 6. The existing harness needed a small path correction

Xojo returned escaped hyphens/spaces in `ProjectShellPath`. The previous identity
check treated backslashes as literal filesystem characters and rejected the
correct fixture. The repository copy now compares literal paths first, then
decodes exactly one shell word without executing it, and still rejects a
different project or multiple words.

The actual observed path was replayed against the guard before and after the
fix. Two regression tests were added; all 12 harness tests pass. This specific
fix was validated by record replay/unit tests, not a new end-to-end IDE session.

## What to adopt

1. **XMCP** for its already-working IDE diagnostics, run/stop, and API-member
   lookup surface.
2. **XDOX** for local indexing and search rather than a duplicate documentation
   database. Its released binary avoids an MBS development-plugin purchase for
   evaluation/runtime use.
3. **The existing skill and harness** for version/migration decisions, file
   editing, project checks, and lease conventions.

## What still needs to be built or verified

The next milestone should implement a thin adapter that binds project identity,
source-reload completion, one operation at a time, fresh runtime results, safe
timeouts, and cleanup. Reuse the existing search and IDE surfaces.

Then add explicit docs source/version/target metadata and a curated platform/API
benchmark. Validate each target on its appropriate runtime environment.

Not exercised here: Windows/Linux hosts, native Intel execution, Desktop UI,
Web browser/server behavior, iOS/Android, remote debugging, XojoUnit, personal
notes/MBS docsets, arbitrary file tools, deployment signing/notarization, and
native MCP attachment in a fresh Codex chat. No cross-platform readiness claim
is made. See the [roadmap](roadmap.md) for acceptance criteria.

## Cleanup and retained state

The disposable fixture was restored to valid source and closed. Xojo returned
to its project chooser. The hold debug process stopped and the shared GUI lease
was released. Model/service shutdown and retained local data are recorded in
`cleanup.json`. Builds, tool clones, downloaded binaries/models, and doc databases
are excluded from Git; source pins, fixture variants, and compact evidence are
retained. No persistent Codex MCP registration or Xojo plugin installation was
performed.
