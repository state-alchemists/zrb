from zrb import Group
from zrb.runner.web import WebRequestHandler
from unittest.mock import MagicMock
from io import BytesIO
import json
import unittest


class TestSimpleRequestHandler(unittest.TestCase):
    def setUp(self):
        # Helper function to create a SimpleRequestHandler instance with mocks
        self.handler = WebRequestHandler
        self.handler.wfile = BytesIO()
        self.handler.rfile = BytesIO()

        # Mocking methods from BaseHTTPRequestHandler
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.root_group = Group(name="zrb-test")

    def test_do_get_success(self):
        # Set up a GET request to the path "/example"
        self.handler.path = '/example'
        self.handler.command = 'GET'

        # Call do_GET method and capture output
        self.handler.do_GET(self.handler)
        self.handler.wfile.seek(0)  # Reset the pointer in BytesIO to read

        # Check that send_response was called with 200 status
        self.handler.send_response.assert_called_with(200)

        # Parse and check the response JSON
        response_data = json.loads(self.handler.wfile.read().decode())
        self.assertEqual(
            response_data,
            {'message': 'GET group = zrb-test'}
        )

    def test_do_post_success(self):
        # Set up a POST request to the path "/example"
        self.handler.path = '/example'
        self.handler.command = 'POST'

        # Mock headers and body content for POST request
        post_data = json.dumps({'key': 'value'}).encode()
        self.handler.rfile = BytesIO(post_data)
        self.handler.headers = {'Content-Length': str(len(post_data))}

        # Call do_POST method and capture output
        self.handler.do_POST(self.handler)
        self.handler.wfile.seek(0)

        # Check that send_response was called with 200 status
        self.handler.send_response.assert_called_with(200)

        # Parse and check the response JSON
        response_data = json.loads(self.handler.wfile.read().decode())
        self.assertEqual(
            response_data,
            {'received_data': {'key': 'value'}, 'message': 'POST group = zrb-test'}
        )
