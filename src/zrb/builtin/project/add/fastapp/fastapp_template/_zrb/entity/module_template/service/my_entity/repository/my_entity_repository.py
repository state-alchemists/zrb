from abc import ABC, abstractmethod

from fastapp_template.schema.my_entity import (
    MyEntity,
    MyEntityCreateWithAudit,
    MyEntityResponse,
    MyEntityUpdateWithAudit,
)


class MyEntityRepository(ABC):

    @abstractmethod
    async def create(self, my_entity_data: MyEntityCreateWithAudit) -> MyEntityResponse:
        pass

    @abstractmethod
    async def get_by_id(self, my_entity_id: str) -> MyEntity:
        pass

    @abstractmethod
    async def get_all(self) -> list[MyEntity]:
        pass

    @abstractmethod
    async def update(
        self, my_entity_id: str, my_entity_data: MyEntityUpdateWithAudit
    ) -> MyEntity:
        pass

    @abstractmethod
    async def delete(self, my_entity_id: str) -> MyEntity:
        pass

    @abstractmethod
    async def create_bulk(
        self, my_entity_data_list: list[MyEntityCreateWithAudit]
    ) -> list[MyEntityResponse]:
        pass
