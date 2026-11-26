"""Smoke tests for page routes and their selected templates."""

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

    with (
        patch(f"{module}.get_jinja_env", return_value=rendered),
        patch(f"{module}.get_user_from_request", return_value=None),
        patch(f"{module}.get_html_subgroup_info", return_value=""),
        patch(f"{module}.get_html_subtask_info", return_value=""),
        patch(f"{module}.get_html_auth_link", return_value=""),
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

    with (
        patch(f"{module}.get_jinja_env", return_value=rendered),
        patch(f"{module}.get_user_from_request", return_value=None),
        patch(f"{module}.get_html_auth_link", return_value=""),
    ):
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
    """UI paths get the rendered error page; API paths get JSON."""
    module = "zrb.runner.web_route.error_page.serve_default_404"
    app = FastAPI()

    with (
        patch(f"{module}.get_user_from_request", return_value=None),
        patch(
            f"{module}.show_error_page",
            return_value=HTMLResponse("<html>404</html>", 404),
        ) as show_page,
    ):
        serve_default_404(app, MagicMock(), auth_config)
        response = TestClient(app).get(path)

    assert response.status_code == 404
    assert show_page.called is expect_html_page


def test_docs_page_renders():
    """`/docs` serves the Swagger UI without needing auth."""
    from zrb.runner.web_route.docs_route import serve_docs

    app = FastAPI()
    serve_docs(app)
    response = TestClient(app).get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_node_page_routes_to_group_task_and_errors(auth_config):
    """The /ui/{path} catch-all dispatches on the resolved node type and
    falls back to error pages for unknown/forbidden/undefined paths."""
    from contextlib import ExitStack

    from zrb.group.any_group import AnyGroup, AnyTask, NodeNotFoundError
    from zrb.runner.web_route.node_page.node_page_route import (
        serve_node_page,
    )

    module = "zrb.runner.web_route.node_page.node_page_route"
    task = MagicMock(spec=AnyTask)
    group = MagicMock(spec=AnyGroup)
    neither = object()
    anon = MagicMock()
    anon.can_access_task.return_value = True
    anon.can_access_group.return_value = True
    forbidden = MagicMock()
    forbidden.can_access_task.return_value = False
    forbidden.can_access_group.return_value = False

    def request(root_group, user, path):
        with ExitStack() as stack:
            app = FastAPI()
            stack.enter_context(
                patch(f"{module}.show_task_page", return_value=HTMLResponse("task"))
            )
            stack.enter_context(
                patch(f"{module}.show_group_page", return_value=HTMLResponse("group"))
            )
            stack.enter_context(
                patch(
                    f"{module}.show_error_page",
                    side_effect=lambda user, rg, code, msg: HTMLResponse(
                        f"error-{code}", status_code=code
                    ),
                )
            )
            stack.enter_context(
                patch(f"{module}.get_user_from_request", return_value=user)
            )
            serve_node_page(app, root_group, auth_config)
            return TestClient(app).get(path)

    # A task node renders the task page.
    root = MagicMock()
    root.extract_node.return_value = (task, ["mytask"], [])
    assert request(root, anon, "/ui/mytask").text == "task"

    # A group node renders the group page.
    root = MagicMock()
    root.extract_node.return_value = (group, ["sub"], [])
    assert request(root, anon, "/ui/sub").text == "group"

    # Unknown node -> 404.
    root = MagicMock()
    root.extract_node.side_effect = NodeNotFoundError("nope")
    assert request(root, anon, "/ui/nope").status_code == 404

    # Forbidden task/group -> 403.
    root = MagicMock()
    root.extract_node.return_value = (task, ["mytask"], [])
    assert request(root, forbidden, "/ui/mytask").status_code == 403
    root = MagicMock()
    root.extract_node.return_value = (group, ["sub"], [])
    assert request(root, forbidden, "/ui/sub").status_code == 403

    # A node that is neither task nor group -> 404.
    root = MagicMock()
    root.extract_node.return_value = (neither, ["odd"], [])
    assert request(root, anon, "/ui/odd").status_code == 404


def test_node_page_hides_a_cli_only_task_behind_a_generic_404(auth_config):
    """A CLI-only task is not on the web, and the page must not name it: the
    error's `Did you mean` candidates include the hidden names of its group."""
    from contextlib import ExitStack

    from zrb.group.group import Group
    from zrb.runner.web_route.node_page.node_page_route import serve_node_page
    from zrb.task.base.base_task import BaseTask

    module = "zrb.runner.web_route.node_page.node_page_route"
    root = Group(name="zrb")
    root.add_task(BaseTask(name="start-server", cli_only=True))
    root.add_task(BaseTask(name="deploy"))
    anon = MagicMock()
    anon.can_access_task.return_value = True
    anon.can_access_group.return_value = True
    messages = []

    def error_page(user, root_group, status_code, message):
        messages.append((status_code, message))
        return HTMLResponse(f"error-{status_code}", status_code=status_code)

    def request(path):
        with ExitStack() as stack:
            app = FastAPI()
            stack.enter_context(
                patch(f"{module}.show_task_page", return_value=HTMLResponse("task"))
            )
            stack.enter_context(
                patch(f"{module}.show_error_page", side_effect=error_page)
            )
            stack.enter_context(
                patch(f"{module}.get_user_from_request", return_value=anon)
            )
            serve_node_page(app, root, auth_config)
            return TestClient(app).get(path)

    # The ordinary sibling still renders: this is not a blanket refusal.
    assert request("/ui/deploy").text == "task"

    # The hidden task's own URL, and a near miss at it, both say only this.
    assert request("/ui/start-server").status_code == 404
    assert request("/ui/start-serve").status_code == 404
    assert messages == [(404, "Not found"), (404, "Not found")]


def test_node_page_undefined_path_is_422(auth_config):
    """/ui with no path at all is a defined error, not a crash."""
    from zrb.runner.web_route.node_page.node_page_route import (
        serve_node_page,
    )

    module = "zrb.runner.web_route.node_page.node_page_route"
    app = FastAPI()
    with (
        patch(
            f"{module}.show_error_page",
            side_effect=lambda user, rg, code, msg: HTMLResponse(
                f"error-{code}", status_code=code
            ),
        ),
        patch(f"{module}.get_user_from_request", return_value=None),
    ):
        serve_node_page(app, MagicMock(), auth_config)
        response = TestClient(app).get("/ui/")
    assert response.status_code == 422
