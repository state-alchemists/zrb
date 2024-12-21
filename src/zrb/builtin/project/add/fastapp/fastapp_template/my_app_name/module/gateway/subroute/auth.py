from fastapi import FastAPI
from my_app_name.module.auth.client.factory import client as auth_client
from my_app_name.schema.user import (
    UserCreate,
    UserCreateWithAudit,
    UserResponse,
    UserUpdate,
    UserUpdateWithAudit,
)


def serve_auth_route(app: FastAPI):

    @app.get("/api/v1/users", response_model=list[UserResponse])
    async def get_all_users() -> UserResponse:
        return await auth_client.get_all_users()

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
