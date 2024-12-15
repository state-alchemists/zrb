from fastapp_template.common.db_engine import engine
from fastapp_template.config import APP_REPOSITORY_TYPE
from fastapp_template.module.auth.service.user.repository.user_db_repository import (
    UserDBRepository,
)
from fastapp_template.module.auth.service.user.repository.user_repository import (
    UserRepository,
)

if APP_REPOSITORY_TYPE == "db":
    user_repository: UserRepository = UserDBRepository(engine)
else:
    user_repository: UserRepository = None
