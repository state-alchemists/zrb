from fastapi import FastAPI
from my_app_name.module.auth.client.auth_client_factory import auth_client
from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)


def serve_auth_route(app: FastAPI):

    # Permission routes

    @app.get("/api/v1/permissions", response_model=MultiplePermissionResponse)
    async def get_permissions(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        return await auth_client.get_permissions(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/permissions/{permission_id}", response_model=PermissionResponse)
    async def get_permission_by_id(permission_id: str) -> PermissionResponse:
        return await auth_client.get_permission_by_id(permission_id)

    @app.post(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def create_permission_bulk(data: list[PermissionCreate]):
        return await auth_client.create_permission(
            [row.with_audit(created_by="system") for row in data]
        )

    @app.post(
        "/api/v1/permissions",
        response_model=PermissionResponse,
    )
    async def create_permission(data: PermissionCreate):
        return await auth_client.create_permission(data.with_audit(created_by="system"))

    @app.put(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def update_permission_bulk(permission_ids: list[str], data: PermissionUpdate):
        return await auth_client.update_permission_bulk(
            permission_ids, data.with_audit(updated_by="system")
        )

    @app.put(
        "/api/v1/permissions/{permission_id}",
        response_model=PermissionResponse,
    )
    async def update_permission(permission_id: str, data: PermissionUpdate):
        return await auth_client.update_permission(data.with_audit(updated_by="system"))

    @app.delete(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def delete_permission_bulk(permission_ids: list[str]):
        return await auth_client.delete_permission_bulk(
            permission_ids, deleted_by="system"
        )

    @app.delete(
        "/api/v1/permissions/{permission_id}",
        response_model=PermissionResponse,
    )
    async def delete_permission(permission_id: str):
        return await auth_client.delete_permission(permission_id, deleted_by="system")

    # Role routes

    @app.get("/api/v1/roles", response_model=MultipleRoleResponse)
    async def get_roles(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        return await auth_client.get_roles(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/roles/{role_id}", response_model=RoleResponse)
    async def get_role_by_id(role_id: str) -> RoleResponse:
        return await auth_client.get_role_by_id(role_id)

    @app.post(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def create_role_bulk(data: list[RoleCreate]):
        return await auth_client.create_role(
            [row.with_audit(created_by="system") for row in data]
        )

    @app.post(
        "/api/v1/roles",
        response_model=RoleResponse,
    )
    async def create_role(data: RoleCreate):
        return await auth_client.create_role(data.with_audit(created_by="system"))

    @app.put(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def update_role_bulk(role_ids: list[str], data: RoleUpdate):
        return await auth_client.update_role_bulk(
            role_ids, data.with_audit(updated_by="system")
        )

    @app.put(
        "/api/v1/roles/{role_id}",
        response_model=RoleResponse,
    )
    async def update_role(role_id: str, data: RoleUpdate):
        return await auth_client.update_role(data.with_audit(updated_by="system"))

    @app.delete(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def delete_role_bulk(role_ids: list[str]):
        return await auth_client.delete_role_bulk(role_ids, deleted_by="system")

    @app.delete(
        "/api/v1/roles/{role_id}",
        response_model=RoleResponse,
    )
    async def delete_role(role_id: str):
        return await auth_client.delete_role(role_id, deleted_by="system")

    # User routes

    @app.get("/api/v1/users", response_model=MultipleUserResponse)
    async def get_users(
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        return await auth_client.get_users(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/users/{user_id}", response_model=UserResponse)
    async def get_user_by_id(user_id: str) -> UserResponse:
        return await auth_client.get_user_by_id(user_id)

    @app.post(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def create_user_bulk(data: list[UserCreate]):
        return await auth_client.create_user(
            [row.with_audit(created_by="system") for row in data]
        )

    @app.post(
        "/api/v1/users",
        response_model=UserResponse,
    )
    async def create_user(data: UserCreate):
        return await auth_client.create_user(data.with_audit(created_by="system"))

    @app.put(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def update_user_bulk(user_ids: list[str], data: UserUpdate):
        return await auth_client.update_user_bulk(
            user_ids, data.with_audit(updated_by="system")
        )

    @app.put(
        "/api/v1/users/{user_id}",
        response_model=UserResponse,
    )
    async def update_user(user_id: str, data: UserUpdate):
        return await auth_client.update_user(data.with_audit(updated_by="system"))

    @app.delete(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def delete_user_bulk(user_ids: list[str]):
        return await auth_client.delete_user_bulk(user_ids, deleted_by="system")

    @app.delete(
        "/api/v1/users/{user_id}",
        response_model=UserResponse,
    )
    async def delete_user(user_id: str):
        return await auth_client.delete_user(user_id, deleted_by="system")
