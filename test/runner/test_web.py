import asyncio
import os
import unittest
from io import BytesIO
from threading import Thread
from unittest.mock import Mock

from zrb import Group
from zrb.runner.web_server import WebRequestHandler

_DIR = os.path.dirname(__file__)
_SESSION_DIR = os.path.join(_DIR, "test-generated-session")


def _start_event_loop(event_loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()


class TestWebRequestHandler(unittest.TestCase):

    def setUp(self):
        self.root_group = Group(name="RootGroup")
        self.coros = []
        # Create a mock request
        self.mock_request = Mock()
        self.mock_request.makefile.return_value = BytesIO()
        # Create mock client address
        self.client_address = ("127.0.0.1", 54321)
        # Create and start event_loop in a loop_thread
        self.event_loop = asyncio.new_event_loop()
        self.loop_thread = Thread(
            target=_start_event_loop, args=[self.event_loop], daemon=True
        )
        self.loop_thread.start()  # we will join the thread on tearDown
        # Create a mock server
        self.mock_server = Mock()
        self.mock_server.server_name = "TestServer"
        self.mock_server.server_port = 8000
        # Create the handler instance
        self.handler = WebRequestHandler(
            request=self.mock_request,
            client_address=self.client_address,
            server=self.mock_server,
            root_group=self.root_group,
            event_loop=self.event_loop,
            session_dir=_SESSION_DIR,
            coros=self.coros,
        )
        # Mock the response methods and attributes
        self.handler.wfile = BytesIO()
        self.handler.rfile = BytesIO()
        self.handler.send_response = Mock()
        self.handler.send_header = Mock()
        self.handler.end_headers = Mock()

    def tearDown(self):
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        self.loop_thread.join()

    def test_do_GET_home_page(self):
        self.handler.path = "/"
        self.handler.do_GET()
        # Check that a response was sent
        self.handler.send_response.assert_called_once_with(200)
        # Check that the correct headers were set
        self.handler.send_header.assert_any_call("Content-type", "text/html")
        # Check that headers were ended
        self.handler.end_headers.assert_called_once()
        # Check the content of the response
        response: str = self.handler.wfile.getvalue().decode()
        self.assertTrue("RootGroup" in response)
