import pytest
from fastapi.testclient import TestClient

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.group import Group
from zrb.input.int_input import IntInput
from zrb.runner.web_app import create_web_app
from zrb.session_state_logger.session_state_logger_factory import (
    session_state_logger,
)
from zrb.task.task import Task


@pytest.fixture
def client():
    root_group = Group(name="root")
    math_group = root_group.add_group(Group("math"))
    math_group.add_task(
        Task(
            name="add",
            input=[IntInput(name="first_num"), IntInput(name="second_num")],
            action="{ctx.input.first_num + ctx.input.second_num}",
        )
    )
    geometry_group = math_group.add_group(Group("geometry"))
    geometry_group.add_task(
        Task(
            name="area",
            input=[IntInput(name="w"), IntInput(name="l")],
            action="{ctx.input.w * ctx.input.l}",
        )
    )
    app = create_web_app(
        root_group,
        WebAuthConfig(
            secret_key="zrb",
            access_token_expire_minutes=30,
            refresh_token_expire_minutes=30,
            access_token_cookie_name="access_token",
            refresh_token_cookie_name="refresh_token",
            enable_auth=False,
            super_admin_username="admin",
            super_admin_password="admin",
            guest_username="guest",
        ),
        session_state_logger,
    )
    with TestClient(app) as test_client:
        yield test_client


def test_home_page(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert CFG.WEB_TITLE in response.text


def test_ui_home_page(client: TestClient):
    response = client.get("/ui")
    assert response.status_code == 200
    assert CFG.WEB_TITLE in response.text


def test_static_found(client: TestClient):
    response = client.get("/static/pico-css/pico.min.css")
    assert response.status_code == 200


def test_static_not_found(client: TestClient):
    response = client.get("/static/nano.css")
    assert response.status_code == 404


def test_ui_group(client: TestClient):
    response = client.get("/ui/math")
    assert response.status_code == 200
    assert "geometry" in response.text
    assert "add" in response.text


def test_ui_task(client: TestClient):
    response = client.get("/ui/math/add")
    assert response.status_code == 200
    assert "add" in response.text
    assert "first_num" in response.text
    assert "second_num" in response.text
