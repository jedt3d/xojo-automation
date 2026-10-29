# Milestone 2: coordinated Analyze and Run

Validated on 2026-10-29 with Xojo 2026r3 (26.3.0.3.68307), macOS ARM64,
and the milestone-1 pin of XMCP 1.11.0. This milestone implements a repository
CLI and persistent worker for **opt-in local Console text projects with flat
code items**. It does not qualify Desktop, Web, iOS, Android, Windows or Linux.

## Delivered behavior

- Project identity combines the expected running IDE path, scripting version,
  canonical project path, and a source digest. A wrong project is rejected before
  stamping or Run. The operation script checks identity and loaded stamps again.
- Agentic reload synchronization waits for the IDE to return the temporary
  `CoordinationStamp` of every managed item. A fixed sleep does not establish
  readiness. Manifest/resources/build steps are explicitly pinned inputs.
- Compiler diagnostics come from the matching serial MCP reply. Runtime events
  carry run ID, project ID, source revision and the compiled stamp, written to a
  fresh private job location. Stale events cannot complete another job.
- A separate worker owns the shared GUI lease and XMCP connection. Client
  deadlines and cancellation request cleanup without disconnecting pending IDE
  IPC. A late reply cannot change a deadline outcome into success.
- Cleanup stops the guarded run, checks captured PID/start-time/executable
  identities, restores only worker-owned file bytes, verifies restored stamps,
  stops XMCP, and releases the lease. Conflicting human edits are preserved and
  reported as a cleanup failure.

The [coordination guide](coordination.md) documents commands, profile setup,
artifacts, exit codes, instrumentation and recovery. The
[developer reference](developer-reference.md) explains the implementation seams.
No additional server, model, package dependency or global MCP registration is
required. The repository skill points agents to this workflow; the installed
personal skill has not been replaced.

## Validation and retained evidence

There are **10 distinct live scenarios with matching expected outcomes**, across
the initial suite and targeted recovery run, plus a separate successful guarded
Analyze. This is not a claim that every attempt passed. The complete ten-case
suite recorded nine matching outcomes and one cleanup failure; the failed case
was then retried successfully after recovery.

| Scenario | Expected result | Evidence directory |
| --- | --- | --- |
| Wrong project profile | Reject without source changes or Run | `final-live/wrong-project` |
| Baseline Run | Fresh completion; restored source | `recovery-live/baseline` |
| Deliberate compiler error | Current `MissingMilestoneType` diagnostic | `final-live/compile-error` |
| Edited code and stale event | New revision/message accepted; stale event rejected | `final-live/edited-source-and-stale-event` |
| Deliberate exception | Current exception, message and stack | `final-live/runtime-error` |
| Long-running app | Capture and stop owned debug process | `final-live/hold-and-stop` |
| Cancel file during runtime | Cancelled, then clean up | `final-live/cancel-running-app` |
| SIGTERM to worker | Cooperative cancellation, then clean up | `final-live/signal-worker-cancellation` |
| Client deadline during an IDE request | Client exits 2; worker drains and restores | `final-live/client-deadline` |
| Deadline after app starts | Fresh started event; captured process stopped; deadline retained | `recovery-live/runtime-deadline` |
| Guarded Analyze | Current reply, stamp restoration confirmed | `analyze` |

Paths above are relative to
[`evidence/2026-10-29-milestone-2`](../evidence/2026-10-29-milestone-2/).
Each job retains its request, protocol journal, result, worker log and available
runtime events. The [validation index](../evidence/2026-10-29-milestone-2/validation.json)
selects the accepted scenario evidence and records cleanup. The
[coordinator tests](../evidence/2026-10-29-milestone-2/coordinator-tests.txt)
cover 17 cases, including a real Unix mock IPC peer behind a subprocess MCP
forwarder. The [existing harness tests](../evidence/2026-10-29-milestone-2/harness-tests.txt)
cover another 12 cases. The packaged skill also passed its structural validator.

Mock coverage includes reload failure preventing Run, source conflict preservation,
lease contention, pre-existing debug rejection, PID reuse, late-reply draining,
stale-event rejection and quarantining uncertain requests until the IDE exits.
These exceptional paths were not forced against the user's live IDE.

## Failures that changed the implementation

1. Numeric version comparisons produced IDE scripting floating-point warnings,
   contaminating exact stamp responses. Guards now compare the documented
   formatted version string. The failed job is retained under
   `development-attempts/version-number-warning`.
2. Literal Base64 padding `=` in a Xojo constant tag was truncated on import.
   The serializer now writes `\x3D`, and the loaded constants and runtime probe
   confirmed the full stamp. Evidence is under
   `development-attempts/base64-padding-truncation` and `first-success`.
3. The first live test driver assumed every deadline reached the reload barrier.
   A valid earlier deadline exposed that assertion error; the first suite is
   retained under `live`. The driver now distinguishes pre-barrier deadlines
   and requires a started event/captured process for the runtime-deadline case.
4. The first full-suite runtime-deadline attempt reported `cleanup_failed`:
   XMCP said every IPC socket candidate was absent. Xojo kept the same PID;
   its endpoint later returned. A launch-failure dialog was found when the Mac
   became accessible and was cleared before retrying. The endpoint disappearance's
   cause is unknown; screen lock is not established as its cause. The failure is
   retained under `final-live/runtime-deadline`.

Cleanup now retries only the pinned backend's explicit **all socket files absent**
response, with one shared 30-second recovery budget. Such an attempt was not
delivered. Ambiguous delivery, partial writes and accepted requests are never
replayed. The retry branch is mock-tested; the successful live retry did not
reproduce the endpoint outage. The recovered baseline and runtime-deadline both
finished with no cleanup errors and no remaining fixture debug process.

## Remaining boundaries

This is a cooperative handoff protocol. Other clients and the human must respect
the lease and avoid editing handed-over items. Compare-before-write detects
observed conflicts, but cannot make an uncooperative concurrent rename atomic.
The revision covers configured project inputs, not an entire SDK/plugin/asset
dependency graph. Fixed inputs must already be reconciled and loaded when pinned.

Runtime diagnostics require the explicit Console probe; this is not a debugger
variable/stack inspection API. A completion event proves that the instrumented
check ran, not general application correctness. No new signing or target build
qualification was performed in this milestone.

A backend timeout, partial write or broken protocol with potentially live IPC
puts the worker in quarantine. It retains the lease until the expected IDE exits
or XMCP has exited. There is no verified safe forced-cancellation API. Preserve
work and resolve the IDE manually if a request cannot drain. Crash/force-kill
recovery and native MCP attachment in a fresh agent session remain future work.

The disposable fixture was returned to baseline with `UNSET` stamps, then closed.
Xojo was left at its original project chooser with no blocking dialog; the shared
lease was released. Agentic Mode was not toggled.
