from my_app_name.module.auth.service.user.repository.user_repository_factory import (
    user_repository,
)
from my_app_name.module.auth.service.user.user_usecase import UserUsecase

user_usecase = UserUsecase(user_repository=user_repository)
