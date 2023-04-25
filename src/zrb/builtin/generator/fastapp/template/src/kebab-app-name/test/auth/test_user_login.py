from typing import AsyncIterator
from httpx import AsyncClient
from src.config import (
    app_auth_admin_active, app_auth_admin_username, app_auth_admin_password
)
import pytest


@pytest.mark.asyncio
async def test_admin_user_login(
    test_client_generator: AsyncIterator[AsyncClient]
):
    if not app_auth_admin_active:
        # Only test if admin user is active
        return
    async for client in test_client_generator:
        login_response = await client.post(
            '/api/v1/login',
            json={
                'identity': app_auth_admin_username,
                'password': app_auth_admin_password
            }
        )
        assert login_response.status_code == 200
        json_login_response = login_response.json()
        assert json_login_response.get('token_type', '') == 'bearer'
        assert json_login_response.get('access_token', '') != ''


@pytest.mark.asyncio
async def test_create_normal_user_and_login_with_username(
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
        admin_access_token = login_admin_response.json().get('access_token', '')
        assert admin_access_token != ''
        # create user
        create_response = await client.post(
            '/api/v1/auth/users',
            json={
                'username': 'test-login-user-success',
                'password': 'test-password',
                'phone': '+628123456789',
                'email': 'test-login-user-success@test.com',
                'groups': [],
                'permissions': [],
                'description': ''
            },
            headers={
                'Authorization': 'Bearer ' + admin_access_token
            }
        )
        assert create_response.status_code == 200
        # login
        login_admin_response = await client.post(
            '/api/v1/login',
            json={
                'identity': 'test-login-user-success',
                'password': 'test-password'
            }
        )
        assert login_admin_response.status_code == 200
        json_login_response = login_admin_response.json()
        assert json_login_response.get('token_type', '') == 'bearer'
        assert json_login_response.get('access_token', '') != ''
