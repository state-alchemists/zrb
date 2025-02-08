import os

from fastapi.testclient import TestClient
from my_app_name.main import app
from my_app_name.module.gateway.util.view import render_error


def test_not_found_error():
    client = TestClient(app, base_url="http://localhost")
    response = client.get(
        "/holly-grail/not-found/philosopher-stone/not-found/hope/inexist"
    )
    assert response.status_code == 404
    assert response.text == render_error(
        error_message="Not found", status_code=404
    ).body.decode("utf-8")
