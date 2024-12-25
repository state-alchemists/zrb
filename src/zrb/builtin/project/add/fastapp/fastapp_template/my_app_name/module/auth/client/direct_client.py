from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.service.user.user_service_factory import user_service


class DirectClient(user_service.as_direct_client(), AnyClient):
    pass
