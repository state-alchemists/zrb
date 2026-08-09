"""Smoke tests for the page-rendering routes.

`test/runner/web_route/` held only API-route tests, so every page module except
login/logout was unexercised: a template renamed on one side of
`get_template("home_page/view.html")` failed at request time and nothing caught
it.

These assert the two things a page route owes its caller — the status code, and
that it reached for the template it claims — with the Jinja environment mocked,
because rendering real templates would test Jinja rather than the routing.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_route.chat_page.chat_page_route import serve_chat_page
from zrb.runner.web_route.error_page.serve_default_404 import serve_default_404
from zrb.runner.web_route.home_page.home_page_route import serve_home_page


@pytest.fixture
def rendered():
    """Mock Jinja env; `rendered.templates` records what each route asked for."""
    env = MagicMock()
    template = MagicMock()
    template.render.return_value = "<html>page</html>"
    env.get_template.return_value = template
    env.templates = lambda: [c.args[0] for c in env.get_template.call_args_list]
    return env


@pytest.fixture
def auth_config():
    cfg = MagicMock(spec=WebAuthConfig)
    cfg.access_token_cookie_name = "access_token"
    return cfg



@pytest.mark.parametrize("path", ["/", "/ui", "/ui/"])
def test_home_page_renders_on_every_alias(path, rendered, auth_config):
    """All three aliases are declared on one handler; a decorator dropped in a
    refactor would leave a 404 that no other test would see."""
    module = "zrb.runner.web_route.home_page.home_page_route"
    app = FastAPI()
    root_group = MagicMock()
    root_group.name = "zrb"
    root_group.description = "automation"

    with patch(f"{module}.get_jinja_env", return_value=rendered), patch(
        f"{module}.get_user_from_request", return_value=None
    ), patch(f"{module}.get_html_subgroup_info", return_value=""), patch(
        f"{module}.get_html_subtask_info", return_value=""
    ), patch(
        f"{module}.get_html_auth_link", return_value=""
    ):
        serve_home_page(app, root_group, auth_config)
        response = TestClient(app).get(path)

    assert response.status_code == 200
    assert "home_page/view.html" in rendered.templates()


@pytest.mark.parametrize("path", ["/ui/chat", "/ui/chat/"])
def test_chat_page_renders_on_every_alias(path, rendered, auth_config):
    module = "zrb.runner.web_route.chat_page.chat_page_route"
    app = FastAPI()
    root_group = MagicMock()

    with patch(f"{module}.get_jinja_env", return_value=rendered), patch(
        f"{module}.get_user_from_request", return_value=None
    ), patch(f"{module}.get_html_auth_link", return_value=""):
        serve_chat_page(app, root_group, auth_config)
        response = TestClient(app).get(path)

    assert response.status_code == 200
    assert "chat_page/view.html" in rendered.templates()


@pytest.mark.parametrize(
    "path, expect_html_page",
    [("/definitely-not-a-route", True), ("/api/definitely-not-a-route", False)],
)
def test_404_serves_a_page_for_the_ui_and_json_for_the_api(
    path, expect_html_page, auth_config
):
    """The handler branches on the `/api` prefix, and that branch is the point.

    Asserting only "a missing route 404s" would pass without the handler
    registered at all, since FastAPI 404s on its own. What is worth pinning is
    that a browser gets the rendered error page while an API client keeps the
    JSON body its caller can parse.
    """
    module = "zrb.runner.web_route.error_page.serve_default_404"
    app = FastAPI()

    with patch(f"{module}.get_user_from_request", return_value=None), patch(
        f"{module}.show_error_page", return_value=HTMLResponse("<html>404</html>", 404)
    ) as show_page:
        serve_default_404(app, MagicMock(), auth_config)
        response = TestClient(app).get(path)

    assert response.status_code == 404
    assert show_page.called is expect_html_page
