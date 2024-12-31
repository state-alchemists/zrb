from my_app_name.common.db_engine_factory import db_engine
from my_app_name.config import APP_REPOSITORY_TYPE
from my_app_name.module.auth.service.role.repository.role_db_repository import (
    RoleDBRepository,
)
from my_app_name.module.auth.service.role.repository.role_repository import (
    RoleRepository,
)

if APP_REPOSITORY_TYPE == "db":
    role_repository: RoleRepository = RoleDBRepository(db_engine)
else:
    role_repository: RoleRepository = None
