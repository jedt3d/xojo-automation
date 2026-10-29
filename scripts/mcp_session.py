"""Persistent stdio session. Deadlines are observed by the owner, never by closing IPC."""
import json
import os
import selectors
import subprocess
import time


class Session:
    def __init__(self, command, journal, tick):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
        self.journal = journal
        self.tick = tick
        self.buffer = b""
        self.serial = 0
        self.pending = False

    def send(self, value):
        self.process.stdin.write((json.dumps(value) + "\n").encode())
        self.process.stdin.flush()

    def request(self, method, params=None):
        if self.pending:
            raise RuntimeError("A request is already in flight")
        self.serial += 1
        request = {"jsonrpc": "2.0", "id": self.serial, "method": method,
                   "params": params or {}}
        self.pending = True
        self.journal({"request": request})
        start = time.monotonic()
        self.send(request)
        while True:
            self.tick(True)
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                response = json.loads(line)
                self.journal({"response": response, "elapsedSeconds": time.monotonic() - start})
                if response.get("id") == self.serial:
                    self.pending = False
                    return response
            for key, _ in self.selector.select(0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    self.selector.unregister(key.fileobj)
                    if key.data == "stdout":
                        # With no child, it no longer owns a live IPC connection.
                        self.process.wait(timeout=5)
                        self.pending = False
                        raise RuntimeError("XMCP exited before the matching response")
                elif key.data == "stdout":
                    self.buffer += chunk
                else:
                    self.journal({"stderr": chunk.decode(errors="replace")})

    def close(self):
        if self.pending:
            raise RuntimeError("Refusing to close XMCP while a request may own IDE IPC")
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.selector.close()
        for stream in [self.process.stdin, self.process.stdout, self.process.stderr]:
            stream.close()


def tool_text(response):
    if "error" in response:
        raise RuntimeError("MCP error: " + json.dumps(response["error"]))
    result = response.get("result", {})
    return "\n".join(block.get("text", "") for block in result.get("content", [])
                     if block.get("type") == "text"), bool(result.get("isError"))
