import os

from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.module.gateway.util.view import render_content


def test_homepage():
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/")
    assert response.status_code == 200
    view_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "module", "gateway", "view"
    )
    assert response.text == render_content("homepage.html").body.decode("utf-8")
