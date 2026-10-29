from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Optional
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import xojo_example_converter  # noqa: E402
import xojo_harness  # noqa: E402


def serve_once(
    socket_path: Path,
    frames: list[dict[str, object]],
    hold_open: float,
    ready: threading.Event,
) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        server.listen(1)
        ready.set()
        connection, _ = server.accept()
        with connection:
            incoming = b""
            while incoming.count(b"\0") < 2:
                chunk = connection.recv(65536)
                if not chunk:
                    return
                incoming += chunk
            for frame in frames:
                connection.sendall(json.dumps(frame).encode("utf-8") + b"\0")
            time.sleep(hold_open)


class IpcCompletionTests(unittest.TestCase):
    def run_server(
        self,
        sender: Callable[..., list[dict[str, Any]]],
        frames: list[dict[str, object]],
        *,
        timeout: float,
        quiet_timeout: Optional[float] = None,
        hold_open: float = 0.5,
    ) -> tuple[list[dict[str, object]], float]:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "XojoIDE"
            ready = threading.Event()
            server = threading.Thread(
                target=serve_once,
                args=(socket_path, frames, hold_open, ready),
                daemon=True,
            )
            server.start()
            self.assertTrue(ready.wait(1))
            started = time.monotonic()
            try:
                if quiet_timeout is None:
                    messages = sender(socket_path, 'Print "test"', "test", timeout)
                else:
                    messages = sender(
                        socket_path,
                        'Print "test"',
                        "test",
                        timeout,
                        quiet_timeout,
                    )
                elapsed = time.monotonic() - started
                return messages, elapsed
            finally:
                server.join(timeout=1)

    def test_harness_returns_after_terminal_response_quiet_window(self) -> None:
        messages, elapsed = self.run_server(
            xojo_harness.send_script,
            [{"tag": "test", "response": "ok"}],
            timeout=2,
            quiet_timeout=0.05,
        )
        self.assertEqual(messages[-1]["response"], "ok")
        self.assertLess(elapsed, 0.4)

    def test_harness_timeout_without_terminal_response(self) -> None:
        with self.assertRaises(TimeoutError):
            self.run_server(
                xojo_harness.send_script,
                [{"tag": "test", "message": "working"}],
                timeout=0.1,
                quiet_timeout=0.05,
                hold_open=0.3,
            )

    def test_converter_returns_before_full_socket_timeout(self) -> None:
        messages, elapsed = self.run_server(
            xojo_example_converter.send_script,
            [{"tag": "test", "response": "ok"}],
            timeout=2,
        )
        self.assertEqual(messages[-1]["response"], "ok")
        self.assertLess(elapsed, 1.2)


class ProjectPreparationTests(unittest.TestCase):
    def args(self, socket_path: Path, reload_policy: str) -> argparse.Namespace:
        return argparse.Namespace(
            command="analyze",
            socket=str(socket_path),
            launch=False,
            launch_timeout=1.0,
            command_timeout=0.2,
            quiet_timeout=0.05,
            reload_policy=reload_policy,
            open_method="auto",
        )

    def test_skip_policy_verifies_project_without_close_or_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "XojoIDE"
            socket_path.touch()
            project_path = Path(directory) / "Demo.xojo_project"
            with mock.patch.object(
                xojo_harness,
                "send_script",
                return_value=[{"response": f"opened|{project_path}"}],
            ) as send_script, mock.patch.object(
                xojo_harness,
                "open_project_with_finder",
            ) as open_with_finder:
                lifecycle = xojo_harness.prepare_project(
                    self.args(socket_path, "skip"),
                    project_path,
                    {"path": "/Applications/Xojo.app"},
                )
            self.assertEqual(lifecycle[0]["step"], "reuse-open-project")
            send_script.assert_called_once()
            self.assertEqual(send_script.call_args.args[1], 'Print "opened|" + ProjectShellPath')
            open_with_finder.assert_not_called()

    def test_skip_policy_rejects_wrong_or_unconfirmed_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "XojoIDE"
            socket_path.touch()
            for response in ["opened|/tmp/Other.xojo_project", "", {"scriptError": "No project"}]:
                with self.subTest(response=response), mock.patch.object(
                    xojo_harness,
                    "send_script",
                    return_value=[{"response": response}],
                ), mock.patch.object(xojo_harness, "open_project_with_finder") as open_with_finder:
                    with self.assertRaises(RuntimeError):
                        xojo_harness.prepare_project(
                            self.args(socket_path, "skip"),
                            Path(directory) / "Demo.xojo_project",
                            {"path": "/Applications/Xojo.app"},
                        )
                    open_with_finder.assert_not_called()

    def test_open_timeout_uses_finder_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "XojoIDE"
            socket_path.touch()
            args = self.args(socket_path, "always")
            project_path = Path(directory) / "Demo.xojo_project"
            with mock.patch.object(
                xojo_harness,
                "send_script",
                side_effect=[
                    [{"response": "closed"}],
                    TimeoutError("open timed out"),
                    [{"response": f"opened|{project_path}"}],
                ],
            ), mock.patch.object(
                xojo_harness,
                "open_project_with_finder",
                return_value={"returnCode": 0, "stdout": "", "stderr": ""},
            ) as open_with_finder:
                lifecycle = xojo_harness.prepare_project(
                    args,
                    project_path,
                    {"path": "/Applications/Xojo.app"},
                )
            self.assertEqual(
                [item["step"] for item in lifecycle],
                ["close", "open-ide-failed", "open-finder", "verify-finder-open"],
            )
            open_with_finder.assert_called_once()

    def test_script_error_is_not_success(self) -> None:
        messages = [{"response": {"scriptError": "unknown symbol"}}]
        with self.assertRaisesRegex(RuntimeError, "scriptError"):
            xojo_harness.require_successful_response(messages, "test")

    def test_open_confirmation_requires_expected_project(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected"):
            xojo_harness.require_opened_project(
                [{"response": "opened|/tmp/Other.xojo_project"}],
                Path("/tmp/Demo.xojo_project"),
            )

    def test_open_confirmation_accepts_observed_shell_escaped_path(self) -> None:
        xojo_harness.require_opened_project(
            [{"response": r"opened|/tmp/2026\-10\-29/xojo\-automation/Agentic\ Smoke.xojo_project"}],
            Path("/tmp/2026-10-29/xojo-automation/Agentic Smoke.xojo_project"),
        )

    def test_open_confirmation_preserves_literal_paths_and_rejects_multiple_words(self) -> None:
        xojo_harness.require_opened_project(
            [{"response": "opened|/tmp/Agentic Smoke.xojo_project"}],
            Path("/tmp/Agentic Smoke.xojo_project"),
        )
        with self.assertRaises(RuntimeError):
            xojo_harness.require_opened_project(
                [{"response": r"opened|/tmp/Other\ Project.xojo_project /tmp/Demo.xojo_project"}],
                Path("/tmp/Demo.xojo_project"),
            )


if __name__ == "__main__":
    unittest.main()
