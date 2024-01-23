from typing import AsyncIterator

import pytest
from httpx import AsyncClient
from src.config import app_auth_admin_password, app_auth_admin_username

inserted_success_data = {
    "name": "test-create-group-success",
    "description": "",
    "permissions": [],
}
to_be_updated_success_data = {
    "name": "test-group-to-be-updated-success",
    "description": "",
    "permissions": [],
}
updated_success_data = {
    "name": "test-group-updated-success",
    "description": "new-description",
    "permissions": [],
}
to_be_deleted_success_data = {
    "name": "test-group-to-be-deleted-success",
    "description": "",
    "permissions": [],
}


@pytest.mark.asyncio
async def test_insert_group_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": app_auth_admin_username,
                "password": app_auth_admin_password,
            },
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get("access_token", "")

        # create group
        create_response = await client.post(
            "/api/v1/auth/groups",
            json=inserted_success_data,
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get("id", "")
        assert create_response_id != ""

        # get_by_id
        get_by_id_response = await client.get(
            f"/api/v1/auth/groups/{create_response_id}",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_by_id_response.status_code == 200
        json_get_by_id_response = get_by_id_response.json()
        get_by_id_response_id = json_get_by_id_response.get("id", "")
        assert get_by_id_response_id == create_response_id

        # get
        get_response = await client.get(
            "/api/v1/auth/groups",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get("count", "")
        assert get_response_count > 0
        get_response_data = json_get_response.get("data", [])
        get_created_response_data = [
            row for row in get_response_data if row["id"] == create_response_id
        ]
        assert len(get_created_response_data) == 1


@pytest.mark.asyncio
async def test_update_group_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": app_auth_admin_username,
                "password": app_auth_admin_password,
            },
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get("access_token", "")

        # create group
        create_response = await client.post(
            "/api/v1/auth/groups",
            json=to_be_updated_success_data,
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get("id", "")
        assert create_response_id != ""

        # update group
        update_response = await client.put(
            f"/api/v1/auth/groups/{create_response_id}",
            json=updated_success_data,
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert update_response.status_code == 200
        json_update_response = update_response.json()
        update_response_id = json_update_response.get("id", "")
        assert update_response_id == create_response_id

        # get_by_id
        get_by_id_response = await client.get(
            f"/api/v1/auth/groups/{create_response_id}",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_by_id_response.status_code == 200
        json_get_by_id_response = get_by_id_response.json()
        get_by_id_response_id = json_get_by_id_response.get("id", "")
        assert get_by_id_response_id == create_response_id
        for key, expected_value in updated_success_data.items():
            actual_value = json_get_by_id_response.get(key, "")
            assert f"{key}:{actual_value}" == f"{key}:{expected_value}"

        # get
        get_response = await client.get(
            "/api/v1/auth/groups",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get("count", "")
        assert get_response_count > 0
        get_response_data = json_get_response.get("data", [])
        get_created_response_data = [
            row for row in get_response_data if row["id"] == create_response_id
        ]
        assert len(get_created_response_data) == 1


@pytest.mark.asyncio
async def test_delete_group_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": app_auth_admin_username,
                "password": app_auth_admin_password,
            },
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get("access_token", "")

        # create group
        create_response = await client.post(
            "/api/v1/auth/groups",
            json=to_be_deleted_success_data,
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get("id", "")
        assert create_response_id != ""

        # create group
        delete_response = await client.delete(
            f"/api/v1/auth/groups/{create_response_id}",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert delete_response.status_code == 200
        json_delete_response = delete_response.json()
        delete_response_id = json_delete_response.get("id", "")
        assert delete_response_id == create_response_id

        # get_by_id
        get_by_id_response = await client.get(
            f"/api/v1/auth/groups/{create_response_id}",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_by_id_response.status_code == 404

        # get
        get_response = await client.get(
            "/api/v1/auth/groups",
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get("count", "")
        assert get_response_count > 0
        get_response_data = json_get_response.get("data", [])
        get_created_response_data = [
            row for row in get_response_data if row["id"] == create_response_id
        ]
        assert len(get_created_response_data) == 0
