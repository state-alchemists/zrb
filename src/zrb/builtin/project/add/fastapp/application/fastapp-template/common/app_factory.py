from fastapi import FastAPI

from ..config import APP_MODE, APP_MODULES

app_title = (
    "App Name" if APP_MODE == "monolith" else f"App Name - {', '.join(APP_MODULES)}"
)

app = FastAPI(title=app_title)
