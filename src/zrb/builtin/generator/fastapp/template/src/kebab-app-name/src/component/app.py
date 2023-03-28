from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from config import (
    app_name, app_enable_message_consumer, app_enable_frontend,
    cors_allow_credentials, cors_allow_headers, cors_allow_methods,
    cors_allow_origin_regex, cors_allow_origins, cors_expose_headers,
    cors_max_age
)
from component.app_state import app_state, set_not_ready_on_error
from component.messagebus import consumer
from component.log import logger
from helper.async_task import create_task
from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'{app_name} started')
    app_state.set_liveness(True)
    if app_enable_message_consumer:
        create_task(consumer.run(), on_error=set_not_ready_on_error)
    if app_enable_frontend:
        build_path = os.path.join('frontend', 'build')
        app.mount(
            path='',
            app=StaticFiles(directory=build_path, html=True),
            name='frontend'
        )
    app_state.set_readiness(True)
    yield
    logger.info(f'{app_name} closed')

app = FastAPI(lifespan=lifespan)

if app_enable_frontend:
    @app.middleware("http")
    async def catch_all(request, call_next):
        response = await call_next(request)
        if response.status_code == 404:
            # This route will match any requests that haven't been handled yet
            index_path = os.path.join('frontend', 'build', 'index.html')
            with open(index_path, "r") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content, status_code=200)
        return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_methods=cors_allow_methods,
    allow_headers=cors_allow_headers,
    allow_credentials=cors_allow_credentials,
    expose_headers=cors_expose_headers,
    max_age=cors_max_age,
)


@app.head('/liveness')
@app.get('/liveness')
def handle_liveness():
    if app_state.get_liveness():
        return JSONResponse(
            content={'message': 'Service is alive'},
            status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={'message': 'Service is not alive'},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )


@app.head('/readiness')
@app.get('/readiness')
def handle_readiness():
    if app_state.get_readiness():
        return JSONResponse(
            content={'message': 'Service is ready'},
            status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={'message': 'Service is not ready'},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )
