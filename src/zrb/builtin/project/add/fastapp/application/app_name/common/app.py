from contextlib import asynccontextmanager

from common.db_engine import engine
from config import APP_MODE, APP_MODULES
from fastapi import FastAPI
from sqlmodel import SQLModel

app_title = (
    "App Name" if APP_MODE == "monolith" else f"App Name - {', '.join(APP_MODULES)}"
)

app = FastAPI(title=app_title)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield
