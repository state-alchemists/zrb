from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapp.common.db_engine import engine
from fastapp.config import APP_MODE, APP_MODULES
from sqlmodel import SQLModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app_title = (
    "Fastapp" if APP_MODE == "monolith" else f"Fastapp - {', '.join(APP_MODULES)}"
)
app = FastAPI(title=app_title, lifespan=lifespan)
