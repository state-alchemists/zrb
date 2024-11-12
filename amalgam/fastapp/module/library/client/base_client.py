from abc import ABC, abstractmethod


class BaseClient(ABC):
    @abstractmethod
    async def greet(name) -> str:
        pass
