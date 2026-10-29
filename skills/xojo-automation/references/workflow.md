# Xojo Workflow

## Route Work Before Opening Xojo

- `Text mode`: inspect/edit text projects, index examples, generate layout docs, or answer questions. Keep Xojo untouched.
- `IDE mode`: use Communicator for Analyze/build/run and prefer structured evidence over pointer automation.
- `GUI lease mode`: use only when menus, dialogs, screenshots, or Accessibility interaction are required.
- `Isolated mode`: use a VM or dedicated Mac for unattended, exclusive-input testing.

The skill cannot change models programmatically. Keep brainstorming and clarification response-first; reserve deeper engineering reasoning for source changes, automation, diagnostics, and release evidence.

## User Workflow

The intended first workflow is the user's real Xojo process:

1. The human creates a project manually in Xojo.
2. The human adds GUI components, arranges containers/controls, renames UI components, and organizes the Xojo project structure.
3. Codex edits non-UI code and generated agent documents outside Xojo.
4. With 2026r3 Agentic Mode enabled, keep the project open and verify automatic reloads using the synchronization procedure below before Analyze Project or Run.
5. Codex runs Analyze Project through IDE Communicator and fixes diagnostics until clean.
6. Codex runs the project and gathers deterministic evidence: terminal response, debug process, logs, output artifacts, and targeted screenshots where applicable.
7. Codex performs automatable runtime checks. Ask the human only for subjective UX judgment, hardware-dependent behavior, or a state that cannot be observed safely.
8. Stop the debug process after checks. Leave the user's Agentic Mode project open for continued collaboration. If closing is part of the task, reconcile disk and IDE changes before saving and resolve any save prompt deliberately.
9. Codex updates handoff and generated indexes/layout docs when facts changed. Update the learning journal only for reusable new evidence.

## Foreground GUI Protocol

Visible Xojo automation may compete with the user's active desktop. Before starting, send one concise notice with:

- action and project
- expected duration
- bounded job deadline
- whether mouse/keyboard input should be avoided
- confirmation that no reply is required when the workflow was already authorized

Then acquire `/tmp/xojo-gui-automation.lock` and proceed. Report each major step; for a long step, relay the harness heartbeat at least every 30 seconds.

Example:

```text
Starting Xojo GUI test for <project>. Expected 2-4 minutes; operation deadline at <time>.
No reply is needed. Please avoid mouse and keyboard input until I report completion or failure.
```

Always finish with a completion or failure notice that states whether the debug app stopped, dialogs were cleared, and the GUI lease was released.

### Safety Boundary

Do not lock the screen, disable user input, change macOS security/Accessibility settings, or install an input interceptor. Those controls can strand the user if automation hangs, and the bundled tools cannot guarantee an out-of-band recovery path. The lease bounds cooperative socket and subprocess operations; it is not an OS-level watchdog. Use isolated mode when true exclusivity is required.

## Project Handoff

Read `AGENTS.md` and `XOJO-CODING.md` before changing files. Xojo generates these in Agentic Mode; preserve project-specific additions when updating them. Also read legacy `AGENT.md` when present. If the project has `agent/handoff.md`, keep it current when facts change:

- Xojo version or app path
- active project/UI source
- tool/script behavior
- validated command results
- open problems and next steps
- portability notes for another Mac
- new example/doc lessons that should be carried into the global skill journal

## Learning Journal

The global skill journal is:

```text
/Users/worajedt/.codex/skills/xojo-automation/references/learning-journal.md
```

Append to it only when studying examples, docs, or runtime evidence teaches something reusable, corrects an assumption, or changes future Xojo automation. Keep entries short enough to scan and skip routine successful runs.

## Agentic Mode And External Edits

Baseline: Xojo 2026r3. The user reports File > Agentic Mode is already checked for their current workflow. Reuse that choice; do not toggle it off or ask them to enable it again. When selecting a different project, establish its own setting and exact path. File presence alone does not prove that Agentic Mode is active or that a reload succeeded.

For an existing project, File > Agentic Mode requires a saved text-format Xojo project. The setting persists per project. New projects offer **for AI (Agentic Mode)** in the project chooser. Text-format saving requires a Xojo license. Read the project's generated `AGENTS.md` and `XOJO-CODING.md` for its coding, documentation, and execution instructions.

### Synchronization Procedure

1. Read the latest files before each edit; preserve the human's IDE work. Complete each changed file before exposing it to the watcher. For new items, create valid companion files before adding their manifest entries. Coordinate edits to the same item rather than allowing overlapping IDE and agent writes.
2. Let Agentic Mode reload the changed items. The Messages pane lists each reload. Verify the affected items through those messages and, where needed, inspect their loaded source through documented IDE scripting. A fixed delay or the existence of instruction files is not proof of synchronization.
3. Confirm `ProjectShellPath` identifies the intended `.xojo_project` before Analyze/build/Run. With synchronization established, use the harness subcommand option `--reload-policy skip` to preserve the open project. The harness verifies identity; it does not verify watcher completion.
4. If a reload is missing or fails, inspect Messages and the edited source/manifest first. Reconcile unsaved IDE edits with disk before an operation that could discard them. On 2026r3 use the narrowest documented reload below, then verify again. Close/reopen only when needed; older IDEs without these commands use close/reopen as the compatibility fallback. Quitting the IDE is usually unnecessary.

| Operation | IDE scripting | Scope |
|---|---|---|
| File > Reload > Changed Files | `ReloadChangedFiles()` | Changed files in a text project |
| File > Reload with an item selected | `ReloadProjectItem(itemPath As String) As Boolean` | Saved text item; a folder/module includes its descendants. Check the Boolean result. |
| File > Reload > Project | `ReloadProject()` | Entire project, any project format |

These are IDE scripting calls sent through Communicator, not application runtime APIs or harness CLI subcommands. Read `topics/build_automation/ide_scripting/project_commands.md` in the current offline docs for exact behavior and item-path syntax.

Close the project before renaming the project, or moving, renaming, or deleting its containing folder. Xojo documents that changing/removing the folder while watched logs an error and disables Agentic Mode. After reopening, re-establish the intended path and mode.

Sources: [Agentic Mode](https://documentation.xojo.com/getting_started/using_the_ide/agentic_mode.html), [project scripting commands](https://documentation.xojo.com/topics/build_automation/ide_scripting/project_commands.html), and their installed 2026r3 Markdown copies.

## Portability

Use absolute local paths in reports, but write instructions so they can be adjusted on another Mac. Confirm these on a new machine:

- Xojo app path and version
- Python version
- offline docs path
- examples root
- project-local `agent/tools`, `agent/reports`, `agent/layout`, and `agent/handoff.md`
