"""Small CPU-bound HTTP workload for isolated local cluster experiments."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.getenv("PORT", "8080"))
WORK_ITERATIONS = int(os.getenv("WORK_ITERATIONS", "1200"))
_hits = 0
_hits_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        global _hits
        if urlparse(self.path).path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        # Deterministic CPU work gives the service a measurable saturation
        # point without relying on an external database or network service.
        digest = b"guardscale-local-workload"
        for _ in range(WORK_ITERATIONS):
            digest = hashlib.sha256(digest).digest()

        with _hits_lock:
            _hits += 1
            request_number = _hits
        body = json.dumps({"ok": True, "request": request_number,
                           "digest": digest.hex()[:12]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
