from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.security import OAuth2PasswordRequestForm
from my_app_name.common.error import ForbiddenError
from my_app_name.module.auth.client.auth_client_factory import auth_client
from my_app_name.module.gateway.util.auth import (
    get_current_user,
    set_user_session_cookie,
    unset_user_session_cookie,
)
from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreateWithPermissions,
    RoleResponse,
    RoleUpdateWithPermissions,
)
from my_app_name.schema.user import (
    AuthUserResponse,
    MultipleUserResponse,
    UserCreateWithRoles,
    UserCredentials,
    UserResponse,
    UserSessionResponse,
    UserUpdateWithRoles,
)


def serve_auth_route(app: FastAPI):

    @app.post("/api/v1/user-sessions", response_model=UserSessionResponse)
    async def create_user_session(
        response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ) -> UserSessionResponse:
        user_session = await auth_client.create_user_session(
            UserCredentials(
                username=form_data.username,
                password=form_data.password,
            )
        )
        set_user_session_cookie(response, user_session)
        return user_session

    @app.put("/api/v1/user-sessions", response_model=UserSessionResponse)
    async def update_user_session(
        response: Response, refresh_token: str
    ) -> UserSessionResponse:
        user_session = await auth_client.update_user_session(refresh_token)
        set_user_session_cookie(response, user_session)
        return user_session

    @app.delete("/api/v1/user-sessions", response_model=UserSessionResponse)
    async def delete_user_session(
        response: Response, refresh_token: str
    ) -> UserSessionResponse:
        user_session = await auth_client.delete_user_session(refresh_token)
        unset_user_session_cookie(response)
        return user_session

    # Permission routes

    @app.get("/api/v1/permissions", response_model=MultiplePermissionResponse)
    async def get_permissions(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        if not current_user.has_permission("permission:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_permissions(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/permissions/{permission_id}", response_model=PermissionResponse)
    async def get_permission_by_id(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        permission_id: str,
    ) -> PermissionResponse:
        if not current_user.has_permission("permission:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_permission_by_id(permission_id)

    @app.post(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def create_permission_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: list[PermissionCreate],
    ) -> list[PermissionResponse]:
        if not current_user.has_permission("permission:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_permission_bulk(
            [row.with_audit(created_by=current_user.id) for row in data]
        )

    @app.post(
        "/api/v1/permissions",
        response_model=PermissionResponse,
    )
    async def create_permission(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: PermissionCreate,
    ) -> PermissionResponse:
        if not current_user.has_permission("permission:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_permission(
            data.with_audit(created_by=current_user.id)
        )

    @app.put(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def update_permission_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        permission_ids: list[str],
        data: PermissionUpdate,
    ) -> list[PermissionResponse]:
        if not current_user.has_permission("permission:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_permission_bulk(
            permission_ids, data.with_audit(updated_by=current_user.id)
        )

    @app.put(
        "/api/v1/permissions/{permission_id}",
        response_model=PermissionResponse,
    )
    async def update_permission(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        permission_id: str,
        data: PermissionUpdate,
    ) -> PermissionResponse:
        if not current_user.has_permission("permission:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_permission(
            permission_id, data.with_audit(updated_by=current_user.id)
        )

    @app.delete(
        "/api/v1/permissions/bulk",
        response_model=list[PermissionResponse],
    )
    async def delete_permission_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        permission_ids: list[str],
    ) -> list[PermissionResponse]:
        if not current_user.has_permission("permission:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_permission_bulk(
            permission_ids, deleted_by=current_user.id
        )

    @app.delete(
        "/api/v1/permissions/{permission_id}",
        response_model=PermissionResponse,
    )
    async def delete_permission(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        permission_id: str,
    ) -> PermissionResponse:
        if not current_user.has_permission("permission:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_permission(
            permission_id, deleted_by=current_user.id
        )

    # Role routes

    @app.get("/api/v1/roles", response_model=MultipleRoleResponse)
    async def get_roles(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        if not current_user.has_permission("role:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_roles(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/roles/{role_id}", response_model=RoleResponse)
    async def get_role_by_id(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        role_id: str,
    ) -> RoleResponse:
        if not current_user.has_permission("role:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_role_by_id(role_id)

    @app.post(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def create_role_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: list[RoleCreateWithPermissions],
    ) -> list[RoleResponse]:
        if not current_user.has_permission("role:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_role_bulk(
            [row.with_audit(created_by=current_user.id) for row in data]
        )

    @app.post(
        "/api/v1/roles",
        response_model=RoleResponse,
    )
    async def create_role(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: RoleCreateWithPermissions,
    ) -> RoleResponse:
        if not current_user.has_permission("role:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_role(
            data.with_audit(created_by=current_user.id)
        )

    @app.put(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def update_role_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        role_ids: list[str],
        data: RoleUpdateWithPermissions,
    ) -> list[RoleResponse]:
        if not current_user.has_permission("role:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_role_bulk(
            role_ids, data.with_audit(updated_by=current_user.id)
        )

    @app.put(
        "/api/v1/roles/{role_id}",
        response_model=RoleResponse,
    )
    async def update_role(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        role_id: str,
        data: RoleUpdateWithPermissions,
    ) -> RoleResponse:
        if not current_user.has_permission("role:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_role(
            role_id, data.with_audit(updated_by=current_user.id)
        )

    @app.delete(
        "/api/v1/roles/bulk",
        response_model=list[RoleResponse],
    )
    async def delete_role_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        role_ids: list[str],
    ) -> list[RoleResponse]:
        if not current_user.has_permission("role:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_role_bulk(role_ids, deleted_by=current_user.id)

    @app.delete(
        "/api/v1/roles/{role_id}",
        response_model=RoleResponse,
    )
    async def delete_role(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        role_id: str,
    ) -> RoleResponse:
        if not current_user.has_permission("role:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_role(role_id, deleted_by=current_user.id)

    # User routes

    @app.get("/api/v1/users", response_model=MultipleUserResponse)
    async def get_users(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        if not current_user.has_permission("user:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_users(
            page=page, page_size=page_size, sort=sort, filter=filter
        )

    @app.get("/api/v1/users/{user_id}", response_model=UserResponse)
    async def get_user_by_id(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        user_id: str,
    ) -> UserResponse:
        if not current_user.has_permission("user:read"):
            raise ForbiddenError("Access denied")
        return await auth_client.get_user_by_id(user_id)

    @app.post(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def create_user_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: list[UserCreateWithRoles],
    ) -> list[UserResponse]:
        if not current_user.has_permission("user:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_user_bulk(
            [row.with_audit(created_by=current_user.id) for row in data]
        )

    @app.post(
        "/api/v1/users",
        response_model=UserResponse,
    )
    async def create_user(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        data: UserCreateWithRoles,
    ) -> UserResponse:
        if not current_user.has_permission("user:create"):
            raise ForbiddenError("Access denied")
        return await auth_client.create_user(
            data.with_audit(created_by=current_user.id)
        )

    @app.put(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def update_user_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        user_ids: list[str],
        data: UserUpdateWithRoles,
    ) -> list[UserResponse]:
        if not current_user.has_permission("user:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_user_bulk(
            user_ids, data.with_audit(updated_by=current_user.id)
        )

    @app.put(
        "/api/v1/users/{user_id}",
        response_model=UserResponse,
    )
    async def update_user(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        user_id: str,
        data: UserUpdateWithRoles,
    ) -> UserResponse:
        if not current_user.has_permission("user:update"):
            raise ForbiddenError("Access denied")
        return await auth_client.update_user(
            user_id, data.with_audit(updated_by=current_user.id)
        )

    @app.delete(
        "/api/v1/users/bulk",
        response_model=list[UserResponse],
    )
    async def delete_user_bulk(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        user_ids: list[str],
    ) -> list[UserResponse]:
        if not current_user.has_permission("user:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_user_bulk(user_ids, deleted_by=current_user.id)

    @app.delete(
        "/api/v1/users/{user_id}",
        response_model=UserResponse,
    )
    async def delete_user(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
        user_id: str,
    ) -> UserResponse:
        if not current_user.has_permission("user:delete"):
            raise ForbiddenError("Access denied")
        return await auth_client.delete_user(user_id, deleted_by=current_user.id)
