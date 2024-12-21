from my_app_name.config import APP_AUTH_BASE_URL
from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.service.user.user_usecase_factory import user_usecase


class APIClient(user_usecase.as_api_client(base_url=APP_AUTH_BASE_URL), AnyClient):
    pass
