import os

from config import app_src_dir
from fastapi.responses import HTMLResponse

index_html_path = os.path.join(app_src_dir, "frontend", "build", "index.html")
with open(index_html_path, "r") as f:
    index_html_content = f.read()

frontend_index_response = HTMLResponse(content=index_html_content, status_code=200)
