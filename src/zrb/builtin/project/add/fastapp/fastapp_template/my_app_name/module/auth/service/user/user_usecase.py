from my_app_name.common.base_usecase import BaseUsecase
from my_app_name.module.auth.service.user.repository.factory import user_repository
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class UserUsecase(BaseUsecase):
    def __init__(self, user_repository: UserRepository):
        super().__init__()
        self.user_repository = user_repository

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["get"], response_model=UserResponse
    )
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        return await self.user_repository.get_by_id(user_id)

    @BaseUsecase.route(
        "/api/v1/users", methods=["get"], response_model=list[UserResponse]
    )
    async def get_all_users(self) -> list[UserResponse]:
        return await self.user_repository.get_all()

    @BaseUsecase.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse | list[UserResponse],
    )
    async def create_user(
        self, data: UserCreateWithAudit | list[UserCreateWithAudit]
    ) -> UserResponse | list[UserResponse]:
        if isinstance(data, UserCreateWithAudit):
            return await self.user_repository.create(data)
        return await self.user_repository.create_bulk(data)

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["put"], response_model=UserResponse
    )
    async def update_user(
        self, user_id: str, data: UserUpdateWithAudit
    ) -> UserResponse:
        return await self.user_repository.update(user_id, data)

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["delete"], response_model=UserResponse
    )
    async def delete_user(self, user_id: str) -> UserResponse:
        return await self.user_repository.delete(user_id)


user_usecase = UserUsecase(user_repository=user_repository)
