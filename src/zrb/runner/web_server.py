from typing import Any
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from ..config import BANNER, WEB_HTTP_PORT, WEB_SESSION_DIR
from ..context.any_context import AnyContext
from ..group.any_group import AnyGroup
from ..task.any_task import AnyTask
from ..session.session import Session
from ..context.shared_context import SharedContext
from .web_app.home_page.controller import handle_home_page
from .web_app.group_info_ui.controller import handle_group_info_ui
from .web_app.task_ui.controller import handle_task_ui
from .web_util import (
    extract_node_from_url,
    get_session_log_dict,
    start_event_loop,
    run_task_and_snapshot_session
)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial

import asyncio
import os
import json

_DIR = os.path.dirname(__file__)
_STATIC_DIR = os.path.join(_DIR, "web_app", "static")
executor = ThreadPoolExecutor()


class WebRequestHandler(BaseHTTPRequestHandler):
    def __init__(
        self,
        request: Any,
        client_address: Any,
        server: Any,
        root_group: AnyGroup,
        event_loop: asyncio.AbstractEventLoop,
        session_dir: str,
    ):
        self._root_group = root_group
        self._event_loop = event_loop
        self._session_dir = session_dir
        super().__init__(
            request=request,
            client_address=client_address,
            server=server
        )

    def do_GET(self):
        if self.path in ["/", "/ui", "/ui/"]:
            handle_home_page(self, self._root_group)
        elif self.path == "/pico.min.css":
            self.send_css_response(os.path.join(_STATIC_DIR, "pico.min.css"))
        elif self.path == "/favicon-32x32.png":
            self.send_image_response(os.path.join(_STATIC_DIR, "favicon-32x32.png"))
        elif self.path.startswith("/ui/"):
            stripped_url = self.path[3:].rstrip("/")
            node, url, args = extract_node_from_url(self._root_group, stripped_url)
            url = f"/ui{url}/"
            if isinstance(node, AnyTask):
                handle_task_ui(self, self._root_group, node, url, args)
            elif isinstance(node, AnyGroup):
                handle_group_info_ui(self, self._root_group, node, url)
            else:
                self.send_error(404, "Not Found")
        elif self.path.startswith("/api/"):
            stripped_url = self.path[5:].rstrip("/")
            node, _, args = extract_node_from_url(self._root_group, stripped_url)
            if isinstance(node, AnyTask) and len(args) > 0:
                session_name = args[0]
                self.send_json_response(get_session_log_dict(self._session_dir, session_name))
            else:
                self.send_error(404, "Not Found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path.startswith("/api/"):
            stripped_url = self.path[5:].rstrip("/")
            task, _, args = extract_node_from_url(self._root_group, stripped_url)
            session_name = args[0] if len(args) > 0 else None
            if not isinstance(task, AnyTask):
                self.send_error(404, "Not found")
            elif session_name is None:
                str_kwargs: dict[str, str] = self.read_json_request()
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx)
                asyncio.run_coroutine_threadsafe(
                    run_task_and_snapshot_session(
                        session=session,
                        session_dir=self._session_dir,
                        task=task,
                        str_kwargs=str_kwargs
                    ), self._event_loop
                )
                self.send_json_response({"session_name": session.name})
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
        try:
            return json.loads(post_data.decode())
        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, http_status=400)
            return None


def run_web_server(ctx: AnyContext, root_group: AnyGroup, port: int = WEB_HTTP_PORT):
    server_address = ('', port)
    event_loop = asyncio.new_event_loop()
    # Use functools.partial to bind the custom attribute
    handler_with_custom_attr = partial(
        WebRequestHandler,
        root_group=root_group,
        event_loop=event_loop,
        session_dir=WEB_SESSION_DIR
    )
    httpd = ThreadingHTTPServer(server_address, handler_with_custom_attr)
    banner_lines = BANNER.split("\n") + [f"Zrb Server running on http://localhost:{port}"]
    for line in banner_lines:
        ctx.print(line)
    loop_thread = Thread(target=start_event_loop, args=[event_loop], daemon=True)
    loop_thread.start()
    httpd.serve_forever()
    loop_thread.join()
