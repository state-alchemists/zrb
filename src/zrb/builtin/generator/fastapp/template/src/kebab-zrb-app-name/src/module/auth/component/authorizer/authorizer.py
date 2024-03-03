from abc import ABC, abstractmethod


class Authorizer(ABC):
    @abstractmethod
    async def is_admin(self, user_id: str) -> bool:
        pass

    @abstractmethod
    async def is_guest(self, user_id: str) -> bool:
        pass

    @abstractmethod
    async def is_having_permission(self, user_id: str, *permission_names: str) -> bool:
        pass
