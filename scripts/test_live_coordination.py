#!/usr/bin/env python3
"""Deliberate-error suite for the repository's disposable coordinated Console fixture.

Open that fixture in Xojo 2026r3 first. This never opens/closes unrelated projects.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import os
import signal
import subprocess
import sys
import time

import coordination as c

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xmcp", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--case", action="append", help="Run only a named case (repeatable)")
    args = parser.parse_args()
    fixture = ROOT / "fixtures/coordinated-smoke"
    app = fixture / "App.xojo_code"
    baseline = app.read_bytes()
    assert c.stamp_value(baseline) == "UNSET", "Fixture already has an in-flight stamp"
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    wrong = ROOT / "work/milestone2-wrong-project"
    if not wrong.exists():
        shutil.copytree(fixture, wrong, ignore=shutil.ignore_patterns("*.debug", "Builds - *", "*.xojo_uistate"))
    cases = [
        ("wrong-project", "baseline", "identity_mismatch", {}),
        ("baseline", "baseline", "success", {}),
        ("compile-error", "baseline", "compile_error", {}),
        ("edited-source-and-stale-event", "revision-two", "success", {"stale": True}),
        ("runtime-error", "runtime-error", "runtime_error", {}),
        ("hold-and-stop", "hold", "success", {"completion": "started"}),
        ("cancel-running-app", "hold", "cancelled", {"cancel": True}),
        ("signal-worker-cancellation", "hold", "cancelled", {"cancel_signal": True}),
        ("client-deadline", "hold", "deadline_exceeded", {"timeout": 8, "foreground": True}),
        ("runtime-deadline", "hold", "deadline_exceeded", {"timeout": 30, "foreground": True}),
    ]
    if args.case:
        if set(args.case) - {case[0] for case in cases}:
            parser.error("Unknown case name")
        cases = [case for case in cases if case[0] in args.case]
    records = []
    current = None
    try:
        for name, scenario, expected, options in cases:
            source = baseline.replace(b'Default = \\"baseline"', ('Default = \\"' + scenario + '"').encode())
            if name == "compile-error":
                source = source.replace(b'#Pragma Unused args', b'#Pragma Unused args\n      Var invalid As MissingMilestoneType')
            app.write_bytes(source)
            profile = wrong / "coordination.json" if name == "wrong-project" else fixture / "coordination.json"
            command = [sys.executable, str(ROOT / "scripts/xojo_coordinator.py"), "run", "--profile", str(profile),
                       "--xmcp", str(args.xmcp.resolve()), "--run-root", str(ROOT / "work/milestone2"),
                       "--timeout", str(options.get("timeout", 120)),
                       "--completion", options.get("completion", "completed")]
            if not options.get("foreground"):
                command.append("--detach")
            client = subprocess.run(command, capture_output=True, text=True,
                                    timeout=max(30, options.get("timeout", 0) + 15))
            client_exit_at = datetime.now(timezone.utc).isoformat()
            first = json.loads(client.stdout.splitlines()[0])
            current = Path(first["directory"])
            if options.get("stale"):
                with (current / "runtime.jsonl").open("x") as out:
                    out.write(json.dumps({"event": "completed", "run_id": "stale-run", "revision": "stale-revision"}) + "\n")
            deadline = time.monotonic() + 180
            cancelled = False
            observed_states = []
            while time.monotonic() < deadline:
                result = json.loads((current / "result.json").read_text())
                if not observed_states or observed_states[-1] != result["state"]:
                    observed_states.append(result["state"])
                runtime = current / "runtime.jsonl"
                if (options.get("cancel") or options.get("cancel_signal")) and runtime.exists() and not cancelled and '"started"' in runtime.read_text():
                    if options.get("cancel_signal"):
                        os.kill(first["worker_pid"], signal.SIGTERM)
                    else:
                        (current / "cancel").touch()
                    cancelled = True
                if result["state"] == "finished":
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Worker still active; do not alter fixture: " + str(current))
            destination = evidence / name
            shutil.copytree(current, destination)
            (destination / "case-source.xojo_code").write_bytes(source)
            observed_processes = c.debug_processes(c.load_profile(fixture / "coordination.json")["executable"])
            case = {"name": name, "expected": expected, "actual": result["outcome"],
                    "client_exit_code": client.returncode, "client_exit_at": client_exit_at,
                    "states_observed": observed_states, "remaining_debug_processes": observed_processes,
                    "result": str(destination.relative_to(evidence) / "result.json")}
            if options.get("foreground"):
                case["client_stdout_after_job_header"] = client.stdout.splitlines()[1:]
            records.append(case)
            c.atomic_json(evidence / "cases.json", records)
            print(json.dumps(case), flush=True)
            assert result["outcome"] == expected, case
            assert result["cleanup_errors"] == [], result["cleanup_errors"]
            assert result["lease_released"], result
            assert not observed_processes, observed_processes
            if name != "wrong-project":
                if expected != "deadline_exceeded":
                    assert result["synchronized"]
                assert app.read_bytes() == source, "Original source not restored"
            if options.get("stale"):
                assert result["rejected_events"]
                assert result["runtime_events"][-1]["message"] == "revision-two"
            if name == "runtime-deadline":
                assert result["synchronized"]
                assert any(event["event"] == "started" for event in result["runtime_events"])
                assert result["owned_processes"], "Deadline case never captured a live process"
            if name == "hold-and-stop":
                assert result["owned_processes"], "No live process captured"
            current = None
    finally:
        if current is not None and json.loads((current / "result.json").read_text())["state"] != "finished":
            (current / "cancel").touch()
            print("Worker still owns fixture; inspect before restoring: " + str(current), file=sys.stderr)
        else:
            app.write_bytes(baseline)


if __name__ == "__main__":
    main()
