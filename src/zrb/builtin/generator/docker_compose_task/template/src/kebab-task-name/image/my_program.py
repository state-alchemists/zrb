import http.server
import socketserver
import os

MESSAGE = os.getenv('MESSAGE', 'Hello, world!')
PORT = int(os.getenv('PORT', '8000'))


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(MESSAGE.encode())


httpd = socketserver.TCPServer(("", PORT), Handler)

print(f"Serving at port {PORT}")
httpd.serve_forever()
