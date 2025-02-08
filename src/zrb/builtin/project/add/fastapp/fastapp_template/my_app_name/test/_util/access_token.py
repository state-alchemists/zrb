import time

from fastapi.testclient import TestClient
from my_app_name.config import APP_AUTH_SUPER_USER, APP_AUTH_SUPER_USER_PASSWORD
from my_app_name.main import app


def get_admin_access_token():
    client = TestClient(app, base_url="http://localhost")
    # Create new admin user session and check the response
    session_response = client.post(
        "/api/v1/user-sessions",
        data={
            "username": APP_AUTH_SUPER_USER,
            "password": APP_AUTH_SUPER_USER_PASSWORD,
        },
    )
    session_data = session_response.json()
    return session_data.get("access_token")
