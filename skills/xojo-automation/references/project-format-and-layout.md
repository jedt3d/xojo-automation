# Project Format And Layout

## Text Project Files

Xojo text projects use a root `.xojo_project` manifest plus companion files such as:

- `.xojo_code`
- `.xojo_window`
- `.xojo_webpage`
- `.xojo_screen`
- `.xojo_menu`
- `.xojo_toolbar`
- `.xojo_resources`
- `.xojo_image`

The project manifest declares project items with lines such as:

```text
Type=Desktop
Class=App;App.xojo_code;...
DesktopWindow=Window1;Window1.xojo_window;...
WebView=WebPage1;WebPage1.xojo_code;...
```

Use `Type`, `IsWebProject`, `DefaultWindow`, and item declarations to classify project shape.

For detailed notes on `#tag` blocks, `Begin ... End` object trees, magic flags, and safe editing boundaries, read `xojo-text-project-format.md`.

## Layout Docs

Xojo may show controls as a flat list even when containers, rectangles, pages, or screens establish a practical hierarchy. Use the layout map tool to preserve the nested `Begin ... End` hierarchy and source freshness metadata.

Check freshness:

```bash
python3 scripts/xojo_layout_map.py \
  /path/to/Window.xojo_window \
  --out /path/to/agent/layout/Window.layout.md \
  --check
```

Regenerate:

```bash
python3 scripts/xojo_layout_map.py \
  /path/to/Window.xojo_window \
  --out /path/to/agent/layout/Window.layout.md
```

## Human/Codex Boundary

The human owns UI layout and component naming. Codex may interpret layout docs, generate hierarchy maps, and edit non-UI source, but should not rearrange visual controls unless explicitly asked.
