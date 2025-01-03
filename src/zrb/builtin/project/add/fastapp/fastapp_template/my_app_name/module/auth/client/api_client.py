from my_app_name.config import APP_AUTH_BASE_URL
from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.service.permission.permission_service_factory import (
    permission_service,
)
from my_app_name.module.auth.service.user.user_service_factory import user_service


class APIClient(
    permission_service.as_api_client(base_url=APP_AUTH_BASE_URL),
    user_service.as_api_client(base_url=APP_AUTH_BASE_URL),
    AnyClient,
):
    pass
