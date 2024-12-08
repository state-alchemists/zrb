from abc import ABC, abstractmethod

from fastapp_template.schema.user import User, UserCreate, UserResponse, UserUpdate


class UserRepository(ABC):

    @abstractmethod
    async def create(self, user_data: UserCreate) -> UserResponse:
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User:
        pass

    @abstractmethod
    async def get_all(self) -> list[User]:
        pass

    @abstractmethod
    async def update(self, user_id: str, user_data: UserUpdate) -> User:
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> User:
        pass

    @abstractmethod
    async def create_bulk(self, user_data_list: list[UserCreate]) -> list[UserResponse]:
        pass

    @abstractmethod
    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        pass
