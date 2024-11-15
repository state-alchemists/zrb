from .....schema.user import NewUserData, UpdateUserData, UserData
from .repository.factory import user_repository


class UserUsecase:
    async def get_user_by_id(self, user_id: str) -> UserData:
        return await user_repository.get_user_by_id(user_id)

    async def get_all_users(self) -> list[UserData]:
        return await user_repository.get_all_users()

    async def create_user(self, data: NewUserData) -> UserData:
        return await user_repository.create_user(data)

    async def create_users_bulk(self, data: list[NewUserData]) -> list[UserData]:
        return await user_repository.create_users_bulk(data)

    async def update_user(self, id: str, data: UpdateUserData) -> UserData:
        return await user_repository.update_user(id, data)

    async def delete_user(self, id: str) -> UserData:
        return await user_repository.delete_user(id)


user_usecase = UserUsecase()
