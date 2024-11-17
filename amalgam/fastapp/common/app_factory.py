from fastapi import FastAPI

from ..config import APP_MODE, APP_MODULES

app_title = (
    "Fastapp" if APP_MODE == "monolith" else f"Fastapp - {', '.join(APP_MODULES)}"
)

app = FastAPI(title=app_title)
