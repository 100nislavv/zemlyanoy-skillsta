import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler  # noqa: E402

from _lib import handle_state  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        handle_state(self)

    def log_message(self, *_args, **_kwargs):
        pass
