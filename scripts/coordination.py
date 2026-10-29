"""Cooperative, fail-closed coordination for opt-in Agentic Mode projects on macOS."""
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

from mcp_session import Session, tool_text

SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "skills/xojo-automation/scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))
from xojo_runtime import GuiLease
from xojo_harness import running_xojo_processes, xojo_escape

STAMP = re.compile(r'(?m)^(\s*#tag Constant, Name = CoordinationStamp, Type = String, Dynamic = False, Default = \\")(.*?)(", Scope = Public\s*)$')


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stamp_value(data):
    matches = list(STAMP.finditer(data.decode("utf-8")))
    if len(matches) != 1:
        raise ValueError("Each managed item needs exactly one public CoordinationStamp string constant")
    return matches[0].group(2).replace(r"\x3D", "=")


def replace_stamp(data, value):
    stamp_value(data)
    # Xojo tag-attribute values must escape '=' even inside string defaults.
    # Unescaped Base64 padding was truncated by the live 2026r3 text parser.
    serialized = value.replace("=", r"\x3D")
    return STAMP.sub(lambda m: m.group(1) + serialized + m.group(3), data.decode("utf-8")).encode("utf-8")


def source_revision(items, fixed):
    content = {name: digest(replace_stamp(data, "UNSET")) for name, data in items.items()}
    content.update({name: digest(data) for name, data in fixed.items()})
    return digest(json.dumps(content, sort_keys=True).encode())


def compare_write(path, before, after):
    if path.read_bytes() != before:
        raise RuntimeError("Source changed before write: " + str(path))
    temporary = path.with_name(path.name + ".coord-tmp")
    try:
        temporary.write_bytes(after)
        temporary.chmod(path.stat().st_mode & 0o777)
        if path.read_bytes() != before:
            raise RuntimeError("Source changed during write: " + str(path))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def inside(base, value):
    path = (base / value).resolve()
    path.relative_to(base.resolve())
    return path


def load_profile(path):
    path = Path(path).resolve()
    profile = json.loads(path.read_text())
    if profile.get("schema") != 1:
        raise ValueError("Unsupported coordination profile schema")
    project = inside(path.parent, profile["project"])
    if project.suffix != ".xojo_project" or not project.is_file():
        raise ValueError("Expected a saved Xojo text project")
    if "AgenticMode=True" not in project.read_text().splitlines():
        raise ValueError("Project must already be saved with AgenticMode=True")
    if "Type=Console" not in project.read_text().splitlines():
        raise ValueError("This milestone supports Console coordination profiles only")
    if not profile["items"]:
        raise ValueError("At least one managed source item is required")
    names = set()
    files = set()
    for item in profile["items"]:
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", item["name"]):
            raise ValueError("Invalid managed item name")
        item["path"] = inside(project.parent, item["file"])
        stamp_value(item["path"].read_bytes())
        if item["name"] in names or item["path"] in files:
            raise ValueError("Duplicate managed item")
        names.add(item["name"])
        files.add(item["path"])
    fixed = {inside(project.parent, name): sha for name, sha in profile["fixed_inputs"].items()}
    if set(fixed) & files:
        raise ValueError("An input cannot be both managed and pinned")
    if project not in fixed:
        raise ValueError("Profile must pin its project manifest")
    manifest_items = {}
    # Every direct manifest source/resource must be managed or explicitly pinned.
    for line in project.read_text().splitlines():
        if ";" in line and "=" in line:
            relative = line.split("=", 1)[1].split(";")[1]
            candidate = inside(project.parent, relative)
            kind, payload = line.split("=", 1)
            if kind in ["Class", "Module", "Interface"]:
                fields = payload.split(";")
                if len(fields) < 4 or fields[3] != "&h0000000000000000":
                    raise ValueError("Nested code items need a future profile adapter")
                manifest_items[fields[0]] = candidate
            if candidate.is_file() and candidate not in files and candidate not in fixed:
                raise ValueError("Unaccounted manifest input: " + relative)
    if any(manifest_items.get(item["name"]) != item["path"] for item in profile["items"]):
        raise ValueError("Managed item names/files must match the project manifest")
    for p, sha in fixed.items():
        if digest(p.read_bytes()) != sha:
            raise ValueError("Pinned input changed; reconcile in IDE and refresh profile: " + str(p))
    app_name = next(line.split("=", 1)[1] for line in project.read_text().splitlines() if line.startswith("MacCarbonMachName="))
    executable = inside(project.parent, profile["debug_executable"])
    if executable != project.parent / (app_name + ".debug") / (app_name + ".debug"):
        raise ValueError("Debug executable must match the macOS Console project name")
    profile.update(project_path=project, fixed_paths=fixed, executable=executable)
    return profile


def find_ide_pid(app):
    processes = running_xojo_processes()
    matches = [p for p in processes if p.get("app") and Path(p["app"]["path"]).resolve() == Path(app).resolve()]
    if len(matches) != 1 or len(processes) != 1:
        raise RuntimeError("Expected exactly one running IDE at " + app)
    return matches[0]["pid"]


def process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def debug_processes(executable):
    found = []
    for line in subprocess.check_output(["ps", "-axo", "pid=,lstart=,comm="], text=True).splitlines():
        parts = line.strip().split(None, 6)
        if len(parts) == 7 and Path(parts[6]).resolve() == executable:
            found.append({"pid": int(parts[0]), "start": " ".join(parts[1:6]), "executable": parts[6]})
    return found


def same_process(record, executable):
    return record in debug_processes(executable)


class JobFailure(Exception):
    def __init__(self, outcome, detail):
        self.outcome = outcome
        super().__init__(detail)


class Coordinator:
    def __init__(self, spec, session_factory=Session):
        self.spec = spec
        self.directory = Path(spec["directory"])
        self.result = {"schema": 1, "run_id": spec["run_id"], "state": "running", "phase": "starting",
                       "started_at": now(), "outcome": None, "runtime_events": [],
                       "rejected_events": [], "cleanup_errors": [], "lease_acquired": False, "lease_released": False}
        self.session_factory = session_factory
        self.session = None
        self.overdue = None
        self.cleaning = False
        self.changed = []
        self.owned = []
        self.run_dispatched = False
        self.run_replied_ok = False
        self.backend_unresolved = False
        self.deadline = time.monotonic() + spec["timeout"]
        self.last_heartbeat = 0

    def save(self, **updates):
        self.result.update(updates)
        atomic_json(self.directory / "result.json", self.result)

    def journal(self, value):
        with (self.directory / "protocol.jsonl").open("a") as output:
            output.write(json.dumps({"timestamp": now(), **value}) + "\n")

    def tick(self, pending=False):
        if self.overdue is None:
            if (self.directory / "cancel").exists():
                self.overdue = "cancelled"
            elif time.monotonic() >= self.deadline:
                self.overdue = "deadline_exceeded"
        if hasattr(self, "ide_pid") and not process_alive(self.ide_pid):
            raise JobFailure("ide_exited", "Expected IDE process exited while waiting")
        if pending and self.overdue and self.result["state"] != "draining":
            self.save(state="draining", phase="waiting-for-late-reply", cancellation=self.overdue)
        if time.monotonic() - self.last_heartbeat >= 30:
            self.last_heartbeat = time.monotonic()
            self.journal({"heartbeat": self.result["phase"], "overdue": self.overdue})
        # Never raise while a request is in flight: its IPC socket must stay alive.
        if self.overdue and not pending and not self.cleaning:
            raise JobFailure(self.overdue, "Job deadline/cancellation observed; cleanup follows")

    def script(self, script, phase):
        self.save(phase=phase)
        while True:
            self.tick()
            response = self.session.request("tools/call", {"name": "run_ide_script",
                "arguments": {"script": script, "timeout": 86400000}})
            text, error = tool_text(response)
            # Classify uncertain delivery before observing a caller deadline.
            # A matching MCP error can still leave backend IDE IPC in flight.
            if error and any(term in text.lower() for term in [
                    "has not finished answering", "still waiting", "request is still pending",
                    "previous ide request is still running", "no answer from the ide within",
                    "writing the request to the xojo ide failed partway"]):
                self.backend_unresolved = True
                raise RuntimeError("Backend still owns pending IDE IPC: " + text)
            self.tick()
            # The pinned backend explicitly reports that no socket file exists:
            # the script was not delivered. Only cleanup can retry this condition.
            # Never replay an accepted command after a missing/late response.
            absent = error and text.startswith("IPC socket not found at ") and all(
                part.strip().endswith("(no socket file).") for part in text.split(" | "))
            if not (self.cleaning and absent):
                break
            if not hasattr(self, "reconnect_until"):
                self.reconnect_until = time.monotonic() + 30
            if time.monotonic() >= self.reconnect_until:
                break
            self.save(phase="waiting-for-cleanup-endpoint")
            time.sleep(.5)
        return text, error

    def guard(self, body, revisions=True):
        conditions = ['ProjectShellPath <> "' + xojo_escape(self.raw_project) + '"',
                      'Format(XojoVersion, "0000.00#") <> "' + xojo_escape(format(Decimal(self.profile["ide_version"]).normalize(), "f")) + '"']
        checks = ["If " + " Or ".join(conditions) + ' Then', 'Print "XCOORD_REJECT|identity"']
        if revisions:
            for item in self.profile["items"]:
                checks += ['ElseIf ConstantValue("' + item["name"] + '.CoordinationStamp") <> "' + self.stamp + '" Then',
                           'Print "XCOORD_REJECT|revision"']
        return "\n".join(checks + ["Else", body, "End If"])

    def checked(self, body, phase, revisions=True):
        self.assert_sources()
        text, error = self.script(self.guard(body, revisions), phase)
        if "XCOORD_REJECT|" in text:
            raise JobFailure("identity_or_revision_changed", text)
        return text, error

    def assert_sources(self):
        for path, expected in self.expected.items():
            if path.read_bytes() != expected:
                raise JobFailure("source_changed", "Source changed during job: " + str(path))

    def observe_processes(self):
        for process in debug_processes(self.profile["executable"]):
            if process not in self.owned:
                self.owned.append(process)
        self.result["owned_processes"] = self.owned

    def wait_stamps(self, wanted, phase, timeout):
        deadline = time.monotonic() + timeout
        body = 'Print "XCOORD_STAMPS|" + ' + " + Chr(10) + ".join(
            'ConstantValue("' + item["name"] + '.CoordinationStamp")' for item in self.profile["items"])
        while True:
            text, error = self.script(self.guard(body, False), phase)
            if "XCOORD_REJECT|" in text:
                raise JobFailure("identity_mismatch", text)
            if error:
                raise JobFailure("stamp_probe_failed", text)
            if text.startswith("XCOORD_STAMPS|") and text[len("XCOORD_STAMPS|"):].splitlines() == wanted:
                return
            if time.monotonic() >= deadline:
                raise JobFailure("sync_timeout", "IDE did not load all requested revision stamps")
            time.sleep(0.1)

    def consume_runtime(self):
        path = self.directory / "runtime.jsonl"
        if not path.exists():
            return None
        raw = path.read_bytes()
        lines = raw.split(b"\n")
        # Ignore an incomplete final write until the next poll.
        for line in lines[self.runtime_cursor:-1]:
            self.runtime_cursor += 1
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                self.result["rejected_events"].append({"reason": "invalid JSON"})
                continue
            expected = {"run_id": self.spec["run_id"], "revision": self.result["revision"],
                        "project_id": self.result["project_id"], "stamp": self.stamp}
            if not isinstance(event, dict) or any(event.get(key) != value for key, value in expected.items()):
                self.result["rejected_events"].append({"reason": "wrong run/revision/stamp", "event": event})
                continue
            if event.get("event") not in ["started", "completed", "exception"]:
                self.result["rejected_events"].append({"reason": "unknown event", "event": event})
                continue
            self.result["runtime_events"].append(event)
            if event["event"] == "exception":
                raise JobFailure("runtime_error", event.get("message", "Runtime exception"))
            if event["event"] == self.spec["completion"]:
                return event
        return None

    def execute(self):
        self.profile = load_profile(self.spec["profile"])
        self.ide_pid = find_ide_pid(self.spec["ide_app"])
        self.result["ide_pid"] = self.ide_pid
        if debug_processes(self.profile["executable"]):
            raise JobFailure("preexisting_debug_session", "Refusing to take ownership of an existing debug app")
        self.original = {item["path"]: item["path"].read_bytes() for item in self.profile["items"]}
        self.fixed = {p: p.read_bytes() for p in self.profile["fixed_paths"]}
        self.expected = {**self.original, **self.fixed}
        self.session = self.session_factory([self.spec["xmcp"]], self.journal, self.tick)
        hello = self.session.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
             "clientInfo": {"name": "xojo-coordinator", "version": "0.2.0"}})
        server = hello.get("result", {}).get("serverInfo", {})
        if server.get("name") != "XMCP" or server.get("version") != "1.11.0":
            raise JobFailure("server_mismatch", "Expected evaluated XMCP 1.11.0")
        self.session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        text, error = self.script('Print "XCOORD_ID|" + Format(XojoVersion, "0000.00#") + Chr(10) + ProjectShellPath', "identity")
        lines = text.splitlines()
        if error or len(lines) != 2 or not lines[0].startswith("XCOORD_ID|"):
            raise JobFailure("identity_mismatch", "Missing IDE identity: " + text)
        self.raw_project = lines[1]
        words = shlex.split(self.raw_project)
        if len(words) != 1 or Path(words[0]).resolve() != self.profile["project_path"] or Decimal(lines[0].split("|", 1)[1]) != Decimal(self.profile["ide_version"]):
            raise JobFailure("identity_mismatch", "Connected IDE/project differs from profile")
        self.result["identity"] = {"project": str(self.profile["project_path"]), "version": lines[0].split("|", 1)[1]}
        self.result["revision"] = source_revision(
            {str(p.relative_to(self.profile["project_path"].parent)): data for p, data in self.original.items()},
            {str(p.relative_to(self.profile["project_path"].parent)): data for p, data in self.fixed.items()})
        self.result["project_id"] = digest(str(self.profile["project_path"]).encode())
        context = {"run_id": self.spec["run_id"], "revision": self.result["revision"], "project_id": self.result["project_id"],
                   "output": str(self.directory / "runtime.jsonl")}
        self.stamp = base64.b64encode(json.dumps(context).encode()).decode()
        # The identity is rechecked in the same script immediately before writes.
        ready, error = self.checked('Print "XCOORD_READY"', "pre-write-identity", False)
        if error or "XCOORD_READY" not in ready:
            raise JobFailure("identity_mismatch", "Pre-write check failed")
        for path, data in self.original.items():
            stamped = replace_stamp(data, self.stamp)
            compare_write(path, data, stamped)
            self.changed.append(path)
            self.expected[path] = stamped
        self.wait_stamps([self.stamp] * len(self.original), "synchronizing", self.spec["sync_timeout"])
        self.save(synchronized=True)
        command = "CheckProjectErrors" if self.spec["operation"] == "analyze" else "RunApp"
        self.run_dispatched = self.spec["operation"] == "run"
        try:
            text, error = self.checked('DoCommand "' + command + '"\nPrint "XCOORD_DONE|' + self.spec["run_id"] + '"', "dispatch")
        except JobFailure as error:
            if error.outcome in ["source_changed", "identity_or_revision_changed"]:
                self.run_dispatched = False
            raise
        self.result["diagnostics"] = {"run_id": self.spec["run_id"], "revision": self.result["revision"],
                                      "text": text, "is_error": error}
        self.assert_sources()
        if error:
            raise JobFailure("compile_error", text)
        if "XCOORD_DONE|" + self.spec["run_id"] not in text:
            raise JobFailure("protocol_error", "Missing operation completion marker")
        if self.spec["operation"] == "analyze":
            return
        self.run_replied_ok = True
        self.runtime_cursor = 0
        self.save(phase="waiting-for-runtime")
        while True:
            self.tick()
            self.assert_sources()
            self.observe_processes()
            if self.consume_runtime():
                break
            time.sleep(0.1)

    def cleanup(self):
        self.cleaning = True
        self.save(state="cleaning", phase="cleanup")
        if self.session is not None and (self.session.pending or self.backend_unresolved):
            # Malformed/broken protocol cannot establish that the child has released
            # IDE IPC. Fail closed until the actual IDE exits; never kill it ourselves.
            self.save(state="quarantined", phase="unresolved-ipc", recovery="Close the IDE after preserving work; worker will release resources when that IDE process exits.")
            while self.session.process.poll() is None and process_alive(self.ide_pid):
                time.sleep(0.1)
            self.session.pending = False
        ide_available = hasattr(self, "ide_pid") and process_alive(self.ide_pid)
        if hasattr(self, "profile") and self.run_dispatched:
            self.observe_processes()
            # Late Run replies may have started an app despite a caller timeout.
            if self.run_replied_ok or self.owned or self.overdue:
                if ide_available:
                    try:
                        text, error = self.script(self.guard('DoCommand "Kill"\nPrint "XCOORD_STOPPED"'), "stopping-owned-run")
                        if error or "XCOORD_STOPPED" not in text:
                            raise RuntimeError(text)
                    except Exception as error:
                        self.result["cleanup_errors"].append("IDE stop: " + str(error))
                for process in self.owned:
                    if same_process(process, self.profile["executable"]):
                        os.kill(process["pid"], signal.SIGTERM)
                limit = time.monotonic() + 5
                while any(same_process(p, self.profile["executable"]) for p in self.owned) and time.monotonic() < limit:
                    time.sleep(0.1)
                if any(same_process(p, self.profile["executable"]) for p in self.owned):
                    self.result["cleanup_errors"].append("Owned debug process did not stop")
        restored = []
        for path in self.changed:
            try:
                compare_write(path, self.expected[path], self.original[path])
                restored.append(path)
            except Exception as error:
                self.result["cleanup_errors"].append("Restore conflict; preserving edited source: " + str(error))
        if restored and len(restored) == len(self.changed) and self.session and self.session.process.poll() is None and ide_available:
            try:
                self.wait_stamps([stamp_value(data) for data in self.original.values()], "confirming-restored-source", self.spec["sync_timeout"])
                self.result["restore_reload_confirmed"] = True
            except Exception as error:
                self.result["cleanup_errors"].append("Restore reload: " + str(error))
        if self.session is not None:
            self.session.close()
        self.result["source_restored"] = len(restored) == len(self.changed)

    def work(self):
        self.save(worker_pid=os.getpid())
        try:
            with GuiLease(Path(self.spec["lease"]), action="coordinated-" + self.spec["operation"],
                          project=self.spec["profile"], timeout=self.spec["timeout"]):
                self.save(lease_acquired=True)
                try:
                    self.execute()
                    self.result["outcome"] = "success"
                except JobFailure as error:
                    self.result.update(outcome=error.outcome, error=str(error))
                except Exception as error:
                    self.result.update(outcome="error", error=f"{type(error).__name__}: {error}")
                finally:
                    try:
                        self.cleanup()
                    except Exception as error:
                        self.result["cleanup_errors"].append(str(error))
                        # Do not release a lease while a backend could still hold IPC.
                        if self.session and (self.session.pending or self.backend_unresolved):
                            self.save(state="quarantined", phase="unresolved-ipc")
                            while self.session.process.poll() is None and process_alive(self.ide_pid):
                                time.sleep(0.1)
                            self.session.pending = False
                            self.session.close()
        except Exception as error:
            self.result.update(outcome="lease_or_setup_error", error=str(error))
        if self.result["cleanup_errors"]:
            self.result["primary_outcome"] = self.result["outcome"]
            self.result["outcome"] = "cleanup_failed"
        self.save(state="finished", phase="finished", ended_at=now(), lease_released=self.result["lease_acquired"])
        return self.result
