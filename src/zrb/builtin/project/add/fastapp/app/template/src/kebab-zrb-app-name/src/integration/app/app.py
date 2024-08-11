from config import (
    APP_AUTH_ACCESS_TOKEN_COOKIE_KEY,
    APP_AUTH_REFRESH_TOKEN_COOKIE_KEY,
    APP_BRAND,
    APP_CORS_ALLOW_CREDENTIALS,
    APP_CORS_ALLOW_HEADERS,
    APP_CORS_ALLOW_METHODS,
    APP_CORS_ALLOW_ORIGIN_REGEX,
    APP_CORS_ALLOW_ORIGINS,
    APP_CORS_EXPOSE_HEADERS,
    APP_CORS_MAX_AGE,
    APP_ENABLE_FRONTEND,
    APP_NAME,
    APP_TITLE,
)
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from integration.app.app_lifespan import app_lifespan
from integration.app.app_state import app_state
from integration.frontend_index import frontend_index_response
from schema.frontend_config import FrontendConfig

app = FastAPI(title=APP_NAME, lifespan=app_lifespan)

if APP_ENABLE_FRONTEND:

    @app.middleware("http")
    async def catch_all(request, call_next):
        response = await call_next(request)
        if response.status_code != 404:
            return response
        api_error = str(response.headers.get("api-error", "")).lower() == "yes"
        if api_error:
            return response
        return frontend_index_response


app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CORS_ALLOW_ORIGINS,
    allow_origin_regex=APP_CORS_ALLOW_ORIGIN_REGEX,
    allow_methods=APP_CORS_ALLOW_METHODS,
    allow_headers=APP_CORS_ALLOW_HEADERS,
    allow_credentials=APP_CORS_ALLOW_CREDENTIALS,
    expose_headers=APP_CORS_EXPOSE_HEADERS,
    max_age=APP_CORS_MAX_AGE,
)


@app.head("/liveness")
@app.get("/liveness")
def get_application_liveness_status():
    """
    Get application liveness status.
    Will return HTTP response status 200 if application is alive,
    or return 503 otherwise.
    Orchestrator like Kubernetes will restart
    any application with non-healthy liveness status.
    """
    if app_state.get_liveness():
        return JSONResponse(
            content={"app": APP_NAME, "alive": True}, status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={"message": "Service is not alive"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"api-error": "yes"},
    )


@app.head("/readiness")
@app.get("/readiness")
def get_application_readiness_status():
    """
    Get application readiness status.
    Will return HTTP response status 200 if application is ready,
    or return 503 otherwise.
    Orchestrator like Kubernetes will only send user request
    to any application with healthy readiness status.
    """
    if app_state.get_readiness():
        return JSONResponse(
            content={"app": APP_NAME, "ready": True}, status_code=status.HTTP_200_OK
        )
    return JSONResponse(
        content={"message": "Service is not ready"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"api-error": "yes"},
    )


@app.get("/api/v1/frontend/configs", response_model=FrontendConfig)
def get_configs() -> FrontendConfig:
    return FrontendConfig(
        brand=APP_BRAND,
        title=APP_TITLE,
        access_token_cookie_key=APP_AUTH_ACCESS_TOKEN_COOKIE_KEY,
        refresh_token_cookie_key=APP_AUTH_REFRESH_TOKEN_COOKIE_KEY,
    )
