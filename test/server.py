import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"200 OK")
        elif self.path == "/kill":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Shutting down server...")
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")


def run_server():
    server_address = ("", 8080)  # Listen on all available interfaces, port 8080
    httpd = HTTPServer(server_address, RequestHandler)
    print("Starting server on port 8080...")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
