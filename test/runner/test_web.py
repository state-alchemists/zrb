import unittest
from unittest.mock import Mock
from io import BytesIO
import json

from zrb.runner.web_server import WebRequestHandler
from zrb import Group


class TestWebRequestHandler(unittest.TestCase):

    def setUp(self):
        self.root_group = Group(name="RootGroup")
        # Create a mock request
        self.mock_request = Mock()
        self.mock_request.makefile.return_value = BytesIO()
        # Create mock client address
        self.client_address = ("127.0.0.1", 54321)
        # Create a mock server
        self.mock_server = Mock()
        self.mock_server.server_name = "TestServer"
        self.mock_server.server_port = 8000
        # Create the handler instance
        self.handler = WebRequestHandler(
            request=self.mock_request,
            client_address=self.client_address,
            server=self.mock_server,
            root_group=self.root_group
        )
        # Mock the response methods and attributes
        self.handler.wfile = BytesIO()
        self.handler.send_response = Mock()
        self.handler.send_header = Mock()
        self.handler.end_headers = Mock()

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

    def test_do_GET_example(self):
        self.handler.path = "/example"
        self.handler.do_GET()
        # Check that a response was sent
        self.handler.send_response.assert_called_once_with(200)
        # Check that the correct headers were set
        self.handler.send_header.assert_any_call("Content-type", "application/json")
        # Check that headers were ended
        self.handler.end_headers.assert_called_once()
        # Check the content of the response
        response = json.loads(self.handler.wfile.getvalue().decode())
        expected_response = {"message": "GET group = RootGroup"}
        self.assertEqual(response, expected_response)
