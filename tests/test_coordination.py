import base64
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import coordination as c
from mcp_session import Session


class Backend:
    def __init__(self, owner):
        self.owner = owner
        self.pending = False
        self.process = mock.Mock()
        self.process.poll.return_value = None
        self.scripts = []
        self.running = False
        self.closed = False

    def send(self, value):
        pass

    def close(self):
        if self.pending:
            raise RuntimeError("closed while pending")
        self.closed = True
        self.process.poll.return_value = 0

    def request(self, method, params):
        if method == "initialize":
            return {"result": {"serverInfo": {"name": "XMCP", "version": "1.11.0"}}}
        script = params["arguments"]["script"]
        self.scripts.append(script)
        if self.owner.pending_error:
            return {"result": {"isError": True, "content": [{"type": "text", "text": self.owner.pending_error}]}}
        if script.startswith('Print "XCOORD_ID|"'):
            text = "XCOORD_ID|2026.03\n" + shlex.quote(str(self.owner.connected))
        elif "XCOORD_STAMPS|" in script:
            paths = [self.owner.fixture / "App.xojo_code", self.owner.fixture / "CoordinationProbe.xojo_code"]
            values = [c.stamp_value(p.read_bytes()) for p in paths]
            if self.owner.stale:
                values = ["UNSET"] * 2
            text = "XCOORD_STAMPS|" + "\n".join(values)
            if self.owner.mutate and not self.owner.mutated and values[0] != "UNSET":
                p = paths[0]
                p.write_bytes(p.read_bytes().replace(b'"baseline"', b'"human-edit"'))
                self.owner.mutated = True
        elif 'DoCommand "RunApp"' in script:
            self.pending = True
            deadline = time.monotonic() + self.owner.delay
            while time.monotonic() < deadline:
                self.owner.job.tick(True)
                time.sleep(.01)
            self.pending = False
            self.running = True
            stamp = c.stamp_value((self.owner.fixture / "App.xojo_code").read_bytes())
            context = json.loads(base64.b64decode(stamp))
            event = {**{k: context[k] for k in ["run_id", "revision", "project_id"]},
                     "stamp": stamp, "event": self.owner.event, "message": "test-result"}
            with Path(context["output"]).open("w") as out:
                out.write(json.dumps({**event, "run_id": "stale-other-run"}) + "\n")
                out.write(json.dumps(event) + "\n")
            text = "XCOORD_DONE|" + self.owner.spec["run_id"]
        elif 'DoCommand "Kill"' in script:
            if self.owner.missing_stop:
                self.owner.missing_stop -= 1
                return {"result": {"isError": True, "content": [{"type": "text", "text": "IPC socket not found at /tmp/XojoIDE (no socket file)."}]}}
            self.running = False
            text = "XCOORD_STOPPED"
        else:
            text = "XCOORD_READY"
        return {"result": {"content": [{"type": "text", "text": text}]}}


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.fixture = self.directory / "fixture"
        shutil.copytree(ROOT / "fixtures/coordinated-smoke", self.fixture,
                        ignore=shutil.ignore_patterns("*.debug", "Builds - *", "*.xojo_uistate"))
        # Unit sources are independent of live-suite variant/stamp edits.
        (self.fixture / "App.xojo_code").write_text('''#tag Class
Protected Class App
Inherits ConsoleApplication
  #tag Constant, Name = Scenario, Type = String, Dynamic = False, Default = \\"baseline", Scope = Public
  #tag EndConstant
  #tag Constant, Name = CoordinationStamp, Type = String, Dynamic = False, Default = \\"UNSET", Scope = Public
  #tag EndConstant
End Class
#tag EndClass
''')
        module = self.fixture / "CoordinationProbe.xojo_code"
        module.write_bytes(c.replace_stamp(module.read_bytes(), "UNSET"))
        self.connected = self.fixture / "CoordinatedSmoke.xojo_project"
        output = self.directory / "job"
        output.mkdir()
        self.spec = {"directory": str(output), "profile": str(self.fixture / "coordination.json"),
                     "run_id": "test-run", "xmcp": "fake", "ide_app": "fake", "operation": "run",
                     "completion": "completed", "timeout": 5, "sync_timeout": .15,
                     "lease": str(self.directory / "lease")}
        self.delay = 0
        self.stale = False
        self.mutate = False
        self.mutated = False
        self.event = "completed"
        self.pending_error = False
        self.missing_stop = 0
        self.backend = Backend(self)
        self.job = c.Coordinator(self.spec, lambda *_: self.backend)

    def tearDown(self):
        self.temp.cleanup()

    def work(self):
        with mock.patch.object(c, "find_ide_pid", return_value=os.getpid()), mock.patch.object(c, "debug_processes", return_value=[]):
            return self.job.work()

    def test_identity_rejected_before_source_write_or_run(self):
        self.connected = self.fixture / "Other.xojo_project"
        before = (self.fixture / "App.xojo_code").read_bytes()
        result = self.work()
        self.assertEqual(result["outcome"], "identity_mismatch")
        self.assertEqual(before, (self.fixture / "App.xojo_code").read_bytes())
        self.assertFalse(any('DoCommand "RunApp"' in s for s in self.backend.scripts))

    def test_stale_run_rejected_valid_event_and_restore_accepted(self):
        before = (self.fixture / "App.xojo_code").read_bytes()
        result = self.work()
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(len(result["rejected_events"]), 1)
        self.assertEqual(result["runtime_events"][0]["run_id"], "test-run")
        self.assertEqual(before, (self.fixture / "App.xojo_code").read_bytes())
        self.assertTrue(result["restore_reload_confirmed"])
        self.assertTrue(self.backend.closed)

    def test_unsynchronized_stamp_never_dispatches_run(self):
        self.stale = True
        result = self.work()
        self.assertEqual(result["outcome"], "sync_timeout")
        self.assertFalse(any('DoCommand "RunApp"' in s for s in self.backend.scripts))

    def test_runtime_exception_has_current_identity(self):
        self.event = "exception"
        result = self.work()
        self.assertEqual(result["outcome"], "runtime_error")
        self.assertEqual(result["runtime_events"][0]["revision"], result["revision"])

    def test_cleanup_retries_only_proven_undelivered_command(self):
        self.missing_stop = 1
        result = self.work()
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(sum('DoCommand "RunApp"' in s for s in self.backend.scripts), 1)
        self.assertEqual(sum('DoCommand "Kill"' in s for s in self.backend.scripts), 2)

    def test_concurrent_source_edit_is_preserved_not_overwritten(self):
        self.mutate = True
        result = self.work()
        self.assertEqual(result["outcome"], "cleanup_failed")
        self.assertEqual(result["primary_outcome"], "source_changed")
        self.assertIn(b"human-edit", (self.fixture / "App.xojo_code").read_bytes())
        self.assertFalse(any('DoCommand "RunApp"' in s for s in self.backend.scripts))

    def test_late_run_reply_drains_before_stop_close_and_lease_release(self):
        self.spec["timeout"] = .15
        self.job.deadline = time.monotonic() + .15
        self.delay = .3
        result = self.work()
        self.assertEqual(result["outcome"], "deadline_exceeded")
        self.assertTrue(any('DoCommand "Kill"' in s for s in self.backend.scripts))
        self.assertTrue(self.backend.closed)
        self.assertTrue(result["source_restored"])
        with c.GuiLease(Path(self.spec["lease"]), action="next", project=None, timeout=1):
            pass

    def test_other_job_cannot_acquire_shared_lease(self):
        with c.GuiLease(Path(self.spec["lease"]), action="other", project=None, timeout=1):
            result = self.work()
        self.assertEqual(result["outcome"], "lease_or_setup_error")
        self.assertEqual(self.backend.scripts, [])
        self.assertFalse(result["lease_acquired"])
        self.assertFalse(result["lease_released"])

    def test_preexisting_debug_app_is_not_touched(self):
        with mock.patch.object(c, "find_ide_pid", return_value=os.getpid()), mock.patch.object(
                c, "debug_processes", return_value=[{"pid": 42}]):
            result = self.job.work()
        self.assertEqual(result["outcome"], "preexisting_debug_session")
        self.assertEqual(self.backend.scripts, [])

    def test_unresolved_backend_holds_lease_until_expected_ide_exits(self):
        self.pending_error = getattr(self, "pending_message", "The Xojo IDE has not finished answering")
        alive = [True]
        with mock.patch.object(c, "find_ide_pid", return_value=os.getpid()), mock.patch.object(
                c, "debug_processes", return_value=[]), mock.patch.object(c, "process_alive", side_effect=lambda _: alive[0]):
            thread = threading.Thread(target=self.job.work)
            thread.start()
            limit = time.monotonic() + 2
            while self.job.result["state"] != "quarantined" and time.monotonic() < limit:
                time.sleep(.01)
            self.assertEqual(self.job.result["state"], "quarantined")
            self.assertFalse(self.backend.closed)
            with self.assertRaises(RuntimeError):
                c.GuiLease(Path(self.spec["lease"]), action="next", project=None, timeout=1).acquire()
            alive[0] = False
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(self.backend.closed)
        self.assertEqual(len(self.backend.scripts), 1)

    def test_partial_write_backend_holds_lease_until_expected_ide_exits(self):
        self.pending_message = "Writing the request to the Xojo IDE failed partway (socket error). It may or may not have arrived."
        self.test_unresolved_backend_holds_lease_until_expected_ide_exits()

    def test_pending_backend_reply_is_classified_before_expired_deadline(self):
        self.job.session = self.backend
        def response(*_):
            self.job.deadline = time.monotonic() - 1
            return {"result": {"isError": True, "content": [{"type": "text",
                "text": "Writing the request to the Xojo IDE failed partway (socket error)."}]}}
        with mock.patch.object(self.backend, "request", side_effect=response):
            with self.assertRaisesRegex(RuntimeError, "Backend still owns pending IDE IPC"):
                self.job.script("test", "test")
        self.assertTrue(self.job.backend_unresolved)
        self.assertFalse(self.backend.closed)

    def test_pinned_manifest_change_rejected(self):
        with self.connected.open("a") as out:
            out.write("\nExtra=changed\n")
        with self.assertRaisesRegex(ValueError, "Pinned input changed"):
            c.load_profile(self.spec["profile"])

    def test_revision_ignores_stamps_but_changes_with_code(self):
        raw = (self.fixture / "App.xojo_code").read_bytes()
        a = c.source_revision({"App": raw}, {})
        self.assertEqual(a, c.source_revision({"App": c.replace_stamp(raw, "some-new-run")}, {}))
        self.assertNotEqual(a, c.source_revision({"App": raw.replace(b"baseline", b"new-code")}, {}))

    def test_padded_base64_uses_xojo_constant_escaping(self):
        raw = (self.fixture / "App.xojo_code").read_bytes()
        written = c.replace_stamp(raw, "eyJ4IjogMX0=")
        self.assertIn(rb"MX0\x3D", written)
        self.assertEqual(c.stamp_value(written), "eyJ4IjogMX0=")

    def test_pid_reuse_is_not_owned(self):
        old = {"pid": 123, "start": "old", "executable": "app"}
        with mock.patch.object(c, "debug_processes", return_value=[{**old, "start": "new"}]):
            self.assertFalse(c.same_process(old, Path("app")))


class LateIPCTransportTests(unittest.TestCase):
    def test_mock_ipc_peer_stays_open_after_caller_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_path = str(Path(directory) / "ide.sock")
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(socket_path)
            listener.listen()
            observations = []
            ready = threading.Event()

            def ide():
                peer, _ = listener.accept()
                with peer:
                    peer.recv(65536)
                    ready.set()
                    time.sleep(.25)
                    peer.setblocking(False)
                    try:
                        data = peer.recv(1, socket.MSG_PEEK)
                        observations.append("closed" if data == b"" else "data")
                    except BlockingIOError:
                        observations.append("open")
                    peer.setblocking(True)
                    peer.sendall(b'{"response":"late reply"}\0')

            forwarder = Path(directory) / "forwarder.py"
            forwarder.write_text('''import sys,json,socket
request=json.loads(sys.stdin.readline())
with socket.socket(socket.AF_UNIX) as peer:
 peer.connect(sys.argv[1]);peer.sendall(b'{"script":"mock"}\\0')
 reply=peer.recv(65536)
print(json.dumps({"id":request["id"],"result":{"content":[{"type":"text","text":"late reply"}]}}),flush=True)
sys.stdin.read()
''')
            thread = threading.Thread(target=ide)
            thread.start()
            expired = []
            deadline = time.monotonic() + .1
            session = Session([sys.executable, str(forwarder), socket_path], lambda _: None,
                              lambda pending: expired.append(pending) if time.monotonic() > deadline else None)
            answer = session.request("tools/call")
            session.close()
            thread.join(2)
            listener.close()
            self.assertTrue(expired)
            self.assertEqual(observations, ["open"])
            self.assertEqual(answer["result"]["content"][0]["text"], "late reply")


if __name__ == "__main__":
    unittest.main()
