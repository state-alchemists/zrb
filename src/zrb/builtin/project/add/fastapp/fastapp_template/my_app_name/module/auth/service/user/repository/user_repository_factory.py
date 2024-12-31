from my_app_name.common.db_engine_factory import db_engine
from my_app_name.config import APP_REPOSITORY_TYPE
from my_app_name.module.auth.service.user.repository.user_db_repository import (
    UserDBRepository,
)
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)

if APP_REPOSITORY_TYPE == "db":
    user_repository: UserRepository = UserDBRepository(db_engine)
else:
    user_repository: UserRepository = None
