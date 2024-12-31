from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.module.auth.service.permission.repository.permission_repository import (
    PermissionRepository,
)
from my_app_name.schema.permission import (
    Permission,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)


class PermissionDBRepository(
    BaseDBRepository[
        Permission,
        PermissionResponse,
        PermissionCreateWithAudit,
        PermissionUpdateWithAudit,
    ],
    PermissionRepository,
):
    db_model = Permission
    response_model = PermissionResponse
    create_model = PermissionCreateWithAudit
    update_model = PermissionUpdateWithAudit
    entity_name = "permission"
