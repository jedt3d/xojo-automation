#!/usr/bin/env python3
"""Shared runtime primitives for bounded Xojo automation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Optional, TypeVar


DEFAULT_GUI_LEASE_FILE = Path("/tmp/xojo-gui-automation.lock")
T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: Optional[datetime] = None) -> str:
    return (value or utc_now()).isoformat(timespec="seconds")


class ProgressReporter:
    def __init__(self, action: str, enabled: bool = True, heartbeat_seconds: float = 30.0) -> None:
        self.action = action
        self.enabled = enabled
        self.heartbeat_seconds = heartbeat_seconds
        self.started = time.monotonic()

    def emit(self, step: str, state: str, **details: Any) -> None:
        if not self.enabled:
            return
        payload = {
            "event": "xojo-progress",
            "action": self.action,
            "step": step,
            "state": state,
            "elapsedMs": round((time.monotonic() - self.started) * 1000),
            "timestamp": utc_text(),
        }
        payload.update(details)
        print(json.dumps(payload, separators=(",", ":")), file=sys.stderr, flush=True)


class GuiLease:
    """Advisory single-owner lease for every Xojo automation entry point."""

    def __init__(
        self,
        path: Path,
        *,
        action: str,
        project: Optional[str],
        timeout: float,
    ) -> None:
        if timeout <= 0:
            raise ValueError("GUI lease timeout must be positive")
        self.path = path
        self.action = action
        self.project = project
        self.timeout = timeout
        self.started_monotonic: Optional[float] = None
        self.deadline_monotonic: Optional[float] = None
        self.handle: Any = None
        self.metadata: dict[str, Any] = {}

    def acquire(self) -> "GuiLease":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip() or "owner metadata unavailable"
            handle.close()
            raise RuntimeError(f"Another Xojo automation job owns {self.path}: {owner}") from exc

        started_at = utc_now()
        self.started_monotonic = time.monotonic()
        self.deadline_monotonic = self.started_monotonic + self.timeout
        self.metadata = {
            "pid": os.getpid(),
            "action": self.action,
            "project": self.project,
            "startedAt": utc_text(started_at),
            "deadlineAt": utc_text(started_at + timedelta(seconds=self.timeout)),
        }
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(self.metadata, separators=(",", ":")) + "\n")
        handle.flush()
        self.handle = handle
        return self

    def remaining_seconds(self) -> float:
        if self.deadline_monotonic is None:
            raise RuntimeError("GUI lease has not been acquired")
        remaining = self.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Xojo GUI lease deadline expired for {self.action}")
        return remaining

    def bound_timeout(self, requested: float) -> float:
        if requested <= 0:
            raise ValueError("Operation timeout must be positive")
        return min(requested, self.remaining_seconds())

    def release(self, state: str = "released") -> None:
        if self.handle is None:
            return
        self.metadata["state"] = state
        self.metadata["releasedAt"] = utc_text()
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(json.dumps(self.metadata, separators=(",", ":")) + "\n")
        self.handle.flush()
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None

    def __enter__(self) -> "GuiLease":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Optional[BaseException], traceback: Any) -> None:
        self.release("failed" if exc is not None else "released")


def measured_call(
    reporter: ProgressReporter,
    step: str,
    operation: Callable[[], T],
) -> tuple[T, int]:
    started = time.monotonic()
    reporter.emit(step, "started")
    stop_heartbeat = threading.Event()

    def heartbeat() -> None:
        while not stop_heartbeat.wait(reporter.heartbeat_seconds):
            reporter.emit(
                step,
                "running",
                stepElapsedMs=round((time.monotonic() - started) * 1000),
            )

    heartbeat_thread: Optional[threading.Thread] = None
    if reporter.enabled and reporter.heartbeat_seconds > 0:
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
    try:
        result = operation()
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        reporter.emit(step, "failed", stepElapsedMs=elapsed_ms, error=str(exc))
        raise
    finally:
        stop_heartbeat.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=0.1)
    elapsed_ms = round((time.monotonic() - started) * 1000)
    reporter.emit(step, "completed", stepElapsedMs=elapsed_ms)
    return result, elapsed_ms
