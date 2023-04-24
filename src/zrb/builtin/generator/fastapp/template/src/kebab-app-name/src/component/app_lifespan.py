from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from config import (
    app_name, app_enable_message_consumer, app_enable_rpc_server,
    app_enable_frontend, app_db_auto_migrate
)
from config import app_src_dir
from migrate import migrate
from component.app_state import app_state, set_not_ready_on_error
from component.messagebus import consumer
from component.rpc import rpc_server
from component.log import logger
from helper.async_task import create_task
from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f'{app_name} started')
    if app_db_auto_migrate:
        await migrate()
    app_state.set_liveness(True)
    if app_enable_message_consumer:
        create_task(consumer.start(), on_error=set_not_ready_on_error)
    if app_enable_rpc_server:
        create_task(rpc_server.start(), on_error=set_not_ready_on_error)
    if app_enable_frontend:
        build_path = os.path.join(app_src_dir, 'frontend', 'build')
        app.mount(
            path='',
            app=StaticFiles(directory=build_path, html=True),
            name='frontend-static-resources'
        )
    app_state.set_readiness(True)
    logger.info(f'{app_name} started')
    yield
    if app_enable_message_consumer:
        await consumer.stop()
    logger.info(f'{app_name} closed')
