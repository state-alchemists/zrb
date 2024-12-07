from fastapp.module.anu.client.any_client import BaseClient
from fastapp.module.anu.service.user.usecase import user_usecase


class DirectClient(user_usecase.as_direct_client(), BaseClient):
    pass
