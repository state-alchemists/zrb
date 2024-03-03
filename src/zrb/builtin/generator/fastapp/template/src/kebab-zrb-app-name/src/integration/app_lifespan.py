import os
from contextlib import asynccontextmanager

from config import (
    app_db_auto_migrate,
    app_enable_event_handler,
    app_enable_frontend,
    app_enable_rpc_server,
    app_src_dir,
    zrb_app_name,
)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from helper.async_task import create_task
from integration.app_state import app_state, set_not_ready_on_error
from integration.log import logger
from integration.messagebus import consumer
from integration.rpc import rpc_server
from migrate import migrate


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f"{zrb_app_name} started")
    if app_db_auto_migrate:
        await migrate()
    app_state.set_liveness(True)
    if app_enable_event_handler:
        create_task(consumer.start(), on_error=set_not_ready_on_error)
    if app_enable_rpc_server:
        create_task(rpc_server.start(), on_error=set_not_ready_on_error)
    if app_enable_frontend:
        build_path = os.path.join(app_src_dir, "frontend", "build")
        app.mount(
            path="",
            app=StaticFiles(directory=build_path, html=True),
            name="frontend-static-resources",
        )
    app_state.set_readiness(True)
    logger.info(f"{zrb_app_name} started")
    yield
    if app_enable_event_handler:
        await consumer.stop()
    logger.info(f"{zrb_app_name} closed")
