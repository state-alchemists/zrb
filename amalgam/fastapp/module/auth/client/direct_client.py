from fastapp.module.auth.client.base_client import BaseClient
from fastapp.module.auth.service.user.usecase import user_usecase


class DirectClient(user_usecase.as_direct_client(), BaseClient):
    pass
