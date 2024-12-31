import os

from fastapi import FastAPI
from my_app_name.common.db_engine_factory import db_engine
from my_app_name.common.util.app import (
    create_default_app_lifespan,
    get_default_app_title,
    serve_docs,
    serve_static_dir,
)
from my_app_name.config import (
    APP_GATEWAY_FAVICON_PATH,
    APP_GATEWAY_TITLE,
    APP_GATEWAY_VIEW_PATH,
    APP_MODE,
    APP_MODULES,
    APP_VERSION,
)

app_title = get_default_app_title(APP_GATEWAY_TITLE, mode=APP_MODE, modules=APP_MODULES)
app = FastAPI(
    title=app_title,
    version=APP_VERSION,
    lifespan=create_default_app_lifespan(db_engine),
    docs_url=None,
)

serve_static_dir(app, os.path.join(APP_GATEWAY_VIEW_PATH, "static"))
serve_docs(app, app_title=app_title, favicon_url=APP_GATEWAY_FAVICON_PATH)
