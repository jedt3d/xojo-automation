#!/usr/bin/env python3
"""Inventory Xojo text-project file formats across a corpus.

This scanner is intentionally conservative. It does not try to fully parse
Xojo source code; it catalogs the outer text-project structure, validates
tag/object-tree balance, and records patterns that future editing tools should
preserve.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ROOTS = [
    Path("/Users/worajedt/XojoUIAgent"),
    Path("/Users/worajedt/xojoexamples"),
]

TAG_RE = re.compile(r"^\s*#tag\s+(.+?)\s*$", re.IGNORECASE)
BEGIN_RE = re.compile(r"^\s*Begin\s+(\S+)(?:\s+(.+))?\s*$")
COMPACT_BEGIN_RE = re.compile(r"^\s*Begin([A-Z][A-Za-z0-9_\.]*)(?:\s+(.+))?\s*$")
END_OBJECT_RE = re.compile(r"^\s*End(?:\s+(\S+))?\s*$")
ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s*=\s*(.*)$")
PROJECT_RE = re.compile(r"^([^=]+)=(.*)$")
FLAGS_RE = re.compile(r"\bFlags\s*=\s*([^,]+)")
COMPAT_RE = re.compile(r"\bCompatibilityFlags\s*=\s*(.+)$")

NO_END_TAGS = {"CompatibilityFlags", "Instance"}
SOURCE_TAGS = {
    "Method",
    "Event",
    "Getter",
    "Setter",
    "ExternalMethod",
    "Hook",
    "Property",
    "Constant",
    "Note",
    "EnumValues",
    "ComputedProperty",
    "Enum",
    "MenuHandler",
    "DelegateDeclaration",
    "Structure",
    "ReportCode",
}
DECLARATION_RE = re.compile(
    r"^\s*(?:Attributes\s*\([^)]*\)\s*)?"
    r"(Protected|Private|Public|Global|Implicit|Shared)?\s*"
    r"(Class|Module|Interface|Structure|Enum|Delegate)\b",
    re.IGNORECASE,
)
END_DECL_RE = re.compile(r"^\s*End\s+(Class|Module|Interface|Structure|Enum)\s*$")


def relpath(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            return f"{root.name}/{path.relative_to(root)}"
        except ValueError:
            pass
    return str(path)


def counter_dict(counter: Counter[str], limit: int | None = None) -> dict[str, int]:
    items = counter.most_common(limit)
    return {k: v for k, v in items}


def is_probably_text(sample: bytes) -> bool:
    if b"\0" in sample:
        return False
    if not sample:
        return True
    control = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return (control / max(len(sample), 1)) < 0.02


def tag_base(content: str) -> str:
    first = content.split(",", 1)[0].strip()
    first = first.split("=", 1)[0].strip()
    return first.split()[0] if first else ""


def project_item_kind(key: str, value: str) -> bool:
    if ".xojo_" in value:
        return True
    return key in {
        "Class",
        "Module",
        "Interface",
        "DesktopWindow",
        "WebView",
        "MenuBar",
        "BuildSteps",
        "Folder",
        "IOSView",
        "MobileScreen",
        "Toolbar",
        "FileTypeSet",
        "Report",
        "Image",
        "DatabaseConnection",
        "ExternalItem",
    }


def add_sample(samples: dict[str, list[str]], key: str, value: str, limit: int = 8) -> None:
    bucket = samples.setdefault(key, [])
    if value not in bucket and len(bucket) < limit:
        bucket.append(value)


def analyze_text_file(
    path: Path,
    text: str,
    roots: list[Path],
    summary: dict[str, Any],
    details: list[dict[str, Any]],
) -> None:
    ext = path.suffix
    rel = relpath(path, roots)
    lines = text.splitlines()

    file_tags: Counter[str] = Counter()
    file_begins: Counter[str] = Counter()
    file_assign_keys: Counter[str] = Counter()
    tag_stack: list[tuple[str, int]] = []
    begin_stack: list[tuple[str, int]] = []
    tag_errors: list[str] = []
    begin_errors: list[str] = []
    first_tag = ""
    first_begin = ""
    in_source_depth = 0
    structural_unknowns: list[str] = []

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if ext == ".xojo_script":
            continue
        tag_match = TAG_RE.match(line)
        if tag_match:
            content = tag_match.group(1)
            base = tag_base(content)
            summary["tags"]["raw"][content] += 1
            if not first_tag:
                first_tag = content
            if base.startswith("End") and len(base) > 3:
                end_base = base[3:]
                summary["tags"]["ends"][end_base] += 1
                if tag_stack and tag_stack[-1][0] == end_base:
                    popped, _ = tag_stack.pop()
                    if popped in SOURCE_TAGS:
                        in_source_depth = max(0, in_source_depth - 1)
                else:
                    top = tag_stack[-1][0] if tag_stack else "<empty>"
                    tag_errors.append(f"line {lineno}: #tag {base} expected {top}")
            else:
                summary["tags"]["starts"][base] += 1
                file_tags[base] += 1
                if base not in NO_END_TAGS:
                    tag_stack.append((base, lineno))
                    if base in SOURCE_TAGS:
                        in_source_depth += 1

            flags_match = FLAGS_RE.search(content)
            if flags_match:
                flag = flags_match.group(1).strip()
                summary["tags"]["flags"][flag] += 1
                add_sample(summary["samples"], f"flag:{flag}", rel)
            compat_match = COMPAT_RE.search(content)
            if compat_match:
                compat = compat_match.group(1).strip()
                summary["tags"]["compatibility_flags"][compat] += 1
                add_sample(summary["samples"], f"compatibility:{compat}", rel)
            continue

        if ext == ".xojo_image" and (
            stripped.startswith("Image ") or stripped == "End Image"
        ):
            summary["declarations"]["image"][stripped.split(" ", 1)[0]] += 1
            continue

        begin_match = BEGIN_RE.match(line)
        compact_begin_match = None if begin_match else COMPACT_BEGIN_RE.match(line)
        if compact_begin_match:
            begin_match = compact_begin_match
        if begin_match and in_source_depth == 0:
            begin_type = begin_match.group(1)
            if not first_begin:
                first_begin = stripped
            summary["begin"]["types"][begin_type] += 1
            file_begins[begin_type] += 1
            begin_stack.append((begin_type, lineno))
            continue

        end_object_match = END_OBJECT_RE.match(line)
        if end_object_match and begin_stack and in_source_depth == 0:
            end_type = end_object_match.group(1)
            top_type, top_line = begin_stack[-1]
            if end_type is None or end_type == top_type:
                begin_stack.pop()
            else:
                begin_errors.append(
                    f"line {lineno}: End {end_type} expected {top_type} from line {top_line}"
                )
                begin_stack.pop()
            continue

        if ext == ".xojo_project":
            project_match = PROJECT_RE.match(line)
            if project_match:
                key = project_match.group(1)
                value = project_match.group(2)
                summary["project"]["keys"][key] += 1
                if project_item_kind(key, value):
                    fields = value.split(";")
                    summary["project"]["item_kinds"][key] += 1
                    summary["project"]["item_field_counts"][str(len(fields))] += 1
                    if len(fields) >= 3:
                        summary["project"]["item_id_prefixes"][fields[2][:4]] += 1
                continue

        assign_match = ASSIGN_RE.match(line)
        if assign_match and in_source_depth == 0:
            key = assign_match.group(1).strip()
            summary["assignments"]["keys"][key] += 1
            file_assign_keys[key] += 1
            continue

        if in_source_depth == 0 and stripped:
            if DECLARATION_RE.match(line):
                summary["declarations"]["starts"][stripped.split(" ", 1)[-1].split()[0]] += 1
                continue
            if END_DECL_RE.match(line):
                summary["declarations"]["ends"][END_DECL_RE.match(line).group(1)] += 1
                continue
            if stripped.startswith(("Inherits ", "Implements ")):
                key = stripped.split()[0]
                summary["declarations"][key.lower()][stripped] += 1
                continue
            if len(structural_unknowns) < 8:
                structural_unknowns.append(f"line {lineno}: {stripped[:160]}")

    for tag, lineno in tag_stack:
        if tag not in NO_END_TAGS:
            tag_errors.append(f"line {lineno}: unclosed #tag {tag}")
    for begin_type, lineno in begin_stack:
        begin_errors.append(f"line {lineno}: unclosed Begin {begin_type}")

    family = summary["families"][ext]
    if first_tag:
        family["first_tags"][first_tag] += 1
        summary["tags"]["first_by_ext"][ext][first_tag] += 1
    if first_begin:
        family["first_begins"][first_begin] += 1
    for key, count in file_tags.items():
        family["tag_types"][key] += count
    for key, count in file_begins.items():
        family["begin_types"][key] += count
    for key, count in file_assign_keys.items():
        family["assignment_keys"][key] += count

    if tag_errors:
        summary["validation"]["tag_balance_error_files"] += 1
        details.append({"path": rel, "kind": "tag_balance", "errors": tag_errors[:20]})
    if begin_errors:
        summary["validation"]["begin_balance_error_files"] += 1
        details.append({"path": rel, "kind": "begin_balance", "errors": begin_errors[:20]})
    if structural_unknowns:
        add_sample(summary["samples"], f"structural_unknown:{ext}", rel + " :: " + " | ".join(structural_unknowns[:3]))


def analyze_roots(roots: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    summary: dict[str, Any] = {
        "generated_at": now,
        "roots": [str(root) for root in roots],
        "files": {
            "total": 0,
            "text": 0,
            "binary_or_opaque": 0,
            "unreadable": 0,
            "by_extension": Counter(),
            "text_by_extension": Counter(),
            "binary_by_extension": Counter(),
            "unreadable_by_extension": Counter(),
        },
        "families": defaultdict(
            lambda: {
                "count": 0,
                "text": 0,
                "binary_or_opaque": 0,
                "first_tags": Counter(),
                "first_begins": Counter(),
                "tag_types": Counter(),
                "begin_types": Counter(),
                "assignment_keys": Counter(),
                "sample_files": [],
            }
        ),
        "project": {
            "keys": Counter(),
            "item_kinds": Counter(),
            "item_field_counts": Counter(),
            "item_id_prefixes": Counter(),
        },
        "tags": {
            "starts": Counter(),
            "ends": Counter(),
            "raw": Counter(),
            "flags": Counter(),
            "compatibility_flags": Counter(),
            "first_by_ext": defaultdict(Counter),
        },
        "begin": {"types": Counter()},
        "assignments": {"keys": Counter()},
        "declarations": {
            "starts": Counter(),
            "ends": Counter(),
            "inherits": Counter(),
            "implements": Counter(),
            "image": Counter(),
        },
        "samples": {},
        "validation": {
            "tag_balance_error_files": 0,
            "begin_balance_error_files": 0,
            "unreadable_files": [],
            "opaque_samples": [],
        },
    }
    details: list[dict[str, Any]] = []

    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in {".git", "__pycache__"}
                and not d.startswith("Builds - ")
                and not d.endswith(".debug.app")
            ]
            for filename in filenames:
                if ".dataless.bak" in filename:
                    continue
                if ".xojo_" not in filename:
                    continue
                files.append(Path(dirpath) / filename)

    for path in sorted(files):
        ext = path.suffix
        rel = relpath(path, roots)
        summary["files"]["total"] += 1
        summary["files"]["by_extension"][ext] += 1
        family = summary["families"][ext]
        family["count"] += 1
        if len(family["sample_files"]) < 8:
            family["sample_files"].append(rel)

        try:
            with path.open("rb") as handle:
                sample = handle.read(8192)
        except OSError as exc:
            summary["files"]["unreadable"] += 1
            summary["files"]["unreadable_by_extension"][ext] += 1
            summary["validation"]["unreadable_files"].append({"path": rel, "error": str(exc)})
            continue

        if not is_probably_text(sample):
            summary["files"]["binary_or_opaque"] += 1
            summary["files"]["binary_by_extension"][ext] += 1
            family["binary_or_opaque"] += 1
            if len(summary["validation"]["opaque_samples"]) < 40:
                summary["validation"]["opaque_samples"].append(
                    {"path": rel, "extension": ext, "magic": sample[:12].hex()}
                )
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            summary["files"]["unreadable"] += 1
            summary["files"]["unreadable_by_extension"][ext] += 1
            summary["validation"]["unreadable_files"].append({"path": rel, "error": str(exc)})
            continue

        summary["files"]["text"] += 1
        summary["files"]["text_by_extension"][ext] += 1
        family["text"] += 1
        analyze_text_file(path, text, roots, summary, details)

    return normalize(summary), details


def normalize(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value.most_common())
    if isinstance(value, defaultdict):
        value = dict(value)
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def top_lines(mapping: dict[str, int], limit: int = 20) -> list[str]:
    return [f"- `{key}`: {value}" for key, value in list(mapping.items())[:limit]]


def render_markdown(summary: dict[str, Any], details: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Xojo Format Corpus Inventory")
    lines.append("")
    lines.append(f"Generated: `{summary['generated_at']}`")
    lines.append("")
    lines.append("## Roots")
    lines.extend(f"- `{root}`" for root in summary["roots"])
    lines.append("")
    files = summary["files"]
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Total `.xojo_*` files scanned: {files['total']}")
    lines.append(f"- Text files parsed: {files['text']}")
    lines.append(f"- Binary/opaque files inventoried: {files['binary_or_opaque']}")
    lines.append(f"- Unreadable files: {files['unreadable']}")
    lines.append("")
    lines.append("### Files By Extension")
    lines.extend(top_lines(files["by_extension"], 40))
    lines.append("")
    lines.append("### Text Files By Extension")
    lines.extend(top_lines(files["text_by_extension"], 40))
    lines.append("")
    lines.append("### Binary/Opaque Files By Extension")
    lines.extend(top_lines(files["binary_by_extension"], 40))
    lines.append("")

    lines.append("## File Families")
    for ext, family in summary["families"].items():
        lines.append("")
        lines.append(f"### `{ext}`")
        lines.append(f"- Files: {family['count']}")
        lines.append(f"- Text parsed: {family['text']}")
        lines.append(f"- Binary/opaque: {family['binary_or_opaque']}")
        if family["first_tags"]:
            lines.append("- First tags:")
            lines.extend(top_lines(family["first_tags"], 12))
        if family["first_begins"]:
            lines.append("- First `Begin` lines:")
            lines.extend(top_lines(family["first_begins"], 12))
        if family["tag_types"]:
            lines.append("- Tag types:")
            lines.extend(top_lines(family["tag_types"], 16))
        if family["begin_types"]:
            lines.append("- Begin types:")
            lines.extend(top_lines(family["begin_types"], 16))
        if family["assignment_keys"]:
            lines.append("- Common assignment keys:")
            lines.extend(top_lines(family["assignment_keys"], 16))
        if family["sample_files"]:
            lines.append("- Sample files:")
            lines.extend(f"  - `{sample}`" for sample in family["sample_files"][:5])

    lines.append("")
    lines.append("## Project Manifest")
    lines.append("")
    lines.append("Top manifest keys:")
    lines.extend(top_lines(summary["project"]["keys"], 80))
    lines.append("")
    lines.append("Project item kinds:")
    lines.extend(top_lines(summary["project"]["item_kinds"], 40))
    lines.append("")
    lines.append("Project item field counts:")
    lines.extend(top_lines(summary["project"]["item_field_counts"], 20))

    lines.append("")
    lines.append("## Tag Grammar")
    lines.append("")
    lines.append("Start tag types:")
    lines.extend(top_lines(summary["tags"]["starts"], 80))
    lines.append("")
    lines.append("End tag types:")
    lines.extend(top_lines(summary["tags"]["ends"], 80))
    lines.append("")
    lines.append("Flags:")
    lines.extend(top_lines(summary["tags"]["flags"], 60))
    lines.append("")
    lines.append("Compatibility flags:")
    lines.extend(top_lines(summary["tags"]["compatibility_flags"], 60))

    lines.append("")
    lines.append("## Begin/End Object Trees")
    lines.extend(top_lines(summary["begin"]["types"], 120))

    lines.append("")
    lines.append("## Assignment Keys Outside Source Blocks")
    lines.extend(top_lines(summary["assignments"]["keys"], 120))

    lines.append("")
    lines.append("## Validation")
    validation = summary["validation"]
    lines.append(f"- Files with tag-balance findings: {validation['tag_balance_error_files']}")
    lines.append(f"- Files with Begin/End balance findings: {validation['begin_balance_error_files']}")
    lines.append(f"- Unreadable files: {len(validation['unreadable_files'])}")
    if validation["opaque_samples"]:
        lines.append("- Opaque samples:")
        for sample in validation["opaque_samples"][:20]:
            lines.append(f"  - `{sample['path']}` `{sample['extension']}` magic `{sample['magic']}`")
    if details:
        lines.append("")
        lines.append("### Balance Details")
        for item in details[:80]:
            lines.append(f"- `{item['path']}` {item['kind']}: " + "; ".join(item["errors"][:5]))

    lines.append("")
    lines.append("## Practical Conclusions")
    lines.append("")
    lines.append("- `.xojo_*` is a family of formats, not one syntax.")
    lines.append("- Text files are mostly combinations of `#tag` blocks, `Begin ... End` object trees, and `Key=Value` assignments.")
    lines.append("- `.xojo_resources`, `.xojo_binary_project`, and `.xojo_uistate` are binary/opaque in this corpus.")
    lines.append("- Preserve unknown flags, IDs, icon references, project item IDs, and compatibility expressions.")
    lines.append("- Edit source only inside the intended tag block and run Analyze Project after Xojo reloads the project.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, help="Root to scan. May be repeated.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "references",
        help="Directory for xojo-format-inventory outputs.",
    )
    args = parser.parse_args()

    roots = args.root or DEFAULT_ROOTS
    roots = [root.expanduser().resolve() for root in roots]
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summary, details = analyze_roots(roots)
    (out_dir / "xojo-format-inventory.json").write_text(
        json.dumps({"summary": summary, "details": details}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "xojo-format-inventory.md").write_text(
        render_markdown(summary, details),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "files": summary["files"],
                "tag_balance_error_files": summary["validation"]["tag_balance_error_files"],
                "begin_balance_error_files": summary["validation"]["begin_balance_error_files"],
                "out_dir": str(out_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
