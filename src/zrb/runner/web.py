from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        # Define different routes based on self.path
        if self.path == "/submit":
            self.handle_submit()
        else:
            self.send_error(404, "Not Found")

    def handle_submit(self):
        # Read the content length to determine the size of the request body
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        # Parse the JSON from the request body
        try:
            data = json.loads(post_data)
            response = {
                "status": "success",
                "message": "Data received",
                "received_data": data
            }
            self._send_json_response(200, response)
        except json.JSONDecodeError:
            response = {
                "status": "error",
                "message": "Invalid JSON format"
            }
            self._send_json_response(400, response)

    def _send_json_response(self, status_code, data):
        # Send response headers
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        # Send JSON response body
        response_body = json.dumps(data)
        self.wfile.write(response_body.encode('utf-8'))

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting server on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
