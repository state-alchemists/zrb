from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.group.any_group import NodeNotFoundError
from zrb.runner.web_route.task_session_api_route import serve_task_session_api


@pytest.fixture
def app_deps():
    app = FastAPI()
    root_group = MagicMock()
    web_auth_config = MagicMock()
    session_state_logger = MagicMock()
    coroutines = []

    serve_task_session_api(
        app, root_group, web_auth_config, session_state_logger, coroutines
    )
    client = TestClient(app)
    return client, root_group, web_auth_config, session_state_logger, coroutines


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.can_access_task.return_value = True
    return user


def test_create_new_task_session_api_not_found_node(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    root_group.extract_node.side_effect = NodeNotFoundError

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.post("/api/v1/task-sessions/my/task", json={})
        assert response.status_code == 404


def test_create_new_task_session_api_forbidden(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    mock_user.can_access_task.return_value = False

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["sess1"])

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.post("/api/v1/task-sessions/my/task/sess1", json={})
        assert response.status_code == 403


def test_create_new_task_session_api_success(app_deps, mock_user):
    client, root_group, _, _, coroutines = app_deps

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    mock_task.async_run = AsyncMock()
    root_group.extract_node.return_value = (mock_task, MagicMock(), [])

    with (
        patch(
            "zrb.runner.web_route.task_session_api_route.get_user_from_request",
            new_callable=AsyncMock,
            return_value=mock_user,
        ),
        patch("asyncio.create_task") as mock_create_task,
    ):

        mock_coro = MagicMock()
        mock_create_task.return_value = mock_coro
        response = client.post("/api/v1/task-sessions/my/task", json={"input1": "val1"})
        assert response.status_code == 200
        assert "session_name" in response.json()
        assert len(coroutines) == 1
        assert coroutines[0] == mock_coro

        # Clean up the unawaited coroutine to prevent RuntimeWarning
        coro = mock_create_task.call_args[0][0]
        coro.close()


def test_create_new_task_session_api_not_task(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    root_group.extract_node.return_value = (MagicMock(), MagicMock(), [])

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.post("/api/v1/task-sessions/my/group", json={})
        assert response.status_code == 404


def test_get_task_session_api_list(app_deps, mock_user):
    client, root_group, _, session_state_logger, _ = app_deps

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    mock_task.inputs = []
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["list"])
    root_group.get_node_path.return_value = "my.task"

    from zrb.session_state_log.session_state_log import SessionStateLogList

    mock_list = SessionStateLogList(total=0, data=[])
    session_state_logger.list.return_value = mock_list

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/list")
        assert response.status_code == 200
        assert response.json()["total"] == 0


def test_get_task_session_api_read(app_deps, mock_user):
    client, root_group, _, session_state_logger, _ = app_deps

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    mock_task.inputs = []
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["sess1"])
    root_group.get_node_path.return_value = ["t1"]

    from zrb.session_state_log.session_state_log import SessionStateLog

    mock_log = SessionStateLog(
        name="sess1",
        start_time="2021-01-01T00:00:00",
        main_task_name="t1",
        path=["t1"],
        input={},
        final_result="",
        finished=True,
        log=[],
        task_status={},
    )
    session_state_logger.read.return_value = mock_log

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/sess1")
        assert response.status_code == 200
        assert response.json()["name"] == "sess1"


def test_get_task_session_api_read_foreign_session(app_deps, mock_user):
    """A session log recorded for another task must not be readable."""
    client, root_group, _, session_state_logger, _ = app_deps

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    mock_task.inputs = []
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["sess1"])
    root_group.get_node_path.return_value = ["this", "task"]

    from zrb.session_state_log.session_state_log import SessionStateLog

    mock_log = SessionStateLog(
        name="sess1",
        start_time="2021-01-01T00:00:00",
        main_task_name="other",
        path=["other", "task"],
        input={},
        final_result="secret-result",
        finished=True,
        log=[],
        task_status={},
    )
    session_state_logger.read.return_value = mock_log

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/sess1")
        assert response.status_code == 404


def test_get_task_session_api_read_missing_session(app_deps, mock_user):
    """A session name that does not resolve to a log yields 404, not 500."""
    client, root_group, _, session_state_logger, _ = app_deps

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    mock_task.inputs = []
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["nope"])
    root_group.get_node_path.return_value = ["t1"]
    session_state_logger.read.side_effect = FileNotFoundError("no such file")

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/nope")
        assert response.status_code == 404


def test_get_task_session_api_forbidden(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    mock_user.can_access_task.return_value = False

    from zrb.task.any_task import AnyTask

    mock_task = MagicMock(spec=AnyTask)
    root_group.extract_node.return_value = (mock_task, MagicMock(), ["sess1"])

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/sess1")
        assert response.status_code == 403


def test_get_task_session_api_not_found(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    root_group.extract_node.side_effect = NodeNotFoundError

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/task/sess1")
        assert response.status_code == 404


def test_get_task_session_api_not_task(app_deps, mock_user):
    client, root_group, _, _, _ = app_deps
    root_group.extract_node.return_value = (MagicMock(), MagicMock(), ["sess1"])

    with patch(
        "zrb.runner.web_route.task_session_api_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/api/v1/task-sessions/my/group/sess1")
        assert response.status_code == 404
