from fastapi import FastAPI
from my_app_name.module.auth.client.factory import client as auth_client
from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreate,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdate,
    PermissionUpdateWithAudit,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreate,
    RoleCreateWithAudit,
    RoleResponse,
    RoleUpdate,
    RoleUpdateWithAudit,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    UserCreate,
    UserCreateWithAudit,
    UserResponse,
    UserUpdate,
    UserUpdateWithAudit,
)


def serve_auth_route(app: FastAPI):
    # Permission routes

    @app.get("/api/v1/permissions", response_model=MultiplePermissionResponse)
    async def get_all_permissions(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        return await auth_client.get_all_permissions(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/permissions/{permission_id}", response_model=PermissionResponse)
    async def get_permission_by_id(permission_id: str) -> PermissionResponse:
        return await auth_client.get_permission_by_id(permission_id)

    @app.post(
        "/api/v1/permissions",
        response_model=PermissionResponse | list[PermissionResponse],
    )
    async def create_permission(data: PermissionCreate | list[PermissionCreate]):
        if isinstance(data, PermissionCreate):
            data_dict = data.model_dump(exclude_unset=True)
            audited_data = PermissionCreateWithAudit(**data_dict, created_by="system")
            return await auth_client.create_permission(audited_data)
        audited_data = [
            PermissionCreateWithAudit(
                **row.model_dump(exclude_unset=True), created_by="system"
            )
            for row in data
        ]
        return await auth_client.create_permission(audited_data)

    @app.put("/api/v1/permissions/{permission_id}", response_model=PermissionResponse)
    async def update_permission(
        permission_id: str, data: PermissionUpdate
    ) -> PermissionResponse:
        data_dict = data.model_dump(exclude_unset=True)
        audited_data = PermissionUpdateWithAudit(**data_dict, updated_by="system")
        return await auth_client.update_permission(permission_id, audited_data)

    @app.delete(
        "/api/v1/permissions/{permission_id}", response_model=PermissionResponse
    )
    async def delete_permission(permission_id: str) -> PermissionResponse:
        return await auth_client.delete_permission(permission_id, deleted_by="system")

    # Role routes

    @app.get("/api/v1/roles", response_model=MultipleRoleResponse)
    async def get_all_roles(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        return await auth_client.get_all_roles(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/roles/{role_id}", response_model=RoleResponse)
    async def get_role_by_id(role_id: str) -> RoleResponse:
        return await auth_client.get_role_by_id(role_id)

    @app.post("/api/v1/roles", response_model=RoleResponse | list[RoleResponse])
    async def create_role(data: RoleCreate | list[RoleCreate]):
        if isinstance(data, RoleCreate):
            data_dict = data.model_dump(exclude_unset=True)
            audited_data = RoleCreateWithAudit(**data_dict, created_by="system")
            return await auth_client.create_role(audited_data)
        audited_data = [
            RoleCreateWithAudit(
                **row.model_dump(exclude_unset=True), created_by="system"
            )
            for row in data
        ]
        return await auth_client.create_role(audited_data)

    @app.put("/api/v1/roles/{role_id}", response_model=RoleResponse)
    async def update_role(role_id: str, data: RoleUpdate) -> RoleResponse:
        data_dict = data.model_dump(exclude_unset=True)
        audited_data = RoleUpdateWithAudit(**data_dict, updated_by="system")
        return await auth_client.update_role(role_id, audited_data)

    @app.delete("/api/v1/roles/{role_id}", response_model=RoleResponse)
    async def delete_role(role_id: str) -> RoleResponse:
        return await auth_client.delete_role(role_id, deleted_by="system")

    # User routes

    @app.get("/api/v1/users", response_model=MultipleUserResponse)
    async def get_all_users(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        return await auth_client.get_all_users(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/users/{user_id}", response_model=UserResponse)
    async def get_user_by_id(user_id: str) -> UserResponse:
        return await auth_client.get_user_by_id(user_id)

    @app.post("/api/v1/users", response_model=UserResponse | list[UserResponse])
    async def create_user(data: UserCreate | list[UserCreate]):
        if isinstance(data, UserCreate):
            data_dict = data.model_dump(exclude_unset=True)
            audited_data = UserCreateWithAudit(**data_dict, created_by="system")
            return await auth_client.create_user(audited_data)
        audited_data = [
            UserCreateWithAudit(
                **row.model_dump(exclude_unset=True), created_by="system"
            )
            for row in data
        ]
        return await auth_client.create_user(audited_data)

    @app.put("/api/v1/users/{user_id}", response_model=UserResponse)
    async def update_user(user_id: str, data: UserUpdate) -> UserResponse:
        data_dict = data.model_dump(exclude_unset=True)
        audited_data = UserUpdateWithAudit(**data_dict, updated_by="system")
        return await auth_client.update_user(user_id, audited_data)

    @app.delete("/api/v1/users/{user_id}", response_model=UserResponse)
    async def delete_user(user_id: str) -> UserResponse:
        return await auth_client.delete_user(user_id, deleted_by="system")
