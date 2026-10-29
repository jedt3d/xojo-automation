# Xojo 2026 Through 2026r3

Reviewed 2026-10-29 against all six official release notes and the installed 2026r3 Markdown documentation. This is a decision map; use the linked release notes and installed member documentation for complete issue lists, signatures, overloads, and target compatibility. A documented fix is not a local runtime test.

For earlier changes or assessing an older project/blog/tutorial, read `migration-and-older-examples.md`. It covers all 15 releases labeled 2024/2025 and the procedure for comparing older advice with the current APIs here.

## Sources And Scope

| Release | Date | Official notes |
|---|---|---|
| 2026r1 | 2026-03-31 | [2026r1](https://documentation.xojo.com/resources/release_notes/2026r1.html) |
| 2026r1.1 | 2026-04-14 | [2026r1.1](https://documentation.xojo.com/resources/release_notes/2026r1.1.html) |
| 2026r1.2 | 2026-04-28 | [2026r1.2](https://documentation.xojo.com/resources/release_notes/2026r1.2.html) |
| 2026r2 | 2026-07-08 | [2026r2](https://documentation.xojo.com/resources/release_notes/2026r2.html) |
| 2026r2.1 | 2026-08-12 | [2026r2.1](https://documentation.xojo.com/resources/release_notes/2026r2.1.html) |
| 2026r3 | 2026-10-20 | [2026r3](https://documentation.xojo.com/resources/release_notes/2026r3.html) |

Local root: `/Users/worajedt/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation`. The same notes are `resources/release_notes/<release>.md`. All relative documentation paths below are relative to that root. Use the local Markdown for focused searches; use `.html` when a visual/table rendering is clearer. Later note files in the bundle are outside this reviewed scope.

Before implementing a component change, determine the project's minimum Xojo version, runtime OS version, target, and Windows UI backend. Read that component's current page, including Compatibility and Notes. Preserve working old-version support unless the user authorizes a newer baseline. Apply changes to the requested feature; these notes do not authorize bulk control replacement or project-format migration.

## Agentic Mode And IDE Changes

- **r3 Agentic Mode:** automatic external-file reloads, reload messages, generated `AGENTS.md`/`XOJO-CODING.md`, and agent-driven run/compile feedback. Follow `workflow.md` for the canonical synchronization procedure and keep the user's enabled mode working.
- **r3 reloads:** `ReloadChangedFiles()`, `ReloadProject()`, and `ReloadProjectItem(itemPath As String) As Boolean` are documented IDE scripting commands. Use the narrowest appropriate reload before falling back to close/reopen. Exact docs: `topics/build_automation/ide_scripting/project_commands.md`.
- **r1 custom control previews:** `DesktopUIControl` and `MobileUIControl` gained `DrawControlInLayoutEditor`; a preference controls live previews. r1.1 adds preview `Print` messages, improved error line reporting, and explicit missing-property errors. r3 adds the event to `WebCanvas` and fixes preview sizes inside `WebContainer`. Read the event documentation before writing preview code; runtime drawing and editor previews require separate validation.
- **r1 debugger:** watchpoints support expression comparisons and previous/current values. **r3:** dictionary inspection is batched. See `debugging.md` for the distinction between IDE features and tested automation capabilities.
- **r2 editing:** classes/modules and multiple code items can be copied/pasted as text; container properties can be exposed through Inspector Behavior. Rendered-layout compiler errors include generated snippets. **r3:** menu symbols preview in the menu editor; dragging an item into code inserts its name; Messages auto-scrolling can be disabled.
- **r3 defaults:** `Overrides` can also live next to the IDE or inside the macOS app's `Contents`; Windows/Linux default-value lookup was fixed. Inspect local overrides when a newly created control differs from documented defaults. Do not change the IDE bundle or global defaults as part of an ordinary project edit.
- **Jade:** r1 improves long replies and compaction; r2 adds OpenAI/OpenRouter/local providers and an AI settings panel, with source/error context requests supported for Claude/OpenAI. r3 improves request timeouts, Windows special characters, and local-base-URL errors. These built-in assistant features do not require changing the user's provider or configuring a second assistant to use external Agentic Mode.
- **Libraries:** r1 private-member obfuscation was disabled in r1.1 because of linking problems. Do not assume it protects exported library implementation details on r3. r3 also improves custom library icons and WebListBox renderer loading.

## Desktop Components

| Component / release | Change and implementation consequence |
|---|---|
| `DesktopTable` — r3 | New table with ListBox-compatible APIs and virtual data. Evaluate for new large-data interfaces; preserve existing ListBoxes unless migration is requested. `TableDataSource` supplies visible-cell data without copying all rows. Read `api/user_interface/desktop/desktoptable.md` and `api/interfaces/tabledatasource.md`, plus editable/sortable/hierarchical interfaces when needed. The table docs cover frozen rows/columns, row actions, cell containers, and style APIs. Verify each used ListBox member/event; compatibility is not proof that custom painting, subclassing, or external type contracts transfer unchanged. |
| `DesktopScrollableArea` — r2/r2.1 | Native scrolling composition option; r2.1 fixes visibility when hosted on a `DesktopPagePanel`. Prefer it for a new scrolling requirement after checking its documented container model. |
| `DesktopToolbar` / `DesktopToolbarButton` — r2/r3 | Styles and semicolon-separated symbol fallbacks; macOS multicolor symbols; WinUI toolbar support. r3 fixes icon assignment overriding a symbol and Linux toggle-button symbol rendering. r1 makes invalid `ButtonAt`/`RemoveButtonAt` indexes raise an exception; validate indexes. |
| `DesktopMenuItem` / `DesktopPopupMenu` — r3 | Symbol lists and item icons/symbols on macOS, Linux, and WinUI. Symbol editing is also available in the IDE. Classic Windows support must be checked separately. |
| `Picture.SystemImage` — r3 | Available across Desktop targets, with ordered symbol-name fallbacks. Use platform-supported symbol names and verify the result on each target; the headline does not imply universal symbol names or support on every mobile/web target. |
| `DesktopGrid` — r1/r2 | Use `ReloadFromDataSource` instead of deprecated `Reload`; new cell focus events and cell-container locking. Parent assignment in panels and runtime Width/Height handling were fixed. |
| `DesktopListBox` — r3 | `ColumnSortTypeAt` alone determines sortability; `ColumnSortDirectionAt` sets direction. Explicitly configure the sort type when sorting is intended. Linux header painting clipping was fixed. |
| `DesktopSegmentedButton` — r3 | Focus events now fire; Linux/Windows support segment focus and arrow navigation with Enter/Space selection. Test keyboard behavior when touching a segmented control. |
| `DesktopHTMLViewer` — r1/r2/r3 | macOS PDF pagination fix in r1; Windows WebView2 support in r2; optional `DesktopHTMLViewerPrintSettings` for `PrintToPDF` in r3. Read backend/target compatibility before using print settings. |
| Windows, containers, printing | Container lifetime/close crashes were fixed through r2.1/r3. New splitter cursors in r3. Linux printing, window sizing, and Windows focus/theme fixes are covered below. Existing app bugs still require a reproducer before removing workarounds. |

Desktop member docs live under `api/user_interface/desktop/`; graphics/symbol docs under `api/graphics/`. For visual changes, validate focus, theme, scaling, hierarchy, and actual runtime bounds on the affected target. Layout ownership remains as agreed in the project.

## Web Components And Behavior

| Component / release | Change and implementation consequence |
|---|---|
| New controls — r1/r2 | r1 adds `WebColorPicker`, `WebSwitch`, and `WebBarcode`; r2 adds `WebSeparator`. Use native controls where their documented behavior meets the request. Check browser capability/permissions for scanning. |
| `WebLabel` — r1/r1.1/r3 | Element-type support helps headings/semantics; generic labels no longer use the HTML form-label element. r1.1 fixes interference with other controls' Pressed events; r3 fixes multiline font/line-height preview. Check semantics and event hit areas. |
| `WebButton` — r1 | Icon support includes `WebPicture` and Bootstrap icons. Rapid Pressed events and Safari focus-ring handling were fixed. |
| `WebListBox` — r1–r3 | Prefer `ReloadFromDataSource` over deprecated `ReloadData`; editable fields inherit Bootstrap styles and get unique IDs. r2 adds `ColumnAlignmentAt`; r3 improves unsorted `AddRow`. Fixes cover selection, row removal/reordering, checkbox sorting, text/style renderers, edit alignment, Edge CellAction, and browser/server consistency on data-source reload. Validate the specific selection/editing/data-source path changed. |
| `WebTextField` / `WebTextArea` — r1/r2/r3 | `WebTextArea.AddText` in r1; `Format` in r2. r3 fixes Format/flicker issues and browser-autofill values reaching the server. Validate formatted entry and autofill, not only programmatic assignment. |
| `WebDatePicker` — r1.1/r2/r3 | Keyboard entry now raises date changes; `AllowKeyboardEntry` is documented; duplicate Nil-to-Nil events fixed; r3 adds Caption. Check keyboard/calendar input separately. |
| `WebPopupMenu` / `WebComboBox` — r1/r3 | Popup dismissal/focus and keyboard-filtering divider fixes; r3 improves large popup sizing on scroll and selected-row removal behavior. WebComboBox is grouped under Inputs in the IDE. |
| `WebCanvas` / `WebGraphics` / `WebRectangle` — r2/r3 | `DrawPath`/`FillPath` in r2; `WebCanvas.DrawControlInLayoutEditor` and `WebRectangle.Pressed` in r3. Verify live rendering separately from editor preview. |
| Layout controls — r3 | WebCheckBox/WebSwitch default Height becomes 38 (34 still allowed); WebSlider/WebProgressBar are resizable; Tab Index is editable in Inspector. WebProgressBar Caption preview and background/foreground styling improve. Apply intentional sizing, rather than rewriting all existing layouts. |
| `WebContainer`, `WebView`, panels, dialogs — r2/r3 | PanelChanged overfiring, nested-container size/locking, WebView placement/subclassing, control-set refresh, and Shown events were fixed. Dialog/container content now clips to bounds. Test nested resize, tab changes, popovers, and overflow when relevant; remove only demonstrated obsolete compensations. |
| `WebFileUploader` — r3 | Adds `FileNameAt`, `RemoveFileAt`, `FileCount`, `LastFileIndex`. Check indexes when managing queued files. |
| `WebToolbar` / `WebMapViewer` — r1–r3 | Toolbar height/menu stacking/mobile overflow fixes; Count added in r2. Map scale indicator in r1; distance, route timing, custom-style flicker, and WebGL-context release fixes follow. |
| Other event paths — r3 | `WebBarcode` stops ScanComplete after StopScan; contextual secondary clicks no longer also raise Pressed when a menu is shown. Callback disappearance is handled by `WebTimer.CallLater`; control events and batched-event dispatch were corrected. |

Web architecture changes also affect implementation:

- **r1:** new projects default `WebSession.SendEventsInBatches` and `LazyLoadDependencies` to True. Bootstrap 5.3.8, TypeScript 5.9.3, and ES2020 frontend output; Modernizr dependency removed and `WebSDKControl.BrowserCompatibility` deprecated. Check custom Web SDK code and browser requirements against current docs.
- **r1:** prefer `WebApplication.AllowAutoQuit`, `WebRadioGroup.RemoveAll`, and `RemoveAt` over their deprecated predecessors.
- **r2:** per-session DatabaseConnection support; `WebPage.Show` from `WebApplication.HandleURL` can support public paths/SEO without automatically making temporary sessions. **r3:** `WebApplication.AddURLRoute` maps URL patterns to pages. Read `api/web/webapplication.md` for route signatures rather than inventing handler types or overloads.
- **r3:** `WebApplication.UnhandledException` now allows the app to quit unless the handler returns True. Audit the handler's intended recovery semantics when upgrading.
- **r3:** WebPage Left/Top/Width/Height cannot be assigned because they have no runtime effect. Use appropriate child layout APIs, not setters on WebPage.
- **r3:** MinSockets handling and batched event delivery fixes. Validate the real browser/server flow when touching these settings.
- **r1.2:** malformed `DecodeURLComponent` input (such as a lone percent sign) no longer crashes; input validation still follows application requirements.

Docs: `api/user_interface/web/`, `api/web/`, `topics/web/`, and `topics/user_interface/web/`. Search the release notes for a control name and issue ID before carrying an older workaround forward.

## iOS Components And Platform

| Release | Changes to consult for the affected feature |
|---|---|
| r1 | Minimum deployment version becomes iOS 15. `MobileMapViewer.HasScaleIndicator`; `MobileScrollableArea`/`iOSMobileTable.Scrolled`. Prefer `iOSMobileTable.ReloadFromDataSource`, `ReloadSectionFromDataSource`, and `ReloadRowFromDataSource` over deprecated reload names. Chart legends, circular-chart Nil handling, and segmented-button iteration/selection fixes. |
| r2 | `MobilePopupMenu` and `MobileMenuItem`; button/toolbar menus; image-picker SelectionLimit. Scene-based app lifecycle. Toolbar badges and `MobileScreen.MinimizeTabBar` have iOS 26+ effects. Device Hub supports debugging with Xcode 27+. Check OS guards and lifecycle code before adopting these. |
| r2.1 | Menu-item property changes update the live UI; navigation toolbar lifetime and modal/single-button `MobileMessageBox` behavior fixed. |
| r3 — new controls | `MobileSearchField`, `MobilePrinterPicker`, `MobileDocumentViewer`, and `MobileDocumentPicker`. Read availability, presentation, callbacks, and document/printing permissions for the exact target before coding. |
| r3 — menus and symbols | Symbols for MobileButton, MobileToolbarButton, MobileMenuItem, MobileSegment, table row actions, and an iOSMobileTable.CreateCell overload. Multicolor-symbol properties on the documented iOS classes; popup menu icons/separators and IntegratedPalette mode. Popup enabling, insertion indexes, and SelectionChanged text consistency fixed. |
| r3 — text and presentation | Dynamic Type for MobileLabel, MobileTextField, MobileTextArea, MobileButton; AllowDoneButton for text fields/areas. More ShowModal presentation options, `MobileScreen.Show(makeCurrent As Boolean)`, and programmatic close for screen/container popovers. Validate large accessibility text and presentation/dismissal behavior. |
| r3 — runtime fixes | App.HandleURL custom schemes, table search alongside toolbars on iOS 26+, table-cell background on iOS 26, and empty-area Donut chart taps. Test any app workaround against the new runtime before changing it. |

Docs: `api/user_interface/mobile/`, `api/ios/`, `topics/ios/`, and class Compatibility sections. Shared `Mobile*` names do not establish identical APIs across iOS and Android.

## Android Components And Platform

| Release | Changes to consult for the affected feature |
|---|---|
| r1 — controls | Adds MobileChart, MobileColorPicker, MobilePDFViewer; Material MobileSlider with Double-valued bounds/value; MobileTextArea.BorderStyle; text KeyDown events; segmented iteration; scroll events; tab caption casing. Check numeric types and actual layout dimensions when upgrading slider code. |
| r1 — framework | FolderItem.Zip/Unzip, Barcode image conversion, locale-aware String casing. Compiler/introspection/array fixes improve compatibility; validate on Android rather than infer from Desktop success. |
| r2 — controls | Material MobilePopupMenu, MobileSwitch, MobileProgressBar; menu-item APIs and changed MobilePopupMenu.SelectionChanged parameter. TintColor/TextColor/TextFont, switch thumb styling, Indeterminate progress, and AdjustTextSizeToFit on the specified button/date-picker/label controls. Check exact callback signatures and color types in Android docs. |
| r2 — toolchain | XMLDocument/XMLReader support; Kotlin 2.3.21 and Material 1.14.0; SQLite AffectedRowCount. IsEventImplemented is hidden because it remains unimplemented for Android. Control subclass constructor fixes do not prove every constructor pattern is portable. |
| r3 — controls | MobileDocumentPicker; scrollable tab containers; Dynamic Type; Material MobileSeparator; popup icons/separators; toolbar BadgeColor/BadgeText/BadgeTextColor; Symbol on MobileButton, MobileDateTimePicker, MobileMenuItem, MobileToolbarButton, MobileSegment. Read Android symbol semantics separately from iOS SF Symbols. |
| r3 — framework | Picture.ApplyMask/CopyMask; MoviePlayer.PositionChanged; improved MobileTextField dark mode, runtime right/bottom locks, scroll-container height, URLConnection threading, semaphore behavior, Base64 MemoryBlock handling, and RGBSurface resolution. |
| r3 — deployment | Android 17 toolchain support; minimum Android version becomes 10. Shrinking/obfuscation optimization changes introspection: Default preserves it, Moderate disables framework introspection, Aggressive disables framework and user-project introspection. Check reflection/introspection dependencies before raising optimization. |

Docs: `topics/android/`, `api/android/`, and mobile control pages. Keep Android build/run evidence separate from iOS/Desktop evidence.

## macOS, Windows, And Linux

| Target | Changes that alter implementation or diagnosis |
|---|---|
| macOS — signing/debug | r1 improves team selection, entitlements/profiles and sandboxed debug, including get-task-allow for IDE runs; r1.1 fixes a post-build debug-signing interaction. r2 extends hardened/ad-hoc and console signing, App Store .pkg generation, and debug entitlements. **r2.1 reverts r2's DMG notarization packaging change** and fixes console Team=None/ad-hoc handling. r3 fixes IDE stalls after signing errors and console universal/CopyFiles behavior. Inspect current build settings, actual entitlements and artifacts before recommending a manual signing workaround. |
| macOS — runtime/UI | r2 adds iCloud-synced generic Keychain password support; r3 fixes false AddPassword failures. r3 corrects AppearanceChanged/accent updates on macOS 26+, window parenting, slider ticks, small BinaryStream writes, and legacy ZIP filename encoding. Preserve the r1 Graphics.Outline Tahoe limitation: brushes are not applied there. Inspect current member docs for any newer qualification. |
| Windows — WinUI | r1 supports DesktopTabPanel/GroupBox and more XAML events/storyboards; r2 adds toolbar, WebView2, MouseWheel and context behavior. r3 updates menu bars/context menus, fixes WebView2 shutdown, mixed-control focus, initialization focus crashes, date-picker timezone behavior, borderless text padding, and toolbar overflow dismissal. Distinguish Use WinUI from classic Win32 before selecting a fix. |
| Windows — themes/layout | Fixes across releases cover dark/high-contrast text and menus, popup selection/dismissal, HiDPI cursors/artifacts, wake-from-sleep layout, and keyboard handling. DesktopContainer.Composited works again in r2 but can prevent DesktopHTMLViewer rendering; check this before recommending compositing. r3 lets focused controls handle Escape first and improves popup font-height/dark backgrounds. |
| Windows — files/console | r3 improves Unicode Picture.Open/Save paths and console Print output, fixes folder launching choosing a same-named executable, and updates timezone mappings. Windows/Linux UInt64/Double formatting now better matches macOS; compare explicit formats in portable serialization/display code. |
| Linux | r1/r2 fix sizing, container clipping, text selection colors, Canvas offsets and path handling; minimum native control height affects alignment. r3 corrects Wayland rapid resizing, non-resizable-window programmatic sizing, printing, toggle symbols, HTMLViewer bounds/duplicate printing, and OS version reporting. PostgreSQL loads with newer glibc (including Ubuntu 25/26); SELinux execstack violations fixed. The x86_64 IDE .deb no longer mandates libsoup 2.4-1 because available v2/v3 is selected dynamically. Diagnose actual libraries/distro instead of requiring the old dependency blindly. |

## Shared APIs, DBKit, And Migration Traps

- **DBKit v2 (r3):** DatabaseConnection support, related-table display, and lazy loading; requires 2026r3 and supports Desktop/Web. Inspect the actual DBKit version in the project before adapting a sample. Read `topics/databases/dbkit.md`, `topics/databases/dbkit-conversion-guide.md`, and `api/databases/dbkit/dbkit.md`; obtain the example matching the target through the IDE rather than assuming the converted snapshot is v2. Copy its module from the same project type as the destination. DBKit currently provides no row locking, so evaluate concurrent edits in a multiuser application.
- **Databases:** r1 adds Database.MetaData. r2 adds AffectedRowCount for SQLite/PostgreSQL/ODBC (unsupported ODBC drivers return -1); Android has its documented variant. r3 `DatabaseColumn.Type` raises InvalidArgumentException for a missing column, replacing -1. Typed writes to noneditable rows raise DatabaseException. SQL with RETURNING uses SelectSQL and returns a RowSet. r3 fixes stale ODBC errors and SQLite backup/close failures.
- **Threads:** r2 corrects Thread.Sleep rollover and makes SleepCurrent reject preemptive calls. Current docs describe a largely concurrency-safe framework with exceptions including XojoScript and Runtime.IterateObjects; protect shared mutable resources, keep UI access on the supported UI-update path, and read the exact class's thread contract. This does not prove all app code or plugins are thread-safe.
- **Delegates (r3):** invoking a weak-referenced target that has gone out of scope is a no-op; do not depend on NilObjectException as its lifetime signal.
- **Graphics/PDF:** r2 adds ShadowBrush on PDFGraphics; r1/r3 fix chart/PDF output paths. Fractional coordinates can blur high-contrast edges on standard-resolution displays; use intentional rounding only where appropriate.
- **Language/data:** r3 adds Math.E/PI/Tau; JSONItem.Compact is documented deprecated. r2.1 clarifies architecture-dependent pointer widths, Int32 Office collection indexes, case-insensitive Select Case string comparison, empty String.ToArray output, and alpha-inclusive Str(Color) output. Read the current type docs when serializing values or writing declares.

For a bug not called out here, search the six local release notes by component, method, or issue ID. Keep observed local results distinct from vendor-reported fixes, especially for platforms not exercised on this Mac.
