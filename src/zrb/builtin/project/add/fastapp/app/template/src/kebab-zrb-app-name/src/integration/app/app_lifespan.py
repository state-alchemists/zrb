import os
from contextlib import asynccontextmanager

from config import (
    APP_DB_AUTO_MIGRATE,
    APP_ENABLE_EVENT_HANDLER,
    APP_ENABLE_FRONTEND,
    APP_ENABLE_RPC_SERVER,
    APP_NAME,
    APP_SRC_DIR,
)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from helper.async_task import create_task
from integration.app.app_state import app_state, set_not_ready_on_error
from integration.log import logger
from integration.messagebus import consumer
from integration.rpc import rpc_server
from migrate import migrate


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f"{APP_NAME} started")
    if APP_DB_AUTO_MIGRATE:
        await migrate()
    app_state.set_liveness(True)
    if APP_ENABLE_EVENT_HANDLER:
        create_task(consumer.start(), on_error=set_not_ready_on_error)
    if APP_ENABLE_RPC_SERVER:
        create_task(rpc_server.start(), on_error=set_not_ready_on_error)
    if APP_ENABLE_FRONTEND:
        build_path = os.path.join(APP_SRC_DIR, "frontend", "build")
        app.mount(
            path="",
            app=StaticFiles(directory=build_path, html=True),
            name="frontend-static-resources",
        )
    app_state.set_readiness(True)
    logger.info(f"{APP_NAME} started")
    yield
    if APP_ENABLE_EVENT_HANDLER:
        await consumer.stop()
    logger.info(f"{APP_NAME} closed")
