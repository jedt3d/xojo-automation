# Xojo Text Project Format Notes

These notes describe the observed Xojo 2026 text project format from `/Users/worajedt/XojoUIAgent` and the converted examples under `/Users/worajedt/xojoexamples`.

This is not a complete official grammar. Treat it as a practical editing guide for Codex.

## Corpus Inventory

Full scanner artifacts:

```text
/Users/worajedt/.codex/skills/xojo-automation/references/xojo-format-inventory.md
/Users/worajedt/.codex/skills/xojo-automation/references/xojo-format-inventory.json
```

Last corpus pass:

- Roots scanned: `/Users/worajedt/XojoUIAgent` and `/Users/worajedt/xojoexamples`
- `.xojo_*` files scanned: 4,406
- Text files parsed: 3,025
- Binary/opaque files inventoried: 1,380
- Unreadable files: 1, an old `.CRM.xojo_uistate` that timed out
- Tag-balance findings: 0
- `Begin`/`End` tree-balance findings: 0
- Structural unknown samples after scanner refinement: 0

## File Families

- `.xojo_project`: root project manifest. Mostly `Key=Value` lines plus project-item declarations.
- `.xojo_code`: class, module, interface, app, session, page, screen, worker, and other code-bearing items.
- `.xojo_window`: desktop window layout plus window code, control event code, and view behavior metadata.
- `.xojo_webpage`: web page/dialog/container layout and code. In the converted examples many web pages use `.xojo_code` with a top `#tag WebPage` or `#tag WebContainerControl`.
- `.xojo_screen`: mobile screen layout and code. In the converted examples many mobile screens use `.xojo_code` with a top `#tag MobileScreen`.
- `.xojo_menu`: menu tree.
- `.xojo_toolbar`: toolbar tree.
- `.xojo_filetypeset`: file type declarations.
- `.xojo_image`: text wrapper for multi-image metadata, paths, image specs, and opaque saved image information.
- `.xojo_resources`: may be binary, such as `ICNS`. Do not assume every `.xojo_*` file is text.
- `.xojo_uistate`: binary/opaque IDE state.
- `.xojo_binary_project`: binary/opaque original project format.
- `.xojo_color`: text color group declarations.
- `.xojo_report`: text report layout tree.
- `.xojo_database_connection`: text database connection sets.
- `.xojo_script`: raw IDE script source, not tag-wrapped.

Observed file counts in the corpus:

```text
.xojo_code: 1787 text
.xojo_project: 446 text
.xojo_window: 295 text
.xojo_menu: 245 text
.xojo_image: 208 text
.xojo_color: 17 text
.xojo_filetypeset: 16 text
.xojo_toolbar: 4 text
.xojo_report: 4 text
.xojo_script: 2 text
.xojo_database_connection: 1 text
.xojo_binary_project: 489 binary/opaque
.xojo_resources: 446 binary/opaque
.xojo_uistate: 445 binary/opaque plus 1 unreadable stale/cloud item
```

## `.xojo_project`

The root manifest uses simple lines:

```text
Type=Desktop
RBProjectVersion=2026.012
Class=App;App.xojo_code;&h0000000041416FFF;&h0000000000000000;false
DesktopWindow=PetProfileWindow;PetProfileWindow.xojo_window;&h0000000026085FFF;&h0000000000000000;false
Folder=Model;Model;&hFFFFFFFFA1000001;&h0000000000000000;false
Class=Pet;Model/Pet.xojo_code;&hFFFFFFFFA1000002;&hFFFFFFFFA1000001;false
DefaultWindow=PetProfileWindow
BuildFlags=&h4900
```

Project-item declarations have an observed shape like:

```text
Kind=DisplayName;relative/path;itemID;parentID;flag
```

The hex IDs and trailing fields are Xojo-owned metadata. Preserve them unless Xojo itself rewrites them.

Useful fields for classification include `Type`, `IsWebProject`, `DefaultWindow`, `AppMenuBar`, platform build architecture fields, and project item kinds such as `Class`, `Module`, `Interface`, `DesktopWindow`, `WebView`, `MenuBar`, `BuildSteps`, and `Folder`.

Release version fields need special care. In observed text projects, app version metadata can appear as both numeric fields and human-facing string fields:

```text
MajorVersion=1
MinorVersion=1
SubVersion=1
NonRelease=0
Release=3
InfoVersion=1.1.1
LongVersion=1.1.1
ShortVersion=1.1.1
```

When preparing a Git release tag such as `v1.1.1`, reconcile the Xojo project metadata before tagging:

- `MajorVersion`, `MinorVersion`, and `SubVersion` should match the semantic version numbers.
- `InfoVersion`, `LongVersion`, and `ShortVersion` should be populated with the same human-facing release string unless the project has an explicit different convention.
- `Release` and `NonRelease` are Xojo build/release-channel metadata; do not change them casually without project-specific intent.
- `RBProjectVersion` is the Xojo IDE/project-format version, not the application release version. Treat an IDE-created `RBProjectVersion` bump as unrelated local project-format noise unless the release intentionally upgrades project format.

Observed project item kinds include:

```text
Class, BuildSteps, AppIcon, DesktopWindow, MenuBar, MobileScreen,
iOSLayout, MultiImage, AppIcons, WebView, Folder, WebSession,
Module, WebContainer, iOSLaunchScreen, MobileContainer, ColorAsset,
FileTypeSet, Interface, iOSContainerControl, DesktopToolbar, Report,
LaunchImages, NotificationCenter, Worker, iOSScreen, SQLiteLocalConnection
```

## `#tag` Code Structure

Code-bearing text files use a case-insensitive `#tag ...` stack. Both `#tag` and `#Tag` occur in the corpus. Common top-level tags include:

```text
#tag Class
#tag Module
#tag Interface
#tag DesktopWindow
#tag WebPage
#tag WebContainerControl
#tag MobileScreen
#tag Menu
#tag DesktopToolbar
#tag FileTypeSet
#tag MultiImage
#tag BuildAutomation
```

Within classes/modules/windows/pages/screens, observed nested tags include:

```text
#tag Method, Flags = &h0
#tag Event
#tag Property, Flags = &h21
#tag ComputedProperty, Flags = &h0
#tag Getter
#tag Setter
#tag ExternalMethod, Flags = &h21
#tag Hook, Flags = &h0
#tag Constant
#tag ViewBehavior
#tag ViewProperty
#tag EnumValues
#tag Events ControlName
#tag Worker
#tag MenuHandler
#tag Note, Name = About
#Tag Instance, Platform = Mac OS, Language = Default, Definition = ...
```

The real Xojo source code lives inside method/event/menu handler/getter/setter/external method/hook/constant/property/note/enum/computed-property blocks, not in the whole file uniformly. A safe editor should parse tag boundaries and edit only the intended block.

`#tag Instance` and `#tag CompatibilityFlags` are singleton tags in the observed corpus; they do not have matching `#tag EndInstance` or `#tag EndCompatibilityFlags`.

Example:

```text
#tag Method, Flags = &h21
  Private Sub ClearPetProfile()
    PetNameTextField.Text = ""
  End Sub
#tag EndMethod
```

## Layout Object Trees

Windows, web pages, mobile screens, menus, and toolbars use `Begin ... End` trees:

```text
#tag DesktopWindow
Begin DesktopWindow PetProfileWindow
   Width = 852
   Begin DesktopGroupBox PetListGroupBox
      Left = 20
      Begin DesktopListBox PetListBox
         InitialParent = "PetListGroupBox"
      End
   End
End
#tag EndDesktopWindow
```

Menus and toolbars are similar:

```text
#tag Menu
Begin Menu MainMenuBar
   Begin DesktopMenuItem FileMenu
      Text = "&File"
   End
End
#tag EndMenu
```

The practical UI hierarchy should be read from nested `Begin ... End`, cross-checking `InitialParent` when present.

Two important variants appeared in the full corpus:

```text
Begin ScreenContent
  ItemName = Tab 0
End ScreenContent
```

and a compact desktop segmented button form:

```text
BeginDesktopSegmentedButton DBKit.NavigationButton NavigationButton1
   Enabled = True
End
```

So a parser should support both plain `End` and typed `End Name`, and should not assume every `Begin` keyword is followed by a space.

## Code Attached To UI Items

After a layout tree, window/page/screen files commonly include code blocks:

```text
#tag WindowCode
  #tag Method, Flags = &h21
  ...
  #tag EndMethod
#tag EndWindowCode

#tag Events PetListBox
  #tag Event
    Sub SelectionChanged()
      ...
    End Sub
  #tag EndEvent
#tag EndEvents
```

Mobile screens may use `#tag ScreenCode`; web pages in observed examples still use `#tag WindowCode` for page code sections.

Classes can also carry attributes directly on the declaration line:

```text
Attributes ( PrimaryKeyName = "ID", Version = 123 ) Protected Class TestClass
```

Methods can also use `Attributes(...)` on the declaration line inside a method tag. Treat these as source/declaration text and preserve them.

## Less Common Text Families

Color groups:

```text
#tag ColorGroup
  CodeName=KanbanCardBackgroundColorGroup
  #tag Color
    Type=2
    Platform=3
    Name=bootstrap|tertiary-bg
  #tag EndColor
#tag EndColorGroup
```

File type sets:

```text
#tag FileTypeSet
  #tag FileType
    CodeName=Png
    Extension=.png
    Flags=&h0
  #tag EndFileType
#tag EndFileTypeSet
```

Images:

```text
#tag MultiImage
Image App Icon
  #tag ImageRepresentation
    SaveInfo = ...
    FullPath = ...
    PartialPath = ...
    #tag ImageSpecification
      PPI = 72
    #tag EndImageSpecification
  #tag EndImageRepresentation
End Image
#tag EndMultiImage
```

Reports use a `Begin Report` tree with report sections such as `PageHeader`, `Body`, `GroupHeader1`, and controls such as `ReportLabel` and `ReportField`.

Database connections use `#tag DatabaseConnection` plus one or more `Begin ConnectionSet ... End` blocks.

IDE scripts in `.xojo_script` are raw script lines, not wrapped in `#tag` blocks.

## Flags And Numeric Metadata

Observed `Flags` values include:

- `&h0`: commonly public/default members.
- `&h1`: observed on protected members.
- `&h21`: observed on private members.
- `&h1000` and `&h4` also appear in examples.

Observed `CompatibilityFlags` can be target expressions, for example:

```text
#tag CompatibilityFlags = (TargetWeb and (Target32Bit or Target64Bit))
#tag Method, Flags = &h0, CompatibilityFlags = API2Only and ( (TargetDesktop and (Target32Bit or Target64Bit)) )
```

Do not fully decode or rewrite unknown flags yet. Preserve numeric flags, compatibility flags, object IDs, icon IDs, menu IDs, and other Xojo-owned numbers unless a focused fixture proves the meaning and Analyze Project passes after the edit.

Observed compatibility expressions include desktop, web, console, iOS, Android, `TargetHasGUI`, and `API2Only` combinations.

## Editing Rules

1. Preserve tag balance: every `#tag X` must keep its matching `#tag EndX`.
2. Preserve `Begin ... End` balance in UI/menu/toolbar trees.
3. Preserve unknown numeric metadata and IDs.
4. Preserve file order when possible; Xojo may care about stable item ordering.
5. Edit source blocks surgically rather than rewriting whole files.
6. Do not treat `.xojo_resources` as text.
7. Before Analyze Project, verify Agentic Mode reloads using `workflow.md`'s synchronization procedure; use manual reload or close/reopen when the version or observed state requires it.
8. Run Analyze Project after edits and let Xojo be the final parser.
9. If a new `.xojo_*` pattern appears, rerun `scripts/analyze_xojo_format.py` and update this document.

## Known Gaps

- Full bit-level meaning of every `Flags` value is not yet mapped.
- `.xojo_report`, `.xojo_color`, `.xojo_database_connection`, and `.xojo_image` are now inventoried, but should still be treated as preserve-first until a focused edit fixture proves safe mutation.
- Some Xojo-owned metadata may be regenerated by the IDE; observe before normalizing.
