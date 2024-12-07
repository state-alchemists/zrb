from fastapp.common.db_engine import engine
from fastapp.config import APP_REPOSITORY_TYPE
from fastapp.module.auth.service.user.repository.db_repository import (
    UserDBRepository,
)
from fastapp.module.auth.service.user.repository.repository import (
    UserRepository,
)

if APP_REPOSITORY_TYPE == "db":
    user_repository: UserRepository = UserDBRepository(engine)
else:
    user_repository: UserRepository = None
