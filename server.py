#!/usr/bin/env python3
"""Local development server.

Mirrors the Vercel deployment: serves static files plus the same /api routes
implemented in api/_lib.py. Production runs each handler as a separate
serverless function; locally we route them through one process.
"""
import http.server
import os
import socketserver
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "api"))

import _lib  # noqa: E402

PORT = 3456


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/state":
            return _lib.handle_state(self)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/complete":
            return _lib.handle_toggle(self, completed=True)
        if path == "/api/uncomplete":
            return _lib.handle_toggle(self, completed=False)
        self.send_error(404)


class ReusableServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ReusableServer(("", PORT), Handler) as httpd:
        print(f"Serving challenges app on :{PORT}")
        httpd.serve_forever()
