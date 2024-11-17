from ....config import APP_AUTH_BASE_URL
from ..service.user.usecase import user_usecase
from .base_client import BaseClient


class APIClient(BaseClient, user_usecase.as_api_client(base_url=APP_AUTH_BASE_URL)):
    pass
