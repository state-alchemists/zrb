from fastapp_template.module.auth.client.any_client import BaseClient
from fastapp_template.module.auth.service.user.user_usecase import user_usecase


class DirectClient(user_usecase.as_direct_client(), BaseClient):
    pass
