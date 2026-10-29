#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import select
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from xojo_runtime import DEFAULT_GUI_LEASE_FILE, GuiLease, ProgressReporter, measured_call


DEFAULT_SOCKET = "/private/tmp/XojoIDE"
GUI_COMMANDS = {"compile", "analyze", "run", "stop-debug", "probe"}
MIN_PYTHON = (3, 9)
RECOMMENDED_PYTHON = "3.14"
TESTED_PYTHON = "3.14.4"

MACOS_BUILD_TYPES = {
    "all": 16,
    "universal": 9,
    "intel": 16,
    "arm": 24,
}
MACOS_BUILD_TYPE_VALUES = set(MACOS_BUILD_TYPES.values())


def version_tuple(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text)
    return tuple(int(part) for part in parts[:4])


def version_matches(actual: str, requested: str) -> bool:
    actual_tuple = version_tuple(actual)
    requested_tuple = version_tuple(requested)
    return bool(requested_tuple) and actual_tuple[: len(requested_tuple)] == requested_tuple


def python_version_text(executable: str) -> Optional[str]:
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or result.stderr).strip()
    return text or None


def python_runtime_info(executable: str) -> dict[str, Any]:
    version = python_version_text(executable)
    return {
        "executable": executable,
        "version": version,
        "exists": version is not None,
    }


def candidate_python_names(requested_version: Optional[str] = None) -> list[str]:
    names: list[str] = []
    if requested_version:
        requested_tuple = version_tuple(requested_version)
        if len(requested_tuple) >= 2:
            names.append(f"python{requested_tuple[0]}.{requested_tuple[1]}")
        if len(requested_tuple) >= 1:
            names.append(f"python{requested_tuple[0]}")
    names.extend(["python3.14", "python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3"])
    seen = set()
    unique_names = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)
    return unique_names


def discover_python_interpreters() -> list[dict[str, Any]]:
    candidates: list[str] = [sys.executable, "/usr/bin/python3"]
    for name in candidate_python_names():
        found = shutil.which(name)
        if found:
            candidates.append(found)

    seen = set()
    interpreters = []
    for candidate in candidates:
        try:
            resolved = str(Path(candidate).resolve())
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        interpreters.append(python_runtime_info(candidate))
    return interpreters


def find_python_for_version(requested_version: str) -> Optional[str]:
    for name in candidate_python_names(requested_version):
        found = shutil.which(name)
        if not found:
            continue
        version = python_version_text(found)
        if version and version_matches(version, requested_version):
            return found
    return None


def ensure_python_runtime(args: argparse.Namespace) -> None:
    if sys.version_info < MIN_PYTHON:
        raise RuntimeError(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; current runtime is {sys.version.split()[0]}. "
            "Install a newer Python and rerun the harness with it."
        )

    target_executable: Optional[str] = None
    if args.python_executable:
        target_executable = shutil.which(args.python_executable) or args.python_executable
        version = python_version_text(target_executable)
        if not version:
            raise RuntimeError(
                f"Python executable not found or not runnable: {args.python_executable}. "
                "Install it, fix PATH, or pass an existing --python-executable."
            )
    elif args.python_version:
        if not version_matches(sys.version, args.python_version):
            target_executable = find_python_for_version(args.python_version)
            if not target_executable:
                raise RuntimeError(
                    f"Requested Python {args.python_version} is not installed or not on PATH. "
                    f"Install it with Homebrew or pyenv, or pass --python-executable. "
                    f"This harness was tested with Python {TESTED_PYTHON}."
                )

    if not target_executable:
        return

    current = str(Path(sys.executable).resolve())
    target = str(Path(target_executable).resolve())
    if current == target:
        return

    if os.environ.get("XOJO_HARNESS_REEXEC") == "1":
        raise RuntimeError(f"Re-exec to {target} did not reach the requested Python runtime.")

    env = dict(os.environ)
    env["XOJO_HARNESS_REEXEC"] = "1"
    os.execve(target, [target] + sys.argv, env)


def app_info(app_path: Path) -> dict[str, Any]:
    info_plist = app_path / "Contents" / "Info.plist"
    data: dict[str, Any] = {}
    if info_plist.exists():
        with info_plist.open("rb") as handle:
            data = plistlib.load(handle)

    executable_name = data.get("CFBundleExecutable", "Xojo")
    executable = app_path / "Contents" / "MacOS" / str(executable_name)
    return {
        "path": str(app_path),
        "executable": str(executable),
        "shortVersion": data.get("CFBundleShortVersionString"),
        "bundleVersion": data.get("CFBundleVersion"),
        "name": data.get("CFBundleName", app_path.stem),
        "copyright": data.get("NSHumanReadableCopyright"),
    }


def discover_xojo_apps() -> list[dict[str, Any]]:
    roots = [Path("/Applications")]
    apps: list[dict[str, Any]] = []
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("**/Xojo.app"):
            if not path.is_dir():
                continue
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                apps.append(app_info(path.resolve()))
            except (OSError, plistlib.InvalidFileException):
                apps.append({"path": resolved, "error": "Cannot read Info.plist"})

    apps.sort(key=lambda item: version_tuple(str(item.get("shortVersion") or item.get("bundleVersion") or "")), reverse=True)
    return apps


def app_path_from_executable(executable: str) -> Optional[Path]:
    path = Path(executable)
    for parent in path.parents:
        if parent.name.endswith(".app"):
            return parent
    return None


def running_xojo_processes() -> list[dict[str, Any]]:
    result = subprocess.run(["pgrep", "-x", "Xojo"], check=False, capture_output=True, text=True)
    processes = []
    for pid_text in result.stdout.splitlines():
        pid_text = pid_text.strip()
        if not pid_text:
            continue
        ps = subprocess.run(["ps", "-p", pid_text, "-o", "command="], check=False, capture_output=True, text=True)
        command = ps.stdout.strip()
        app_path = app_path_from_executable(command)
        processes.append(
            {
                "pid": int(pid_text),
                "command": command,
                "app": app_info(app_path) if app_path and app_path.exists() else None,
            }
        )
    return processes


def describe_xojo_options(apps: list[dict[str, Any]]) -> str:
    lines = []
    for item in apps:
        label = item.get("shortVersion") or item.get("bundleVersion") or "unknown version"
        lines.append(f"- {label}: {item.get('path')}")
    return "\n".join(lines)


def resolve_xojo_app(args: argparse.Namespace) -> dict[str, Any]:
    if args.xojo_app:
        path = Path(args.xojo_app).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return app_info(path)

    running = running_xojo_processes()
    running_apps = [proc["app"] for proc in running if proc.get("app")]
    if args.xojo_version:
        matches = [
            item
            for item in discover_xojo_apps()
            if version_matches(str(item.get("shortVersion") or ""), args.xojo_version)
            or version_matches(str(item.get("bundleVersion") or ""), args.xojo_version)
            or args.xojo_version in str(item.get("path") or "")
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise RuntimeError(f"No installed Xojo.app matched --xojo-version {args.xojo_version}.")
        raise RuntimeError("Multiple Xojo installs matched --xojo-version. Pass --xojo-app explicitly.\n" + describe_xojo_options(matches))

    if len(running_apps) == 1:
        return running_apps[0]

    installed = discover_xojo_apps()
    if len(installed) == 1:
        return installed[0]
    if not installed:
        raise RuntimeError("No Xojo.app found under /Applications. Install Xojo or pass --xojo-app /path/to/Xojo.app.")

    raise RuntimeError("Multiple Xojo installs found. Pass --xojo-app or --xojo-version.\n" + describe_xojo_options(installed))


def ensure_running_xojo_matches(selected: dict[str, Any]) -> None:
    running = running_xojo_processes()
    selected_path = str(Path(str(selected["path"])).resolve())
    running_paths = {
        str(Path(str(proc["app"]["path"])).resolve())
        for proc in running
        if proc.get("app") and proc["app"].get("path")
    }
    if running_paths and selected_path not in running_paths:
        raise RuntimeError(
            "A different Xojo.app is already running. Quit it or select that version with --xojo-app.\n"
            + "\n".join(f"- running: {path}" for path in sorted(running_paths))
            + f"\n- selected: {selected_path}"
        )


def launch_xojo(app_path: str) -> None:
    subprocess.run(["open", app_path], check=False)


def open_project_with_finder(project_path: Path, xojo: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(
        ["open", "-a", str(xojo["path"]), str(project_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "returnCode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def matching_debug_processes(project_path: Optional[Path] = None) -> list[dict[str, Any]]:
    result = subprocess.run(["pgrep", "-afil", ".debug"], check=False, capture_output=True, text=True)
    processes = []
    expected_name = f"{project_path.stem}.debug" if project_path else None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, command = line.partition(" ")
        if not pid_text.isdigit():
            continue
        if expected_name and expected_name not in command:
            continue
        processes.append({"pid": int(pid_text), "command": command})
    return processes


def wait_for_debug_process(project_path: Path, timeout: float) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        processes = matching_debug_processes(project_path)
        if processes:
            return processes
        time.sleep(0.25)
    raise TimeoutError(f"No {project_path.stem}.debug process appeared within {timeout:.1f}s")


def stop_debug_with_shortcut(xojo: dict[str, Any]) -> dict[str, Any]:
    subprocess.run(["open", "-a", str(xojo["path"])], check=False)
    time.sleep(0.5)
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "." using command down',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "returnCode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def terminate_debug_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for proc in processes:
        pid = int(proc["pid"])
        try:
            os.kill(pid, 15)
            results.append({"pid": pid, "signal": "TERM", "ok": True})
        except OSError as exc:
            results.append({"pid": pid, "signal": "TERM", "ok": False, "error": str(exc)})
    return results


def wait_for_socket(socket_path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if socket_path.exists():
            return
        time.sleep(0.25)
    raise TimeoutError(f"Xojo IPC socket not found: {socket_path}")


def nul_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\0"


def send_script(
    socket_path: Path,
    script: str,
    tag: str,
    timeout: float,
    quiet_timeout: float = 0.75,
) -> list[dict[str, Any]]:
    if timeout <= 0 or quiet_timeout <= 0:
        raise ValueError("Script and quiet timeouts must be positive")

    deadline = time.monotonic() + timeout
    messages: list[dict[str, Any]] = []
    buffer = b""
    response_seen = False
    quiet_deadline: Optional[float] = None

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        while True:
            client.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                client.connect(str(socket_path))
                break
            except (ConnectionRefusedError, FileNotFoundError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        client.sendall(nul_json({"protocol": 2}))
        client.sendall(nul_json({"script": script, "tag": tag}))
        client.setblocking(False)

        while True:
            now = time.monotonic()
            active_deadline = min(deadline, quiet_deadline) if quiet_deadline else deadline
            remaining = active_deadline - now
            if remaining <= 0:
                if response_seen:
                    break
                raise TimeoutError(f"Xojo did not return a terminal response for {tag} within {timeout:.1f}s")

            readable, _, _ = select.select([client], [], [], remaining)
            if not readable:
                if response_seen:
                    break
                raise TimeoutError(f"Xojo did not return a terminal response for {tag} within {timeout:.1f}s")

            chunk = client.recv(65536)
            if not chunk:
                if response_seen:
                    break
                raise RuntimeError(f"Xojo closed the IPC connection before returning a response for {tag}")

            buffer += chunk
            parts = buffer.split(b"\0")
            buffer = parts[-1]
            for raw in parts[:-1]:
                if not raw:
                    continue
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    message = {"tag": tag, "raw": raw.decode("utf-8", errors="replace")}
                messages.append(message)
                if "response" in message:
                    response_seen = True
                    quiet_deadline = time.monotonic() + quiet_timeout

    if buffer:
        messages.append({"tag": tag, "raw": buffer.decode("utf-8", errors="replace")})

    if not response_seen:
        raise RuntimeError(f"Xojo returned data without a terminal response for {tag}")
    return messages


def xojo_escape(value: str) -> str:
    return value.replace('"', '""')


def read_project_map(project_path: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    base = project_path.parent
    for line in project_path.read_text(errors="replace").splitlines():
        if "=" not in line or ";" not in line:
            continue
        _, rest = line.split("=", 1)
        parts = rest.split(";")
        if len(parts) < 2:
            continue
        item_name = parts[0].strip()
        rel_path = parts[1].strip()
        if item_name and rel_path.endswith((".xojo_code", ".xojo_window", ".xojo_menu", ".xojo_toolbar")):
            mapping[item_name] = base / rel_path
    return mapping


def parse_position(position: str) -> tuple[Optional[str], Optional[str], Optional[int]]:
    match = re.match(r"(?P<item>[^.,]+)\.(?P<member>[^,]+),\s*line\s*(?P<line>\d+)", position or "")
    if not match:
        return None, None, None
    return match.group("item"), match.group("member"), int(match.group("line"))


def method_name_from_declaration(line: str) -> Optional[str]:
    match = re.match(r"\s*(?:Public|Protected|Private)?\s*(?:Shared\s+)?(?:Sub|Function)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
    if match:
        return match.group(1)
    return None


def method_blocks(lines: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("#tag Method"):
            start = i
            end = i + 1
            while end < len(lines) and not lines[end].lstrip().startswith("#tag EndMethod"):
                end += 1

            declaration_index = None
            name = None
            for j in range(start + 1, end):
                candidate = method_name_from_declaration(lines[j])
                if candidate:
                    declaration_index = j
                    name = candidate
                    break

            if declaration_index is not None and name:
                body_start = declaration_index + 1
                body_end = end
                while body_end > body_start and re.match(r"\s*End\s+(?:Sub|Function)\s*$", lines[body_end - 1]):
                    body_end -= 1
                blocks.append(
                    {
                        "name": name,
                        "start": start,
                        "end": end,
                        "declaration": declaration_index,
                        "body_start": body_start,
                        "body": lines[body_start:body_end],
                    }
                )
            i = end
        i += 1
    return blocks


def enrich_error(error: dict[str, Any], project_map: dict[str, Path]) -> dict[str, Any]:
    enriched = dict(error)
    item, member, body_line = parse_position(str(error.get("position", "")))
    if not item or not member or body_line is None:
        return enriched

    source_file = project_map.get(item)
    if not source_file or not source_file.exists():
        return enriched

    lines = source_file.read_text(errors="replace").splitlines()
    source_hint = str(error.get("source", "") or "")
    candidates = [block for block in method_blocks(lines) if block["name"].lower() == member.lower()]
    if not candidates:
        return enriched

    chosen = None
    if source_hint:
        for block in candidates:
            idx = body_line - 1
            if 0 <= idx < len(block["body"]) and source_hint in block["body"][idx]:
                chosen = block
                break
            if any(source_hint in body_line_text for body_line_text in block["body"]):
                chosen = block
                break

    if chosen is None:
        for block in candidates:
            if body_line <= len(block["body"]):
                chosen = block
                break

    if chosen is None:
        return enriched

    body_index = body_line - 1
    if 0 <= body_index < len(chosen["body"]):
        absolute_line = chosen["body_start"] + body_index + 1
        enriched["sourceFile"] = str(source_file)
        enriched["sourceFileLine"] = absolute_line
        enriched["fullSourceLine"] = chosen["body"][body_index].strip()

    return enriched


def parse_involved(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if not path or not path.exists():
        return None
    entries = []
    current: dict[str, str] = {}
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("- role:"):
            if current:
                entries.append(current)
            current = {"role": line.split(":", 1)[1].strip()}
        elif current and line.startswith("path:"):
            current["path"] = line.split(":", 1)[1].strip()
        elif current and line.startswith("notes:"):
            current["notes"] = line.split(":", 1)[1].strip()
    if current:
        entries.append(current)
    return {"path": str(path), "entries": entries}


def extract_result(messages: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"rawMessages": messages}
    for message in messages:
        response = message.get("response")
        if isinstance(response, dict) and any(key in response for key in ("buildError", "openErrors", "scriptError")):
            result["response"] = response
            return result
    for message in reversed(messages):
        if "response" in message:
            result["response"] = message["response"]
            return result
    return result


def response_failure(response: Any) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    for key in ("scriptError", "openErrors"):
        value = response.get(key)
        if value:
            return f"{key}: {value}"
    return None


def require_successful_response(messages: list[dict[str, Any]], action: str) -> None:
    failure = response_failure(extract_result(messages).get("response"))
    if failure:
        raise RuntimeError(f"Xojo {action} failed: {failure}")


def require_opened_project(messages: list[dict[str, Any]], expected: Path) -> None:
    require_successful_response(messages, "open project")
    response = extract_result(messages).get("response")
    prefix = "opened|"
    if not isinstance(response, str) or not response.startswith(prefix):
        raise RuntimeError(f"Xojo did not confirm the opened project path: {response!r}")
    raw_path = response[len(prefix) :]
    actual = Path(raw_path).expanduser().resolve()
    expected = expected.expanduser().resolve()
    if actual != expected:
        # ProjectShellPath is shell-escaped on macOS. Compare literal paths first
        # for compatibility, then decode exactly one shell word without execution.
        try:
            words = shlex.split(raw_path)
        except ValueError:
            words = []
        if len(words) == 1:
            actual = Path(words[0]).expanduser().resolve()
    if actual != expected:
        raise RuntimeError(f"Xojo opened {actual}, expected {expected}")


def enrich_build_error_payload(response: Any, project_map: dict[str, Path]) -> Any:
    if not isinstance(response, dict):
        return response
    build_error = response.setdefault("buildError", {})
    if not isinstance(build_error, dict):
        return response
    for key in ("errors", "warnings"):
        items = build_error.get(key, [])
        if isinstance(items, list):
            build_error[key] = [enrich_error(item, project_map) if isinstance(item, dict) else item for item in items]
    return response


def resolve_macos_build_type(args: argparse.Namespace) -> tuple[int, str]:
    if args.build_type is not None:
        if args.build_type not in MACOS_BUILD_TYPE_VALUES:
            raise RuntimeError(
                f"Only macOS BuildApp targets are supported now. Got {args.build_type}; "
                f"allowed values: {sorted(MACOS_BUILD_TYPE_VALUES)}."
            )
        label = next((name for name, value in MACOS_BUILD_TYPES.items() if value == args.build_type), "custom-macos")
        return args.build_type, label
    return MACOS_BUILD_TYPES[args.macos_build], args.macos_build


def bounded_timeout(args: argparse.Namespace, requested: float) -> float:
    lease = getattr(args, "_lease", None)
    if lease is None:
        return requested
    return lease.bound_timeout(requested)


def run_step(
    args: argparse.Namespace,
    step: str,
    operation: Any,
) -> tuple[Any, int]:
    reporter = getattr(args, "_progress", ProgressReporter(args.command, enabled=False))
    return measured_call(reporter, step, operation)


def prepare_project(args: argparse.Namespace, project_path: Path, xojo: dict[str, Any]) -> list[dict[str, Any]]:
    socket_path = Path(args.socket)
    if args.launch:
        launch_xojo(str(xojo["path"]))
    run_step(
        args,
        "wait-for-xojo",
        lambda: wait_for_socket(socket_path, bounded_timeout(args, args.launch_timeout)),
    )

    lifecycle: list[dict[str, Any]] = []
    if args.reload_policy == "skip":
        verify_messages, verify_elapsed = run_step(
            args,
            "verify-open-project",
            lambda: send_script(
                socket_path,
                'Print "opened|" + ProjectShellPath',
                "xojo-verify-reuse",
                bounded_timeout(args, args.command_timeout),
                args.quiet_timeout,
            ),
        )
        require_opened_project(verify_messages, project_path)
        lifecycle.append(
            {
                "step": "reuse-open-project",
                "note": "Verified project path; skipped close and open. Caller must verify source synchronization.",
                "elapsedMs": verify_elapsed,
                "messages": verify_messages,
            }
        )
        return lifecycle

    close_script = 'CloseProject(False)\nPrint "Closed front project if one was open"'
    close_messages, close_elapsed = run_step(
        args,
        "close-project",
        lambda: send_script(
            socket_path,
            close_script,
            "xojo-close",
            bounded_timeout(args, args.command_timeout),
            args.quiet_timeout,
        ),
    )
    require_successful_response(close_messages, "close project")
    lifecycle.append({"step": "close", "elapsedMs": close_elapsed, "messages": close_messages})

    if args.open_method in ("auto", "ide"):
        try:
            open_script = f'OpenFile("{xojo_escape(str(project_path))}")\nPrint "opened|" + ProjectShellPath'
            open_messages, open_elapsed = run_step(
                args,
                "open-project-ide",
                lambda: send_script(
                    socket_path,
                    open_script,
                    "xojo-open",
                    bounded_timeout(args, args.command_timeout),
                    args.quiet_timeout,
                ),
            )
            require_opened_project(open_messages, project_path)
            lifecycle.append({"step": "open-ide", "elapsedMs": open_elapsed, "messages": open_messages})
        except Exception as exc:
            if args.open_method == "ide":
                raise
            lifecycle.append({"step": "open-ide-failed", "error": str(exc)})
            finder_result, finder_elapsed = run_step(
                args,
                "open-project-finder",
                lambda: open_project_with_finder(project_path, xojo),
            )
            if finder_result["returnCode"] != 0:
                raise RuntimeError(f"Finder failed to open {project_path}: {finder_result['stderr']}")
            lifecycle.append({"step": "open-finder", "elapsedMs": finder_elapsed, "result": finder_result})
            verify_messages, verify_elapsed = run_step(
                args,
                "verify-finder-open",
                lambda: send_script(
                    socket_path,
                    'Print "opened|" + ProjectShellPath',
                    "xojo-verify-open",
                    bounded_timeout(args, args.command_timeout),
                    args.quiet_timeout,
                ),
            )
            require_opened_project(verify_messages, project_path)
            lifecycle.append(
                {"step": "verify-finder-open", "elapsedMs": verify_elapsed, "messages": verify_messages}
            )
    else:
        finder_result, finder_elapsed = run_step(
            args,
            "open-project-finder",
            lambda: open_project_with_finder(project_path, xojo),
        )
        if finder_result["returnCode"] != 0:
            raise RuntimeError(f"Finder failed to open {project_path}: {finder_result['stderr']}")
        lifecycle.append({"step": "open-finder", "elapsedMs": finder_elapsed, "result": finder_result})
        verify_messages, verify_elapsed = run_step(
            args,
            "verify-finder-open",
            lambda: send_script(
                socket_path,
                'Print "opened|" + ProjectShellPath',
                "xojo-verify-open",
                bounded_timeout(args, args.command_timeout),
                args.quiet_timeout,
            ),
        )
        require_opened_project(verify_messages, project_path)
        lifecycle.append(
            {"step": "verify-finder-open", "elapsedMs": verify_elapsed, "messages": verify_messages}
        )

    return lifecycle


def markdown_report(report: dict[str, Any]) -> str:
    xojo = report.get("xojo", {})
    python = report.get("python", {})
    lines = [
        "# Xojo Compile Report",
        "",
        f"- Project: `{report['project']}`",
        f"- Platform: `{report['platform']}`",
        f"- Action: `{report.get('action', 'compile')}`",
        f"- Reload policy: `{report['reloadPolicy']}`",
        f"- Xojo: `{xojo.get('shortVersion') or xojo.get('bundleVersion')}` at `{xojo.get('path')}`",
        f"- Python: `{python.get('version')}` at `{python.get('executable')}`",
        "",
    ]
    if report.get("buildType") is not None:
        lines.insert(5, f"- Build type: `{report['buildType']}` (`{report['buildTypeLabel']}`)")
    response = report.get("result", {}).get("response")
    errors = []
    warnings = []
    failure = response_failure(response)
    if failure:
        lines.extend(["## Harness Failure", "", failure])
        return "\n".join(lines) + "\n"
    if isinstance(response, dict):
        errors = response.get("buildError", {}).get("errors", [])
        warnings = response.get("buildError", {}).get("warnings", [])

    if not errors and not warnings:
        if report.get("action") == "analyze":
            lines.append("No diagnostics were returned by Analyze Project.")
        else:
            lines.append("No build errors were reported.")
        if isinstance(response, str) and report.get("action") not in ("analyze", "run"):
            lines.append("")
            lines.append(f"Build output: `{response}`")
        return "\n".join(lines) + "\n"

    if errors:
        lines.append("## Errors")
        lines.append("")
        for index, error in enumerate(errors, start=1):
            append_diagnostic_markdown(lines, index, error)

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for index, warning in enumerate(warnings, start=1):
            append_diagnostic_markdown(lines, index, warning)
    return "\n".join(lines)


def append_diagnostic_markdown(lines: list[str], index: int, diagnostic: dict[str, Any]) -> None:
    lines.append(f"### {index}. {diagnostic.get('position', diagnostic.get('location', 'Unknown'))}")
    lines.append("")
    lines.append(str(diagnostic.get("message", "")))
    if diagnostic.get("fullSourceLine"):
        lines.append("")
        lines.append("```xojo")
        lines.append(str(diagnostic["fullSourceLine"]))
        lines.append("```")
    elif diagnostic.get("source"):
        lines.append("")
        lines.append("```xojo")
        lines.append(str(diagnostic["source"]))
        lines.append("```")
    if diagnostic.get("sourceFile"):
        lines.append("")
        lines.append(f"Source: `{diagnostic['sourceFile']}:{diagnostic['sourceFileLine']}`")
    lines.append("")


def build_report(
    args: argparse.Namespace,
    project_path: Path,
    xojo: dict[str, Any],
    action: str,
    result: dict[str, Any],
    lifecycle: list[dict[str, Any]],
    build_type: Optional[int] = None,
    build_label: Optional[str] = None,
) -> dict[str, Any]:
    involved_path = Path(args.involved).expanduser().resolve() if getattr(args, "involved", None) else None
    action_started = getattr(args, "_action_started", time.monotonic())
    return {
        "project": str(project_path),
        "platform": "macOS",
        "action": action,
        "xojo": xojo,
        "python": python_runtime_info(sys.executable),
        "socket": str(Path(args.socket)),
        "buildType": build_type,
        "buildTypeLabel": build_label,
        "reloadPolicy": args.reload_policy,
        "involved": parse_involved(involved_path),
        "runningXojo": running_xojo_processes(),
        "lease": getattr(getattr(args, "_lease", None), "metadata", None),
        "elapsedMs": round((time.monotonic() - action_started) * 1000),
        "lifecycle": lifecycle,
        "result": result,
    }


def write_and_print_report(args: argparse.Namespace, report: dict[str, Any]) -> None:
    if getattr(args, "output_json", None):
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if getattr(args, "output_markdown", None):
        Path(args.output_markdown).write_text(markdown_report(report), encoding="utf-8")

    if args.format == "markdown":
        print(markdown_report(report), end="")
    else:
        print(json.dumps(report, indent=2))


def report_has_failures(report: dict[str, Any]) -> bool:
    response = report["result"].get("response")
    if response_failure(response):
        return True
    if not isinstance(response, dict):
        return False
    build_error = response.get("buildError", {})
    if not isinstance(build_error, dict):
        return False
    return bool(build_error.get("errors") or build_error.get("warnings"))


def command_compile(args: argparse.Namespace) -> int:
    project_path = Path(args.project).expanduser().resolve()
    if not project_path.exists():
        raise FileNotFoundError(project_path)

    build_type, build_label = resolve_macos_build_type(args)
    xojo = resolve_xojo_app(args)
    ensure_running_xojo_matches(xojo)

    socket_path = Path(args.socket)
    lifecycle = prepare_project(args, project_path, xojo)

    build_script = f"Print BuildApp({build_type}, False)"
    build_messages, build_elapsed = run_step(
        args,
        "build-project",
        lambda: send_script(
            socket_path,
            build_script,
            "xojo-build",
            bounded_timeout(args, args.build_timeout),
            args.quiet_timeout,
        ),
    )
    result = extract_result(build_messages)
    result["elapsedMs"] = build_elapsed

    project_map = read_project_map(project_path)
    result["response"] = enrich_build_error_payload(result.get("response"), project_map)

    report = build_report(args, project_path, xojo, "compile", result, lifecycle, build_type, build_label)
    write_and_print_report(args, report)

    if report_has_failures(report):
        return 1
    return 0


def command_analyze(args: argparse.Namespace) -> int:
    project_path = Path(args.project).expanduser().resolve()
    if not project_path.exists():
        raise FileNotFoundError(project_path)

    xojo = resolve_xojo_app(args)
    ensure_running_xojo_matches(xojo)
    socket_path = Path(args.socket)
    lifecycle = prepare_project(args, project_path, xojo)

    messages, analyze_elapsed = run_step(
        args,
        "analyze-project",
        lambda: send_script(
            socket_path,
            'DoCommand("CheckProjectErrors")\nPrint "Analyze Project requested"',
            "xojo-analyze",
            bounded_timeout(args, args.analyze_timeout),
            args.quiet_timeout,
        ),
    )
    result = extract_result(messages)
    result["elapsedMs"] = analyze_elapsed

    project_map = read_project_map(project_path)
    result["response"] = enrich_build_error_payload(result.get("response"), project_map)

    report = build_report(args, project_path, xojo, "analyze", result, lifecycle)
    write_and_print_report(args, report)

    if report_has_failures(report):
        return 1
    return 0


def command_run(args: argparse.Namespace) -> int:
    project_path = Path(args.project).expanduser().resolve()
    if not project_path.exists():
        raise FileNotFoundError(project_path)

    xojo = resolve_xojo_app(args)
    ensure_running_xojo_matches(xojo)
    socket_path = Path(args.socket)
    lifecycle = prepare_project(args, project_path, xojo)

    messages, run_elapsed = run_step(
        args,
        "run-project",
        lambda: send_script(
            socket_path,
            'DoCommand("RunApp")\nPrint "Run requested"',
            "xojo-run",
            bounded_timeout(args, args.run_timeout),
            args.quiet_timeout,
        ),
    )
    result = extract_result(messages)
    result["elapsedMs"] = run_elapsed

    project_map = read_project_map(project_path)
    result["response"] = enrich_build_error_payload(result.get("response"), project_map)

    response = result.get("response")
    build_error = response.get("buildError", {}) if isinstance(response, dict) else {}
    has_diagnostics = isinstance(build_error, dict) and bool(
        build_error.get("errors") or build_error.get("warnings")
    )
    if not has_diagnostics and args.run_evidence == "process":
        debug_processes, debug_elapsed = run_step(
            args,
            "verify-debug-process",
            lambda: wait_for_debug_process(
                project_path,
                bounded_timeout(args, args.debug_start_timeout),
            ),
        )
        result["debugProcesses"] = debug_processes
        result["debugStartElapsedMs"] = debug_elapsed
    else:
        result["runEvidence"] = "terminal-response"

    report = build_report(args, project_path, xojo, "run", result, lifecycle)
    write_and_print_report(args, report)

    if report_has_failures(report):
        return 1
    return 0


def command_stop_debug(args: argparse.Namespace) -> int:
    project_path = Path(args.project).expanduser().resolve() if args.project else None
    xojo = resolve_xojo_app(args)
    before = matching_debug_processes(project_path)
    report: dict[str, Any] = {
        "action": "stop-debug",
        "xojo": xojo,
        "python": python_runtime_info(sys.executable),
        "project": str(project_path) if project_path else None,
        "before": before,
    }

    if before or args.force:
        report["shortcut"] = stop_debug_with_shortcut(xojo)
        time.sleep(args.settle_timeout)
    else:
        report["shortcut"] = {"skipped": "No matching debug process was running."}

    after_shortcut = matching_debug_processes(project_path)
    report["afterShortcut"] = after_shortcut

    if after_shortcut and args.fallback_kill:
        report["fallbackKill"] = terminate_debug_processes(after_shortcut)
        time.sleep(args.settle_timeout)
        report["afterFallbackKill"] = matching_debug_processes(project_path)

    print(json.dumps(report, indent=2))
    remaining = report.get("afterFallbackKill", after_shortcut)
    return 1 if remaining else 0


def command_probe(args: argparse.Namespace) -> int:
    xojo = resolve_xojo_app(args)
    ensure_running_xojo_matches(xojo)
    socket_path = Path(args.socket)
    if args.launch:
        launch_xojo(str(xojo["path"]))
    run_step(
        args,
        "wait-for-xojo",
        lambda: wait_for_socket(socket_path, bounded_timeout(args, args.launch_timeout)),
    )
    messages, elapsed_ms = run_step(
        args,
        "probe-xojo",
        lambda: send_script(
            socket_path,
            'Print "Codex ping"',
            "xojo-probe",
            bounded_timeout(args, args.command_timeout),
            args.quiet_timeout,
        ),
    )
    print(
        json.dumps(
            {
                "xojo": xojo,
                "python": python_runtime_info(sys.executable),
                "elapsedMs": elapsed_ms,
                "messages": messages,
            },
            indent=2,
        )
    )
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    data = {
        "python": {
            "current": python_runtime_info(sys.executable),
            "minimum": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            "recommended": RECOMMENDED_PYTHON,
            "tested": TESTED_PYTHON,
            "available": discover_python_interpreters(),
        },
        "xojo": {
            "installed": discover_xojo_apps(),
            "running": running_xojo_processes(),
        },
        "macosBuildTypes": MACOS_BUILD_TYPES,
    }
    if args.format == "json":
        print(json.dumps(data, indent=2))
        return 0

    print("# Xojo Harness Doctor")
    print("")
    print(f"Current Python: {data['python']['current']['version']} at {data['python']['current']['executable']}")
    print(f"Minimum Python: {data['python']['minimum']}")
    print(f"Recommended Python: {data['python']['recommended']} (tested with {data['python']['tested']})")
    print("")
    print("Available Python interpreters:")
    for item in data["python"]["available"]:
        print(f"- {item.get('version') or 'not runnable'}: {item.get('executable')}")
    print("")
    print("Installed Xojo apps:")
    for item in data["xojo"]["installed"]:
        print(f"- {item.get('shortVersion') or item.get('bundleVersion')}: {item.get('path')}")
    print("")
    print("Running Xojo processes:")
    if data["xojo"]["running"]:
        for item in data["xojo"]["running"]:
            app = item.get("app") or {}
            print(f"- pid {item.get('pid')}: {app.get('shortVersion') or app.get('bundleVersion')} at {app.get('path')}")
    else:
        print("- none")
    print("")
    print("macOS BuildApp targets:")
    for name, value in MACOS_BUILD_TYPES.items():
        print(f"- {name}: {value}")
    return 0


def command_init_involved(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if target.exists() and not args.force:
        raise FileExistsError(f"{target} already exists; pass --force to overwrite")
    project = Path(args.project).expanduser().resolve() if args.project else Path("/absolute/path/to/App.xojo_project")
    content = f"""# Involved

## Target

- role: target
  path: {project}
  notes: Main project Codex should compile.

## References

- role: reference
  path: /absolute/path/to/reference-project-or-folder
  notes: Study design and data structure only.

## Human-owned UI

- The human arranges controls, renames UI components, and organizes Xojo project folders unless explicitly delegated.

## Current Agreements

- Codex may edit non-UI source outside Xojo.
- With Xojo 2026r3 Agentic Mode, verify changed-item reloads before compiling and keep the project open.
- Use manual reload or close/reopen when synchronization fails or Agentic Mode is unavailable.
"""
    target.write_text(content, encoding="utf-8")
    print(str(target))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex harness for macOS Xojo IDE Communicator v2 builds.")
    parser.add_argument("--python-version", help="Re-exec with a specific Python version, for example 3.14.")
    parser.add_argument("--python-executable", help="Re-exec with a specific Python executable path.")
    parser.add_argument("--xojo-app", help="Exact /Applications/.../Xojo.app bundle to use.")
    parser.add_argument("--xojo-version", help="Select an installed Xojo.app by short or bundle version prefix.")
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument("--launch", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--launch-timeout", type=float, default=30.0)
    parser.add_argument("--command-timeout", type=float, default=15.0)
    parser.add_argument(
        "--quiet-timeout",
        type=float,
        default=0.75,
        help="Finish after this quiet period once a terminal Xojo response is received.",
    )
    parser.add_argument("--lease-file", default=str(DEFAULT_GUI_LEASE_FILE))
    parser.add_argument(
        "--lease-timeout",
        type=float,
        default=600.0,
        help="Deadline used to bound an interactive Xojo automation job.",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write JSONL progress events to stderr.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile", help="Prepare a Xojo project and compile it for macOS.")
    compile_parser.add_argument("project")
    compile_parser.add_argument("--macos-build", choices=sorted(MACOS_BUILD_TYPES), default="all")
    compile_parser.add_argument("--build-type", type=int, help="Override with a macOS BuildApp target value.")
    compile_parser.add_argument("--build-timeout", type=float, default=180.0)
    compile_parser.add_argument("--reload-policy", choices=["always", "skip"], default="always", help="always: close/reopen; skip: verify and reuse the open project after caller verifies Agentic Mode reloads or unchanged source.")
    compile_parser.add_argument("--open-method", choices=["auto", "ide", "finder"], default="auto")
    compile_parser.add_argument("--involved")
    compile_parser.add_argument("--output-json")
    compile_parser.add_argument("--output-markdown")
    compile_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    compile_parser.set_defaults(func=command_compile)

    analyze_parser = subparsers.add_parser("analyze", help="Prepare a Xojo project and request Project > Analyze Project.")
    analyze_parser.add_argument("project")
    analyze_parser.add_argument("--analyze-timeout", type=float, default=120.0)
    analyze_parser.add_argument("--reload-policy", choices=["always", "skip"], default="always", help="always: close/reopen; skip: verify and reuse the open project after caller verifies Agentic Mode reloads or unchanged source.")
    analyze_parser.add_argument("--open-method", choices=["auto", "ide", "finder"], default="auto")
    analyze_parser.add_argument("--involved")
    analyze_parser.add_argument("--output-json")
    analyze_parser.add_argument("--output-markdown")
    analyze_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    analyze_parser.set_defaults(func=command_analyze)

    run_parser = subparsers.add_parser("run", help="Prepare a Xojo project, request RunApp, and verify launch evidence.")
    run_parser.add_argument("project")
    run_parser.add_argument("--run-timeout", type=float, default=180.0)
    run_parser.add_argument("--debug-start-timeout", type=float, default=15.0)
    run_parser.add_argument(
        "--run-evidence",
        choices=["process", "response"],
        default="process",
        help="Require a matching .debug process, or accept the terminal Communicator response for fast-exit apps.",
    )
    run_parser.add_argument("--reload-policy", choices=["always", "skip"], default="always", help="always: close/reopen; skip: verify and reuse the open project after caller verifies Agentic Mode reloads or unchanged source.")
    run_parser.add_argument("--open-method", choices=["auto", "ide", "finder"], default="auto")
    run_parser.add_argument("--involved")
    run_parser.add_argument("--output-json")
    run_parser.add_argument("--output-markdown")
    run_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    run_parser.set_defaults(func=command_run)

    stop_parser = subparsers.add_parser("stop-debug", help="Activate Xojo and press Command-period to stop debugging.")
    stop_parser.add_argument("project", nargs="?")
    stop_parser.add_argument("--settle-timeout", type=float, default=1.0)
    stop_parser.add_argument("--force", action="store_true", help="Send Command-period even if no matching debug process is detected.")
    stop_parser.add_argument("--fallback-kill", action="store_true", help="Terminate remaining matching debug processes if the shortcut fails.")
    stop_parser.set_defaults(func=command_stop_debug)

    probe_parser = subparsers.add_parser("probe", help="Send a harmless ping script to Xojo.")
    probe_parser.set_defaults(func=command_probe)

    doctor_parser = subparsers.add_parser("doctor", help="Report Python, Xojo, and macOS build target configuration.")
    doctor_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    doctor_parser.set_defaults(func=command_doctor)

    involved_parser = subparsers.add_parser("init-involved", help="Create an involved.md template.")
    involved_parser.add_argument("--path", default="involved.md")
    involved_parser.add_argument("--project")
    involved_parser.add_argument("--force", action="store_true")
    involved_parser.set_defaults(func=command_init_involved)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    reporter = ProgressReporter(args.command, enabled=args.progress)
    args._progress = reporter
    args._action_started = time.monotonic()
    lease: Optional[GuiLease] = None
    try:
        ensure_python_runtime(args)
        if args.command not in GUI_COMMANDS:
            return args.func(args)

        project = getattr(args, "project", None)
        with GuiLease(
            Path(args.lease_file).expanduser(),
            action=args.command,
            project=str(Path(project).expanduser().resolve()) if project else None,
            timeout=args.lease_timeout,
        ) as active_lease:
            lease = active_lease
            args._lease = lease
            reporter.emit("gui-lease", "acquired", **lease.metadata)
            exit_code = args.func(args)
        reporter.emit("gui-lease", "released")
        reporter.emit("action", "completed", exitCode=exit_code)
        return exit_code
    except Exception as exc:
        if lease is not None and lease.handle is None:
            reporter.emit("gui-lease", "released", afterFailure=True)
        reporter.emit("action", "failed", error=str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
