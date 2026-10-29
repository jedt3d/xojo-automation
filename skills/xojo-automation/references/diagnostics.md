# Diagnostics And Harness

## Preferred Route

Use Xojo IDE Communicator v2 to run IDE scripts and capture structured diagnostics. It can return `response.buildError.errors` and `response.buildError.warnings` for Analyze Project failures.

Current known socket endpoint: `/private/tmp/XojoIDE`.

The 2026r2.1 docs clarify that the IDE uses the first writable temporary directory (`/tmp`, then `SpecialFolder.Temporary`) plus `XojoIDE`, or the name in `XOJO_IPCPATH`. On macOS `/tmp` normally resolves to `/private/tmp`. With a custom instance name, pass the matching full socket path via `--socket`; a matching name contains only letters, digits, and underscores. Confirm the connected IDE version and project rather than assuming an existing socket belongs to the requested app. See `topics/build_automation/ide_communicator.md` in the offline docs.

## Runtime Contract

- Interactive harness commands and example conversion share `/tmp/xojo-gui-automation.lock`.
- The lease file contains owner, action, project, start time, and deadline metadata. The OS file lock, not stale file contents, determines ownership.
- Harness progress is JSONL on stderr. Step starts/completions include elapsed time; long steps emit a heartbeat every 30 seconds.
- Structured reports remain on stdout or in `--output-json`/`--output-markdown`.
- A Communicator call succeeds only after a message containing `response`. After that terminal response, the harness waits only a short quiet window for trailing frames.
- Missing response, expired deadline, closed socket, unverified artifact, or incomplete cleanup is failure. Silence is never a clean Analyze/build/run result.
- Example conversion refuses to start while any Xojo project window is open. This protects unrelated human work from broad dialog/window cleanup.

Set the cooperative whole-job deadline before the subcommand when needed:

```bash
python3 scripts/xojo_harness.py \
  --lease-timeout 420 \
  analyze /path/to/Project.xojo_project
```

Use `--no-progress` only when another caller already supplies equivalent live status. For an already-open Agentic Mode project whose changed items have reloaded, pass `--reload-policy skip` to Analyze, compile, or run. It verifies `ProjectShellPath` and skips close/open; it does not wait for automatic reloads. The default remains `always`, which closes/reopens, for explicit fresh-open and older-IDE workflows. Apply `workflow.md`'s synchronization procedure first.

## Layout Helper Visual Rules

- For layout-only controls built on `DesktopRectangle`, do not rely only on `Transparent=True`. Clear the rectangle paint in the class:
  - `FillColor = Color.Clear`
  - `BorderColor = Color.Clear`
  - `BorderThickness = 0`
  - `CornerSize = 0`
- Call the clearing helper from both `Opening` and the layout application path so stale instance metadata cannot reintroduce a visible white strip.
- For reusable `DesktopContainer` roots used only for composition, keep `HasBackgroundColor=False` and `Transparent=True`; clear stale design-time `BackgroundColor` values when they visually confuse review.
- Make text-only `DesktopLabel` controls transparent when they sit directly on a shared app surface. Keep native controls such as text fields, buttons, popup menus, and listboxes opaque unless the specific component contract says otherwise.

## Harness Commands

Run doctor:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  doctor
```

Analyze an already-open Agentic Mode project after verifying its reloads:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  analyze --reload-policy skip \
  /path/to/Project.xojo_project
```

If communicator Analyze blocks during project close/open but the IDE is responsive, use the GUI fallback:

```bash
open -a "/Applications/Xojo 2026 Release 3/Xojo.app" /path/to/Project.xojo_project
osascript -e 'tell application "Xojo" to activate' \
  -e 'delay 0.3' \
  -e 'tell application "System Events" to tell process "Xojo" to click menu item "Analyze Project" of menu "Project" of menu bar 1'
```

After the menu Analyze, inspect for error dialogs or visible diagnostics and capture the specific project window if needed. Follow the cleanup rules below; keep the user's active Agentic Mode project open.

Run the synchronized, already-open project:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  run --reload-policy skip \
  /path/to/Project.xojo_project
```

Compile/build a universal macOS app:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  compile \
  --reload-policy skip \
  --macos-build universal \
  --build-timeout 300 \
  /path/to/Project.xojo_project
```

If Xojo produces an app but never returns a terminal response, the harness exits as a timeout failure. Inspect the build folder as independent evidence, verify the app with `file`, `lipo -info`, and `plutil`, then clean up Xojo/debug processes and project windows. Report this as "artifact verified; Communicator timed out," not as a clean harness result.

Xojo may advance `NonRelease` in the source project after a successful build when auto-increment versioning is enabled. Re-read the project file after the build and record both the source metadata and the built app's `CFBundleShortVersionString` / `CFBundleVersion`.

For Apple Silicon-only handoff builds on an Apple Silicon Mac, use `--macos-build arm` and verify the executable reports `arm64`:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  compile \
  --reload-policy skip \
  --macos-build arm \
  --build-timeout 300 \
  /path/to/Project.xojo_project

lipo -info "/path/to/Builds - Project/macOS ARM 64 bit/App.app/Contents/MacOS/App"
```

Do not hand off a completed local-test cycle without recording the build path, bundle version, signature status, and architecture verification.

For File Provider-backed build folders, strict ad-hoc verification may fail with `resource fork, Finder information, or similar detritus not allowed` even after the first cleanup. Clear `com.apple.FinderInfo` and `com.apple.fileprovider.fpfs#P` on the app root, `Contents/Frameworks/XojoFramework.framework`, and affected Xojo `.nib` package directories; sign; clear those attrs again; then run strict verification immediately.

## Current Project And Synchronization

Follow `workflow.md`'s Agentic Mode procedure to establish current source. On 2026r3, externally edited files can be validated without closing the project after their reloads are verified:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  analyze --reload-policy skip /path/to/Project.xojo_project
```

Use the same subcommand option for `compile` or `run`. On a different project or older IDE, open the explicit project path and verify it. File > Open Recent is an acceptable GUI fallback after checking the selected item's identity. The harness's explicit app path controls launch selection; verify that the connected socket belongs to that IDE instance.

Stop debugging:

```bash
python3 scripts/xojo_harness.py \
  --xojo-app "/Applications/Xojo 2026 Release 3/Xojo.app" \
  stop-debug
```

## Cleanup After Checks

- After a Codex-driven check, stop the debug app. Keep the user's Agentic Mode project open by default so automatic reload and collaboration continue. Close only a disposable test project, a project opened solely for a bounded check, or when the task calls for closing it.
- Before saving or closing, reconcile unsaved IDE work with external disk edits; then persist intended metadata and user edits. Avoid a blind Command-S over changes the IDE has not loaded.
- Use `stop-debug` for the debug app. When closing is appropriate, use `CloseProject(False)` through the IDE Communicator and resolve any prompt intentionally.
- Treat Xojo save prompts as blocking modal state. After any close/quit command, explicitly check for a save/discard/cancel dialog and choose intentionally:
  - Save when Xojo-generated metadata is part of the intended result, such as an auto-incremented version counter, deliberate user layout edits, or this user's active Xojo workflow.
  - Do Not Save when the run only produced transient IDE state, window placement, chooser state, or accidental metadata churn.
  - Cancel only when more inspection is required.
- Cleanup is not complete while a save prompt is open; the modal can block later Analyze/Run/build automation even if the shell command returned.
- Verify cleanup: no debug process started for the check, no blocking dialog, lease released, and the intended project either remains open for Agentic Mode or is closed as requested. Report that state explicitly.

## Interpreting Analyze

- Clean Analyze Project may return no diagnostics; that is success.
- Warnings count as diagnostics when the user's goal is "no error and warning at all".
- For unused parameters or locals, prefer Xojo-appropriate `#Pragma Unused name` when the value is intentionally unused.
- If `source` in the diagnostic frame is partial or empty, read the referenced local `.xojo_code`/`.xojo_window` file to reconstruct the line.

## Runtime Errors

The harness can run and stop a debug app, but direct variable/stack inspection is not available through the tested IDE Communicator surface. First gather process, log, artifact, and screenshot evidence or add reversible project-side instrumentation. Ask the human only for behavior that cannot be observed safely or for subjective UX judgment.

If the communicator `run` command reaches its bounded deadline while the IDE appears idle and no debug app launches, let the harness fail and release its lease before using the Xojo GUI Run command as a fallback:

```bash
osascript -e 'tell application "Xojo" to activate' \
  -e 'delay 0.3' \
  -e 'tell application "System Events" to keystroke "r" using command down'
```

After GUI Run, verify with the same process/window checks and targeted screenshots. Never start a fallback while another process owns the shared GUI lease.

Canvas-heavy custom controls may not expose useful macOS Accessibility elements. For `DesktopCanvas` components, validate rendering with targeted window screenshots, and validate click behavior manually or with temporary app-side instrumentation when AX click targets are absent.

## macOS Targeted Window Screenshots

For visual proof of Xojo desktop apps, prefer window-ID screenshots over whole-screen or rectangle screenshots. A rectangle capture can still include unrelated overlapping windows; `screencapture -l <window-id>` captures only the chosen window.

Use CoreGraphics from Swift when Python does not have PyObjC/Quartz installed:

```bash
swift -e 'import CoreGraphics; let opts = CGWindowListOption(arrayLiteral: .optionOnScreenOnly, .excludeDesktopElements); if let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] { for w in list { let owner = w[kCGWindowOwnerName as String] as? String ?? ""; let name = w[kCGWindowName as String] as? String ?? ""; let id = w[kCGWindowNumber as String] as? Int ?? 0; if owner.contains("Northwind") || owner.contains("Xojo") || name.contains("XjNorthwind") { print("\(id)|\(owner)|\(name)|\(w[kCGWindowBounds as String] ?? "")") } } }'
screencapture -x -l <window-id> /tmp/xojo-window.png
```

For process checks, avoid matching the `pgrep` command itself by using a bracketed pattern:

```bash
pgrep -af '[N]orthwind\.debug|[N]orthwind Debug|[X]ojo Debug' || true
```

## macOS Developer ID Signing Readiness

For a local machine readiness check before distributing a Xojo-built Mac app outside the Mac App Store, verify all of these:

- Xcode command line tools are selected: `xcode-select -p`.
- Required tools are present: `codesign`, `spctl`, `ditto`, `xcrun notarytool`, and `xcrun stapler`.
- A valid `Developer ID Application` identity appears in `security find-identity -v -p codesigning`.
- The private key is usable, not just the public certificate: sign a disposable `.app` with `codesign --force --timestamp --options runtime --sign "Developer ID Application: ..."` and verify with `codesign --verify --deep --strict --verbose=2`.
- The App Store Connect API key authenticates with `xcrun notarytool history --key ... --key-id ... --issuer ...`.
- A `Developer ID Installer` certificate is only needed for signed flat `.pkg` workflows. Zip or DMG distribution can use a Developer ID Application-signed and notarized app without an installer certificate.
