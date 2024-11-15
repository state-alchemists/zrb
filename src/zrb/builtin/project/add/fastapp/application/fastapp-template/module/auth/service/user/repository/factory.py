from ......common.db_session import async_session
from ......config import APP_REPOSITORY_TYPE
from .db_repository import UserDBRepository
from .repository import UserRepository

if APP_REPOSITORY_TYPE == "db":
    user_repository: UserRepository = UserDBRepository(async_session)
else:
    user_repository: UserRepository = None
