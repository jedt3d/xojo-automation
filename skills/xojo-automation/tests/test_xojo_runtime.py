from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from xojo_runtime import GuiLease  # noqa: E402


class GuiLeaseTests(unittest.TestCase):
    def test_lease_is_exclusive_and_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "xojo.lock"
            first = GuiLease(path, action="run", project="Demo", timeout=30).acquire()
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(metadata["action"], "run")
                self.assertEqual(metadata["project"], "Demo")
                self.assertIn("deadlineAt", metadata)

                with self.assertRaisesRegex(RuntimeError, "owns"):
                    GuiLease(path, action="analyze", project="Other", timeout=30).acquire()
            finally:
                first.release()

            second = GuiLease(path, action="analyze", project="Other", timeout=30).acquire()
            second.release()

    def test_bound_timeout_never_exceeds_remaining_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lease = GuiLease(
                Path(directory) / "xojo.lock",
                action="run",
                project=None,
                timeout=0.2,
            ).acquire()
            try:
                self.assertLessEqual(lease.bound_timeout(10), 0.2)
                time.sleep(0.15)
                self.assertLess(lease.bound_timeout(10), 0.08)
            finally:
                lease.release()


if __name__ == "__main__":
    unittest.main()
