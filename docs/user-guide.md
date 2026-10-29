# User guide

## 1. Choose the pieces you need

The **skill** supplies workflow and version-aware guidance. The **Python harness**
talks to a running Xojo IDE. **XMCP** exposes IDE/documentation operations to an
MCP client. **XDOX** builds the local search database and runs optional search
models. XDOX is not required for direct class lookup or plain-text fallback.

Use text-format Xojo projects with version control. Agentic Mode requires a
saved text project; text-format saving requires a Xojo license.

This milestone has live evidence for an Apple Silicon Mac running Xojo 2026r3.
The Windows/Linux/mobile/Web workflows remain future validation work.

## 2. Check your installation

From the repository root:

```sh
python3 skills/xojo-automation/scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" doctor
```

Adjust the application path on your machine. The evaluated local docs are:

```text
~/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation
```

The doctor and command-line `--help` output are authoritative for available
options. The current harness compile command validates macOS build types;
do not assume it already implements a platform matrix.

## 3. Use the packaged skill

The complete skill directory is `skills/xojo-automation/`. An agent can read its
`SKILL.md` directly when working in this repository. For normal installed-skill
discovery, place that directory in your agent's configured skills directory;
review an existing installation before replacing it. This evaluation preserves
the existing global installation and publishes a repository copy.

Read the skill's workflow reference before IDE operations. For an old project or
tutorial, load `references/migration-and-older-examples.md`; for current APIs,
load `references/2026-changes.md` and verify exact members in installed docs.

## 4. Build XMCP

Clone [XMCP](https://github.com/o3jvind/XMCP) into an untracked tools/work folder
and check out the commit listed in `upstreams.json`. Open
`src/XMCP.xojo_project` in Xojo 2026r3. Build for macOS ARM64 on an Apple Silicon
development host. Keep its runtime libraries and copied resources beside the
executable.

The evaluation successfully used the documented IDE `BuildApp(24, False)`
operation, returning an executable under:

```text
src/Builds - XMCP/macOS ARM 64 bit/XMCP/XMCP
```

Run that executable with `--help` to check its actual arguments. For an MCP
client, configure it as a **stdio server**, passing an explicit docs directory:

```text
command: /absolute/path/to/XMCP
arguments:
  --docs-path
  /absolute/path/to/Xojo 2026r3/Documentation
```

Use your client's documented configuration mechanism. The evaluation exercised
JSON-RPC directly; attaching XMCP as a native tool in a fresh Codex chat remains
a separate integration check. The repository does not automatically edit client
configuration. Optional general file tools were left disabled.

## 5. Run XDOX

Use the [XDOX 0.2.0 release](https://github.com/o3jvind/XDOX/releases/tag/v0.2.0)
for the evaluated binary. Compare its archive SHA-256 with `upstreams.json`.
The release runs without an MBS license; rebuilding current source requires the
MBS plugins and other dependencies described by its upstream README.

XDOX reads your installed documentation and writes its own application-data
directory. On first launch it downloads a roughly 146 MB embedding model and
a roughly 4.3 GB reranker. These are separate readiness stages:

1. Documentation parsed/indexed: keyword search can work.
2. Embedding model ready and all chunks embedded: semantic search can be assessed.
3. Reranker ready: reranking and no-match behavior can be assessed.

An open window or green semantic indicator does not prove that all chunks have
been embedded. Check the index progress and database counts. Keep the active
documentation version aligned with the project; XMCP's database search uses
XDOX's active version, which may differ from an explicit `--docs-path`.

The default application-data location is:

```text
~/Library/Application Support/dk.o3jvind.xdox/
```

It contains `xdox.db`, model files, and `XDOX_debug.log`. Keep these out of Git.
Inspect readiness without reading personal notes or modifying the database:

```sh
python3 scripts/inspect_xdox.py --output work/xdox-readiness.json
```

Quitting XDOX normally shuts down its model servers. XMCP can continue keyword
searching the completed database without those servers.

## 6. Daily Agentic Mode workflow

1. Open the intended text project in Xojo and enable File > Agentic Mode if it
   is not already enabled. Preserve an existing setting. Read the project's
   generated `AGENTS.md` and `XOJO-CODING.md`.
2. Confirm the project path and IDE version. Coordinate with the human before
   editing an item they are changing in the IDE.
3. Edit complete source files on disk. Preserve manifest item IDs. Create a new
   item file before referencing it in the manifest.
4. Observe a **new reload entry for the affected item** in Messages. A successful
   file write, a fixed delay, or a successful MCP connection is not this barrier.
5. Analyze, then Run or Build as appropriate. Check error results and actual
   runtime behavior. The milestone observed an old diagnostic when Run was
   requested immediately after an edit; retrying after verified reload used the
   new source.
6. Poll for the expected runtime marker/process/error with a deadline. A Run
   command response can precede application startup and log creation.
7. Stop the debug session after the check. Verify its process exited and clear
   blocking dialogs. Keep the user's active project open for continued work.

For a fixture already synchronized and open:

```sh
python3 skills/xojo-automation/scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  analyze --reload-policy skip \
  /absolute/path/to/AgenticSmoke.xojo_project
```

The `skip` policy checks project identity; it does not establish reload completion.

## 7. Agentic Mode without MCP

Create `XojoRunProject.txt` in the project directory to request a run. Xojo
consumes the file and writes `XojoCompileErrors.txt` for compiler errors. Before
a new check, distinguish earlier error files from newly produced results.

Trigger consumption alone proves a request was processed, not that the app
completed successfully. In this milestone, a changed runtime marker proved the
new source executed. See `evidence/2026-10-29/agentic-trigger.json`.

## 8. Documentation questions

- Use `lookup_class` for an exact class name; pass `member` separately for a
  property, method, event, or constant. Default output is a class summary.
- Use `search_docs` for concepts, release history, and locating member text.
- Follow up in the exact member's official/local documentation for signatures
  and platform constraints.
- Inspect the returned version label and section title. A 2024 release note
  retrieved from the 2026r3 documentation bundle is historical evidence.
- For `DesktopButton.Pressed`, pass `class_name: DesktopButton` and
  `member: Pressed`. A dotted value in `class_name` is not this tool's contract.
  For an inherited member, follow the declaring base class when necessary.
- Treat project notes as conventions or observations, separately from API facts.

## 9. Debugging

Compiler diagnostics work without application instrumentation. The evaluated
`get_debug_log` reads `/tmp/xmcp_debug.log`; runtime exception details require an
`App.UnhandledException` handler that writes the log. See the deliberately
failing `fixtures/variants/runtime-error.xojo_code` for the tested Console
example. Do not add its deliberate exception to a real application.

Use a fresh run marker and bounded polling to avoid stale global logs. The
current logger is not project-isolated and does not provide live locals/watch
inspection. Console, Desktop, Web, and mobile exception policies need their own
review before adopting the example in production.

## 10. Troubleshooting and recovery

| Symptom | Check / response |
| --- | --- |
| Old code or diagnostic | Verify Messages reload entry and project identity before retrying |
| No runtime log immediately after Run | Poll for new output with a deadline; check the handler and process |
| Documentation wrong version | Check XDOX's active version as well as XMCP's docs path |
| Semantic result missing a relevant API | Check embedding completion and use exact member docs |
| IPC request times out | Inspect IDE state; an IDE operation may still be running. Preserve the server connection until it answers. |
| Another automation owns the lease | Let that job finish; stale text in the lease file alone does not prove the OS lock is held |
| XDOX signature rejects Finder metadata | Preserve checksum/signature diagnostics; operate only on a disposable extracted copy. In this run, clearing `com.apple.FinderInfo` restored strict verification without re-signing. |
| Build runs but strict signature fails | Record it separately; do not describe the artifact as distribution-ready |

Close a watched project before moving/renaming its directory or project. When
recovering from a failed edit, reconcile disk and unsaved IDE changes before any
reload/revert. Use the narrowest documented reload; a broad revert can discard
human work.
