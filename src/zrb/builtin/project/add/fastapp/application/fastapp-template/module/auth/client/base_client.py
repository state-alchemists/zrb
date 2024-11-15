from abc import ABC, abstractmethod

from ....schema.user import NewUserData, UserData


class BaseClient(ABC):
    @abstractmethod
    async def create_user(data: NewUserData) -> UserData:
        pass

    @abstractmethod
    async def get_all_users() -> list[UserData]:
        pass
