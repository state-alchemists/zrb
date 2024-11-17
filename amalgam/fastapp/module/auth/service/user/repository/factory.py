from ......common.db_session_maker_factory import session_maker
from ......config import APP_REPOSITORY_TYPE
from .db_repository import UserDBRepository
from .repository import UserRepository

if APP_REPOSITORY_TYPE == "db":
    user_repository: UserRepository = UserDBRepository(session_maker)
else:
    user_repository: UserRepository = None
