#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_EXAMPLES_ROOT = Path("/Users/worajedt/xojoexamples")
DEFAULT_DOCS_ROOT = Path("/Users/worajedt/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation")
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "references"

TEXT_SUFFIXES = {
    ".xojo_project",
    ".xojo_code",
    ".xojo_window",
    ".xojo_webpage",
    ".xojo_screen",
    ".xojo_menu",
    ".xojo_toolbar",
    ".xojo_filetypeset",
    ".txt",
    ".md",
}

FEATURE_KEYWORDS: dict[str, list[str]] = {
    "ai": ["chatgpt", "groqai", "openai"],
    "android": ["android"],
    "api2": ["api 2", "api2"],
    "applescript": ["applescript", "apple script"],
    "automation": ["ide scripting", "idecommunicator"],
    "canvas": ["canvas", "graphicscontext", "drawpicture"],
    "chart": ["chart", "graphing", "graph"],
    "console": ["console", "stdin", "stdout", "stderr", "standardinput"],
    "container": ["container", "containercontrol", "webcontainer"],
    "crypto": ["crypto", "rsa", "encrypt", "decrypt"],
    "database": ["database", "databaserow", "rowset", "selectsql", "executesql", "preparedstatement"],
    "dbkit": ["dbkit", "bindable"],
    "declares": ["declare", "soft declare", "external method"],
    "desktop": ["desktop", "desktopwindow", "desktopcontrol"],
    "design-patterns": ["singleton", "factory", "observer", "interpreter", "lazy initialization"],
    "drag-drop": ["drag and drop", "dragitem", "dropobject"],
    "files": ["folderitem", "specialfolder", "binarystream", "textinputstream", "textoutputstream", "filetype"],
    "graphics": ["graphics", "graphicspath", "opengl", "drawpicture", "bezier", "pdfgraphics"],
    "ios": ["ios", "iphone", "ipad"],
    "json": ["json", "parsejson", "generatejson"],
    "layout": ["constraint", "auto-layout", "autolayout", "layout"],
    "listbox": ["listbox", "desktoplistbox", "weblistbox"],
    "menu-toolbar": ["menu", "menubar", "toolbar"],
    "networking": ["socket", "tcp", "udp", "urlconnection", "http", "webservice", "ipcsocket"],
    "pdf": ["pdf", "pdfdocument", "pdfpage", "pdfannotation"],
    "printing": ["printer", "printing", "print"],
    "raspberry-pi": ["raspberry", "wiringpi", "gpio"],
    "shell": ["shell", "execute", "executeasync"],
    "sqlite": ["sqlite", "sqlitedatabase"],
    "text": ["styledtext", "regex", "textinputstream", "textoutputstream"],
    "threading": ["thread", "timer", "worker"],
    "web": ["web", "webpage", "websession", "webapplication"],
    "websdk": ["websdk", "sdkcontrol"],
    "xml": ["xml", "xmlreader", "xmldocument"],
}

IMPORTANT_DOC_PATTERNS = [
    "agentic_mode",
    "ai_quickstart",
    "api/user_interface/",
    "api/interfaces/",
    "api/graphics/",
    "api/android/",
    "api/ios/",
    "topics/android/",
    "topics/ios/",
    "topics/macos/",
    "topics/windows/",
    "topics/linux/",
    "topics/user_interface/",
    "topics/api_design/",
    "topics/web/",
    "api/web/",
    "resources/updating_older_projects.md",
    "resources/ios_api_2.0_changes.md",
    "resources/deprecations.md",
    "resources/release_notes/2024r1.md",
    "resources/release_notes/2024r1.1.md",
    "resources/release_notes/2024r2.md",
    "resources/release_notes/2024r2.1.md",
    "resources/release_notes/2024r3.md",
    "resources/release_notes/2024r3.1.md",
    "resources/release_notes/2024r4.md",
    "resources/release_notes/2024r4.1.md",
    "resources/release_notes/2024r4.2.md",
    "resources/release_notes/2025r1.md",
    "resources/release_notes/2025r1.1.md",
    "resources/release_notes/2025r2.md",
    "resources/release_notes/2025r2.1.md",
    "resources/release_notes/2025r3.md",
    "resources/release_notes/2025r3.1.md",
    "resources/release_notes/2026r1.md",
    "resources/release_notes/2026r1.1.md",
    "resources/release_notes/2026r1.2.md",
    "resources/release_notes/2026r2.md",
    "resources/release_notes/2026r2.1.md",
    "resources/release_notes/2026r3.md",
    "ide_communicator",
    "ide_scripting",
    "docommand",
    "project_commands",
    "text_commands",
    "running_the_project",
    "/break",
    "targetdesktop",
    "targetweb",
    "targetios",
    "targetandroid",
    "targetconsole",
    "database",
    "sqlite",
    "webapplication",
    "desktopapplication",
    "consoleapplication",
    "xojo_library",
]


def read_text(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[:limit] if limit else text


def parse_project(project: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    settings: dict[str, str] = {}
    items: list[dict[str, str]] = []
    for raw_line in read_text(project).splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if ";" in value and key[:1].isupper():
            parts = value.split(";")
            if len(parts) >= 2:
                items.append({"kind": key, "name": parts[0], "file": parts[1]})
        else:
            settings[key] = value
    return settings, items


def infer_platform(project: Path, examples_root: Path, settings: dict[str, str]) -> str:
    rel = str(project.relative_to(examples_root)).lower()
    project_type = settings.get("Type", "").lower()
    if project_type.startswith("web") or "platforms/web/" in rel or "/web/" in rel:
        return "web"
    if project_type == "console" or "console" in rel:
        return "console"
    if "android" in rel:
        return "android"
    if "ios" in rel or project_type == "mobile":
        return "ios"
    if project_type == "desktop":
        return "desktop"
    return project_type or "unknown"


def nearby_text_files(project: Path) -> list[Path]:
    names = {
        normalize_name(project.stem),
        normalize_name(project.parent.name),
    }
    scored: list[tuple[int, Path]] = []
    for depth, folder in enumerate([project.parent, project.parent.parent, project.parent.parent.parent]):
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in {".txt", ".md"} and not path.name.startswith("._"):
                doc_name = normalize_name(path.stem)
                score = 0
                if doc_name in names:
                    score = 100 - depth
                elif any(doc_name and (doc_name in name or name in doc_name) for name in names):
                    score = 80 - depth
                elif depth == 0:
                    score = 50
                if score:
                    scored.append((score, path))
    deduped = {path: score for score, path in scored}
    return [path for path, _ in sorted(deduped.items(), key=lambda item: (-item[1], str(item[0])))]


def normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def clean_snippet(text: str) -> str:
    text = text.replace("\\n", " ")
    text = text.replace('""', '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text[:320]


def extract_descriptions(project: Path, items: list[dict[str, str]]) -> list[str]:
    snippets: list[str] = []
    for doc in nearby_text_files(project):
        text = read_text(doc, 4000)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            snippets.append(clean_snippet(f"{doc.name}: {' '.join(lines[:4])}"))
    files = []
    for item in items:
        item_file = item.get("file", "")
        if item_file.endswith((".xojo_window", ".xojo_webpage", ".xojo_screen", ".xojo_code")):
            files.append((project.parent / item_file).resolve())
    for file_path in sorted(set(files))[:20]:
        text = read_text(file_path, 60000)
        for match in re.finditer(r'Text\s*=\s*"([^"]{20,1000})"', text):
            value = clean_snippet(match.group(1))
            lower = value.lower()
            if "example" in lower or "demonstrates" in lower or "illustrates" in lower:
                snippets.append(value)
                break
        if len(snippets) >= 4:
            break
    deduped: list[str] = []
    for snippet in snippets:
        if snippet and snippet not in deduped:
            deduped.append(snippet)
    return deduped[:4]


def project_text_for_tags(project: Path, examples_root: Path, settings: dict[str, str], items: list[dict[str, str]]) -> str:
    parts = [str(project.relative_to(examples_root)), settings.get("Type", "")]
    parts.extend(f"{item.get('kind','')} {item.get('name','')} {item.get('file','')}" for item in items[:80])
    for doc in nearby_text_files(project)[:4]:
        parts.append(read_text(doc, 1200))
    for item in items[:20]:
        file_name = item.get("file", "")
        if file_name.endswith((".xojo_code", ".xojo_window", ".xojo_webpage", ".xojo_screen")):
            parts.append(read_text(project.parent / file_name, 6000))
    return "\n".join(parts).lower()


def infer_tags(text: str, platform: str) -> list[str]:
    tags = {platform}
    for tag, keywords in FEATURE_KEYWORDS.items():
        if any(keyword_matches(text, keyword) for keyword in keywords):
            tags.add(tag)
    return sorted(tags)


def keyword_matches(text: str, keyword: str) -> bool:
    if any(ch.isspace() for ch in keyword) or not keyword.replace("_", "").isalnum():
        return keyword in text
    return re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", text) is not None


def summarize_project(project: Path, examples_root: Path) -> dict[str, Any]:
    settings, items = parse_project(project)
    platform = infer_platform(project, examples_root, settings)
    text_for_tags = project_text_for_tags(project, examples_root, settings, items)
    rel = project.relative_to(examples_root)
    item_counts = Counter(item["kind"] for item in items)
    category = rel.parts[0] if rel.parts else ""
    return {
        "name": project.stem,
        "relative_path": str(rel),
        "folder": str(project.parent.relative_to(examples_root)),
        "category": category,
        "type": settings.get("Type", ""),
        "platform": platform,
        "tags": infer_tags(text_for_tags, platform),
        "default_window": settings.get("DefaultWindow", ""),
        "is_web_project": settings.get("IsWebProject", ""),
        "item_counts": dict(sorted(item_counts.items())),
        "notable_items": [
            item for item in items
            if item["kind"] in {"Class", "Module", "Interface", "DesktopWindow", "WebView", "WebSession", "iOSView", "MobileScreen", "AndroidScreen"}
        ][:24],
        "descriptions": extract_descriptions(project, items),
    }


def build_docs_index(docs_root: Path) -> list[dict[str, str]]:
    docs = []
    if not docs_root.exists():
        return docs
    for path in sorted(docs_root.rglob("*.md")):
        rel = str(path.relative_to(docs_root))
        lower = rel.lower()
        if any(pattern in lower for pattern in IMPORTANT_DOC_PATTERNS):
            first_heading = ""
            for line in read_text(path, 3000).splitlines():
                if line.startswith("#"):
                    first_heading = line.lstrip("#").strip()
                    break
            docs.append({"relative_path": rel, "heading": first_heading})
    return docs


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_examples_markdown(path: Path, index: list[dict[str, Any]], root: Path) -> None:
    by_platform = Counter(item["platform"] for item in index)
    by_category = Counter(item["category"] for item in index)
    lines = [
        "# Xojo Examples Index",
        "",
        f"Generated from `{root}`.",
        "",
        "## Platform Counts",
        "",
    ]
    lines.extend(f"- `{name}`: {count}" for name, count in by_platform.most_common())
    lines.extend(["", "## Top Categories", ""])
    lines.extend(f"- `{name}`: {count}" for name, count in by_category.most_common(30))
    lines.extend(["", "## Projects", ""])
    for item in index:
        descriptions = " ".join(item["descriptions"][:1])
        lines.append(
            f"- `{item['relative_path']}` | platform `{item['platform']}` | tags `{', '.join(item['tags'][:10])}`"
            + (f" | {descriptions}" if descriptions else "")
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_platforms_markdown(path: Path, index: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in index:
        grouped[item["platform"]].append(item)
    lines = ["# Xojo Platform Summary", ""]
    for platform in sorted(grouped):
        projects = grouped[platform]
        tag_counts = Counter(tag for item in projects for tag in item["tags"])
        lines.extend([f"## {platform}", "", f"- Projects: {len(projects)}"])
        lines.append(f"- Common tags: {', '.join(tag for tag, _ in tag_counts.most_common(16))}")
        lines.append("- Representative examples:")
        for item in projects[:20]:
            lines.append(f"  - `{item['relative_path']}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_features_markdown(path: Path, index: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in index:
        for tag in item["tags"]:
            grouped[tag].append(item)
    lines = ["# Xojo Feature Summary", ""]
    for tag in sorted(grouped):
        projects = grouped[tag]
        lines.extend([f"## {tag}", "", f"- Projects: {len(projects)}", "- Representative examples:"])
        for item in projects[:18]:
            desc = item["descriptions"][0] if item["descriptions"] else ""
            lines.append(f"  - `{item['relative_path']}`" + (f" - {desc}" if desc else ""))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_docs_markdown(path: Path, docs: list[dict[str, str]], docs_root: Path) -> None:
    lines = ["# Xojo Offline Docs Index", "", f"Docs root: `{docs_root}`", ""]
    for doc in docs:
        heading = f" - {doc['heading']}" if doc["heading"] else ""
        lines.append(f"- `{doc['relative_path']}`{heading}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_learning_journal(path: Path, index: list[dict[str, Any]], docs: list[dict[str, str]], append: bool) -> None:
    by_platform = Counter(item["platform"] for item in index)
    tag_counts = Counter(tag for item in index for tag in item["tags"])
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = [
        f"## {now} - 444-example index pass",
        "",
        "- Indexed all converted Xojo example text projects rather than relying on folder names alone.",
        f"- Platform distribution: {', '.join(f'{name}={count}' for name, count in by_platform.most_common())}.",
        f"- Most common feature tags: {', '.join(f'{name}={count}' for name, count in tag_counts.most_common(18))}.",
        "- Project manifests expose useful structure through `Type`, `DefaultWindow`, `IsWebProject`, and project item declarations such as `DesktopWindow`, `WebView`, `Class`, `Module`, `Interface`, and `BuildSteps`.",
        "- Many examples include human descriptions in nearby `.txt` files or visible label text inside window/webpage files; the indexer captures those snippets when present.",
        "- The skill should use examples as a searchable reference library, not as bulk context. Load `examples-index.json` or feature/platform summaries only when the task needs them.",
        f"- Offline docs index captured {len(docs)} current-version documentation files relevant to automation, build commands, target platforms, databases, and debugger work.",
        "",
    ]
    if path.exists() and append:
        path.write_text(path.read_text(encoding="utf-8") + "\n" + "\n".join(entry), encoding="utf-8")
    else:
        path.write_text("# Xojo Automation Learning Journal\n\n" + "\n".join(entry), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Index converted Xojo examples and offline docs for the xojo-automation skill.")
    parser.add_argument("--examples-root", default=str(DEFAULT_EXAMPLES_ROOT))
    parser.add_argument("--docs-root", default=str(DEFAULT_DOCS_ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--append-journal", action="store_true")
    args = parser.parse_args()

    examples_root = Path(args.examples_root).expanduser().resolve()
    docs_root = Path(args.docs_root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    projects = sorted(path for path in examples_root.rglob("*.xojo_project") if not path.name.startswith("._"))
    index = [summarize_project(project, examples_root) for project in projects]
    docs = build_docs_index(docs_root)

    write_json(out_dir / "examples-index.json", index)
    write_json(out_dir / "offline-docs-index.json", docs)
    write_examples_markdown(out_dir / "examples-index.md", index, examples_root)
    write_platforms_markdown(out_dir / "platform-summary.md", index)
    write_features_markdown(out_dir / "feature-summary.md", index)
    write_docs_markdown(out_dir / "offline-docs-index.md", docs, docs_root)
    write_learning_journal(out_dir / "learning-journal.md", index, docs, append=args.append_journal)

    summary = {
        "projects": len(index),
        "platforms": Counter(item["platform"] for item in index),
        "top_tags": Counter(tag for item in index for tag in item["tags"]).most_common(20),
        "docs": len(docs),
        "out_dir": str(out_dir),
    }
    print(json.dumps(summary, indent=2, default=dict, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
