from fastapp.config import APP_AUTH_BASE_URL
from fastapp.module.auth.client.any_client import BaseClient
from fastapp.module.auth.service.user.usecase import user_usecase


class APIClient(user_usecase.as_api_client(base_url=APP_AUTH_BASE_URL), BaseClient):
    pass
