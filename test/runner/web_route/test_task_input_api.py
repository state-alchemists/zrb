"""Tests for task_input_api_route.py."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.task_input_api_route import serve_task_input_api
from zrb.task.any_task import AnyTask


@pytest.fixture
def web_auth_config():
    return WebAuthConfig(
        secret_key="test-secret-key-for-testing-only-32-chars",
        access_token_expire_minutes=30,
        refresh_token_expire_minutes=10080,
    )


@pytest.fixture
def root_group():
    group = MagicMock(spec=AnyGroup)
    group.name = "root"
    return group


class TestTaskInputAPI:
    """Test serve_task_input_api endpoint."""

    def test_task_not_found(self, web_auth_config, root_group):
        """Returns 404 when task/group not found."""
        from zrb.util.group import NodeNotFoundError

        app = FastAPI()
        serve_task_input_api(app, root_group, web_auth_config)
        client = TestClient(app)

        with patch(
            "zrb.runner.web_route.task_input_api_route.get_user_from_request"
        ) as mock_user:
            mock_user.return_value = MagicMock(can_access_task=lambda t: True)

            with patch(
                "zrb.runner.web_route.task_input_api_route.extract_node_from_args",
                side_effect=NodeNotFoundError("not found"),
            ):
                response = client.get("/api/v1/task-inputs/nonexistent")

        assert response.status_code == 404

    def test_task_access_forbidden(self, web_auth_config, root_group):
        """Returns 403 when user cannot access the task."""
        task = MagicMock(spec=AnyTask)
        task.name = "protected_task"

        app = FastAPI()
        serve_task_input_api(app, root_group, web_auth_config)
        client = TestClient(app)

        user = MagicMock()
        user.can_access_task.return_value = False

        with patch(
            "zrb.runner.web_route.task_input_api_route.get_user_from_request"
        ) as mock_user:
            mock_user.return_value = user

            with patch(
                "zrb.runner.web_route.task_input_api_route.extract_node_from_args",
                return_value=(task, ["task"], []),
            ):
                response = client.get("/api/v1/task-inputs/protected_task")

        assert response.status_code == 403

    def test_task_returns_defaults(self, web_auth_config, root_group):
        """Returns task default inputs when user has access."""
        task = MagicMock(spec=AnyTask)
        task.name = "test_task"

        app = FastAPI()
        serve_task_input_api(app, root_group, web_auth_config)
        client = TestClient(app)

        user = MagicMock()
        user.can_access_task.return_value = True

        with patch(
            "zrb.runner.web_route.task_input_api_route.get_user_from_request"
        ) as mock_user:
            mock_user.return_value = user

            with patch(
                "zrb.runner.web_route.task_input_api_route.extract_node_from_args",
                return_value=(task, ["task"], []),
            ):
                with patch(
                    "zrb.runner.web_route.task_input_api_route.get_task_str_kwargs",
                    return_value={"input1": "default_value"},
                ):
                    response = client.get("/api/v1/task-inputs/test_task")

        assert response.status_code == 200

    def test_node_is_group_returns_404(self, web_auth_config, root_group):
        """Returns 404 when extracted node is a group, not a task."""
        group = MagicMock(spec=AnyGroup)
        group.name = "some_group"

        app = FastAPI()
        serve_task_input_api(app, root_group, web_auth_config)
        client = TestClient(app)

        user = MagicMock()

        with patch(
            "zrb.runner.web_route.task_input_api_route.get_user_from_request"
        ) as mock_user:
            mock_user.return_value = user

            with patch(
                "zrb.runner.web_route.task_input_api_route.extract_node_from_args",
                return_value=(group, ["group"], []),
            ):
                response = client.get("/api/v1/task-inputs/some_group")

        assert response.status_code == 404
