# Migration And Older Xojo Examples

Use when migrating an old project, adapting a blog/tutorial, diagnosing a historical workaround, or deciding whether an API 1/API 2 example applies. Reviewed 2026-10-29: all 15 releases labeled 2024/2025, plus the six 2026 releases covered by `2026-changes.md`. The implementation baseline remains the user's installed 2026r3, subject to each project's agreed compatibility requirements.

## Sources And How To Resolve Differences

Documentation root: `/Users/worajedt/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation`. Paths below are relative to this root. Historical notes are `resources/release_notes/<release>.md`; public equivalents are linked in the release table.

Read these guides only for the relevant branch:

- API generations and Desktop conversion: `topics/api_design/moving_to_api_2.0.md` ([official guide](https://documentation.xojo.com/topics/api_design/moving_to_api_2.0.html)).
- Concrete compatibility traps and conversion scope: `resources/updating_older_projects.md` ([official guide](https://documentation.xojo.com/resources/updating_older_projects.html)).
- Old iOS Text/Auto/framework code: `resources/ios_api_2.0_changes.md`.
- Status terminology: `resources/deprecations.md`; search the specific class/member's current and deprecated pages for its actual replacement and availability.
- Web performance advice: `topics/web/web_app_optimization.md`, checked against current class pages and the release timeline below.

Prefer the project's actual implementation/configuration and reproducible behavior, then exact current member signatures/Compatibility/Notes plus the relevant release fixes. Overview guides and historical notes provide context; old samples and blog posts provide ideas. If these conflict, record the conflict and verify the smallest affected call/event on the target instead of silently choosing one source.

The installed deprecations overview's newest release table is 2024r1, while 2025r3 records the removal of REALSQLDatabase. Treat the overview as an entry point, not an exhaustive current availability list; read subsequent notes and specific API pages.

Even official guides can contain old snippets. For example, the installed Web optimization guide uses `ImageView1.Picture`, while the current `WebImageViewer` page documents `Image`. Check the concrete class/member before copying the snippet. Similarly, an older general statement that Web runs on one core needs checking against current Thread/WebThread contracts; adding preemptive support does not make UI/session code automatically parallel-safe. Avoid repeating historical user-capacity estimates as current load-test evidence.

## Decide How Far Back To Investigate

The reviewed 2024r1–2026r3 range is a starting map, not a research cutoff or a requirement to read every intervening release. Decide the investigation depth autonomously from the affected API and the question; routine read-only historical research does not need another user confirmation.

- Start with the project's/source's version, the exact current member docs, and relevant entries in this map. If these resolve compatibility and the proposed behavior, an earlier release-note sweep adds little.
- Judge change rate within the affected subsystem: repeated signature/event changes, platform additions, bug fixes, regressions, and reversals justify a closer release-by-release trace. Whole-IDE feature/bug totals do not measure the stability of one API. Sparse search results are incomplete evidence, not proof of stability.
- Extend earlier when the source predates this map and a relevant introduction, rename, removal, prerequisite, or workaround origin remains unresolved; when a note points to an older issue; or when project behavior contradicts the current account. API-generation transitions, early Android support, Web framework/SDK changes, and platform backends are useful boundaries to investigate, rather than arbitrary calendar years.
- Search by class/member, former names, issue ID, and target first. Read the matching release and nearby patches, then trace relevant later corrections forward to the destination version. Broaden the interval only when the evidence exposes another unresolved dependency or transition.
- Stop when the evidence supports a concrete compatibility verdict and implementation choice, with material uncertainties resolved or explicitly bounded. If release notes do not settle runtime behavior, use a focused target-specific fixture instead of continuing an unrelated historical sweep.
- Briefly explain the choice when it affects the recommendation: why older notes were needed, or why current docs and the reviewed range suffice. Record newly inspected sources and reusable findings with their actual scope; inspecting one older issue does not establish a complete additional year of review.

## Assess An Older Blog Or Tutorial

1. Read the actual source when a URL is supplied. Establish its publication/update date, stated Xojo version, platform, framework generation, third-party dependencies, and intended behavior. If a version is absent, infer only from concrete API names and label that inference.
2. Identify the project's own generations below. A publication date alone does not establish API compatibility: a new article may intentionally teach legacy controls, and an old algorithm may still be useful unchanged.
3. Check each API that the proposed implementation will use: current class, exact overload, parameters/return type, event and AddHandler signature, indexing, errors, lifecycle, OS/backend availability, and ownership/session context. Look at deprecated pages when a legacy name is hidden from normal autocomplete.
4. Search the historical release notes for the affected member and issue; trace later fixes and reversals through 2026r3. Treat a patch release's repeated Highlights as inherited features, not a fresh introduction date. Distinguish feature addition, rename/deprecation, removal, behavior change, bug fix, and documentation-only correction.
5. Give a short verdict: **use as written**, **adapt the named APIs/behavior**, **use only for the existing legacy target**, or **reuse the concept with a current implementation**. Cite the decisive current member docs and release/issue when available. If evidence is incomplete, state the specific unverified point rather than declaring the whole article valid or obsolete.
6. Implement only within the user's task and compatibility baseline. Use a small fixture or the affected project path to test the changed behavior; report the target, IDE/build mode, and what was actually executed. Do not describe an unrun platform as validated.

A useful assessment is concrete: “This 2025 example's WebListBox idea applies, but use RowsReordered rather than the introduction note's DragReorderRows, and use CellRendererAt for the renderer object; current CellTextAt is textual.” The class's current page resolves the same-release introduction/rename wording.

## Identify The API Generation First

| Evidence in the project/example | Interpretation and migration route |
|---|---|
| Core API 1 names such as `RecordSet`, `SQLSelect`, error flags, `Date`, or legacy string/file members | API 2 changes began before this reviewed release range: the official guide identifies 2019r2. Follow exact replacement docs and translate error/return semantics along with names. |
| `Window`, `PushButton`, `ContainerControl` versus `DesktopWindow`, `DesktopButton`, `DesktopContainer` | Desktop-prefixed controls arrived in 2021r3. Old and new controls can coexist in supported IDEs; a core API 2 method does not prove a Desktop API 2 UI. Check event definitions, inheritance, typed parameters, and delegates when converting. |
| iOS `Text`, `Auto`, and iOS-prefixed legacy controls | iOS API 2 support began in 2020r2 with String/Variant and Mobile classes. Read the iOS migration guide; the same Mobile class name does not prove Android support. |
| A Web 1 project or Web 1 custom control/JavaScript | Web framework generation is a separate migration dimension from core/Desktop API 2. Establish the source framework and current supported APIs; preserve portable logic while evaluating UI, SDK, styles, events, and deployment separately. The official deprecations guide identifies 2019r3.2 as the last Web 1 release. |
| Android code | Check Android-specific Compatibility/Notes and release availability. Kotlin/Android Declares and handles require their own signatures; Desktop/iOS success is not Android evidence. |

Deprecated means still available under the stated support conditions; removed means unavailable. Do not turn the old API 2 migration guide's gradual-transition advice into a permanent availability promise: `REALSQLDatabase`, for example, was removed in 2025r3.

## Migrating An Existing Project

1. Record the source IDE version if known, project format, target OS/architectures, minimum supported IDE/runtime versions, control/API generations, plugins/libraries/Declares, build steps, and current diagnostics. Keep a recoverable copy or source-control checkpoint before saving in a newer format or running broad conversion. Opening in a new IDE is distinct from authorizing a format conversion.
2. Establish what already compiles/runs on the intended destination. Read `workflow.md` before IDE interaction, including Agentic Mode synchronization. For a migration audit, check whether the deprecation analysis warning is enabled; absence of warnings otherwise does not prove API 2 compliance. Record any analysis-setting change.
3. Separate required repairs from optional modernization. Fix removed APIs, invalid signatures, supported-OS/build requirements, and reproduced behavior regressions first. Preserve functioning legacy code where the task permits. Newer UI defaults do not authorize rewriting every serialized property.
4. Convert a coherent item or feature at a time. The IDE provides Project > Update Controls to API 2.0 and more limited class/window/container/control/menu conversions; use the scope the user requested. Retest subclass event forwarding, AddHandler/RemoveHandler, interface conformance, indexing, data-source behavior, and error handling after each slice. Avoid mechanical global replacement.
5. Verify affected runtime flows and release artifacts where relevant: event order/count, programmatic value changes, selections, database transactions, theme/scaling, Web browser/server interaction, mobile permissions/lifecycle, plugin architecture/minimum OS, and signing. Use the current member docs for the particular behavior; a clean compile alone cannot prove a migrated callback is wired.

Two documented Desktop traps deserve an explicit check: converting PushButton subclasses may require changing custom Action event definitions/forwarding to Pressed; SegmentedControl cannot be converted to DesktopSegmentedButton by merely changing Super, so controls and event code must be moved deliberately. Keep the human's UI ownership agreement when choosing the conversion route.

## API And Behavior Map

The release and issue identify evidence, not permission to bulk-edit code. Read the current member page for exact overloads and compatibility.

| Older assumption / boundary | Verified change and consequence |
|---|---|
| Numeric `FromText`; `TextShape.Value` | 2024r1 deprecates numeric FromText in favor of FromString, and TextShape.Value in favor of Text (#75458, #74594). Verify locale/encoding and the intended number conversion; do not replace arbitrary user-defined FromText methods. |
| `DesktopDisclosureTriangle.Pressed` | 2024r1 notes the ValueChanged rename and requires moving event code (#67597). The note uses the shortened “DesktopDisclosure” name; verify the actual class in `api/user_interface/desktop/desktopdisclosuretriangle.md`. |
| Boolean `Database.Connect`, error flags, SQLSelect/SQLExecute | API 2 uses exception-oriented Connect/SelectSQL/ExecuteSQL and RowSet. 2024r2/r4 correct Connect deprecation markers (#68003, #76760); rewrite the success/error control flow, not just the method name. |
| Provider-specific last-inserted IDs | 2024r2 adds the ID-returning Database.AddRow overload and deprecates SQLite.LastRowID/MySQL.LastInsertedRowID (#76031). Confirm the database's ID column and correct overload; DatabaseConnection gains implicit instances/subclassing in 2025r2 (#78837), then per-session Web support in 2026r2. |
| Editing a RowSet without EditRow; manual COMMIT workaround | 2025r2 makes a missing EditRow raise DatabaseException (#78777). 2024r4 fixes PostgreSQL RowSet.SaveRow commit behavior (#64077). Reproduce transaction behavior before removing application-level transaction logic. |
| `SQLiteException` or `REALSQLDatabase` | SQLiteException is deprecated in 2025r1 in favor of DatabaseException (#78203); REALSQLDatabase is removed in 2025r3 (#34421). These have different migration urgency. |
| `String.Characters`/`Codepoints` are iterators; length means glyphs | 2024r2 returns arrays from Characters and Codepoints and adds CharacterCount (#76078, #76166, #76172). Check explicit Iterable declarations and distinguish bytes, code points, and user-visible characters. 2025r3 fixes upper-range emoji Codepoints on Windows/Linux (#79304). |
| Old selection/index values silently tolerated | 2025r1 DesktopListBox/WebListBox/WebComboBox SelectedRowIndex changes raise OutOfBoundsException for invalid values (#78107, #78110, #78111). Validate bounds, including empty lists and source reloads. 2025r3.1 corrects DesktopContainer.PanelIndex on Windows/Linux to zero-based (#71195). |
| Programmatic UI changes never raise events | 2024r4 adds/corrects selection/value/text events on iOS and WebRadioGroup/WebDatePicker; 2025r2 does so for iOS MobileSwitch. WebTabPanel programmatic PanelChanged is corrected in 2025r3. Review handlers for reentrancy/duplicate work instead of manually raising every event. |
| Stable container event order across every platform/release | 2024r1 changes DesktopContainer Resized/Opening behavior; 2024r3 explicitly reverts the order on Linux (#55578, #76025). 2025r2 fixes locked-container resize delivery (#79157); 2025r3.1 fixes Web panel events before Opening (#80467). Test the target-specific lifecycle rather than encode a universal historical order. |
| Every visible historical event remains supported | DesktopMoviePlayer/HTMLViewer mouse events are removed in 2024r3, DesktopSearchField mouse events in r4; 2025r2 removes never-supported HTMLViewer drag events while fixing supported focus/key events. Check current class events before moving old callback code. |
| WebListBox cells hold arbitrary values/renderers through CellTextAt | 2025r1 makes CellTextAt String-based and adds CellRendererAt (#73946). 2025r3 adds renderer ToString integration (#79370). Use the renderer API when the object is needed; check data-source mode separately. |
| Web row-reorder event named DragReorderRows | 2025r1 introduces reordering and also records its rename to RowsReordered (#77913, #60616). Use current WebListBox event signatures. |
| Old Web count, bulk-add, rectangle, segment, cursor names | 2025r1: WebPopupMenu.Count → RowCount, WebComboBox.AddAllRows → AddRow. 2025r2: WebRectangle.BackgroundColor/HasBackgroundColor → FillColor/HasFillColor. 2025r3: WebSegment.Title → Caption. 2024r2: System.WebCursors → WebStyle.Cursors. Check exact receiver and overload. |
| Web content is interpreted as HTML by default | 2025r2 changes WebBreadcrumb/WebSegmentedButton/WebListBox to escape HTML by default (#78828). Preserve intended plain text and use only documented explicit HTML/rendering paths where needed. |
| Cookie SameSite Off/None defaults stay unchanged | 2025r3 renames Off to None and changes defaults to Lax, extending cookie removal/clearing parameters (#79652, #79663, #79661). Inspect the actual enum and login/embed flow; retain intended cookie policy when adapting an older recipe. |
| JSON formatting is configured only on JSONItem | 2025r1 adds JSONOptions for JSONItem.ToString/GenerateJSON (#74489); JSONItem.Compact is documented deprecated in 2026r3. Match compactness, decimal precision, and serialized output when changing code. |
| Threads are all cooperative / any framework is safe to share | 2024r3 adds Thread/Semaphore/CriticalSection.Type; 2025r2 adds Android preemptive support. Check lock type, UI-update route, shared mutable state and plugin contracts; follow current Thread notes and 2026 fixes. |
| Async work completes on object destruction | 2024r4 stops Shell.Completed firing merely because Shell goes out of scope (#55312); 2025r3 releases URLConnection response buffers sooner (#59626). Preserve object lifetime and capture results through documented completion paths. |

For 2026 changes such as ReloadFromDataSource names, WebApplication exception handling, DesktopListBox sorting, DatabaseColumn.Type, and Android optimization/introspection, continue with `2026-changes.md` instead of duplicating that map here.

## Web Optimization History

| Release | What changed and what older advice needs rechecking |
|---|---|
| 2024r1 | Memory/session/temporary-file leak fixes; WebResponse can buffer in memory; quicker WebCanvas tab rendering and less unnecessary ListBox refresh. Inspect the original leak/performance symptom before retaining a workaround. |
| 2024r2 / r2.1 | More efficient server CPU use, better WebListBox large-data-source performance, Control Sets, runtime panels, row/header dimensions. r2.1 fixes early regressions in ComboBox, indicators, ListBox, and charts. A tutorial's eager loading or manual panel recreation may no longer be required. |
| 2024r3 | Native CSSClasses, Bootstrap 5.3.3 / Icons 1.11.3, improved focus/keyboard/layout. Put class names in CSSClasses, not CSS declaration text; inspect the current DOM/SDK before using old selectors. |
| 2024r4 | Deferred Tooltip/CSSClasses allocation, WebLabel element reuse, session-aware WebTimer.CallLater; Canvas refresh throttling and event/lifecycle fixes. Use session-aware callbacks when appropriate and verify ownership/cleanup. |
| 2025r1 / r1.1 | ListBox editable/checkbox cells, drag/drop and row reorder; fixes avoid redundant data-source calls, stale DOM references and focus/layout errors. Data-source mode has distinct supported operations; read current WebListBox notes. |
| 2025r2 / r2.1 | DataTables moves 1.13.4 → 2.2.2; renderer/selection/data-fetch fixes, dialog queuing, timer cleanup, richer WebStyle states. r2.1 fixes column resizing, multiple dialogs, and leftover DOM styles. Old DataTables/CSS/JavaScript assumptions require fresh inspection. |
| 2025r3 / r3.1 | On-demand frontend dependencies with WebSDK LazyLoadDependencies events; ListBox frozen columns, editable-cell focus/hints and renderer ToString. r3.1 fixes panel/layout/runtime-event regressions and WebAuthn behavior. Check SDK dependency timing rather than assume libraries exist immediately. |
| 2026r1–r3 | New projects default batching/lazy dependencies to True; framework payload/performance updates and later batching/data-source fixes. Bootstrap 5.3.8, ES2020, and removal of Modernizr dependency change the baseline for custom frontend code. Details are in `2026-changes.md`. |

The installed WebSession docs still mark SendEventsInBatches and LazyLoadDependencies experimental, while 2026r1 notes set them True for new projects. Report both facts; neither establishes the setting in a migrated project. Inspect the actual project values and test custom SDK events, startup, and dependency loading before proposing a change.

Measure the relevant browser payload/request count, event traffic, server CPU, memory per session and user-visible latency on the real flow. Check whether the cost is database work, duplicate fetches, rendering, network latency, or framework behavior. Use native data sources, caching, and current controls when they solve the observed cause. Vendor performance fixes do not guarantee a speedup for a particular app or justify replacing its architecture.

## Android History And Portability

| Release | Changes that alter advice from older examples |
|---|---|
| 2024r1 | Numerous SQLite RowSet/DatabaseRow, binary stream, JSON, introspection, locking/layout and transpiler corrections. Many “Android behaves differently” workarounds need a current reproducer; type discovery does not prove readability, writability, or invocation. |
| 2024r2 | TCPSocket and major Graphics additions; more consistent string slicing and introspection. Readable methods and exception/type details continue evolving; check current interface definitions. |
| 2024r3 | Tablet layouts, RegEx, more native handles, Declares/library callbacks/imports, text selection and focus. Using clauses are supported on items, while the in-code Using command is explicitly not added by that change. |
| 2024r4 | Kotlin 2.0/K2, ByRef, Structures, localized strings, Operator_Convert/Lookup. Recheck old claims that these are absent; later releases also fix edge cases. Non-global extension methods remain an explicit limitation in these notes, so check current docs before proposing one. |
| 2025r1 | Initial ColorGroup/dark mode, AndroidMobileUserControl, SDK 35/Android 15 build target, more consistent framework behavior. This is a compile target, not proof of the minimum runtime Android version. |
| 2025r2 / r2.1 | Preemptive threads/UI-update support, MobileMapViewer, UserAuthentication, clipboard pictures, edge-to-edge, manifest/SDK configuration, JitPack and ANDROID_HOME support. r2.1 fixes release APK signing and a release-build regression. Current toolchain requirements take precedence over old setup recipes. |
| 2025r3 | PDFDocument, richer graphics/brush/text APIs, colors and appearance events; Kotlin 2.2.20; SQLite encryption re-enabled. Some Ptr setters now compile but explicitly raise PlatformNotSupportedException at runtime (#79648): compilation is not proof of implementation. |
| 2026r1–r3 | Native controls and Material styling expand; XML arrives, toolchains advance, minimum Android becomes 10, and optimization changes introspection. Check the detailed current map and actual build settings before porting a Desktop/iOS control recipe. |

## Release Lookup And Patch Boundaries

These are release labels, not calendar-year buckets: 2024r4.2 shipped in 2025 and 2025r3.1 in 2026. Search the exact labeled release and later patches when diagnosing a workaround.

| Release / date | Relevant evidence to inspect |
|---|---|
| [2024r1](https://documentation.xojo.com/resources/release_notes/2024r1.html) — 2024-03-26 | Numeric/TextShape deprecations, disclosure event change, popovers/barcodes, Web memory fixes and extensive Android corrections. |
| [2024r1.1](https://documentation.xojo.com/resources/release_notes/2024r1.1.html) — 2024-04-15 | Popover checkbox/click coordinates, round buttons, barcode size, Linux movie repeat, debugger window list. |
| [2024r2](https://documentation.xojo.com/resources/release_notes/2024r2.html) — 2024-06-26 | DatabaseConnection/AddRow ID, Unicode APIs, Web data sources/Control Sets/panels, Android sockets/graphics. |
| [2024r2.1](https://documentation.xojo.com/resources/release_notes/2024r2.1.html) — 2024-07-17 | SQLite connection path fallback, ODBC IsConnected, barcode minimum OS and Web regressions. |
| [2024r3](https://documentation.xojo.com/resources/release_notes/2024r3.html) — 2024-10-01 | Preemptive threads, Android tablets/Declares/RegEx, CSSClasses; 32-bit Windows/Linux deprecation. |
| [2024r3.1](https://documentation.xojo.com/resources/release_notes/2024r3.1.html) — 2024-10-23 | Thread sleep/stop, preemptive Timer.CallLater and encoding-race fixes; Android Studio Ladybug compatibility. |
| [2024r4](https://documentation.xojo.com/resources/release_notes/2024r4.html) — 2024-12-10 | Integrated Mac signing, atomic reference locks, TLS1.3/redirect options, Kotlin2/K2 and Android language support; Windows 8.1 deprecation. |
| [2024r4.1](https://documentation.xojo.com/resources/release_notes/2024r4.1.html) — 2024-12-17 | ListBox selection, chart/dialog regressions, menus and numeric conversion. |
| [2024r4.2](https://documentation.xojo.com/resources/release_notes/2024r4.2.html) — 2025-01-22 | CancelCallLater across threads, sheet Show behavior, list/menu layout, iOS App Store build and unsigned conversion regressions. |
| [2025r1](https://documentation.xojo.com/resources/release_notes/2025r1.html) — 2025-03-25 | Web editing/dragging, Android dark mode, native Windows ICU, JSONOptions, App Store publishing, Linux ARM64 IDE. |
| [2025r1.1](https://documentation.xojo.com/resources/release_notes/2025r1.1.html) — 2025-04-28 | Build/notarization logs now only on errors; Mac bundle version grouping, Linux ARM64 build-script fix, Web data-source editing and restored plugin property writes. |
| [2025r2](https://documentation.xojo.com/resources/release_notes/2025r2.html) — 2025-07-08 | Aggressive-optimized frameworks, Random.UUID, PrintToPDF, DataTables2, Android threading/map/auth and SDK settings. |
| [2025r2.1](https://documentation.xojo.com/resources/release_notes/2025r2.1.html) — 2025-07-28 | Android release signing/build regressions and Web sizing/dialog/style cleanup. |
| [2025r3](https://documentation.xojo.com/resources/release_notes/2025r3.html) — 2025-12-09 | DesktopGrid, Libraries/Jade, Tahoe/iOS26 compatibility, Web lazy dependencies/passkeys, Android PDF and removal of REALSQLDatabase. |
| [2025r3.1](https://documentation.xojo.com/resources/release_notes/2025r3.1.html) — 2026-01-21 | Library access, IsDebugBuild function, Thread.StartMethod delegate/result changes, Grid/media defaults, Web/WinUI fixes and PanelIndex correction. |

Check supported targets before carrying old deployment instructions forward. In 2025r1 Windows requirements move to Windows Server 2019 build 1809+, Windows 10 1703+, or Windows 11 with built-in ICU; current docs/build artifacts may add requirements. iOS minimum rises to 14 in 2025r1 then 15 in 2026r1, and plugins can raise effective minimum OS. Historical deprecation of 32-bit builds is distinct from proving their status in the installed IDE.

Version-specific remedies can also expire: 2024r1's MoviePlayer/Wayland limitation was followed by a 2025r3 fix requiring gstreamer1.0-gtk3; 2025r1 updates Linux URLConnection to libsoup3 with fallback, and 2026r3 changes IDE package dependencies again. Diagnose actual runtime/backend/dependencies before recommending the old workaround. Preserve the user's enabled platform features while fixing the cause.
