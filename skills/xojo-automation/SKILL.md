---
name: xojo-automation
description: Assist Xojo development on macOS with text project editing, Agentic Mode, IDE diagnostics, build/run/debug workflows, older-project migration, and version-aware API or tutorial assessment. Use for `.xojo_*` projects, Xojo IDE automation, and adapting Xojo examples.
---

# Xojo Automation

## Work Mode

Choose the cheapest mode that preserves correctness:

- `Fast`: questions, brainstorming, path checks, or explanations. Keep Xojo untouched; load only the relevant reference when an API/version claim or older example needs verification.
- `Text`: scoped `.xojo_*` inspection or edits. Read project instructions and only directly relevant files. Validate with parsers or static checks before involving the IDE.
- `IDE`: Analyze, build, Run, conversion, visual checks, release work, or any operation that changes visible Xojo state. Read `references/workflow.md` and `references/diagnostics.md`, then use the shared GUI lease.

The skill can route work but cannot switch the active model by itself. Favor responsiveness for `Fast`; use full engineering reasoning for source edits, automation, diagnostics, and release evidence.

Do not start IDE mode merely because a repository contains Xojo files.

## Execution Route

1. Use text/background tools for parsing, indexing, editing, and documentation.
2. Use IDE Communicator for structured Analyze/build/run commands that do not require pointer control.
3. Use GUI automation only for dialogs, menus, screenshots, or workflows unavailable through Communicator.
4. Use a VM or dedicated Mac for unattended automation that must be isolated from the user's active keyboard and mouse.

## GUI Lease Contract

Before any foreground Xojo interaction:

1. Tell the user what will run, the expected duration, and the bounded job deadline. If the user has already authorized the workflow, proceed without asking for another confirmation.
2. Acquire the shared lease at `/tmp/xojo-gui-automation.lock`. All bundled Xojo entry points use it; never overlap jobs.
3. Relay progress at step boundaries and at least every 30 seconds during long operations.
4. Treat timeout, missing terminal response, unverified output, or incomplete cleanup as failure. Never infer success from silence.
5. Stop debug processes, resolve blocking dialogs, and release the lease on every exit path. Tell the user whether control is cleanly returned.

Do not lock the macOS session, suppress all user input, change Accessibility/security settings, or install a global keyboard/mouse interceptor. An advisory lease coordinates agents; it does not make the user's current desktop safe for unattended exclusive control.

Suggested notice:

```text
Starting Xojo GUI test: <action>. Expected <estimate>; operation deadline <deadline>.
No confirmation is needed. Please avoid mouse and keyboard input until I report completion or failure.
```

## Start Here

1. Prefer project-local truth over chat memory. Read `AGENTS.md`, Xojo-generated `XOJO-CODING.md`, legacy `AGENT.md`, and `agent/handoff.md` when present.
2. Confirm the active Xojo app/version. Current baseline: 2026r3, `/Applications/Xojo 2026 Release 3/Xojo.app` (IDE version string observed: `26.3.0.68307`).
3. If using examples, consult `references/examples-index.json`, `references/platform-summary.md`, or `references/feature-summary.md` instead of loading many example files.
4. If docs matter, consult local offline docs first: `/Users/worajedt/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation`. Use `references/2026-changes.md` for current controls/platforms. For older projects, blogs/tutorials, historical workarounds, or API 1/API 2 differences, read `references/migration-and-older-examples.md` before recommending or applying changes; its reviewed history covers 2024r1 through 2026r3.
5. For external edits, follow the Agentic Mode synchronization procedure in `references/workflow.md`. The user has enabled File > Agentic Mode for their current workflow; preserve it and keep the project open. Confirm the setting and exact project when changing projects; it is remembered per project.
6. Append to `references/learning-journal.md` only when evidence reveals a reusable behavior, corrects an existing rule, or changes future automation.
7. For release/tag work, reconcile the Git version tag with the Xojo project version metadata before tagging or immediately in the next patch release. Check `MajorVersion`, `MinorVersion`, `SubVersion`, `InfoVersion`, `LongVersion`, and `ShortVersion`; do not treat `RBProjectVersion` as the app version.

## Choose A Reference

- XMCP/XDOX selection or Agentic Mode integration: read `references/mcp-evaluation.md` for the tested versions, schemas, synchronization boundaries, and remaining integration work.
- Real user workflow, Agentic Mode reloads, manual reload fallbacks, and portability: read `references/workflow.md`.
- 2026r1 through 2026r3 control additions, API changes, platform requirements, and migration pitfalls: read `references/2026-changes.md`; follow its local documentation pointers for exact signatures.
- Older-project migration or evaluating an older blog/tutorial: read `references/migration-and-older-examples.md` for API generations, the 2024–2025 change map, fix/reversal history, and a source-assessment procedure. Check current member documentation before translating an example; choose any deeper historical investigation using its affected-API change-rate and stopping criteria.
- Analyze Project, Run, diagnostics, and harness commands: read `references/diagnostics.md`.
- Xojo text project structure and UI hierarchy docs: read `references/project-format-and-layout.md`.
- Detailed `.xojo_*` syntax and safe-editing notes: read `references/xojo-text-project-format.md`.
- Runtime debugging limits and probe strategy: read `references/debugging.md`.
- Example library and offline docs index usage: read `references/examples-and-docs.md`.
- What has been learned over time: read `references/learning-journal.md`.

## Script Tools

Use bundled scripts from this skill before rewriting automation:

- `scripts/xojo_harness.py`: doctor, probe, analyze, run, stop-debug.
- `scripts/xojo_runtime.py`: shared GUI lease, bounded operation deadlines, progress events, and heartbeat support.
- `scripts/xojo_layout_map.py`: parse `.xojo_window`, `.xojo_webpage`, or `.xojo_screen` into hierarchy docs.
- `scripts/xojo_example_converter.py`: convert `.xojo_binary_project` examples to text projects through Xojo GUI automation.
- `scripts/index_xojo_examples.py`: rebuild `references/examples-index.*`, platform/feature summaries, docs index, and learning journal entries.
- `scripts/analyze_xojo_format.py`: scan all `.xojo_*` files under the project/examples corpus and rebuild `references/xojo-format-inventory.*`.

## Core Rules

- The human owns UI layout: adding controls, arranging containers, renaming UI components, and organizing Xojo project folders.
- Codex owns non-UI source edits, generated docs, diagnostics capture, example lookup, and handoff continuity.
- On 2026r3 with Agentic Mode enabled, external edits reload automatically and appear in Messages. Verify synchronization before IDE checks; use the version-aware fallback in `references/workflow.md` if it fails or Agentic Mode is unavailable.
- Xojo release metadata has both numeric fields (`MajorVersion`, `MinorVersion`, `SubVersion`) and human-facing string fields (`InfoVersion`, `LongVersion`, `ShortVersion`). Keep them aligned with the Git tag for release commits, while preserving unrelated IDE format noise such as `RBProjectVersion` unless intentionally upgrading project format.
- Treat Xojo as a single GUI-controlled IDE process. The shared lease is mandatory for IDE and GUI automation.
- Prefer IDE Communicator v2 for structured compile diagnostics. Avoid OCR/screenshot workflows except as a weak fallback.
- Do not patch Xojo binaries, bypass signing/SIP, inject runtime hooks, or scrape private memory as a production path.

## Validation

Run the smallest useful check. Load `references/diagnostics.md` only for IDE validation and `references/project-format-and-layout.md` only for layout work.
