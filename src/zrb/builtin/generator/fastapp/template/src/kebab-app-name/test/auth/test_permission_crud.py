from typing import AsyncIterator
from httpx import AsyncClient
from src.config import app_auth_admin_username, app_auth_admin_password
import pytest


@pytest.mark.asyncio
async def test_insert_permission_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient]
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            '/api/v1/login',
            json={
                'identity': app_auth_admin_username,
                'password': app_auth_admin_password
            }
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get(
            'access_token', ''
        )

        # create permission
        create_response = await client.post(
            '/api/v1/auth/permissions',
            json={
                'name': 'test-create_permission-success',
                'description': '',
            },
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get('id', '')
        assert create_response_id != ''

        # get_by_id
        get_by_id_response = await client.get(
            f'/api/v1/auth/permissions/{create_response_id}',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_by_id_response.status_code == 200
        json_get_by_id_response = get_by_id_response.json()
        get_by_id_response_id = json_get_by_id_response.get('id', '')
        assert get_by_id_response_id == create_response_id

        # get
        get_response = await client.get(
            '/api/v1/auth/permissions',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get('count', '')
        assert get_response_count > 0
        get_response_data = json_get_response.get('data', [])
        get_created_response_data = [
            row for row in get_response_data
            if row['id'] == create_response_id
        ]
        assert len(get_created_response_data) == 1


@pytest.mark.asyncio
async def test_update_permission_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient]
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            '/api/v1/login',
            json={
                'identity': app_auth_admin_username,
                'password': app_auth_admin_password,
            }
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get(
            'access_token', ''
        )

        # create permission
        create_response = await client.post(
            '/api/v1/auth/permissions',
            json={
                'name': 'test-to-be-updated-success',
                'description': '',
            },
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get('id', '')
        assert create_response_id != ''

        # update permission
        update_response = await client.put(
            f'/api/v1/auth/permissions/{create_response_id}',
            json={
                'name': 'test-updated-success',
                'description': '',
            },
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert update_response.status_code == 200
        json_update_response = update_response.json()
        update_response_id = json_update_response.get('id', '')
        assert update_response_id == create_response_id

        # get_by_id
        get_by_id_response = await client.get(
            f'/api/v1/auth/permissions/{create_response_id}',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_by_id_response.status_code == 200
        json_get_by_id_response = get_by_id_response.json()
        get_by_id_response_id = json_get_by_id_response.get('id', '')
        assert get_by_id_response_id == create_response_id
        get_by_id_response_name = json_get_by_id_response.get('name', '')
        assert get_by_id_response_name == 'test-updated-success'

        # get
        get_response = await client.get(
            '/api/v1/auth/permissions',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get('count', '')
        assert get_response_count > 0
        get_response_data = json_get_response.get('data', [])
        get_created_response_data = [
            row for row in get_response_data
            if row['id'] == create_response_id
        ]
        assert len(get_created_response_data) == 1


@pytest.mark.asyncio
async def test_delete_permission_and_get_success(
    test_client_generator: AsyncIterator[AsyncClient]
):
    async for client in test_client_generator:
        # login
        login_admin_response = await client.post(
            '/api/v1/login',
            json={
                'identity': app_auth_admin_username,
                'password': app_auth_admin_password
            }
        )
        assert login_admin_response.status_code == 200
        admin_access_token = login_admin_response.json().get(
            'access_token', ''
        )

        # create permission
        create_response = await client.post(
            '/api/v1/auth/permissions',
            json={
                'name': 'test-to-be-deleted-success',
                'description': '',
            },
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert create_response.status_code == 200
        json_create_response = create_response.json()
        create_response_id = json_create_response.get('id', '')
        assert create_response_id != ''

        # delete permission
        delete_response = await client.delete(
            f'/api/v1/auth/permissions/{create_response_id}',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert delete_response.status_code == 200
        json_delete_response = delete_response.json()
        delete_response_id = json_delete_response.get('id', '')
        assert delete_response_id == create_response_id

        # get_by_id
        get_by_id_response = await client.get(
            f'/api/v1/auth/permissions/{create_response_id}',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_by_id_response.status_code == 404

        # get
        get_response = await client.get(
            '/api/v1/auth/permissions',
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert get_response.status_code == 200
        json_get_response = get_response.json()
        get_response_count = json_get_response.get('count', '')
        assert get_response_count > 0
        get_response_data = json_get_response.get('data', [])
        get_created_response_data = [
            row for row in get_response_data
            if row['id'] == create_response_id
        ]
        assert len(get_created_response_data) == 0
