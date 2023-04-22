from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import (
    app_name, app_enable_frontend, cors_allow_credentials, cors_allow_headers,
    cors_allow_methods, cors_allow_origin_regex, cors_allow_origins,
    cors_expose_headers, cors_max_age
)
from component.app_lifespan import app_state
from component.app_lifespan import app_lifespan
from component.frontend_index import frontend_index_response

app = FastAPI(title=app_name, lifespan=app_lifespan)

if app_enable_frontend:
    @app.middleware("http")
    async def catch_all(request, call_next):
        response = await call_next(request)
        if response.status_code != 404:
            return response
        api_error = str(response.headers.get('api-error', '')).lower() == 'yes'
        if api_error:
            return response
        return frontend_index_response


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
def get_application_liveness_status():
    '''
    Get application liveness status.
    Will return HTTP response status 200 if application is alive,
    or return 503 otherwise.
    Orchestrator like Kubernetes will restart
    any application with non-healthy liveness status.
    '''
    if app_state.get_liveness():
        return JSONResponse(
            content={'app': app_name, 'alive': True},
            status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={'message': 'Service is not alive'},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={'api-error': 'yes'}
    )


@app.head('/readiness')
@app.get('/readiness')
def get_application_readiness_status():
    '''
    Get application readiness status.
    Will return HTTP response status 200 if application is ready,
    or return 503 otherwise.
    Orchestrator like Kubernetes will only send user request
    to any application with healthy readiness status.
    '''
    if app_state.get_readiness():
        return JSONResponse(
            content={'app': app_name, 'ready': True},
            status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={'message': 'Service is not ready'},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={'api-error': 'yes'}
    )
