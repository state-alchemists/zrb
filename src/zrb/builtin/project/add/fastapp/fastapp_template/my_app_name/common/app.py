import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from my_app_name.common.db_engine import engine
from my_app_name.config import (
    APP_GATEWAY_FAVICON_PATH,
    APP_GATEWAY_TITLE,
    APP_GATEWAY_VIEW_PATH,
    APP_MODE,
    APP_MODULES,
    APP_VERSION,
)
from sqlmodel import SQLModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app_title = (
    APP_GATEWAY_TITLE
    if APP_MODE == "monolith"
    else f"{APP_GATEWAY_TITLE} - {', '.join(APP_MODULES)}"
)
app = FastAPI(
    title=app_title,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None,
)

_STATIC_DIR = os.path.join(APP_GATEWAY_VIEW_PATH, "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# Serve static files
@app.get("/static/{file_path:path}", include_in_schema=False)
async def static_files(file_path: str):
    full_path = os.path.join(_STATIC_DIR, file_path)
    if os.path.isfile(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app_title,
        swagger_favicon_url=APP_GATEWAY_FAVICON_PATH,
    )
