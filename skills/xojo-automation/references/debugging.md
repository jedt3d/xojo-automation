# Debugging And Runtime State

## Current Boundary

Xojo IDE Communicator can drive Run/Stop and some debugger commands, but tested symbols did not expose reliable locals, watch values, stack frames, or current variable state.

Stable production scope:

- Analyze Project
- build/run/stop-debug lifecycle
- structured compile diagnostics
- project-side logging or instrumentation

Experimental scope:

- breakpoint/step commands
- debugger transport observation
- project-side `Break` fixtures

Avoid as production paths:

- binary patching
- runtime injection
- decompilation for implementation copying
- bypassing signing/SIP
- private memory scraping

## Practical Runtime Strategy

Xojo 2026r1 added debugger watchpoints, including comparison expressions and previous/current values. They are not currently supported for Android. On 2026r3 dictionary inspection loads entries in batches of 50. These are IDE capabilities; they do not establish a programmatic watchpoint/locals API in this harness. Read the Setting watchpoints section in `getting_started/using_the_ide/running_the_project.md` when a watchpoint helps, and retain the tested Communicator boundary above until a new probe proves otherwise.

When runtime state matters:

1. Prefer a tiny reproducible fixture or targeted method.
2. Add reversible logging or a `DebugProbe` module.
3. Use the `Break` keyword only in IDE-run fixtures when a deterministic pause is useful.
4. Run through the harness.
5. Remove or guard instrumentation after the issue is understood.

Official docs note: `Break` pauses into the debugger only when running in the IDE and is ignored in built standalone apps.
