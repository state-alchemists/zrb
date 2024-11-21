from fastapp_template.config import APP_AUTH_BASE_URL
from fastapp_template.module.auth.client.base_client import BaseClient
from fastapp_template.module.auth.service.user.usecase import user_usecase


class APIClient(user_usecase.as_api_client(base_url=APP_AUTH_BASE_URL), BaseClient):
    pass
