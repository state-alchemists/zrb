from abc import ABC, abstractmethod

# from fastapp_template.schema.my_entity import (
#     MyEntityCreateWithAudit, MyEntityResponse, MyEntityUpdateWithAudit
# )


class AnyClient(ABC):
    pass

    # @abstractmethod
    # async def get_my_entity_by_id(self, my_entity_id: str) -> MyEntityResponse:
    #     pass

    # @abstractmethod
    # async def get_all_my_entitys(self) -> list[MyEntityResponse]:
    #     pass

    # @abstractmethod
    # async def create_my_entity(
    #     self, data: MyEntityCreateWithAudit | list[MyEntityCreateWithAudit]
    # ) -> MyEntityResponse | list[MyEntityResponse]:
    #     pass

    # @abstractmethod
    # async def update_my_entity(
    #     self, my_entity_id: str, data: MyEntityUpdateWithAudit
    # ) -> MyEntityResponse:
    #     pass

    # @abstractmethod
    # async def delete_my_entity(self, my_entity_id: str) -> MyEntityResponse:
    #     pass
