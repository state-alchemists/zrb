from fastapp_template.config import APP_MODULE_NAME_BASE_URL
from fastapp_template.module.module_template.client.any_client import BaseClient
from fastapp_template.module.module_template.service.user.usecase import user_usecase


class APIClient(
    user_usecase.as_api_client(base_url=APP_MODULE_NAME_BASE_URL), BaseClient
):
    pass
