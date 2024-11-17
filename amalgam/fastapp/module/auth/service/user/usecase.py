from .....common.base_usecase import BaseUsecase
from .....schema.user import NewUserData, UpdateUserData, UserData
from .repository.factory import user_repository


class UserUsecase(BaseUsecase):

    @BaseUsecase.route(
        "/api/v1/user/{user_id}", methods=["get"], response_model=UserData
    )
    async def get_user_by_id(self, user_id: str) -> UserData:
        return await user_repository.get_user_by_id(user_id)

    @BaseUsecase.route("/api/v1/user", methods=["get"], response_model=list[UserData])
    async def get_all_users(self) -> list[UserData]:
        return await user_repository.get_all_users()

    @BaseUsecase.route(
        "/api/v1/user", methods=["post"], response_model=UserData | list[UserData]
    )
    async def create_user(
        self, data: NewUserData | list[NewUserData]
    ) -> UserData | list[UserData]:
        if isinstance(data, NewUserData):
            return await user_repository.create_user(data)
        return await user_repository.create_users_bulk(data)

    @BaseUsecase.route(
        "/api/v1/user/{user_id}", methods=["put"], response_model=UserData
    )
    async def update_user(self, user_id: str, data: UpdateUserData) -> UserData:
        return await user_repository.update_user(user_id, data)

    @BaseUsecase.route(
        "/api/v1/user/{user_id}", methods=["delete"], response_model=UserData
    )
    async def delete_user(self, user_id: str) -> UserData:
        return await user_repository.delete_user(user_id)


user_usecase = UserUsecase()
