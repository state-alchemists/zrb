from contextlib import asynccontextmanager

from fastapi import FastAPI
from my_app_name.common.db_engine import engine
from my_app_name.config import APP_MODE, APP_MODULES
from sqlmodel import SQLModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app_title = (
    "My App Name"
    if APP_MODE == "monolith"
    else f"My App Name - {', '.join(APP_MODULES)}"
)
app = FastAPI(title=app_title, lifespan=lifespan)
