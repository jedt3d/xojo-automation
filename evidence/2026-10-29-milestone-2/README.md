# Milestone-2 evidence

Start with [validation.json](validation.json) for the selected result of each
of ten distinct live scenarios, the separate Analyze, environment and cleanup.
The [milestone report](../../docs/milestone-2-coordination.md) explains failures,
retries, implementation changes and limits.

- `development-attempts/`: failed version warning/Base64 imports and first success.
- `live/`: first suite; eight actual outcomes matched, then the driver failed an
  assertion that incorrectly required synchronization on an early deadline.
- `final-live/`: complete ten-case attempt; nine matched, runtime-deadline had a
  cleanup failure while the IPC endpoint was absent.
- `recovery-live/`: baseline and runtime-deadline successful retries, after clearing
  the fixture launch-failure dialog. Endpoint outage cause remains unknown.
- `analyze/`: separate successful guarded Analyze.
- `*-tests.txt`: final automated test output; `checks.json` records other checks.

Each job retains raw request/result/protocol and available runtime data. Absolute
paths and timestamps describe this test machine; do not copy them as portable
configuration. `manifest.json` hashes the retained evidence and implementation
inputs. No builds, upstream executables, models or documentation database are
included. A failed attempt is historical evidence, not the current acceptance.
