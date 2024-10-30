from typing import Any
from .util import extract_node_from_url
from ..config import BANNER, HTTP_PORT
from ..context.any_context import AnyContext
from ..group.any_group import AnyGroup
from ..task.any_task import AnyTask
from .web_app.home_page.controller import handle_home_page
from .web_app.group_info_ui.controller import handle_group_info_ui
from .web_app.task_ui.controller import handle_task_ui

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import os
import json

_DIR = os.path.dirname(__file__)
_STATIC_DIR = os.path.join(_DIR, "web_app", "static")


class WebRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, root_group: AnyGroup, **kwargs):
        self.root_group = root_group
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path in ["/", "/ui", "/ui/"]:
            handle_home_page(self, self.root_group)
        elif self.path == "/pico.classless.min.css":
            self.send_css_response(os.path.join(_STATIC_DIR, "pico.classless.min.css"))
        elif self.path == "/favicon-32x32.png":
            self.send_image_response(os.path.join(_STATIC_DIR, "favicon-32x32.png"))
        elif self.path.startswith("/ui/"):
            stripped_url = self.path[3:].rstrip("/")
            node, url = extract_node_from_url(self.root_group, stripped_url)
            url = f"/ui{url}/"
            if isinstance(node, AnyTask):
                handle_task_ui(self, self.root_group, node, url)
            elif isinstance(node, AnyGroup):
                handle_group_info_ui(self, self.root_group, node, url)
            else:
                self.send_error(404, 'Not Found')
        elif self.path == '/example':
            response = {'message': f"GET group = {self.root_group.name}"}
            self.send_json_response(response)
        else:
            node, url = extract_node_from_url(self.root_group, self.path)
            if isinstance(node, AnyTask):
                self._handle_get_task(node)
            elif isinstance(node, AnyGroup):
                self._handle_get_group(node)
            else:
                self.send_error(404, 'Not Found')

    def _handle_get_task(self, task: AnyTask):
        self.send_html_response(f"Task: {task.name}")

    def _handle_get_group(self, group: AnyGroup):
        self.send_html_response(f"Group: {group.name}")

    def do_POST(self):
        if self.path == '/example':
            data = self.read_json_request()
            response = {
                'received_data': data,
                'message': f"POST group = {self.root_group.name}",
            }
            self.send_json_response(response)
        else:
            self.send_error(404, 'Not Found')

    def send_json_response(self, data: Any, http_status: int = 200):
        self.send_response(http_status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(f"{json.dumps(data)}".encode())

    def send_html_response(self, html: str, http_status: int = 200):
        self.send_response(http_status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"{html}".encode())

    def send_css_response(self, css_path: str):
        self.send_response(200)
        self.send_header('Content-type', 'text/css')
        self.end_headers()
        # If css_content is provided, send it; otherwise, you could read from a file here
        with open(css_path, "r") as f:
            css_content = f.read()
        self.wfile.write(css_content.encode())

    def send_image_response(self, image_path: str):
        try:
            with open(image_path, 'rb') as img:
                self.send_response(200)
                if image_path.endswith('.png'):
                    self.send_header('Content-type', 'image/png')
                elif image_path.endswith('.jpg') or image_path.endswith('.jpeg'):
                    self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                self.wfile.write(img.read())
        except FileNotFoundError:
            self.send_error(404, 'Image Not Found')

    def read_json_request(self) -> Any:
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode())


def run_web_server(ctx: AnyContext, root_group: AnyGroup, port: int = HTTP_PORT):
    server_address = ('', port)
    # Use functools.partial to bind the custom attribute
    handler_with_custom_attr = partial(WebRequestHandler, root_group=root_group)
    httpd = ThreadingHTTPServer(server_address, handler_with_custom_attr)
    banner_lines = BANNER.split("\n") + [f"Zrb Server running on http://localhost:{port}"]
    for line in banner_lines:
        ctx.print(line)
    httpd.serve_forever()
