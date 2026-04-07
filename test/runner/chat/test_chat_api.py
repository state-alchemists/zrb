"""Tests for chat_api_route.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from zrb.config.web_auth_config import web_auth_config
from zrb.runner.cli import cli
from zrb.runner.web_app import create_web_app
from zrb.session_state_logger.session_state_logger_factory import session_state_logger


@pytest.fixture
def app():
    return create_web_app(
        root_group=cli,
        web_auth_config=web_auth_config,
        session_state_logger=session_state_logger,
    )


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient):
    response = await client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient):
    response = await client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "session_name" in data


@pytest.mark.asyncio
async def test_create_session_with_id(client: AsyncClient):
    session_id = "test-session-123"
    response = await client.post(
        "/api/v1/chat/sessions", json={"session_id": session_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient):
    session_id = "test-session-delete"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_nonexistent_session(client: AsyncClient):
    response = await client.delete("/api/v1/chat/sessions/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_session_status(client: AsyncClient):
    session_id = "test-session-status"
    response = await client.get(f"/api/v1/chat/sessions/{session_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False


@pytest.mark.asyncio
async def test_session_status_after_create(client: AsyncClient):
    session_id = "test-session-status-2"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.get(f"/api/v1/chat/sessions/{session_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert "is_processing" in data
    assert "has_pending_approvals" in data


@pytest.mark.asyncio
async def test_approval_endpoint(client: AsyncClient):
    session_id = "test-session-approval"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.get(f"/api/v1/chat/sessions/{session_id}/approval")
    assert response.status_code == 200
    data = response.json()
    assert "pending_approvals" in data
    assert "is_waiting_for_edit" in data


@pytest.mark.asyncio
async def test_get_messages_nonexistent(client: AsyncClient):
    response = await client.get("/api/v1/chat/sessions/nonexistent-session/messages")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_message_creates_session(client: AsyncClient):
    response = await client.post(
        "/api/v1/chat/sessions/new-session-xyz/messages", json={"message": "Hello"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "sent"


@pytest.mark.asyncio
async def test_post_message_with_session(client: AsyncClient):
    session_id = "test-post-msg-session"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages", json={"message": "Test message"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_multi_session_isolation(client: AsyncClient):
    import uuid

    prefix = uuid.uuid4().hex[:8]
    session1 = f"test-multi-1-{prefix}"
    session2 = f"test-multi-2-{prefix}"

    await client.post("/api/v1/chat/sessions", json={"session_id": session1})
    await client.post("/api/v1/chat/sessions", json={"session_id": session2})

    status1 = await client.get(f"/api/v1/chat/sessions/{session1}/status")
    status2 = await client.get(f"/api/v1/chat/sessions/{session2}/status")

    assert status1.json()["exists"] is True
    assert status2.json()["exists"] is True


@pytest.mark.asyncio
async def test_chat_page(client: AsyncClient):
    response = await client.get("/ui/chat")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_page_with_slash(client: AsyncClient):
    response = await client.get("/ui/chat/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_sessions_pagination(client: AsyncClient):
    response = await client.get("/api/v1/chat/sessions?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "page" in data
    assert "limit" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_multiple_sessions(client: AsyncClient):
    for i in range(3):
        session_id = f"test-multi-{i}"
        response = await client.post(
            "/api/v1/chat/sessions", json={"session_id": session_id}
        )
        assert response.status_code == 200


# ─── get_messages with timestamp ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_messages_with_timestamp(client: AsyncClient):
    """Cover lines 101-102: message with timestamp field serialized to string."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-msg-timestamp"

    with patch.object(
        sm,
        "get_messages",
        return_value=[
            {"role": "user", "content": "hello", "timestamp": "2024-01-01T00:00:00"},
            {"role": "assistant", "content": "hi", "timestamp": None},
        ],
    ):
        response = await client.get(f"/api/v1/chat/sessions/{session_id}/messages")

    assert response.status_code == 200
    data = response.json()
    msgs = data["messages"]
    assert any("timestamp" in m for m in msgs if m.get("timestamp"))


# ─── approval action handling ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approval_action_json_edit_handled(client: AsyncClient):
    """Cover lines 130-140: JSON edit response when waiting for edit."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-approval-json-edit"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    with patch.object(sm, "is_waiting_for_edit", return_value=True), patch.object(
        sm,
        "handle_approval_response",
        return_value={"handled": True, "type": "edit"},
    ):
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": {"key": "value"}, "isApprovalAction": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_handled"
    assert data["type"] == "edit"


@pytest.mark.asyncio
async def test_approval_action_regular_response_handled(client: AsyncClient):
    """Cover lines 142-152: regular approval response (y/n) handled."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-approval-regular"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    with patch.object(sm, "is_waiting_for_edit", return_value=False), patch.object(
        sm,
        "handle_approval_response",
        return_value={"handled": True, "type": "approval"},
    ):
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "y", "isApprovalAction": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_handled"
    assert data["type"] == "approval"


@pytest.mark.asyncio
async def test_approval_action_waiting_edit_non_json_returns_400(client: AsyncClient):
    """Cover lines 154-159: waiting for edit but non-JSON message → 400."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-approval-waiting-edit"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    with patch.object(sm, "is_waiting_for_edit", return_value=True), patch.object(
        sm,
        "handle_approval_response",
        return_value={"handled": False},
    ):
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "not-json", "isApprovalAction": True},
        )

    assert response.status_code == 400
    assert "edit" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_approval_action_pending_but_not_handled_returns_400(client: AsyncClient):
    """Cover lines 161-166: pending approvals exist but response not handled → 400."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-approval-pending"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    with patch.object(sm, "is_waiting_for_edit", return_value=False), patch.object(
        sm, "handle_approval_response", return_value={"handled": False}
    ), patch.object(sm, "has_pending_approvals", return_value=True):
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "invalid", "isApprovalAction": True},
        )

    assert response.status_code == 400
    assert "pending" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_post_dict_message_converted_to_json(client: AsyncClient):
    """Cover line 171: dict message is JSON-serialized before sending."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-dict-message"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    sent_messages = []

    original_send = sm.send_input

    async def capture_send(sid, text):
        sent_messages.append(text)
        return True

    with patch.object(sm, "send_input", side_effect=capture_send):
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": {"foo": "bar"}},
        )

    assert response.status_code == 200
    assert len(sent_messages) == 1
    import json as json_mod

    parsed = json_mod.loads(sent_messages[0])
    assert parsed["foo"] == "bar"


# ─── GET /approval with editing_args ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_approval_endpoint_returns_editing_args(client: AsyncClient):
    """Cover line 186: get_editing_args called when waiting for edit."""
    from zrb.runner.chat.chat_session_manager import ChatSessionManager

    sm = ChatSessionManager.get_instance_sync()
    session_id = "test-approval-editing-args"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})

    with patch.object(sm, "is_waiting_for_edit", return_value=True), patch.object(
        sm, "get_editing_args", return_value={"param": "value"}
    ), patch.object(sm, "get_pending_approvals", return_value=[]):
        response = await client.get(f"/api/v1/chat/sessions/{session_id}/approval")

    assert response.status_code == 200
    data = response.json()
    assert data["is_waiting_for_edit"] is True
    assert data["editing_args"] == {"param": "value"}
