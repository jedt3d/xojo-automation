#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import select
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from xojo_runtime import DEFAULT_GUI_LEASE_FILE, GuiLease, ProgressReporter, measured_call


DEFAULT_ROOT = Path("/Users/worajedt/xojoexamples")
DEFAULT_XOJO_APP = Path("/Applications/Xojo 2026 Release 3/Xojo.app")
DEFAULT_SOCKET = Path("/private/tmp/XojoIDE")
DEFAULT_LOCK_FILE = DEFAULT_GUI_LEASE_FILE
TEXT_PROJECT_EXTENSIONS = {
    ".xojo_project",
    ".xojo_code",
    ".xojo_window",
    ".xojo_webpage",
    ".xojo_screen",
    ".xojo_menu",
    ".xojo_resources",
    ".xojo_image",
    ".xojo_report",
    ".xojo_toolbar",
}


def xojo_escape(text: str) -> str:
    return text.replace('"', '""')


def apple_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def wait_for_socket(socket_path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if socket_path.exists():
            return
        time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for Xojo IDE socket: {socket_path}")


def launch_xojo(app_path: Path, timeout: float) -> None:
    subprocess.run(["open", "-a", str(app_path)], check=False)
    wait_for_socket(DEFAULT_SOCKET, timeout)


def xojo_process_ids() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-x", "Xojo"],
        check=False,
        capture_output=True,
        text=True,
    )
    return [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]


def is_xojo_running() -> bool:
    return bool(xojo_process_ids())


def ensure_xojo_ready(app_path: Path, settle_timeout: float, timeout: float) -> dict[str, Any]:
    before_pids = xojo_process_ids()
    was_running = bool(before_pids)
    launch_result = subprocess.run(
        ["open", "-a", str(app_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current_pids = xojo_process_ids()
        if current_pids:
            if not was_running:
                time.sleep(settle_timeout)
            socket_ready = DEFAULT_SOCKET.exists()
            if not socket_ready:
                try:
                    wait_for_socket(DEFAULT_SOCKET, min(8.0, max(0.5, deadline - time.monotonic())))
                    socket_ready = True
                except TimeoutError:
                    socket_ready = False
            return {
                "returncode": launch_result.returncode,
                "wasRunning": was_running,
                "recovered": not was_running,
                "pidsBefore": before_pids,
                "pidsAfter": current_pids,
                "pidCountAfter": len(current_pids),
                "singleXojoProcess": len(current_pids) == 1,
                "socketReady": socket_ready,
                "stdout": launch_result.stdout.strip(),
                "stderr": launch_result.stderr.strip(),
            }
        time.sleep(0.3)
    return {
        "returncode": 1,
        "wasRunning": was_running,
        "recovered": False,
        "pidsBefore": before_pids,
        "pidsAfter": [],
        "pidCountAfter": 0,
        "singleXojoProcess": False,
        "stdout": launch_result.stdout.strip(),
        "stderr": launch_result.stderr.strip(),
        "error": "Timed out waiting for Xojo process",
    }


def read_messages(
    sock: socket.socket,
    timeout: float,
    quiet_timeout: float = 0.75,
) -> list[dict[str, Any]]:
    if timeout <= 0 or quiet_timeout <= 0:
        raise ValueError("Script and quiet timeouts must be positive")

    messages: list[dict[str, Any]] = []
    buffer = b""
    sock.setblocking(False)
    deadline = time.monotonic() + timeout
    response_seen = False
    quiet_deadline: float | None = None
    while True:
        now = time.monotonic()
        active_deadline = min(deadline, quiet_deadline) if quiet_deadline else deadline
        wait = active_deadline - now
        if wait <= 0:
            if response_seen:
                break
            raise TimeoutError(f"Xojo did not return a terminal response within {timeout:.1f}s")
        readable, _, _ = select.select([sock], [], [], wait)
        if not readable:
            if response_seen:
                break
            raise TimeoutError(f"Xojo did not return a terminal response within {timeout:.1f}s")
        try:
            chunk = sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            continue
        if not chunk:
            if response_seen:
                break
            raise RuntimeError("Xojo closed the IPC connection before returning a response")
        buffer += chunk
        while b"\0" in buffer:
            frame, buffer = buffer.split(b"\0", 1)
            if not frame:
                continue
            message = json.loads(frame.decode("utf-8"))
            messages.append(message)
            if "response" in message:
                response_seen = True
                quiet_deadline = time.monotonic() + quiet_timeout
    if not response_seen:
        raise RuntimeError("Xojo returned data without a terminal response")
    return messages


def send_script(socket_path: Path, script: str, tag: str, timeout: float) -> list[dict[str, Any]]:
    payloads = [
        json.dumps({"protocol": 2}).encode("utf-8") + b"\0",
        json.dumps({"script": script, "tag": tag}).encode("utf-8") + b"\0",
    ]
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path))
        for payload in payloads:
            sock.sendall(payload)
        return read_messages(sock, timeout)


def send_script_fire_and_forget(socket_path: Path, script: str, tag: str, timeout: float) -> None:
    payloads = [
        json.dumps({"protocol": 2}).encode("utf-8") + b"\0",
        json.dumps({"script": script, "tag": tag}).encode("utf-8") + b"\0",
    ]
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path))
        for payload in payloads:
            sock.sendall(payload)


def result_response(messages: list[dict[str, Any]]) -> Any:
    for message in reversed(messages):
        if "response" in message:
            return message["response"]
    return None


def binary_projects(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.xojo_binary_project") if not p.name.startswith("._"))


def target_for(binary_project: Path) -> Path:
    return binary_project.with_suffix("") / f"{binary_project.stem}.xojo_project"


def duplicate_extension_target(target: Path) -> Path:
    return target.with_name(f"{target.name}.xojo_project")


def text_project_candidates(target: Path) -> list[Path]:
    folder = target.parent
    if not folder.exists():
        return []
    candidates = [
        path
        for path in folder.glob("*.xojo_project")
        if path.is_file() and not path.name.startswith("._")
    ]
    return sorted(candidates, key=lambda path: (path != target, path.name))


def normalize_text_project_filename(target: Path) -> dict[str, Any]:
    duplicate = duplicate_extension_target(target)
    if target.exists() or not duplicate.exists():
        return {"renamed": False, "from": str(duplicate), "to": str(target)}
    try:
        duplicate.rename(target)
        return {"renamed": True, "from": str(duplicate), "to": str(target)}
    except Exception as exc:
        return {"renamed": False, "from": str(duplicate), "to": str(target), "error": str(exc)}


def companion_summary(target: Path) -> dict[str, Any]:
    folder = target.parent
    files = []
    if folder.exists():
        files = sorted(
            str(path.relative_to(folder))
            for path in folder.rglob("*")
            if path.is_file() and path.suffix in TEXT_PROJECT_EXTENSIONS and not path.name.startswith("._")
        )
    candidates = text_project_candidates(target)
    actual = target if target.exists() else (candidates[0] if len(candidates) == 1 else None)
    return {
        "target": str(target),
        "exists": target.exists(),
        "folderExists": folder.exists(),
        "actualTextProject": str(actual) if actual else None,
        "actualTextProjectExists": bool(actual and actual.exists()),
        "textProjectCandidates": [str(path.relative_to(folder)) for path in candidates],
        "textProjectFileCount": len(files),
        "textProjectFiles": files[:80],
        "truncated": len(files) > 80,
    }


def build_manifest(root: Path) -> dict[str, Any]:
    projects = []
    for source in binary_projects(root):
        target = target_for(source)
        summary = companion_summary(target)
        projects.append(
            {
                "source": str(source),
                "relativeSource": str(source.relative_to(root)),
                "target": str(target),
                "relativeTarget": str(target.relative_to(root)),
                "targetExists": target.exists(),
                "actualTextProjectExists": summary["actualTextProjectExists"],
                "actualTextProject": summary["actualTextProject"],
                "textProjectCandidates": summary["textProjectCandidates"],
                "targetFolderExists": target.parent.exists(),
            }
        )
    converted = sum(1 for project in projects if project["actualTextProjectExists"])
    partial = sum(
        1
        for project in projects
        if project["targetFolderExists"] and not project["actualTextProjectExists"]
    )
    return {
        "root": str(root),
        "count": len(projects),
        "convertedCount": converted,
        "unconvertedCount": len(projects) - converted,
        "partialTargetFolderCount": partial,
        "projects": projects,
    }


def run_osascript(script: str, timeout: float) -> subprocess.CompletedProcess[str]:
    command = ["osascript", "-e", script]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(command, 124, stdout, stderr + f"\nTimed out after {timeout} seconds")


def xojo_window_inventory(timeout: float) -> dict[str, Any]:
    script = '''
set output to ""
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      repeat with currentWindow in windows
        set output to output & (name of currentWindow as text) & linefeed
      end repeat
    end tell
  end if
end tell
return output
'''
    result = run_osascript(script, timeout)
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "returncode": result.returncode,
        "windows": names,
        "projectWindows": [name for name in names if name != "Choose a Project"],
        "stderr": result.stderr.strip(),
    }


def osascript_result(result: subprocess.CompletedProcess[str], **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    data.update(extra)
    return data


def terminate_xojo_processes(timeout: float = 8.0) -> dict[str, Any]:
    before = xojo_process_ids()
    if not before:
        return {"pidsBefore": [], "pidsAfter": [], "terminated": False, "killed": False}
    subprocess.run(["kill", "-TERM", *[str(pid) for pid in before]], check=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not xojo_process_ids():
            return {"pidsBefore": before, "pidsAfter": [], "terminated": True, "killed": False}
        time.sleep(0.3)
    after_term = xojo_process_ids()
    if after_term:
        subprocess.run(["kill", "-KILL", *[str(pid) for pid in after_term]], check=False)
        time.sleep(0.5)
    return {
        "pidsBefore": before,
        "pidsAfter": xojo_process_ids(),
        "terminated": True,
        "killed": bool(after_term),
    }


def remove_empty_target_folder(target: Path) -> dict[str, Any]:
    folder = target.parent
    if not folder.exists():
        return {"targetFolder": str(folder), "existed": False, "removed": False, "reason": "missing"}
    files = [path for path in folder.rglob("*") if path.is_file()]
    dirs = [path for path in folder.rglob("*") if path.is_dir()]
    if files:
        return {
            "targetFolder": str(folder),
            "existed": True,
            "removed": False,
            "reason": "contains_files",
            "fileCount": len(files),
        }
    try:
        shutil.rmtree(folder)
        return {
            "targetFolder": str(folder),
            "existed": True,
            "removed": True,
            "reason": "empty_or_dirs_only",
            "dirCount": len(dirs),
        }
    except Exception as exc:
        return {
            "targetFolder": str(folder),
            "existed": True,
            "removed": False,
            "reason": "remove_failed",
            "error": str(exc),
        }


def open_project_with_finder(source: Path, app_path: Path, settle_timeout: float) -> dict[str, Any]:
    result = subprocess.run(
        ["open", "-a", str(app_path), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    time.sleep(settle_timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "source": str(source),
    }


def dismiss_runtime_error_dialog(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
set dismissed to false
set clickedButton to ""
set windowName to ""
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      set frontmost to true
      if exists window 1 then
        set windowName to name of window 1
        if exists button "Quit" of window 1 then
          if exists button "Continue" of window 1 then
            click button "Quit" of window 1
            set clickedButton to "Quit"
            set dismissed to true
            delay 1.0
          end if
        else if exists sheet 1 of window 1 then
          if exists button "Quit" of sheet 1 of window 1 then
            if exists button "Continue" of sheet 1 of window 1 then
              click button "Quit" of sheet 1 of window 1
              set clickedButton to "Quit"
              set dismissed to true
              delay 1.0
            end if
          end if
        end if
      end if
    end tell
  end if
end tell
return "dismissed=" & dismissed & ";clickedButton=" & clickedButton & ";windowName=" & windowName
'''
    return osascript_result(run_osascript(script, min(timeout, 8.0)))


def accept_known_prompts(timeout: float) -> dict[str, Any]:
    runtime_error = dismiss_runtime_error_dialog(timeout)
    script = '''
tell application "Xojo" to activate
delay 0.2
set clickedButtons to {}
set remainingSheets to 0
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      set frontmost to true
      repeat 5 times
        if exists window 1 then
          if exists sheet 1 of window 1 then
            set clickedName to ""
            set issueSheetFound to false
            try
              repeat with t in static texts of sheet 1 of window 1
                set tName to name of t
                if tName contains "Please resolve the following issues" then set issueSheetFound to true
                if tName contains "Found " and tName contains "issues" then set issueSheetFound to true
              end repeat
            end try
            if issueSheetFound and exists button "Close" of sheet 1 of window 1 then
              click button "Close" of sheet 1 of window 1
              set clickedName to "CloseIssues"
            else if exists button "Convert" of sheet 1 of window 1 then
              click button "Convert" of sheet 1 of window 1
              set clickedName to "Convert"
            else if exists button "Update" of sheet 1 of window 1 then
              click button "Update" of sheet 1 of window 1
              set clickedName to "Update"
            else if exists button "Open" of sheet 1 of window 1 then
              click button "Open" of sheet 1 of window 1
              set clickedName to "Open"
            else if exists button "Continue" of sheet 1 of window 1 then
              click button "Continue" of sheet 1 of window 1
              set clickedName to "Continue"
            else if exists button "OK" of sheet 1 of window 1 then
              click button "OK" of sheet 1 of window 1
              set clickedName to "OK"
            end if
            if clickedName is "" then
              set remainingSheets to remainingSheets + 1
              exit repeat
            else
              set end of clickedButtons to clickedName
              delay 1.0
            end if
          else
            exit repeat
          end if
        else
          exit repeat
        end if
      end repeat
      if exists window 1 then
        if exists sheet 1 of window 1 then set remainingSheets to remainingSheets + 1
      end if
    end tell
  end if
end tell
return "clicked=" & clickedButtons & ";remainingSheets=" & remainingSheets
'''
    result = osascript_result(run_osascript(script, timeout))
    result["runtimeError"] = runtime_error
    return result


def accept_save_as_warning(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.4
set acceptedWarning to false
tell application "System Events"
  tell process "Xojo"
    if exists sheet 1 of window 1 then
      set warningTextFound to false
      try
        repeat with t in static texts of sheet 1 of window 1
          if (name of t) starts with "Saving will update" then set warningTextFound to true
        end repeat
      end try
      if warningTextFound then
        click button "Save" of sheet 1 of window 1
        set acceptedWarning to true
      end if
    end if
  end tell
end tell
if acceptedWarning then delay 1.8
return "acceptedWarning=" & acceptedWarning
'''
    return osascript_result(run_osascript(script, timeout))


def save_dialog_visible(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
set dialogVisible to false
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      set frontmost to true
      repeat 24 times
        if exists window 1 then
          if exists sheet 1 of window 1 then
            if exists button "Save" of sheet 1 of window 1 then
              set dialogVisible to true
              exit repeat
            end if
          else if exists button "Save" of window 1 then
            set dialogVisible to true
            exit repeat
          end if
          repeat with e in UI elements of window 1
            if role of e is "AXSheet" then
              try
                if exists button "Save" of UI element 1 of e then
                  set dialogVisible to true
                  exit repeat
                end if
              end try
            end if
          end repeat
          if dialogVisible then exit repeat
        end if
        delay 0.25
      end repeat
    end tell
  end if
end tell
return "visible=" & dialogVisible
'''
    return osascript_result(run_osascript(script, min(timeout, 8.0)))


def invoke_save_as_menu(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
tell application "System Events"
  tell process "Xojo"
    set frontmost to true
    click menu bar item "File" of menu bar 1
    delay 0.2
    click menu item "Save As..." of menu 1 of menu bar item "File" of menu bar 1
  end tell
end tell
delay 0.8
return "method=menu"
'''
    result = run_osascript(script, timeout)
    warning = accept_save_as_warning(timeout)
    visible = save_dialog_visible(timeout)
    data = osascript_result(result, method="menu", warning=warning, saveDialog=visible)
    if result.returncode == 0 and "visible=true" not in visible["stdout"]:
        data["returncode"] = 1
        data["stderr"] = (data["stderr"] + "\nSave dialog was not visible after menu request").strip()
    return data


def invoke_save_as_hotkey(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
tell application "System Events"
  tell process "Xojo"
    set frontmost to true
    keystroke "s" using {command down, shift down}
  end tell
end tell
delay 0.8
return "method=hotkey"
'''
    result = run_osascript(script, timeout)
    warning = accept_save_as_warning(timeout)
    visible = save_dialog_visible(timeout)
    data = osascript_result(result, method="hotkey", warning=warning, saveDialog=visible)
    if result.returncode == 0 and "visible=true" not in visible["stdout"]:
        data["returncode"] = 1
        data["stderr"] = (data["stderr"] + "\nSave dialog was not visible after hotkey request").strip()
    return data


def invoke_save_as_ide(socket_path: Path, timeout: float) -> dict[str, Any]:
    try:
        send_script_fire_and_forget(socket_path, 'DoCommand("SaveFileAs")', "save-as-fire-and-forget", timeout)
        time.sleep(0.8)
        runtime_error = dismiss_runtime_error_dialog(timeout)
        if "dismissed=true" in runtime_error["stdout"]:
            return {
                "returncode": 1,
                "method": "ide",
                "messages": [],
                "response": "runtime-error",
                "runtimeError": runtime_error,
                "warning": None,
                "stdout": "",
                "stderr": "IDE SaveFileAs produced a runtime error dialog",
            }
        warning = accept_save_as_warning(timeout)
        visible = save_dialog_visible(timeout)
        returncode = 0 if "visible=true" in visible["stdout"] else 1
        return {
            "returncode": returncode,
            "method": "ide",
            "messages": [],
            "response": "fire-and-forget",
            "runtimeError": runtime_error,
            "warning": warning,
            "saveDialog": visible,
            "stdout": "",
            "stderr": "" if returncode == 0 else "Save dialog was not visible after IDE SaveFileAs request",
        }
    except Exception as exc:
        return {
            "returncode": 1,
            "method": "ide",
            "messages": [],
            "response": None,
            "warning": None,
            "stdout": "",
            "stderr": str(exc),
        }


def invoke_save_as(args: argparse.Namespace) -> dict[str, Any]:
    methods = [args.save_as_method]
    if args.save_as_method == "auto":
        methods = ["ide", "hotkey", "menu"]

    attempts = []
    for method in methods:
        if method == "ide":
            result = invoke_save_as_ide(Path(args.socket), bounded_timeout(args, args.command_timeout))
        elif method == "hotkey":
            result = invoke_save_as_hotkey(bounded_timeout(args, args.ui_timeout))
        elif method == "menu":
            result = invoke_save_as_menu(bounded_timeout(args, args.ui_timeout))
        else:
            result = {"returncode": 1, "method": method, "stdout": "", "stderr": f"unknown method {method}"}
        attempts.append(result)
        if result["returncode"] == 0:
            return {"returncode": 0, "stdout": f"method={method}", "stderr": "", "attempts": attempts}
        cleanup = accept_known_prompts(bounded_timeout(args, args.ui_timeout))
        attempts.append({"method": "settle-after-save-as-failure", **cleanup})
    return {"returncode": 1, "stdout": "", "stderr": "All Save As request methods failed", "attempts": attempts}


def save_as_text_project(target: Path, timeout: float) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    target_name = target.stem
    target_dir = str(target.parent)
    script = f'''
tell application "Xojo" to activate
delay 1.0
set dialogFound to false
tell application "System Events"
  tell process "Xojo"
    set frontmost to true
    repeat 80 times
      if exists window 1 then
        if exists sheet 1 of window 1 then
          if exists button "Save" of sheet 1 of window 1 then
            set dialogFound to true
            exit repeat
          end if
        end if
        repeat with e in UI elements of window 1
          if role of e is "AXSheet" then
            try
              if exists button "Save" of UI element 1 of e then
                set dialogFound to true
                exit repeat
              end if
            end try
          end if
        end repeat
        if dialogFound then exit repeat
      end if
      delay 0.25
    end repeat
    if dialogFound is false then error "Save dialog not found"
    keystroke "g" using {{command down, shift down}}
  end tell
end tell
delay 0.8
tell application "System Events"
  tell process "Xojo"
    keystroke "{apple_escape(target_dir)}"
    key code 36
  end tell
end tell
delay 1.0
tell application "System Events"
  tell process "Xojo"
    keystroke "a" using {{command down}}
    keystroke "{apple_escape(target_name)}"
    key code 36
  end tell
end tell
delay 1.0
tell application "System Events"
  tell process "Xojo"
    if exists window 1 then
      if exists sheet 1 of window 1 then
        if exists button "Replace" of sheet 1 of window 1 then
          click button "Replace" of sheet 1 of window 1
        else if exists button "Save" of sheet 1 of window 1 then
          click button "Save" of sheet 1 of window 1
        else if exists button "OK" of sheet 1 of window 1 then
          click button "OK" of sheet 1 of window 1
        end if
      else
        repeat with e in UI elements of window 1
          if role of e is "AXSheet" then
            try
              if exists button "Save" of UI element 1 of e then
                click button "Save" of UI element 1 of e
                exit repeat
              end if
            end try
          end if
        end repeat
      end if
    end if
  end tell
end tell
return "dialogFound=" & dialogFound
'''
    result = run_osascript(script, timeout)
    return osascript_result(result, targetDir=target_dir, targetName=target_name)


def convert_project_to_api2(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.3
set didClick to false
set acceptedPrompt to false
set clickError to ""
tell application "System Events"
  tell process "Xojo"
    try
      click menu bar item "Project" of menu bar 1
      delay 0.2
      if exists menu item "Convert Project to API 2" of menu 1 of menu bar item "Project" of menu bar 1 then
        set itemRef to menu item "Convert Project to API 2" of menu 1 of menu bar item "Project" of menu bar 1
        if enabled of itemRef then
          click itemRef
          set didClick to true
        end if
      end if
      if didClick is false then key code 53
    on error errText
      key code 53
      set clickError to errText
    end try
  end tell
end tell
if didClick then delay 1.0
tell application "System Events"
  tell process "Xojo"
    if exists sheet 1 of window 1 then
      set apiPromptFound to false
      try
        repeat with t in static texts of sheet 1 of window 1
          set tName to name of t
          if tName contains "API 2" or tName contains "API 2.0" or tName contains "convert" or tName contains "Convert" then set apiPromptFound to true
        end repeat
      end try
      if apiPromptFound then
        if exists button "Convert" of sheet 1 of window 1 then
          click button "Convert" of sheet 1 of window 1
          set acceptedPrompt to true
        else if exists button "OK" of sheet 1 of window 1 then
          click button "OK" of sheet 1 of window 1
          set acceptedPrompt to true
        else if exists button "Save" of sheet 1 of window 1 then
          click button "Save" of sheet 1 of window 1
          set acceptedPrompt to true
        end if
      end if
    end if
  end tell
end tell
if didClick then delay 1.0
return "didClick=" & didClick & ";acceptedPrompt=" & acceptedPrompt & ";error=" & clickError
'''
    result = run_osascript(script, timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def wait_for_text_project(target: Path, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = companion_summary(target)
    while time.monotonic() < deadline:
        normalize_result = normalize_text_project_filename(target)
        last = companion_summary(target)
        last["normalize"] = normalize_result
        if last["actualTextProjectExists"] and last["textProjectFileCount"] > 1:
            return last
        time.sleep(0.5)
    return last


def open_binary_project(source: Path, socket_path: Path, timeout: float) -> list[dict[str, Any]]:
    script = "\n".join(
        [
            f'OpenFile("{xojo_escape(str(source))}")',
            f'Print "opened|" + ProjectShellPath',
        ]
    )
    return send_script(socket_path, script, "open-binary", timeout)


def request_save_as(socket_path: Path, timeout: float) -> list[dict[str, Any]]:
    script = 'DoCommand("SaveFileAs")\nPrint "save-as-requested"'
    return send_script(socket_path, script, "save-as", timeout)


def close_front_project(socket_path: Path, timeout: float) -> list[dict[str, Any]]:
    script = 'CloseProject(False)\nPrint "closed-front-project"'
    return send_script(socket_path, script, "close-front", timeout)


def close_front_window(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
tell application "System Events"
  tell process "Xojo"
    keystroke "w" using {command down}
  end tell
end tell
'''
    result = run_osascript(script, timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def close_choose_project_window(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
set didClose to false
set stillOpen to false
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      if exists window "Choose a Project" then
        perform action "AXRaise" of window "Choose a Project"
        delay 0.2
        set frontmost to true
        try
          set closeButtons to (buttons of window "Choose a Project" whose subrole is "AXCloseButton")
          if (count of closeButtons) > 0 then
            click item 1 of closeButtons
          else
            keystroke "w" using {command down}
          end if
        on error
          keystroke "w" using {command down}
        end try
        set didClose to true
        delay 0.5
      end if
      if exists window "Choose a Project" then set stillOpen to true
    end tell
  end if
end tell
return "didClose=" & didClose & ";stillOpen=" & stillOpen
'''
    result = run_osascript(script, timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def choose_project_still_open(result: dict[str, Any]) -> bool:
    return result["returncode"] != 0 or "stillOpen=true" in result["stdout"]


def cleanup_after_failed_attempt(timeout: float) -> dict[str, Any]:
    script = '''
tell application "Xojo" to activate
delay 0.2
set closedWindows to 0
set canceledSheets to 0
set chooserStillOpen to false
tell application "System Events"
  if exists process "Xojo" then
    tell process "Xojo"
      set frontmost to true
      repeat 3 times
        if exists window 1 then
          if exists sheet 1 of window 1 then
            if exists button "Don't Save" of sheet 1 of window 1 then
              click button "Don't Save" of sheet 1 of window 1
            else if exists button "Don’t Save" of sheet 1 of window 1 then
              click button "Don’t Save" of sheet 1 of window 1
            else if exists button "Cancel" of sheet 1 of window 1 then
              click button "Cancel" of sheet 1 of window 1
            else if exists button "OK" of sheet 1 of window 1 then
              click button "OK" of sheet 1 of window 1
            else
              key code 53
            end if
            set canceledSheets to canceledSheets + 1
            delay 0.5
          end if
        end if
      end repeat

      repeat 6 times
        if not (exists window 1) then exit repeat
        set frontWindowName to name of window 1
        if frontWindowName is "Choose a Project" then exit repeat
        keystroke "w" using {command down}
        set closedWindows to closedWindows + 1
        delay 0.6
        if exists window 1 then
          if exists sheet 1 of window 1 then
            if exists button "Don't Save" of sheet 1 of window 1 then
              click button "Don't Save" of sheet 1 of window 1
            else if exists button "Don’t Save" of sheet 1 of window 1 then
              click button "Don’t Save" of sheet 1 of window 1
            else if exists button "Cancel" of sheet 1 of window 1 then
              click button "Cancel" of sheet 1 of window 1
            else
              key code 53
            end if
            set canceledSheets to canceledSheets + 1
            delay 0.5
          end if
        end if
      end repeat

      if exists window "Choose a Project" then
        perform action "AXRaise" of window "Choose a Project"
        delay 0.2
        try
          set closeButtons to (buttons of window "Choose a Project" whose subrole is "AXCloseButton")
          if (count of closeButtons) > 0 then
            click item 1 of closeButtons
          else
            keystroke "w" using {command down}
          end if
        on error
          keystroke "w" using {command down}
        end try
        delay 0.5
      end if
      if exists window "Choose a Project" then set chooserStillOpen to true
    end tell
  end if
end tell
return "closedWindows=" & closedWindows & ";canceledSheets=" & canceledSheets & ";chooserStillOpen=" & chooserStillOpen
'''
    result = run_osascript(script, timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def bounded_timeout(args: argparse.Namespace, requested: float) -> float:
    lease = getattr(args, "_lease", None)
    if lease is None:
        return requested
    return lease.bound_timeout(requested)


def best_effort_cleanup(args: argparse.Namespace) -> dict[str, Any]:
    try:
        timeout = bounded_timeout(args, args.ui_timeout)
    except TimeoutError as exc:
        return {"returncode": 124, "stdout": "", "stderr": str(exc), "skipped": "lease-expired"}
    return cleanup_after_failed_attempt(timeout)


def append_step(
    args: argparse.Namespace,
    report: dict[str, Any],
    name: str,
    operation: Any,
) -> Any:
    reporter = getattr(args, "_progress", ProgressReporter("convert", enabled=False))
    result, elapsed_ms = measured_call(reporter, name, operation)
    report["steps"].append({"name": name, "elapsedMs": elapsed_ms, "result": result})
    return result


def _convert_one(args: argparse.Namespace, source: Path) -> dict[str, Any]:
    target = target_for(source)
    report: dict[str, Any] = {
        "source": str(source),
        "target": str(target),
        "steps": [],
    }
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing target folder: {target.parent}")
    if target.parent.exists():
        append_step(
            args,
            report,
            "cleanup-empty-target-folder-before-open",
            lambda: remove_empty_target_folder(target),
        )
        if target.parent.exists():
            raise FileExistsError(f"Refusing to overwrite existing target folder: {target.parent}")

    if args.reset_xojo_before_each:
        append_step(args, report, "reset-xojo-before-open", terminate_xojo_processes)

    if args.launch:
        ready_result = append_step(
            args,
            report,
            "ensure-xojo-ready-before-open",
            lambda: ensure_xojo_ready(
                Path(args.xojo_app),
                bounded_timeout(args, args.open_settle_timeout),
                bounded_timeout(args, args.launch_timeout),
            ),
        )
        if ready_result["returncode"] != 0:
            report["status"] = "failed"
            report["error"] = "Could not launch or recover Xojo before opening the source project"
            return report

    chooser_before = append_step(
        args,
        report,
        "close-choose-project-before-open",
        lambda: close_choose_project_window(bounded_timeout(args, args.ui_timeout)),
    )
    if choose_project_still_open(chooser_before):
        report["status"] = "failed"
        report["error"] = "Could not close Xojo Choose a Project window before opening the source project"
        return report

    open_result = append_step(
        args,
        report,
        "open-binary-finder",
        lambda: open_project_with_finder(
            source,
            Path(args.xojo_app),
            bounded_timeout(args, args.open_settle_timeout),
        ),
    )
    if open_result["returncode"] != 0:
        report["status"] = "failed"
        report["error"] = "Finder/open failed to open binary project"
        return report

    append_step(
        args,
        report,
        "settle-prompts-after-open",
        lambda: accept_known_prompts(bounded_timeout(args, args.ui_timeout)),
    )

    if args.convert_api2:
        append_step(
            args,
            report,
            "settle-prompts-before-api2",
            lambda: accept_known_prompts(bounded_timeout(args, args.ui_timeout)),
        )
        api2_result = append_step(
            args,
            report,
            "convert-project-to-api2",
            lambda: convert_project_to_api2(bounded_timeout(args, args.ui_timeout)),
        )
        if api2_result["returncode"] != 0:
            report["status"] = "failed"
            report["error"] = "Could not run Project > Convert Project to API 2"
            return report
        append_step(
            args,
            report,
            "settle-prompts-after-api2",
            lambda: accept_known_prompts(bounded_timeout(args, args.ui_timeout)),
        )

    save_request = append_step(args, report, "request-save-as", lambda: invoke_save_as(args))
    if save_request["returncode"] != 0:
        report["status"] = "failed"
        report["error"] = "Could not invoke File > Save As"
        return report

    ui_result = append_step(
        args,
        report,
        "drive-save-dialog",
        lambda: save_as_text_project(target, bounded_timeout(args, args.ui_timeout)),
    )
    if ui_result["returncode"] != 0:
        report["status"] = "failed"
        report["error"] = "Save As dialog automation failed"
        return report

    append_step(
        args,
        report,
        "settle-prompts-after-save",
        lambda: accept_known_prompts(bounded_timeout(args, args.ui_timeout)),
    )

    verification = append_step(
        args,
        report,
        "verify-output",
        lambda: wait_for_text_project(target, bounded_timeout(args, args.verify_timeout)),
    )
    if not verification["actualTextProjectExists"] or verification["textProjectFileCount"] <= 1:
        report["status"] = "failed"
        report["error"] = "Text project output was not verified"
        return report

    if args.close_after:
        append_step(
            args,
            report,
            "close-after",
            lambda: close_front_window(bounded_timeout(args, args.ui_timeout)),
        )
        chooser_after = append_step(
            args,
            report,
            "close-choose-project-after-close",
            lambda: close_choose_project_window(bounded_timeout(args, args.ui_timeout)),
        )
        if choose_project_still_open(chooser_after):
            report["status"] = "failed"
            report["error"] = "Text project was created, but Xojo Choose a Project cleanup failed"
            return report

    report["status"] = "converted"
    return report


def convert_one(args: argparse.Namespace, source: Path) -> dict[str, Any]:
    reporter = getattr(args, "_progress", ProgressReporter("convert", enabled=False))
    result, elapsed_ms = measured_call(
        reporter,
        "convert-project",
        lambda: _convert_one(args, source),
    )
    result["elapsedMs"] = elapsed_ms
    reporter.emit(
        "convert-project-result",
        result.get("status", "unknown"),
        source=str(source),
        elapsedMs=elapsed_ms,
    )
    return result


def write_json(path: Path | None, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def failed_sources_from_reports(paths: list[str] | None) -> set[str]:
    failed: set[str] = set()
    for raw_path in paths or []:
        path = Path(raw_path).expanduser()
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        candidates = data.get("results", [data] if data.get("source") else [])
        for item in candidates:
            if item.get("status") == "failed" and item.get("source"):
                failed.add(str(Path(item["source"]).expanduser().resolve()))
    return failed


def command_inventory(args: argparse.Namespace) -> int:
    write_json(Path(args.output_json) if args.output_json else None, build_manifest(Path(args.root)))
    return 0


def command_pilot(args: argparse.Namespace) -> int:
    source = Path(args.project).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    try:
        report = convert_one(args, source)
    except Exception:
        cleanup = best_effort_cleanup(args)
        getattr(args, "_progress", ProgressReporter("pilot", enabled=False)).emit(
            "cleanup-after-exception",
            "completed" if cleanup["returncode"] == 0 else "failed",
            result=cleanup,
        )
        raise
    if report.get("status") != "converted":
        cleanup = best_effort_cleanup(args)
        report.setdefault("steps", []).append({"name": "cleanup-after-failure", "result": cleanup})
    write_json(Path(args.output_json) if args.output_json else None, report)
    return 0 if report.get("status") == "converted" else 1


def command_batch(args: argparse.Namespace) -> int:
    batch_started = time.monotonic()
    root = Path(args.root).expanduser().resolve()
    sources = binary_projects(root)
    skip_failed_sources = failed_sources_from_reports(args.skip_failed_from_json)
    if args.match:
        matches = [text.lower() for text in args.match]
        sources = [source for source in sources if any(match in str(source.relative_to(root)).lower() for match in matches)]
    skip_path_contains = [text.lower() for text in args.skip_path_contains or []]

    selected: list[Path] = []
    skipped: list[dict[str, Any]] = []
    for source in sources:
        target = target_for(source)
        summary = companion_summary(target)
        if summary["actualTextProjectExists"]:
            skipped.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "reason": "target_exists",
                    "actualTextProject": summary["actualTextProject"],
                }
            )
            continue
        relative_source_lower = str(source.relative_to(root)).lower()
        matched_skip = next((text for text in skip_path_contains if text in relative_source_lower), None)
        if matched_skip:
            skipped.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "reason": "path_contains",
                    "match": matched_skip,
                }
            )
            continue
        if str(source.resolve()) in skip_failed_sources:
            skipped.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "reason": "prior_failed_report",
                }
            )
            continue
        selected.append(source)

    if args.limit is not None:
        selected = selected[: args.limit]

    report: dict[str, Any] = {
        "root": str(root),
        "match": args.match,
        "limit": args.limit,
        "skipPathContains": args.skip_path_contains,
        "skipFailedFromJson": args.skip_failed_from_json,
        "skipFailedCount": len(skip_failed_sources),
        "selectedCount": len(selected),
        "skipped": skipped,
        "results": [],
    }
    output_path = Path(args.output_json) if args.output_json else None
    if output_path:
        write_json(output_path, report)

    ok = True
    for index, source in enumerate(selected, start=1):
        previous_attempts: list[dict[str, Any]] = []
        result: dict[str, Any] | None = None
        for attempt in range(1, args.retry_attempts + 1):
            try:
                result = convert_one(args, source)
            except Exception as exc:
                result = {
                    "source": str(source),
                    "target": str(target_for(source)),
                    "status": "failed",
                    "error": str(exc),
                    "steps": [],
                }
            result["attempt"] = attempt
            if result.get("status") == "converted":
                break

            cleanup = cleanup_after_failed_attempt(bounded_timeout(args, args.ui_timeout))
            result.setdefault("steps", []).append({"name": "cleanup-after-failed-attempt", "result": cleanup})
            empty_cleanup = remove_empty_target_folder(target_for(source))
            result.setdefault("steps", []).append({"name": "cleanup-empty-target-folder", "result": empty_cleanup})
            reset_needed = cleanup["returncode"] != 0 or "chooserStillOpen=true" in cleanup["stdout"] or attempt < args.retry_attempts
            if reset_needed:
                reset = terminate_xojo_processes()
                result.setdefault("steps", []).append({"name": "reset-xojo-after-failed-attempt", "result": reset})

            if attempt < args.retry_attempts:
                previous_attempts.append(result)
                if output_path:
                    interim = dict(report)
                    interim["inProgress"] = {
                        "batchIndex": index,
                        "source": str(source),
                        "attempt": attempt,
                        "status": result.get("status"),
                        "error": result.get("error"),
                    }
                    write_json(output_path, interim)
                continue
            break

        assert result is not None
        if previous_attempts:
            result["previousAttempts"] = previous_attempts
            result["attemptCount"] = len(previous_attempts) + 1
        result["batchIndex"] = index
        report["results"].append(result)
        if output_path:
            write_json(output_path, report)
        if result.get("status") != "converted":
            ok = False
            if not args.continue_on_error:
                report["stoppedAfterFailure"] = True
                if output_path:
                    write_json(output_path, report)
                break
        elif args.reset_xojo_after_each:
            reset_after = terminate_xojo_processes()
            result.setdefault("steps", []).append({"name": "reset-xojo-after-converted-project", "result": reset_after})
            if output_path:
                write_json(output_path, report)

    report["convertedCount"] = sum(1 for item in report["results"] if item.get("status") == "converted")
    report["failedCount"] = sum(1 for item in report["results"] if item.get("status") == "failed")
    report["elapsedMs"] = round((time.monotonic() - batch_started) * 1000)
    if output_path:
        write_json(output_path, report)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Xojo binary example projects to text projects through Xojo Save As.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--xojo-app", default=str(DEFAULT_XOJO_APP))
    parser.add_argument("--socket", default=str(DEFAULT_SOCKET))
    parser.add_argument("--launch", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--launch-timeout", type=float, default=30.0)
    parser.add_argument("--command-timeout", type=float, default=10.0)
    parser.add_argument("--ui-timeout", type=float, default=30.0)
    parser.add_argument("--verify-timeout", type=float, default=20.0)
    parser.add_argument("--open-settle-timeout", type=float, default=3.0)
    parser.add_argument("--convert-api2", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--save-as-method", choices=["auto", "ide", "hotkey", "menu"], default="auto")
    parser.add_argument("--reset-xojo-before-each", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--reset-xojo-after-each", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--lock-file",
        default=str(DEFAULT_LOCK_FILE),
        help="Shared GUI lease file used by every Xojo automation entry point.",
    )
    parser.add_argument(
        "--lease-timeout",
        type=float,
        default=1800.0,
        help="Deadline used to bound a pilot or batch GUI automation job.",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write JSONL progress events to stderr.",
    )
    parser.add_argument("--output-json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Write a manifest of binary examples and proposed text targets.")
    inventory.add_argument("--output-json")
    inventory.set_defaults(func=command_inventory)

    pilot = subparsers.add_parser("pilot", help="Convert exactly one binary example project.")
    pilot.add_argument("project")
    pilot.add_argument("--output-json")
    pilot.add_argument("--close-after", action=argparse.BooleanOptionalAction, default=True)
    pilot.set_defaults(func=command_pilot)

    batch = subparsers.add_parser("batch", help="Convert multiple binary example projects, skipping existing targets.")
    batch.add_argument("--output-json")
    batch.add_argument("--match", action="append", help="Only convert projects whose relative path contains this text. Can be repeated.")
    batch.add_argument("--limit", type=int, help="Maximum number of not-yet-converted projects to process.")
    batch.add_argument("--skip-failed-from-json", action="append", help="Skip sources that failed in a prior converter report JSON. Can be repeated.")
    batch.add_argument("--skip-path-contains", action="append", help="Skip sources whose relative path contains this text. Can be repeated.")
    batch.add_argument("--retry-attempts", type=int, default=1, help="Attempts per selected project before marking it failed.")
    batch.add_argument("--continue-on-error", action="store_true")
    batch.add_argument("--close-after", action=argparse.BooleanOptionalAction, default=True)
    batch.set_defaults(func=command_batch)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    reporter = ProgressReporter(args.command, enabled=args.progress)
    args._progress = reporter
    lease: GuiLease | None = None
    try:
        if args.command not in {"pilot", "batch"}:
            return args.func(args)

        project = getattr(args, "project", None)
        with GuiLease(
            Path(args.lock_file).expanduser(),
            action=args.command,
            project=str(Path(project).expanduser().resolve()) if project else str(Path(args.root).expanduser().resolve()),
            timeout=args.lease_timeout,
        ) as active_lease:
            lease = active_lease
            args._lease = lease
            reporter.emit("gui-lease", "acquired", **lease.metadata)
            preflight = xojo_window_inventory(bounded_timeout(args, args.ui_timeout))
            reporter.emit("clean-session-check", "completed", result=preflight)
            if preflight["returncode"] != 0:
                raise RuntimeError(f"Could not inspect Xojo windows safely: {preflight['stderr']}")
            if preflight["projectWindows"]:
                raise RuntimeError(
                    "Refusing GUI conversion while Xojo project windows are open: "
                    + ", ".join(preflight["projectWindows"])
                )
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
