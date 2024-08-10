import os

from config import APP_SRC_DIR
from fastapi.responses import HTMLResponse

index_html_path = os.path.join(APP_SRC_DIR, "frontend", "build", "index.html")
with open(index_html_path, "r") as f:
    index_html_content = f.read()

frontend_index_response = HTMLResponse(content=index_html_content, status_code=200)
