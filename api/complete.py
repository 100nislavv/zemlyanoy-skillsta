from http.server import BaseHTTPRequestHandler

from _lib import handle_toggle


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        handle_toggle(self, completed=True)

    def log_message(self, *_args, **_kwargs):
        pass
