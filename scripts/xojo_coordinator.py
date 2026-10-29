#!/usr/bin/env python3
"""Run guarded XMCP jobs; workers survive client deadlines and drain late replies."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from coordination import Coordinator, atomic_json
from xojo_runtime import DEFAULT_GUI_LEASE_FILE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--xmcp", type=Path, required=True)
    run.add_argument("--ide-app", default="/Applications/Xojo 2026 Release 3/Xojo.app")
    run.add_argument("--operation", choices=["run", "analyze"], default="run")
    run.add_argument("--completion", choices=["started", "completed"], default="completed")
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--sync-timeout", type=float, default=15)
    run.add_argument("--run-root", type=Path, default=Path("work/coordinator"))
    run.add_argument("--lease", type=Path, default=DEFAULT_GUI_LEASE_FILE)
    run.add_argument("--detach", action="store_true")
    for name in ["status", "cancel", "wait"]:
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path)
        if name == "wait":
            command.add_argument("--timeout", type=float, default=30)
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "_worker":
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, lambda *_: (args.directory / "cancel").touch())
        signal.signal(signal.SIGHUP, lambda *_: (args.directory / "cancel").touch())
        spec = json.loads((args.directory / "request.json").read_text())
        Coordinator(spec).work()
        return
    if args.command == "run":
        if args.timeout <= 0 or args.sync_timeout <= 0:
            parser.error("Timeouts must be positive")
        if not args.xmcp.is_file():
            parser.error("XMCP executable does not exist")
        run_id = uuid.uuid4().hex
        directory = (args.run_root / run_id).resolve()
        directory.mkdir(parents=True, mode=0o700)
        spec = {"run_id": run_id, "directory": str(directory), "profile": str(args.profile.resolve()),
                "xmcp": str(args.xmcp.resolve()), "ide_app": args.ide_app,
                "operation": args.operation, "completion": args.completion,
                "timeout": args.timeout, "sync_timeout": args.sync_timeout,
                "lease": str(args.lease.resolve())}
        atomic_json(directory / "request.json", spec)
        atomic_json(directory / "result.json", {"run_id": run_id, "state": "queued"})
        with (directory / "worker.log").open("ab") as output:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", str(directory)],
                stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)
        print(json.dumps({"directory": str(directory), "worker_pid": process.pid}), flush=True)
        if args.detach:
            return
        timeout = args.timeout + 5
    else:
        directory = args.directory.resolve()
        if args.command == "cancel":
            (directory / "cancel").touch()
        if args.command in ["status", "cancel"]:
            print((directory / "result.json").read_text())
            return
        timeout = args.timeout
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            result = json.loads((directory / "result.json").read_text())
            if result["state"] == "finished":
                print(json.dumps(result, indent=2))
                raise SystemExit(0 if result["outcome"] == "success" else 1)
            if result["state"] in ["draining", "quarantined"]:
                print(json.dumps(result, indent=2))
                raise SystemExit(2)
            time.sleep(0.1)
    except KeyboardInterrupt:
        (directory / "cancel").touch()
        print("Cancellation requested. Worker retains any pending connection; inspect status.", file=sys.stderr)
        raise SystemExit(2)
    print((directory / "result.json").read_text())
    raise SystemExit(2)


if __name__ == "__main__":
    main()
