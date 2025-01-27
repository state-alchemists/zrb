from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)
from my_app_name.schema.my_entity import (
    MultipleMyEntityResponse,
    MyEntityCreateWithAudit,
    MyEntityResponse,
    MyEntityUpdateWithAudit,
)


class MyEntityService(BaseService):

    def __init__(self, logger: Logger, my_entity_repository: MyEntityRepository):
        super().__init__(logger)
        self.my_entity_repository = my_entity_repository

    @BaseService.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["get"],
        response_model=MyEntityResponse,
    )
    async def get_my_entity_by_id(self, my_entity_id: str) -> MyEntityResponse:
        return await self.my_entity_repository.get_by_id(my_entity_id)

    @BaseService.route(
        "/api/v1/my-entities",
        methods=["get"],
        response_model=MultipleMyEntityResponse,
    )
    async def get_my_entities(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleMyEntityResponse:
        my_entities = await self.my_entity_repository.get(page, page_size, filter, sort)
        count = await self.my_entity_repository.count(filter)
        return MultipleMyEntityResponse(data=my_entities, count=count)

    @BaseService.route(
        "/api/v1/my-entities/bulk",
        methods=["post"],
        response_model=list[MyEntityResponse],
    )
    async def create_my_entity_bulk(
        self, data: list[MyEntityCreateWithAudit]
    ) -> list[MyEntityResponse]:
        my_entities = await self.my_entity_repository.create_bulk(data)
        return await self.my_entity_repository.get_by_ids(
            [my_entity.id for my_entity in my_entities]
        )

    @BaseService.route(
        "/api/v1/my-entities",
        methods=["post"],
        response_model=MyEntityResponse,
    )
    async def create_my_entity(self, data: MyEntityCreateWithAudit) -> MyEntityResponse:
        my_entity = await self.my_entity_repository.create(data)
        return await self.my_entity_repository.get_by_id(my_entity.id)

    @BaseService.route(
        "/api/v1/my-entities/bulk",
        methods=["put"],
        response_model=list[MyEntityResponse],
    )
    async def update_my_entity_bulk(
        self, my_entity_ids: list[str], data: MyEntityUpdateWithAudit
    ) -> list[MyEntityResponse]:
        await self.my_entity_repository.update_bulk(my_entity_ids, data)
        return await self.my_entity_repository.get_by_ids(my_entity_ids)

    @BaseService.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["put"],
        response_model=MyEntityResponse,
    )
    async def update_my_entity(
        self, my_entity_id: str, data: MyEntityUpdateWithAudit
    ) -> MyEntityResponse:
        await self.my_entity_repository.update(my_entity_id, data)
        return await self.my_entity_repository.get_by_id(my_entity_id)

    @BaseService.route(
        "/api/v1/my-entities/bulk",
        methods=["delete"],
        response_model=list[MyEntityResponse],
    )
    async def delete_my_entity_bulk(
        self, my_entity_ids: list[str], deleted_by: str
    ) -> list[MyEntityResponse]:
        my_entities = await self.my_entity_repository.get_by_ids(my_entity_ids)
        await self.my_entity_repository.delete_bulk(my_entity_ids)
        return my_entities

    @BaseService.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["delete"],
        response_model=MyEntityResponse,
    )
    async def delete_my_entity(
        self, my_entity_id: str, deleted_by: str
    ) -> MyEntityResponse:
        my_entity = await self.my_entity_repository.get_by_id(my_entity_id)
        await self.my_entity_repository.delete(my_entity_id)
        return my_entity
