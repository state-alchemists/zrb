from fastapp.config import APP_ANU_BASE_URL
from fastapp.module.anu.client.any_client import BaseClient
from fastapp.module.anu.service.user.usecase import user_usecase


class APIClient(
    user_usecase.as_api_client(base_url=APP_ANU_BASE_URL), BaseClient
):
    pass
