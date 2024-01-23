from typing import AsyncIterator

import pytest
from httpx import AsyncClient
from src.config import app_auth_admin_password, app_auth_admin_username


@pytest.mark.asyncio
async def test_admin_user_login_success(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": app_auth_admin_username,
                "password": app_auth_admin_password,
            },
        )
        assert login_response.status_code == 200
        json_login_response = login_response.json()
        assert json_login_response.get("token_type", "") == "bearer"
        assert json_login_response.get("access_token", "") != ""


@pytest.mark.asyncio
async def test_admin_user_login_empty_identity_failed(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"identity": "", "password": app_auth_admin_password},
        )
        assert login_response.status_code == 422


@pytest.mark.asyncio
async def test_admin_user_login_invalid_identity_failed(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"identity": "invalid-identity", "password": app_auth_admin_password},
        )
        assert login_response.status_code == 404


@pytest.mark.asyncio
async def test_admin_user_failed_invalid_password(
    test_client_generator: AsyncIterator[AsyncClient],
):
    async for client in test_client_generator:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"identity": app_auth_admin_username, "password": "invalid-password"},
        )
        assert login_response.status_code == 404


@pytest.mark.asyncio
async def test_create_normal_user_and_login_with_username_success(
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
        assert admin_access_token != ""
        # create user
        create_response = await client.post(
            "/api/v1/auth/users",
            json={
                "username": "test-login-user-with-username-success",
                "password": "test-password",
                "phone": "+628123456789",
                "email": "test-login-user-with-username-success@test.com",
                "groups": [],
                "permissions": [],
                "description": "",
            },
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": "test-login-user-with-username-success",
                "password": "test-password",
            },
        )
        assert login_admin_response.status_code == 200
        json_login_response = login_admin_response.json()
        assert json_login_response.get("token_type", "") == "bearer"
        assert json_login_response.get("access_token", "") != ""


@pytest.mark.asyncio
async def test_create_normal_user_and_login_with_phone_success(
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
        assert admin_access_token != ""
        # create user
        create_response = await client.post(
            "/api/v1/auth/users",
            json={
                "username": "test-login-user-with-phone-success",
                "password": "test-password",
                "phone": "+628123456789",
                "email": "test-login-user-with-phone-success@test.com",
                "groups": [],
                "permissions": [],
                "description": "",
            },
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={"identity": "+628123456789", "password": "test-password"},
        )
        assert login_admin_response.status_code == 200
        json_login_response = login_admin_response.json()
        assert json_login_response.get("token_type", "") == "bearer"
        assert json_login_response.get("access_token", "") != ""


@pytest.mark.asyncio
async def test_create_normal_user_and_login_with_email_success(
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
        assert admin_access_token != ""
        # create user
        create_response = await client.post(
            "/api/v1/auth/users",
            json={
                "username": "test-login-user-with-email-success",
                "password": "test-password",
                "phone": "+628123456789",
                "email": "test-login-user-with-email-success@test.com",
                "groups": [],
                "permissions": [],
                "description": "",
            },
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": "test-login-user-with-email-success@test.com",
                "password": "test-password",
            },
        )
        assert login_admin_response.status_code == 200
        json_login_response = login_admin_response.json()
        assert json_login_response.get("token_type", "") == "bearer"
        assert json_login_response.get("access_token", "") != ""


@pytest.mark.asyncio
async def test_create_normal_user_and_login_failed(
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
        assert admin_access_token != ""
        # create user
        create_response = await client.post(
            "/api/v1/auth/users",
            json={
                "username": "test-login-user-with-email-failed",
                "password": "test-password",
                "phone": "+628123456789",
                "email": "test-login-user-with-email-failed@test.com",
                "groups": [],
                "permissions": [],
                "description": "",
            },
            headers={"Authorization": "Bearer " + admin_access_token},
        )
        assert create_response.status_code == 200
        # login
        login_admin_response = await client.post(
            "/api/v1/auth/login",
            json={
                "identity": "test-login-user-with-email-failed",
                "password": "invalid-password",
            },
        )
        assert login_admin_response.status_code == 404
