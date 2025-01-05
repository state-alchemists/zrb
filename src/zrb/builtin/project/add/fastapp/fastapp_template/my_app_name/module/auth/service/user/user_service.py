from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    UserCreateWithRolesAndAudit,
    UserResponse,
    UserUpdateWithRolesAndAudit,
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
        "/api/v1/users/bulk",
        methods=["post"],
        response_model=list[UserResponse],
    )
    async def create_user_bulk(
        self, data: list[UserCreateWithRolesAndAudit]
    ) -> list[UserResponse]:
        role_ids = [row.get_role_ids() for row in data]
        data = [row.get_user_create_with_audit() for row in data]
        users = await self.user_repository.create_bulk(data)
        if len(users) > 0:
            created_by = users[0].created_by
            await self.user_repository.add_roles(
                data={user.id: role_ids[i] for i, user in enumerate(data)},
                created_by=created_by,
            )
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse,
    )
    async def create_user(self, data: UserCreateWithRolesAndAudit) -> UserResponse:
        role_ids = data.get_role_ids()
        data = data.get_user_create_with_audit()
        user = await self.user_repository.create(data)
        await self.user_repository.add_roles(
            data={user.id: role_ids}, created_by=user.created_by
        )
        return await self.user_repository.get_by_id(user.id)

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["put"],
        response_model=UserResponse,
    )
    async def update_user_bulk(
        self, user_ids: list[str], data: UserUpdateWithRolesAndAudit
    ) -> UserResponse:
        role_ids = [row.get_role_ids() for row in data]
        data = [row.get_user_create_with_audit() for row in data]
        users = await self.user_repository.update_bulk(user_ids, data)
        if len(users) > 0:
            updated_by = users[0].updated_by
            await self.user_repository.remove_all_roles([user.id for user in users])
            await self.user_repository.add_roles(
                data={user.id: role_ids[i] for i, user in enumerate(data)},
                updated_by=updated_by,
            )
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["put"],
        response_model=UserResponse,
    )
    async def update_user(
        self, user_id: str, data: UserUpdateWithRolesAndAudit
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
