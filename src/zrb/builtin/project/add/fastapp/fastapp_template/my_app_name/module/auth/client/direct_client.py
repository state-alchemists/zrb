from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.service.permission.permission_service_factory import (
    permission_service,
)
from my_app_name.module.auth.service.role.role_service_factory import role_service
from my_app_name.module.auth.service.user.user_service_factory import user_service


class DirectClient(
    permission_service.as_direct_client(),
    role_service.as_direct_client(),
    user_service.as_direct_client(),
    AnyClient,
):
    pass
