#!/usr/bin/env python3
"""Generate a Markdown/YAML hierarchy document from a Xojo UI text file."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
from typing import Any


BEGIN_RE = re.compile(r"^\s*Begin\s+(\S+)\s+(\S+)\s*$")
END_RE = re.compile(r"^\s*End\s*$")
PROPERTY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
METADATA_RE = re.compile(r"^\s*(sourceFile|sourceSha256|sourceMtimeUtc|sourceMtimeUnixNs|sourceSizeBytes):\s*(.+?)\s*$", re.MULTILINE)

CONTAINER_MARKERS = (
    "Container",
    "GroupBox",
    "Rectangle",
    "Canvas",
    "TabPanel",
    "PagePanel",
    "ScrollView",
    "Panel",
)

ANCHOR_PROPS = (
    ("LockLeft", "left"),
    ("LockTop", "top"),
    ("LockRight", "right"),
    ("LockBottom", "bottom"),
)


@dataclass
class Node:
    control_type: str
    control_id: str
    line: int
    parent: "Node | None" = None
    end_line: int | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)


def utc_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat()


def source_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    stat = path.stat()
    return {
        "sourceFile": str(path),
        "sourceSha256": hashlib.sha256(data).hexdigest(),
        "sourceMtimeUtc": utc_from_timestamp(stat.st_mtime),
        "sourceMtimeUnixNs": stat.st_mtime_ns,
        "sourceSizeBytes": stat.st_size,
    }


def parse_value(raw: str) -> Any:
    value = raw.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('""', '"')
    if value == "True":
        return True
    if value == "False":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_xojo_ui(path: Path) -> Node:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    root: Node | None = None
    stack: list[Node] = []

    for line_number, line in enumerate(lines, 1):
        begin = BEGIN_RE.match(line)
        if begin:
            node = Node(begin.group(1), begin.group(2), line_number)
            if stack:
                node.parent = stack[-1]
                stack[-1].children.append(node)
            elif root is None:
                root = node
            else:
                break
            stack.append(node)
            continue

        if stack and END_RE.match(line):
            stack[-1].end_line = line_number
            finished = stack.pop()
            if not stack and finished is root:
                break
            continue

        if stack:
            prop = PROPERTY_RE.match(line)
            if prop:
                stack[-1].properties[prop.group(1)] = parse_value(prop.group(2))

    if root is None:
        raise ValueError(f"No Xojo UI Begin block found in {path}")
    if stack:
        open_ids = ", ".join(node.control_id for node in stack)
        raise ValueError(f"Unclosed Xojo UI blocks: {open_ids}")
    return root


def role_for(node: Node) -> str:
    if "Window" in node.control_type or node.control_type in {
        "WebPage",
        "MobileScreen",
        "DesktopWindow",
    }:
        return "surface"
    if node.children:
        return "container"
    if any(marker in node.control_type for marker in CONTAINER_MARKERS):
        return "container"
    return "control"


def label_for(node: Node) -> str | None:
    for key in ("Title", "Caption", "Text", "Hint", "Name"):
        value = node.properties.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def int_prop(node: Node, key: str) -> int | None:
    value = node.properties.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def frame_for(node: Node) -> dict[str, int] | None:
    width = int_prop(node, "Width")
    height = int_prop(node, "Height")
    if width is None or height is None:
        return None
    x = int_prop(node, "Left")
    y = int_prop(node, "Top")
    if role_for(node) == "surface":
        x = 0 if x is None else x
        y = 0 if y is None else y
    if x is None or y is None:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


def offset_from_parent(node: Node) -> dict[str, int] | None:
    if node.parent is None:
        return None
    frame = frame_for(node)
    parent_frame = frame_for(node.parent)
    if frame is None or parent_frame is None:
        return None
    return {
        "x": frame["x"] - parent_frame["x"],
        "y": frame["y"] - parent_frame["y"],
        "width": frame["width"],
        "height": frame["height"],
    }


def anchors_for(node: Node) -> list[str]:
    return [name for prop, name in ANCHOR_PROPS if node.properties.get(prop) is True]


def parent_confidence(node: Node) -> str:
    if node.parent is None:
        return "root"
    initial_parent = node.properties.get("InitialParent")
    if initial_parent is None:
        return "declared_nesting"
    if initial_parent == node.parent.control_id:
        return "declared_and_initial_parent_match"
    return "declared_nesting_initial_parent_mismatch"


def initial_value_details(node: Node) -> dict[str, Any]:
    value = node.properties.get("InitialValue")
    if not isinstance(value, str) or not value:
        return {}
    if "\\n" in value:
        return {"items": value.split("\\n")}
    if "\t" in value:
        return {"columns": value.split("\t")}
    return {"initialValue": value}


def node_to_dict(
    node: Node,
    source_path: Path,
    generated_at: str,
    source_meta: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": node.control_id,
        "type": node.control_type,
        "role": role_for(node),
        "sourceLine": node.line,
        "parentConfidence": parent_confidence(node),
    }

    if node.parent is not None:
        result["parent"] = node.parent.control_id

    label = label_for(node)
    if label is not None:
        result["label"] = label

    frame = frame_for(node)
    if frame is not None:
        result["frame"] = frame

    offset = offset_from_parent(node)
    if offset is not None:
        result["offsetFromParent"] = offset

    anchors = anchors_for(node)
    if anchors:
        result["anchors"] = anchors

    if "Visible" in node.properties:
        result["visible"] = node.properties["Visible"]
    if "TabIndex" in node.properties:
        result["tabIndex"] = node.properties["TabIndex"]
    if "InitialParent" in node.properties:
        result["initialParent"] = node.properties["InitialParent"]

    result.update(initial_value_details(node))

    if node.parent is None:
        result["generatedAt"] = generated_at
        result.update(source_meta)
        result["coordinateRule"] = (
            "Stored Left/Top values are Xojo source designer coordinates; "
            "offsetFromParent is computed for nested controls."
        )

    if node.children:
        result["children"] = [node_to_dict(child, source_path, generated_at, source_meta) for child in node.children]

    return result


def node_to_brief_dict(node: Node) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": node.control_id,
        "type": node.control_type,
    }
    if node.children:
        result["children"] = [node_to_brief_dict(child) for child in node.children]
    return result


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def dump_yaml(value: Any, indent: int = 0) -> list[str]:
    space = " " * indent
    lines: list[str] = []

    if isinstance(value, dict):
        for key, item in value.items():
            if is_scalar(item):
                lines.append(f"{space}{key}: {yaml_scalar(item)}")
            elif isinstance(item, list) and not item:
                lines.append(f"{space}{key}: []")
            else:
                lines.append(f"{space}{key}:")
                lines.extend(dump_yaml(item, indent + 2))
        return lines

    if isinstance(value, list):
        if not value:
            lines.append(f"{space}[]")
            return lines
        for item in value:
            if isinstance(item, dict) and item:
                keys = list(item.keys())
                first_key = keys[0]
                first_value = item[first_key]
                if is_scalar(first_value):
                    lines.append(f"{space}- {first_key}: {yaml_scalar(first_value)}")
                else:
                    lines.append(f"{space}- {first_key}:")
                    lines.extend(dump_yaml(first_value, indent + 4))
                for key in keys[1:]:
                    sub_value = item[key]
                    if is_scalar(sub_value):
                        lines.append(f"{space}  {key}: {yaml_scalar(sub_value)}")
                    elif isinstance(sub_value, list) and not sub_value:
                        lines.append(f"{space}  {key}: []")
                    else:
                        lines.append(f"{space}  {key}:")
                        lines.extend(dump_yaml(sub_value, indent + 4))
            elif is_scalar(item):
                lines.append(f"{space}- {yaml_scalar(item)}")
            else:
                lines.append(f"{space}-")
                lines.extend(dump_yaml(item, indent + 2))
        return lines

    lines.append(f"{space}{yaml_scalar(value)}")
    return lines


def walk(node: Node) -> list[Node]:
    result = [node]
    for child in node.children:
        result.extend(walk(child))
    return result


def describe_frame(node: Node) -> str:
    frame = frame_for(node)
    if frame is None:
        return "frame=unknown"
    return f"frame=({frame['x']},{frame['y']},{frame['width']}x{frame['height']})"


def tree_lines(node: Node, depth: int = 0) -> list[str]:
    indent = "  " * depth
    label = label_for(node)
    label_text = f' "{label}"' if label else ""
    anchors = anchors_for(node)
    anchor_text = f" anchors={','.join(anchors)}" if anchors else ""
    line = (
        f"{indent}- {node.control_id} [{node.control_type}; {role_for(node)}; "
        f"{describe_frame(node)}{anchor_text}]{label_text}"
    )
    lines = [line]
    for child in node.children:
        lines.extend(tree_lines(child, depth + 1))
    return lines


def format_container_summary(node: Node) -> list[str]:
    containers = [item for item in walk(node) if role_for(item) == "container" and item is not node]
    if not containers:
        return ["- No nested containers were found."]
    lines = []
    for item in containers:
        label = label_for(item)
        label_text = f' ({label})' if label else ""
        child_count = len(item.children)
        lines.append(
            f"- `{item.control_id}`{label_text}: {item.control_type}, "
            f"{child_count} direct child control{'s' if child_count != 1 else ''}, {describe_frame(item)}."
        )
    return lines


def format_direct_surface_controls(node: Node) -> list[str]:
    direct_controls = [child for child in node.children if role_for(child) != "container"]
    if not direct_controls:
        return ["- None. All direct children of the surface are containers."]
    return [
        f"- `{child.control_id}`: {child.control_type}, {describe_frame(child)}."
        for child in direct_controls
    ]


def sort_key_by_frame(node: Node) -> tuple[int, int, str]:
    frame = frame_for(node) or {}
    return (int(frame.get("y", 0)), int(frame.get("x", 0)), node.control_id)


def sort_key_by_surface_position(node: Node) -> tuple[int, int, str]:
    frame = frame_for(node) or {}
    return (int(frame.get("x", 0)), int(frame.get("y", 0)), node.control_id)


def control_phrase(node: Node) -> str:
    short_type = node.control_type.replace("Desktop", "")
    label = label_for(node)
    phrase = f"`{node.control_id}` {short_type}"
    if label:
        phrase += f' "{label}"'
    details = initial_value_details(node)
    if "columns" in details:
        phrase += f" columns [{', '.join(str(item) for item in details['columns'])}]"
    if "items" in details:
        phrase += f" items [{', '.join(str(item) for item in details['items'])}]"
    return phrase


def group_rows(children: list[Node], tolerance: int = 6) -> list[tuple[int, list[Node]]]:
    rows: list[tuple[int, list[Node]]] = []
    for child in sorted(children, key=sort_key_by_frame):
        offset = offset_from_parent(child)
        frame = frame_for(child)
        y = (offset or frame or {}).get("y")
        if y is None:
            y = 0
        y = int(y)
        if rows and abs(rows[-1][0] - y) <= tolerance:
            rows[-1][1].append(child)
            continue
        rows.append((y, [child]))
    for _, row_children in rows:
        row_children.sort(key=lambda item: (offset_from_parent(item) or frame_for(item) or {}).get("x", 0))
    return rows


def format_visual_interpretation(root: Node) -> list[str]:
    top_children = sorted(root.children, key=sort_key_by_surface_position)
    if not top_children:
        return ["- The surface has no direct child controls."]

    lines: list[str] = []
    for child in top_children:
        label = label_for(child)
        label_text = f' "{label}"' if label else ""
        frame = frame_for(child)
        frame_text = "unknown frame"
        if frame:
            frame_text = f"x={frame['x']}, y={frame['y']}, {frame['width']}x{frame['height']}"
        lines.append(
            f"- `{child.control_id}`{label_text} is a {child.control_type} at {frame_text} "
            f"with {len(child.children)} direct child control{'s' if len(child.children) != 1 else ''}."
        )
        if not child.children:
            continue
        for y, row_children in group_rows(child.children):
            row_text = "; ".join(control_phrase(item) for item in row_children)
            lines.append(f"  - row y+{y}: {row_text}")
    return lines


def format_notes(node: Node) -> list[str]:
    notes: list[str] = []
    for item in walk(node):
        if item.parent is None:
            continue
        initial_parent = item.properties.get("InitialParent")
        if initial_parent is not None and initial_parent != item.parent.control_id:
            notes.append(
                f"- `{item.control_id}` is nested under `{item.parent.control_id}` "
                f"but InitialParent says `{initial_parent}`."
            )
    if not notes:
        notes.append("- No InitialParent mismatches were found.")

    non_surface = [item for item in walk(node) if item is not node]
    if non_surface:
        bottom_locked = [item.control_id for item in non_surface if "bottom" in anchors_for(item)]
        right_locked = [item.control_id for item in non_surface if "right" in anchors_for(item)]
        if bottom_locked:
            notes.append(f"- Bottom-anchored controls: {', '.join(f'`{item}`' for item in bottom_locked)}.")
        if right_locked:
            notes.append(f"- Right-anchored controls: {', '.join(f'`{item}`' for item in right_locked)}.")
    return notes


def parse_recorded_metadata(layout_path: Path) -> dict[str, Any]:
    text = layout_path.read_text(encoding="utf-8", errors="replace")
    metadata: dict[str, Any] = {}
    for key, raw_value in METADATA_RE.findall(text):
        metadata[key] = parse_value(raw_value)
    return metadata


def check_layout(source_path: Path, layout_path: Path) -> int:
    current = source_metadata(source_path)
    recorded = parse_recorded_metadata(layout_path)
    required = ("sourceFile", "sourceSha256", "sourceMtimeUtc", "sourceMtimeUnixNs", "sourceSizeBytes")
    missing = [key for key in required if key not in recorded]
    if missing:
        print(f"STALE: {layout_path} is missing metadata: {', '.join(missing)}")
        return 2

    hash_matches = recorded["sourceSha256"] == current["sourceSha256"]
    mtime_matches = recorded["sourceMtimeUnixNs"] == current["sourceMtimeUnixNs"]
    size_matches = recorded["sourceSizeBytes"] == current["sourceSizeBytes"]

    if hash_matches:
        print(f"FRESH: {layout_path} matches {source_path}")
    else:
        print(f"STALE: {layout_path} does not match {source_path}")

    print(f"recordedSourceFile: {recorded['sourceFile']}")
    print(f"currentSourceFile: {current['sourceFile']}")
    print(f"recordedSha256: {recorded['sourceSha256']}")
    print(f"currentSha256: {current['sourceSha256']}")
    print(f"recordedMtimeUtc: {recorded['sourceMtimeUtc']}")
    print(f"currentMtimeUtc: {current['sourceMtimeUtc']}")
    print(f"mtimeMatches: {str(mtime_matches).lower()}")
    print(f"sizeMatches: {str(size_matches).lower()}")
    if hash_matches and not mtime_matches:
        print("note: source timestamp changed, but content hash still matches.")
    return 0 if hash_matches else 2


def render_markdown(root: Node, source_path: Path) -> str:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_meta = source_metadata(source_path)
    surface = node_to_dict(root, source_path, generated_at, source_meta)
    brief_surface = node_to_brief_dict(root)
    all_nodes = walk(root)
    controls = [node for node in all_nodes if role_for(node) == "control"]
    containers = [node for node in all_nodes if role_for(node) == "container" and node is not root]
    label = label_for(root)
    frame = frame_for(root) or {}

    summary = [
        f"# Layout: {root.control_id}",
        "",
        "## Summary",
        "",
        f"- Source: `{source_path}`",
        f"- Surface: `{root.control_id}` ({root.control_type})" + (f', label "{label}"' if label else ""),
        f"- Size: {frame.get('width', 'unknown')} x {frame.get('height', 'unknown')}",
        f"- Parsed nodes: {len(all_nodes)} total, {len(containers)} containers, {len(controls)} controls",
        f"- Source SHA-256: `{source_meta['sourceSha256']}`",
        f"- Source mtime UTC: `{source_meta['sourceMtimeUtc']}`",
        "- Parentage source: Xojo `Begin ... End` nesting, cross-checked with `InitialParent` when present.",
        "- Coordinate rule: stored `Left/Top` values are preserved; nested controls also include `offsetFromParent`.",
        "",
        "## Visual Interpretation",
        "",
        *format_visual_interpretation(root),
        "",
        "## Brief Canonical Hierarchy",
        "",
        "```yaml",
        *dump_yaml({"surface": brief_surface}),
        "```",
        "",
        "## Detailed Canonical Hierarchy",
        "",
        "```yaml",
        *dump_yaml({"surface": surface}),
        "```",
        "",
        "## Tree",
        "",
        *tree_lines(root),
        "",
        "## Containers",
        "",
        *format_container_summary(root),
        "",
        "## Direct Surface Controls",
        "",
        *format_direct_surface_controls(root),
        "",
        "## Notes",
        "",
        *format_notes(root),
        "",
    ]
    return "\n".join(summary)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown/YAML UI hierarchy document from a Xojo text UI file."
    )
    parser.add_argument("source", type=Path, help="Path to a .xojo_window, .xojo_webpage, or .xojo_screen file.")
    parser.add_argument("--out", "-o", type=Path, help="Markdown output path. Prints to stdout when omitted.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether --out is fresh for source. Returns 0 when content hash matches, 2 when stale.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.check:
            if not args.out:
                parser.error("--check requires --out")
            return check_layout(args.source, args.out)

        root = parse_xojo_ui(args.source)
        markdown = render_markdown(root, args.source)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(markdown, encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(markdown)
        return 0
    except Exception as exc:
        print(f"xojo_layout_map: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
