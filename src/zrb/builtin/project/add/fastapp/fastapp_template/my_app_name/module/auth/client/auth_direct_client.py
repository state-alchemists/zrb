from my_app_name.module.auth.client.auth_client import AuthClient
from my_app_name.module.auth.service.permission.permission_service_factory import (
    permission_service,
)
from my_app_name.module.auth.service.role.role_service_factory import role_service
from my_app_name.module.auth.service.user.user_service_factory import user_service


class AuthDirectClient(
    permission_service.as_direct_client(),
    role_service.as_direct_client(),
    user_service.as_direct_client(),
    AuthClient,
):
    pass
