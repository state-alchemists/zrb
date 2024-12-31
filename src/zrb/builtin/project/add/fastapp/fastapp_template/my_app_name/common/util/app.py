import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel
from starlette.types import Lifespan


def get_default_app_title(app_title: str, mode: str, modules: list[str] = []) -> str:
    if mode == "monolith":
        return app_title
    return f"{app_title} - {', '.join(modules)}"


def create_default_app_lifespan(db_engine: Engine) -> Lifespan:
    @asynccontextmanager
    async def default_app_lifespan(app: FastAPI):
        SQLModel.metadata.create_all(db_engine)
        yield

    return default_app_lifespan


def serve_static_dir(app: FastAPI, static_dir: str):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve static files
    @app.get("/static/{file_path:path}", include_in_schema=False)
    async def static_files(file_path: str):
        full_path = os.path.join(static_dir, file_path)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
        raise HTTPException(status_code=404, detail="File not found")


def serve_docs(app: FastAPI, app_title: str, favicon_url: str):
    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=app_title,
            swagger_favicon_url=favicon_url,
        )
