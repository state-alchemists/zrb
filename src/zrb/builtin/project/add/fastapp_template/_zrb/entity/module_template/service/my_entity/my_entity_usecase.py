from fastapp_template.common.base_usecase import BaseUsecase
from fastapp_template.module.my_module.service.my_entity.repository.factory import (
    my_entity_repository,
)
from fastapp_template.module.my_module.service.my_entity.repository.repository import (
    MyEntityRepository,
)
from fastapp_template.schema.my_entity import (
    MyEntityCreate,
    MyEntityResponse,
    MyEntityUpdate,
)


class MyEntityUsecase(BaseUsecase):

    def __init__(self, my_entity_repository: MyEntityRepository):
        super().__init__()
        self.my_entity_repository = my_entity_repository

    @BaseUsecase.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["get"],
        response_model=MyEntityResponse,
    )
    async def get_my_entity_by_id(self, my_entity_id: str) -> MyEntityResponse:
        return await self.my_entity_repository.get_by_id(my_entity_id)

    @BaseUsecase.route(
        "/api/v1/my-entities", methods=["get"], response_model=list[MyEntityResponse]
    )
    async def get_all_my_entities(self) -> list[MyEntityResponse]:
        return await self.my_entity_repository.get_all()

    @BaseUsecase.route(
        "/api/v1/my-entities",
        methods=["post"],
        response_model=MyEntityResponse | list[MyEntityResponse],
    )
    async def create_my_entity(
        self, data: MyEntityCreate | list[MyEntityCreate]
    ) -> MyEntityResponse | list[MyEntityResponse]:
        if isinstance(data, MyEntityCreate):
            return await self.my_entity_repository.create(data)
        return await self.my_entity_repository.create_bulk(data)

    @BaseUsecase.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["put"],
        response_model=MyEntityResponse,
    )
    async def update_my_entity(
        self, my_entity_id: str, data: MyEntityUpdate
    ) -> MyEntityResponse:
        return await self.my_entity_repository.update(my_entity_id, data)

    @BaseUsecase.route(
        "/api/v1/my-entities/{my_entity_id}",
        methods=["delete"],
        response_model=MyEntityResponse,
    )
    async def delete_my_entity(self, my_entity_id: str) -> MyEntityResponse:
        return await self.my_entity_repository.delete(my_entity_id)


my_entity_usecase = MyEntityUsecase(my_entity_repository=my_entity_repository)
