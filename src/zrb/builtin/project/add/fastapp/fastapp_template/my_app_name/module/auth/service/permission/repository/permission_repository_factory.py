from my_app_name.common.db_engine_factory import db_engine
from my_app_name.config import APP_REPOSITORY_TYPE
from my_app_name.module.auth.service.permission.repository.permission_db_repository import (
    PermissionDBRepository,
)
from my_app_name.module.auth.service.permission.repository.permission_repository import (
    PermissionRepository,
)

if APP_REPOSITORY_TYPE == "db":
    permission_repository: PermissionRepository = PermissionDBRepository(db_engine)
else:
    permission_repository: PermissionRepository = None
