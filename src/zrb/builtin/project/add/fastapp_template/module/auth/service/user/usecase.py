from fastapp_template.common.usecase import BaseUsecase
from fastapp_template.module.auth.service.user.repository.factory import user_repository
from fastapp_template.schema.user import UserCreate, UserResponse, UserUpdate


class UserUsecase(BaseUsecase):

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["get"], response_model=UserResponse
    )
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        return await user_repository.get_by_id(user_id)

    @BaseUsecase.route(
        "/api/v1/users", methods=["get"], response_model=list[UserResponse]
    )
    async def get_all_users(self) -> list[UserResponse]:
        return await user_repository.get_all()

    @BaseUsecase.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse | list[UserResponse],
    )
    async def create_user(
        self, data: UserCreate | list[UserCreate]
    ) -> UserResponse | list[UserResponse]:
        if isinstance(data, UserCreate):
            return await user_repository.create(data)
        return await user_repository.create_bulk(data)

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["put"], response_model=UserResponse
    )
    async def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        return await user_repository.update(user_id, data)

    @BaseUsecase.route(
        "/api/v1/users/{user_id}", methods=["delete"], response_model=UserResponse
    )
    async def delete_user(self, user_id: str) -> UserResponse:
        return await user_repository.delete(user_id)


user_usecase = UserUsecase()
