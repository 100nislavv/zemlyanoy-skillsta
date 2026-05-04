from http.server import BaseHTTPRequestHandler

from _lib import handle_state


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        handle_state(self)

    def log_message(self, *_args, **_kwargs):
        pass
