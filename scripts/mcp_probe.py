#!/usr/bin/env python3
"""Probe an explicitly selected stdio MCP server; retain JSON-RPC evidence.

Input is a JSON list of {method, params}. This does not register an MCP server
in the user's client configuration. Serialize IDE operations under the GUI lease.
"""
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import time


def probe(command, requests, timeout):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffer = b""
    records = []
    stderr = []

    def send(value):
        process.stdin.write((json.dumps(value) + "\n").encode())
        process.stdin.flush()

    def exchange(request):
        nonlocal buffer
        start = time.monotonic()
        send(request)
        while time.monotonic() - start < timeout:
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                response = json.loads(line)
                if response.get("id") == request["id"]:
                    return {"request": request, "response": response,
                            "elapsedSeconds": round(time.monotonic() - start, 3)}
            for key, _ in selector.select(min(1, timeout - (time.monotonic() - start))):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    if key.data == "stdout":
                        raise RuntimeError("Server stdout closed before response")
                elif key.data == "stdout":
                    buffer += chunk
                else:
                    stderr.append(chunk.decode(errors="replace"))
        raise TimeoutError(f"No MCP response for request {request['id']} within {timeout}s")

    try:
        records.append(exchange({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "xojo-automation-evaluation", "version": "0.1.0"}}}))
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        for index, request in enumerate(requests, 2):
            records.append(exchange({"jsonrpc": "2.0", "id": index, **request}))
            print(json.dumps({"id": index, "method": request["method"],
                              "elapsedSeconds": records[-1]["elapsedSeconds"]}), flush=True)
        return {"command": command, "records": records, "stderr": "".join(stderr),
                "status": "complete"}
    except Exception as error:
        return {"command": command, "records": records, "stderr": "".join(stderr),
                "status": "failed", "error": f"{type(error).__name__}: {error}"}
    finally:
        # XMCP documents that stdin EOF alone does not reliably exit its loop.
        # Callers must not use a short timeout for an IDE build still in progress.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        selector.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.timeout <= 0:
        parser.error("Specify a server command and positive timeout")
    report = probe(command, json.loads(args.requests.read_text()), args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
