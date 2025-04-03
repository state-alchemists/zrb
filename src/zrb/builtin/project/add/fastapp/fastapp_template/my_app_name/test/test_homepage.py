from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.module.auth.service.user.user_service_factory import user_service
from my_app_name.module.gateway.util.view import render_content


async def test_homepage():
    current_user = await user_service.get_current_user(access_token=None)
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == render_content(
        "homepage.html",
        page_name="gateway.home",
        current_user=current_user,
    ).body.decode("utf-8")
