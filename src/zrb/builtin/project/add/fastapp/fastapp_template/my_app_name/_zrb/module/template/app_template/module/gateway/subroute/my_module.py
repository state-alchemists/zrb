from typing import Annotated

from fastapi import Depends, FastAPI
from my_app_name.module.gateway.util.auth import get_current_user
from my_app_name.schema.user import AuthUserResponse


def serve_my_module_route(app: FastAPI):
    """
    Serving routes for my_module
    """
