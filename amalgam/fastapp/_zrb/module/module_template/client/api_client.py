from fastapp.config import APP_MY_MODULE_NAME_BASE_URL
from fastapp.module.module_template.client.any_client import BaseClient
from fastapp.module.module_template.service.user.usecase import user_usecase


class APIClient(
    user_usecase.as_api_client(base_url=APP_MY_MODULE_NAME_BASE_URL), BaseClient
):
    pass
