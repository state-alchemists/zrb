from my_app_name.module.auth.service.user.repository.user_repository_factory import (
    user_repository,
)
from my_app_name.module.auth.service.user.user_service import UserService

user_service = UserService(user_repository=user_repository)
