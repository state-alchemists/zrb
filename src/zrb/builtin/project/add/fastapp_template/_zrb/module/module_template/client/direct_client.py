from fastapp_template.module.module_template.client.any_client import BaseClient
from fastapp_template.module.module_template.service.user.usecase import user_usecase


class DirectClient(user_usecase.as_direct_client(), BaseClient):
    pass
