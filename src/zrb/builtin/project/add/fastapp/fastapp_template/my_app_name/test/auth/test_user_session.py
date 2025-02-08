import time
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from my_app_name.config import (
    APP_AUTH_ACCESS_TOKEN_COOKIE_NAME,
    APP_AUTH_GUEST_USER,
    APP_AUTH_GUEST_USER_PERMISSIONS,
    APP_AUTH_REFRESH_TOKEN_COOKIE_NAME,
    APP_AUTH_SUPER_USER,
    APP_AUTH_SUPER_USER_PASSWORD,
)
from my_app_name.main import app
from my_app_name.module.gateway.util.auth import get_current_user
from my_app_name.schema.user import AuthUserResponse


@app.get("/test/current-user", response_model=AuthUserResponse)
async def serve_get_current_user(
    current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
) -> AuthUserResponse:
    return current_user


def test_create_invalid_user_session():
    client = TestClient(app, base_url="http://localhost")
    response = client.post(
        "/api/v1/user-sessions",
        data={
            "username": "nonExistingUserFromSevenKingdom",
            "password": "nonExistingSecurity",
        },
    )
    assert response.status_code == 401


def test_get_guest_user():
    client = TestClient(app, base_url="http://localhost")
    # Fetch current user
    response = client.get("/test/current-user")
    assert response.status_code == 200
    user_data = response.json()
    assert user_data.get("username") == APP_AUTH_GUEST_USER
    assert not user_data.get("is_super_user")
    assert user_data.get("is_guest")
    assert user_data.get("permission_names") == APP_AUTH_GUEST_USER_PERMISSIONS


def test_create_admin_user_session():
    client = TestClient(app, base_url="http://localhost")
    # Create new admin user session and check the response
    session_response = client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data.get("user_id") == APP_AUTH_SUPER_USER
    assert session_data.get("token_type") == "bearer"
    assert "access_token" in session_data
    assert "access_token_expired_at" in session_data
    assert "refresh_token" in session_data
    assert "refresh_token_expired_at" in session_data
    assert session_response.cookies.get(
        APP_AUTH_ACCESS_TOKEN_COOKIE_NAME
    ) == session_data.get("access_token")
    assert session_response.cookies.get(
        APP_AUTH_REFRESH_TOKEN_COOKIE_NAME
    ) == session_data.get("refresh_token")


def test_get_admin_user_with_bearer():
    client = TestClient(app, base_url="http://localhost")
    session_response = client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    assert session_response.status_code == 200
    access_token = session_response.json()["access_token"]
    # Fetch current user with bearer token
    response = client.get(
        "/test/current-user", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data.get("username") == APP_AUTH_SUPER_USER
    assert user_data.get("is_super_user")
    assert not user_data.get("is_guest")


def test_get_admin_user_with_cookie():
    login_client = TestClient(app, base_url="http://localhost")
    session_response = login_client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    assert session_response.status_code == 200
    # Fetch current user with cookies
    cookies = {
        APP_AUTH_ACCESS_TOKEN_COOKIE_NAME: session_response.cookies.get(
            APP_AUTH_ACCESS_TOKEN_COOKIE_NAME
        )
    }
    # re-initiate client with cookies
    client = TestClient(app, base_url="http://localhost", cookies=cookies)
    response = client.get("/test/current-user")
    assert response.status_code == 200
    user_data = response.json()
    assert user_data.get("username") == APP_AUTH_SUPER_USER
    assert user_data.get("is_super_user")
    assert not user_data.get("is_guest")


def test_update_user_session():
    login_client = TestClient(app, base_url="http://localhost")
    old_session_response = login_client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    assert old_session_response.status_code == 200
    old_session_data = old_session_response.json()
    # re-initiate client with cookies and delete user session
    client = TestClient(app, base_url="http://localhost")
    time.sleep(1)
    new_session_response = client.put(
        "/api/v1/user-sessions",
        params={"refresh_token": old_session_data.get("refresh_token")},
    )
    assert new_session_response.status_code == 200
    new_session_data = new_session_response.json()
    # Cookies and response should match
    assert new_session_response.cookies.get(
        APP_AUTH_ACCESS_TOKEN_COOKIE_NAME
    ) == new_session_data.get("access_token")
    assert new_session_response.cookies.get(
        APP_AUTH_REFRESH_TOKEN_COOKIE_NAME
    ) == new_session_data.get("refresh_token")
    # New session should has longer TTL than old session
    assert old_session_data.get("access_token") != new_session_data.get("access_token")
    assert old_session_data.get("access_token_expired_at") < new_session_data.get(
        "access_token_expired_at"
    )
    assert old_session_data.get("refresh_token") != new_session_data.get(
        "refresh_token"
    )
    assert old_session_data.get("refresh_token_expired_at") < new_session_data.get(
        "refresh_token_expired_at"
    )


def test_delete_user_session():
    login_client = TestClient(app, base_url="http://localhost")
    session_response = login_client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    assert session_response.status_code == 200
    # Initiate cookies that should be deleted when user session is deleted.
    cookies = {
        APP_AUTH_ACCESS_TOKEN_COOKIE_NAME: session_response.cookies.get(
            APP_AUTH_ACCESS_TOKEN_COOKIE_NAME
        ),
        APP_AUTH_REFRESH_TOKEN_COOKIE_NAME: session_response.cookies.get(
            APP_AUTH_REFRESH_TOKEN_COOKIE_NAME
        ),
    }
    # re-initiate client with cookies and delete user session
    client = TestClient(app, base_url="http://localhost", cookies=cookies)
    response = client.delete(
        "/api/v1/user-sessions",
        params={
            "refresh_token": session_response.cookies.get(
                APP_AUTH_REFRESH_TOKEN_COOKIE_NAME
            ),
        },
    )
    assert response.status_code == 200
    assert response.cookies.get(APP_AUTH_ACCESS_TOKEN_COOKIE_NAME, None) is None
    assert response.cookies.get(APP_AUTH_REFRESH_TOKEN_COOKIE_NAME, None) is None
