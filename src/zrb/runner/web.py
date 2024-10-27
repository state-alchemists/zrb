from ..group.any_group import AnyGroup

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import json


class WebRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, root_group: AnyGroup, **kwargs):
        self.root_group = root_group
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/example':
            response = {
                'message': f"GET group = {self.root_group.get_name()}"
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        if self.path == '/example':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())

            response = {
                'received_data': data,
                'message': f"POST group = {self.root_group.get_name()}",
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404, 'Not Found')


def run_web_server(root_group: AnyGroup):
    server_address = ('', 8080)
    # Use functools.partial to bind the custom attribute
    handler_with_custom_attr = partial(WebRequestHandler, root_group=root_group)
    httpd = ThreadingHTTPServer(server_address, handler_with_custom_attr)
    print("Zrb Server running on http://localhost:8080")
    httpd.serve_forever()
