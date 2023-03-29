from fastapi.responses import HTMLResponse
import os

frontend_index_path = os.path.join('frontend', 'build', 'index.html')
with open(frontend_index_path, "r") as f:
    frontend_index_content = f.read()
frontend_index_response = HTMLResponse(
    content=frontend_index_content, status_code=200
)
