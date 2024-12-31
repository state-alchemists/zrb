from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.common.parser_factory import parse_filter_param, parse_sort_param
from my_app_name.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)
from my_app_name.schema.my_entity import (
    MultipleMyEntityResponse,
    MyEntity,
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
        "/api/v1/my-entities", methods=["get"], response_model=MultipleMyEntityResponse
    )
    async def get_all_my_entities(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleMyEntityResponse:
        filters = parse_filter_param(MyEntity, filter) if filter else None
        sorts = parse_sort_param(MyEntity, sort) if sort else None
        data = await self.my_entity_repository.get_all(
            page=page, page_size=page_size, filters=filters, sorts=sorts
        )
        count = await self.my_entity_repository.count(filters=filters)
        return MultipleMyEntityResponse(data=data, count=count)

    @BaseService.route(
        "/api/v1/my-entities",
        methods=["post"],
        response_model=MyEntityResponse | list[MyEntityResponse],
    )
    async def create_my_entity(
        self, data: MyEntityCreateWithAudit | list[MyEntityCreateWithAudit]
    ) -> MyEntityResponse | list[MyEntityResponse]:
        if isinstance(data, MyEntityCreateWithAudit):
            return await self.my_entity_repository.create(data)
        return await self.my_entity_repository.create_bulk(data)

    @BaseService.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["put"],
        response_model=MyEntityResponse,
    )
    async def update_my_entity(
        self, my_entity_id: str, data: MyEntityUpdateWithAudit
    ) -> MyEntityResponse:
        return await self.my_entity_repository.update(my_entity_id, data)

    @BaseService.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["delete"],
        response_model=MyEntityResponse,
    )
    async def delete_my_entity(
        self, my_entity_id: str, deleted_by: str
    ) -> MyEntityResponse:
        return await self.my_entity_repository.delete(my_entity_id)
