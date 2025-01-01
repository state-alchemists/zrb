from abc import ABC, abstractmethod

from my_app_name.schema.my_entity import (
    MyEntity,
    MyEntityCreateWithAudit,
    MyEntityResponse,
    MyEntityUpdateWithAudit,
)


class MyEntityRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: str) -> MyEntityResponse:
        """Get my entity by id"""

    @abstractmethod
    async def get_by_ids(self, id_list: list[str]) -> MyEntityResponse:
        """Get my entities by ids"""

    @abstractmethod
    async def get(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> list[MyEntity]:
        """Get my entities by filter and sort"""

    @abstractmethod
    async def count(self, filter: str | None = None) -> int:
        """Count my entities by filter"""

    @abstractmethod
    async def create(self, data: MyEntityCreateWithAudit) -> MyEntity:
        """Create a new my entity"""

    @abstractmethod
    async def create_bulk(self, data: list[MyEntityCreateWithAudit]) -> list[MyEntity]:
        """Create some my entities"""

    @abstractmethod
    async def delete(self, id: str) -> MyEntity:
        """Delete a my entity"""

    @abstractmethod
    async def delete_bulk(self, id_list: list[str]) -> list[MyEntity]:
        """Delete some my entities"""

    @abstractmethod
    async def update(self, id: str, data: MyEntityUpdateWithAudit) -> MyEntity:
        """Update a my entity"""

    @abstractmethod
    async def update_bulk(
        self, id_list: list[str], data: MyEntityUpdateWithAudit
    ) -> list[MyEntity]:
        """Update some my entities"""
