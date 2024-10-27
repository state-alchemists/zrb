from .util import InvalidCommandError, extract_node_from_url
from ..config import BANNER, HTTP_PORT
from ..context.any_context import AnyContext
from ..group.any_group import AnyGroup
from ..task.any_task import AnyTask

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import json


class WebRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, root_group: AnyGroup, **kwargs):
        self.root_group = root_group
        self.cok = "anu"
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/example':
            response = {
                'message': f"GET group = {self.root_group.name}"
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            node, url = extract_node_from_url(self.root_group, self.path)
            if isinstance(node, AnyTask):
                self._handle_get_task(node)
            elif isinstance(node, AnyGroup):
                self._handle_get_group(node)
            else:
                self.send_error(404, 'Not Found')

    def _handle_get_task(self, task: AnyTask):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Task: {task.name}".encode())

    def _handle_get_group(self, group: AnyGroup):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Group: {group.name}".encode())

    def do_POST(self):
        if self.path == '/example':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())

            response = {
                'received_data': data,
                'message': f"POST group = {self.root_group.name}",
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404, 'Not Found')


def run_web_server(ctx: AnyContext, root_group: AnyGroup, port: int = HTTP_PORT):
    server_address = ('', port)
    # Use functools.partial to bind the custom attribute
    handler_with_custom_attr = partial(WebRequestHandler, root_group=root_group)
    httpd = ThreadingHTTPServer(server_address, handler_with_custom_attr)
    banner_lines = BANNER.split("\n") + [f"Zrb Server running on http://localhost:{port}"]
    for line in banner_lines:
        ctx.print(line)
    httpd.serve_forever()
