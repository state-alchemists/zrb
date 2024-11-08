import asyncio
import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import urlparse, parse_qs

from ..config import BANNER, SESSION_LOG_DIR, WEB_HTTP_PORT
from ..context.any_context import AnyContext
from ..context.shared_context import SharedContext
from ..group.any_group import AnyGroup
from ..session.session import Session
from ..session_state_logger.default_session_state_logger import (
    default_session_state_logger,
)
from ..task.any_task import AnyTask
from ..util.group import extract_node_from_args, get_node_path
from .web_app.group_info_ui.controller import handle_group_info_ui
from .web_app.home_page.controller import handle_home_page
from .web_app.task_ui.controller import handle_task_ui
from .web_util import node_path_to_url, start_event_loop, url_to_args

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
        super().__init__(request=request, client_address=client_address, server=server)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path in ["/", "/ui", "/ui/"]:
            handle_home_page(self, self._root_group)
        elif parsed_url.path == "/pico.min.css":
            self.send_css_response(os.path.join(_STATIC_DIR, "pico.min.css"))
        elif parsed_url.path == "/favicon-32x32.png":
            self.send_image_response(os.path.join(_STATIC_DIR, "favicon-32x32.png"))
        elif parsed_url.path.startswith("/ui/"):
            args = url_to_args(parsed_url.path[3:])
            node, node_path, residual_args = extract_node_from_args(
                self._root_group, args
            )
            url = f"/ui{node_path_to_url(node_path)}"
            if isinstance(node, AnyTask):
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=self._root_group)
                handle_task_ui(
                    self, self._root_group, node, session, url, residual_args
                )
            elif isinstance(node, AnyGroup):
                handle_group_info_ui(self, self._root_group, node, url)
            else:
                self.send_error(404, "Not Found")
        elif parsed_url.path.startswith("/api/"):
            args = url_to_args(parsed_url.path[5:])
            node, _, residual_args = extract_node_from_args(self._root_group, args)
            if isinstance(node, AnyTask) and len(residual_args) > 0:
                if residual_args[0] == "list":
                    task_path = get_node_path(self._root_group, node)
                    query_params = parse_qs(parsed_url.query)
                    self.send_session_list_json_data(task_path, query_params)
                else:
                    self.send_session_json_data(residual_args[0])
            else:
                self.send_error(404, "Not Found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path.startswith("/api/"):
            args = url_to_args(parsed_url.path[5:])
            task, _, residual_args = extract_node_from_args(self._root_group, args)
            session_name = residual_args[0] if len(residual_args) > 0 else None
            if not isinstance(task, AnyTask):
                self.send_error(404, "Not found")
            elif session_name is None:
                str_kwargs: dict[str, str] = self.read_json_request()
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=self._root_group)
                asyncio.run_coroutine_threadsafe(
                    task.async_run(session, str_kwargs=str_kwargs),
                    self._event_loop,
                )
                self.send_json_response({"session_name": session.name})
        else:
            self.send_error(404, "Not Found")

    def send_session_list_json_data(
        self, task_path: list[str], query_params: dict[str, list[Any]]
    ):
        print(query_params)
        max_start_time = datetime.datetime.now()
        if "to" in query_params and len(query_params["to"]) > 0:
            max_start_time = datetime.datetime.strptime(
                query_params["to"][0], "%Y-%m-%d %H:%M:%S"
            )
        min_start_time = max_start_time - datetime.timedelta(hours=1)
        if "from" in query_params and len(query_params["from"]) > 0:
            min_start_time = datetime.datetime.strptime(
                query_params["from"][0], "%Y-%m-%d %H:%M:%S"
            )
        page = 0
        if "page" in query_params and len(query_params["page"]) > 0:
            page = int(query_params["page"][0])
        limit = 10
        if "limit" in query_params and len(query_params["limit"]) > 0:
            limit = int(query_params["limit"][0])
        try:
            self.send_json_response(
                default_session_state_logger.list(
                    task_path,
                    min_start_time=min_start_time,
                    max_start_time=max_start_time,
                    page=page,
                    limit=limit
                )
            )
        except Exception as e:
            self.send_json_response({"error": f"{e}"}, 500)

    def send_session_json_data(self, session_name: str):
        try:
            self.send_json_response(
                default_session_state_logger.read(session_name)
            )
        except Exception as e:
            self.send_json_response({"error": f"{e}"}, 500)

    def send_json_response(self, data: Any, http_status: int = 200):
        self.send_response(http_status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(f"{json.dumps(data)}".encode())

    def send_html_response(self, html: str, http_status: int = 200):
        self.send_response(http_status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(f"{html}".encode())

    def send_css_response(self, css_path: str):
        self.send_response(200)
        self.send_header("Content-type", "text/css")
        self.end_headers()
        # If css_content is provided, send it; otherwise, you could read from a file here
        with open(css_path, "r") as f:
            css_content = f.read()
        self.wfile.write(css_content.encode())

    def send_image_response(self, image_path: str):
        try:
            with open(image_path, "rb") as img:
                self.send_response(200)
                if image_path.endswith(".png"):
                    self.send_header("Content-type", "image/png")
                elif image_path.endswith(".jpg") or image_path.endswith(".jpeg"):
                    self.send_header("Content-type", "image/jpeg")
                self.end_headers()
                self.wfile.write(img.read())
        except FileNotFoundError:
            self.send_error(404, "Image Not Found")

    def read_json_request(self) -> Any:
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        try:
            return json.loads(post_data.decode())
        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, http_status=400)
            return None


def run_web_server(ctx: AnyContext, root_group: AnyGroup, port: int = WEB_HTTP_PORT):
    server_address = ("", port)
    event_loop = asyncio.new_event_loop()
    # Use functools.partial to bind the custom attribute
    handler_with_custom_attr = partial(
        WebRequestHandler,
        root_group=root_group,
        event_loop=event_loop,
        session_dir=SESSION_LOG_DIR,
    )
    httpd = ThreadingHTTPServer(server_address, handler_with_custom_attr)
    banner_lines = BANNER.split("\n") + [
        f"Zrb Server running on http://localhost:{port}"
    ]
    for line in banner_lines:
        ctx.print(line)
    loop_thread = Thread(target=start_event_loop, args=[event_loop], daemon=True)
    loop_thread.start()
    httpd.serve_forever()
    loop_thread.join()
