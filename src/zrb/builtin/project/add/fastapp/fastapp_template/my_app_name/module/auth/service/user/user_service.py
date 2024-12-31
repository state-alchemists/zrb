from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.common.parser_factory import parse_filter_param, parse_sort_param
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    User,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class UserService(BaseService):
    def __init__(self, logger, user_repository: UserRepository):
        super().__init__(logger)
        self.user_repository = user_repository

    @BaseService.route(
        "/api/v1/users/{user_id}", methods=["get"], response_model=UserResponse
    )
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        return await self.user_repository.get_by_id(user_id)

    @BaseService.route(
        "/api/v1/users", methods=["get"], response_model=MultipleUserResponse
    )
    async def get_all_users(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        filters = parse_filter_param(User, filter) if filter else None
        sorts = parse_sort_param(User, sort) if sort else None
        data = await self.user_repository.get_all(
            page=page, page_size=page_size, filters=filters, sorts=sorts
        )
        count = await self.user_repository.count(filters=filters)
        return MultipleUserResponse(data=data, count=count)

    @BaseService.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse | list[UserResponse],
    )
    async def create_user(
        self, data: UserCreateWithAudit | list[UserCreateWithAudit]
    ) -> UserResponse | list[UserResponse]:
        if isinstance(data, UserCreateWithAudit):
            return await self.user_repository.create(data)
        return await self.user_repository.create_bulk(data)

    @BaseService.route(
        "/api/v1/users/{user_id}", methods=["put"], response_model=UserResponse
    )
    async def update_user(
        self, user_id: str, data: UserUpdateWithAudit
    ) -> UserResponse:
        return await self.user_repository.update(user_id, data)

    @BaseService.route(
        "/api/v1/users/{user_id}", methods=["delete"], response_model=UserResponse
    )
    async def delete_user(self, user_id: str, deleted_by: str) -> UserResponse:
        return await self.user_repository.delete(user_id)
