# Coordinated IDE jobs

Milestone 2 adds a persistent worker around the evaluated XMCP 1.11.0 server.
The supported profile in this milestone is a **local macOS Console text project
with flat code items, Xojo 2026r3, and Agentic Mode already enabled**. Desktop,
Web, mobile, remote execution, nested/external code items, and Windows/Linux
hosts need their own adapters and validation. The CLI rejects other project types.

## What the boundary does

1. Acquire the same `/tmp/xojo-gui-automation.lock` used by the existing harness.
2. Verify one running IDE at the expected application path and verify the project
   and IDE version returned through XMCP. Reject an existing target debug app.
3. Snapshot managed files and pinned manifest/resource/build-step inputs.
4. Temporarily stamp each opt-in item with a run UUID, project ID, source digest,
   and private output location. Compare source bytes before each replacement.
5. Poll documented `ConstantValue("Item.CoordinationStamp")` until every item
   reports the requested stamp. This is the reload barrier; there is no fixed
   sleep, manual revert, forced reload, or project reopen.
6. Recheck project/version and loaded stamps **inside the same IDE script** that
   invokes Analyze or Run. Check the disk snapshot before/after dispatch.
7. Associate the matching MCP reply and runtime events with this run/revision.
8. Stop this run, verify captured PID/start-time/executable identities, restore
   owned stamps, confirm their reload, stop XMCP, and release the lease.

Every participating agent/IDE client must respect the lease. Raw XMCP, direct
Communicator calls, and manual editing can bypass it. Run these jobs only while
the named source items are handed to automation. The byte comparisons detect
observed conflicts; they do not provide filesystem transactions against an
uncooperative writer racing the final rename.

## Run the supplied fixture

Build the pinned XMCP as described in the [user guide](user-guide.md). Open
`fixtures/coordinated-smoke/CoordinatedSmoke.xojo_project` in Xojo 2026r3. Leave
its Agentic Mode setting on and save/reconcile IDE edits before handing it over.

From the repository root:

```sh
python3 scripts/xojo_coordinator.py run \
  --profile fixtures/coordinated-smoke/coordination.json \
  --xmcp "/absolute/path/to/XMCP"
```

The first output line identifies the job directory and worker PID. The default
job deadline is 120 seconds and the reload-probe deadline is 15 seconds. Use
`--operation analyze` for analysis only. `--completion started` checks readiness
and then cleans up; the default `completed` waits for the app's completion event.
Neither is a general assertion about business correctness.

Use `--detach` to return after launching the worker. A detached client's exit
code reports submission, not the final job outcome. Inspect or wait for it:

```sh
python3 scripts/xojo_coordinator.py status /absolute/path/to/job
python3 scripts/xojo_coordinator.py wait /absolute/path/to/job --timeout 30
python3 scripts/xojo_coordinator.py cancel /absolute/path/to/job
```

Foreground exit codes: `0` means a completed successful job; `1` means a finished
failure; `2` means the worker is still draining, quarantined, or the client's
wait ended. **Exit 2 is not permission to kill the worker or start an unguarded
IDE command.** Inspect the job until it finishes.

## Deadline and cancellation behavior

The caller and worker are separate processes. The worker owns the lease, XMCP,
and its pipes. A client deadline or Ctrl-C records cancellation and returns
without cutting an in-flight connection. Normal worker SIGTERM/SIGHUP signals
also request cancellation. The worker waits for the outstanding reply, then
cleans up. No second request is sent while the first is pending.

XMCP's own tool timeout is set generously (24 hours); the coordinator's shorter
deadline determines the client outcome. A late reply cannot turn a deadline
failure into success. If the backend reports unresolved IPC or the protocol is
broken, the worker enters **quarantined** state and retains the lease/connection
until the expected IDE exits or XMCP has already exited. It never quits the IDE.

There is no verified safe forced-cancellation API for a permanently stuck IDE
request. Preserve work in Xojo, resolve its modal/operation if possible, and let
the reply drain. If that is impossible, close that IDE yourself after preserving
work; the worker can then release the connection. Do not SIGKILL the worker/XMCP
while the IDE might still answer. Recovery after an OS crash or force-kill is
outside the guarantees of this milestone.

Cleanup retries a command for up to 30 seconds only when the pinned XMCP response
explicitly says every candidate IPC socket file is absent. That proves this
attempt was not delivered. Accepted, partial-write, and ambiguous requests are
never replayed. The retry budget is shared across cleanup operations.

## Diagnostics and artifacts

Each private job directory contains:

| File | Contents |
| --- | --- |
| `request.json` | Profile, executable paths, run ID, operation and limits |
| `result.json` | Current phase, outcome, source/project identities, diagnostics, cleanup state |
| `protocol.jsonl` | Timestamped requests/replies, stderr, and heartbeats |
| `runtime.jsonl` | Fresh app events; only matching run/project/revision/stamp records are accepted |
| `worker.log` | Worker process output/errors |
| `cancel` | Optional cancellation request |

Compile errors come from this job's matching MCP response. The coordinator does
not read `XojoCompileErrors.txt` or the shared `/tmp/xmcp_debug.log`. App exceptions
come from the opt-in runtime probe, including message/error number/stack.

Source edits during a job cause failure. Cleanup restores a file only if its
bytes still match the worker's version. A conflicting edit is preserved and
reported as `cleanup_failed`; reconcile that item before the next job. Logs may
contain private application diagnostics, so review them before publishing.

## Adapting another Console project

This is explicit instrumentation, not a transparent wrapper for arbitrary
projects. First import `CoordinationProbe.xojo_code` in the IDE and add a public,
non-dynamic String constant named `CoordinationStamp`, initially `UNSET`, to
every managed code item. Add suitable probe calls to your app:

```xojo
CoordinationProbe.Emit("started", CoordinationStamp)
' Application checks/work...
CoordinationProbe.Emit("completed", CoordinationStamp)
```

Use the fixture's `UnhandledException` handler as the Console logging example;
review exception/debugger policy before adopting it. The supplied helper does
nothing when its stamp is `UNSET`, so it does not create a shared global log.

Create a profile beside the project using the supplied profile as a schema
example. `items` maps actual flat manifest names to files. `fixed_inputs` maps
every remaining direct manifest/resource/build-step file to its SHA-256; include
the manifest itself. Compute hashes only after reconciling/reloading those inputs
in the IDE. A changed fixed input requires an explicit profile refresh; it is
not silently accepted. `debug_executable` must match the local Console debug name.

Revision hashes cover the configured managed and pinned files, excluding only
the generated stamp values. This is not a hermetic SDK/plugin/asset dependency
graph. Expanding that scope requires additional profile adapters.

## Reproduce validation

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/xojo-automation/tests -v
python3 scripts/test_live_coordination.py \
  --xmcp "/absolute/path/to/XMCP" \
  --evidence work/new-live-evidence
```

The live suite changes only the disposable coordinated fixture, deliberately
injects compile/runtime errors, and restores its App source at the end. The
evidence directory must be new. Keep the fixture open and avoid manual edits
throughout the suite. The original milestone-1 fixture is unchanged.
