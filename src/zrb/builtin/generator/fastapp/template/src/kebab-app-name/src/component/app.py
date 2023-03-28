from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import (
    app_enable_frontend, cors_allow_credentials, cors_allow_headers,
    cors_allow_methods, cors_allow_origin_regex, cors_allow_origins,
    cors_expose_headers, cors_max_age
)
from component.app_state import app_state
from starlette.requests import Request
from starlette.responses import FileResponse
import os

app = FastAPI()

if app_enable_frontend:
    @app.middleware("http")
    async def static_file_middleware(request: Request, call_next):
        frontend_build_path = os.path.join('frontend', 'build')
        request_url = request.url.path.strip('/')
        resource_path = os.path.join(frontend_build_path, request_url)
        if os.path.isfile(resource_path):
            # Resource exists
            return FileResponse(resource_path)
        if os.path.isdir(resource_path):
            # Resource is directory
            file_path = os.path.join(resource_path, 'index.html')
            if os.path.isfile(file_path):
                # Index.html is exist within the directory
                return FileResponse(file_path)
        # Nothing exists, this must be served programmatically
        response = await call_next(request)
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
