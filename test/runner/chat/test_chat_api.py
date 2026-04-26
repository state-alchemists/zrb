"""Tests for chat_api_route.py."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from zrb.config.web_auth_config import web_auth_config
from zrb.runner.web_app import create_web_app
from zrb.session_state_logger.session_state_logger_factory import session_state_logger

# Module-level cache for the app
_cached_app = None
_mock_sm = MagicMock()


@pytest.fixture(autouse=True)
def mock_heavy_runners():
    with patch(
        "zrb.runner.chat.chat_api_route._run_chat_session", new_callable=AsyncMock
    ), patch("zrb.llm.agent.common.create_agent"):
        yield


@pytest.fixture
def app():
    global _cached_app
    if _cached_app is None:
        mock_root = MagicMock()
        mock_root.name = "root"
        mock_root.tasks = []
        mock_root.groups = []
        # We patch get_instance_sync before creating the app so serve_chat_api gets our mock
        with patch(
            "zrb.runner.chat.chat_api_route.ChatSessionManager.get_instance_sync",
            return_value=_mock_sm,
        ):
            _cached_app = create_web_app(
                root_group=mock_root,
                web_auth_config=web_auth_config,
                session_state_logger=session_state_logger,
            )
    return _cached_app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient):
    _mock_sm.get_sessions.return_value = []
    _mock_sm.get_sessions_count.return_value = 0
    response = await client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient):
    mock_session = MagicMock()
    mock_session.session_id = "test-s"
    mock_session.session_name = "test-n"
    _mock_sm.create_session = AsyncMock(return_value=mock_session)

    response = await client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient):
    _mock_sm.remove_session = AsyncMock(return_value=True)
    response = await client.delete("/api/v1/chat/sessions/test")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_session_status(client: AsyncClient):
    _mock_sm.get_session.return_value = None
    response = await client.get("/api/v1/chat/sessions/none/status")
    assert response.status_code == 200
    assert response.json()["exists"] is False


@pytest.mark.asyncio
async def test_approval_endpoint(client: AsyncClient):
    _mock_sm.get_pending_approvals.return_value = []
    _mock_sm.is_waiting_for_edit.return_value = False
    response = await client.get("/api/v1/chat/sessions/test/approval")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_messages(client: AsyncClient):
    _mock_sm.get_messages.return_value = [{"role": "user", "content": "hi"}]
    response = await client.get("/api/v1/chat/sessions/test/messages")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_message_creates_session(client: AsyncClient):
    _mock_sm.get_session.return_value = None
    mock_session = MagicMock()
    _mock_sm.create_session = AsyncMock(return_value=mock_session)
    _mock_sm.send_input = AsyncMock()

    response = await client.post(
        "/api/v1/chat/sessions/new-session-xyz/messages", json={"message": "Hello"}
    )
    assert response.status_code == 200
    assert response.json().get("status") == "sent"


@pytest.mark.asyncio
async def test_approval_action_json_edit_handled(client: AsyncClient):
    _mock_sm.get_session.return_value = MagicMock()
    _mock_sm.is_waiting_for_edit.return_value = True
    _mock_sm.handle_approval_response.return_value = {"handled": True, "type": "edit"}

    response = await client.post(
        "/api/v1/chat/sessions/test/messages",
        json={"message": {"key": "value"}, "isApprovalAction": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approval_handled"


@pytest.mark.asyncio
async def test_approval_action_waiting_edit_non_json_returns_400(client: AsyncClient):
    _mock_sm.get_session.return_value = MagicMock()
    _mock_sm.is_waiting_for_edit.return_value = True
    _mock_sm.handle_approval_response.return_value = {"handled": False}

    response = await client.post(
        "/api/v1/chat/sessions/test/messages",
        json={"message": "not a dict", "isApprovalAction": True},
    )

    assert response.status_code == 400
    assert "JSON" in response.json()["error"]


@pytest.mark.asyncio
async def test_approval_action_pending_but_not_handled_returns_400(client: AsyncClient):
    _mock_sm.get_session.return_value = MagicMock()
    _mock_sm.is_waiting_for_edit.return_value = False
    _mock_sm.handle_approval_response.return_value = {"handled": False}
    _mock_sm.has_pending_approvals.return_value = True

    response = await client.post(
        "/api/v1/chat/sessions/test/messages",
        json={"message": "y", "isApprovalAction": True},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_approval_endpoint_returns_editing_args(client: AsyncClient):
    _mock_sm.get_pending_approvals.return_value = []
    _mock_sm.is_waiting_for_edit.return_value = True
    _mock_sm.get_editing_args.return_value = {"k": "v"}

    response = await client.get("/api/v1/chat/sessions/test/approval")

    assert response.status_code == 200
    assert response.json()["editing_args"] == {"k": "v"}
