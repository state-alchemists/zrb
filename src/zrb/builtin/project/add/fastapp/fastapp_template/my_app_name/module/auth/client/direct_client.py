from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.service.user.user_usecase import user_usecase


class DirectClient(user_usecase.as_direct_client(), AnyClient):
    pass
