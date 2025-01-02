from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class UserService(BaseService):

    def __init__(self, logger: Logger, user_repository: UserRepository):
        super().__init__(logger)
        self.user_repository = user_repository

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["get"],
        response_model=UserResponse,
    )
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        return await self.user_repository.get_by_id(user_id)

    @BaseService.route(
        "/api/v1/users",
        methods=["get"],
        response_model=MultipleUserResponse,
    )
    async def get_users(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        users = await self.user_repository.get(page, page_size, filter, sort)
        count = await self.user_repository.count(filter)
        return MultipleUserResponse(data=users, count=count)

    @BaseService.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse,
    )
    async def create_user(self, data: UserCreateWithAudit) -> UserResponse:
        user = await self.user_repository.create(data)
        return await self.user_repository.get_by_id(user.id)

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["post"],
        response_model=list[UserResponse],
    )
    async def create_user_bulk(
        self, data: list[UserCreateWithAudit]
    ) -> list[UserResponse]:
        users = await self.user_repository.create_bulk(data)
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["put"],
        response_model=UserResponse,
    )
    async def update_user_bulk(
        self, user_ids: list[str], data: UserUpdateWithAudit
    ) -> UserResponse:
        users = await self.user_repository.update_bulk(user_ids, data)
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["put"],
        response_model=UserResponse,
    )
    async def update_user(
        self, user_id: str, data: UserUpdateWithAudit
    ) -> UserResponse:
        user = await self.user_repository.update(user_id, data)
        return await self.user_repository.get_by_id(user.id)

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["delete"],
        response_model=UserResponse,
    )
    async def delete_user_bulk(
        self, user_ids: list[str], deleted_by: str
    ) -> UserResponse:
        users = await self.user_repository.delete_bulk(user_ids)
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["delete"],
        response_model=UserResponse,
    )
    async def delete_user(self, user_id: str, deleted_by: str) -> UserResponse:
        user = await self.user_repository.delete(user_id)
        return await self.user_repository.get_by_id(user.id)
