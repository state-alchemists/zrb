from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from config import (
    app_name, app_enable_message_consumer, app_enable_frontend,
)
from component.app_state import app_state, set_not_ready_on_error
from component.messagebus import consumer
from component.log import logger
from helper.async_task import create_task
from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f'{app_name} started')
    app_state.set_liveness(True)
    if app_enable_message_consumer:
        create_task(consumer.start(), on_error=set_not_ready_on_error)
    if app_enable_frontend:
        build_path = os.path.join('frontend', 'build')
        app.mount(
            path='',
            app=StaticFiles(directory=build_path, html=True),
            name='frontend'
        )
    app_state.set_readiness(True)
    yield
    if app_enable_message_consumer:
        await consumer.stop()
    logger.info(f'{app_name} closed')
