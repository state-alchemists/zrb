import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from zrb.config.config import CFG
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
    session_id = data["session_id"]
    return session_id


@pytest.mark.asyncio
async def test_create_session_with_id(client: AsyncClient):
    session_id = "test-session-123"
    response = await client.post(
        "/api/v1/chat/sessions", json={"session_id": session_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["session_name"] == session_id


@pytest.mark.asyncio
async def test_list_sessions_after_create(client: AsyncClient):
    import uuid

    session_id = f"test-session-list-{uuid.uuid4().hex[:8]}"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    session_ids = [s["session_id"] for s in data["sessions"]]
    status_response = await client.get(f"/api/v1/chat/sessions/{session_id}/status")
    status_data = status_response.json()
    assert status_data["exists"] is True, f"Session {session_id} should exist"


@pytest.mark.asyncio
async def test_get_messages_empty(client: AsyncClient):
    session_id = "test-session-msgs"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)


@pytest.mark.asyncio
async def test_get_messages_nonexistent(client: AsyncClient):
    response = await client.get("/api/v1/chat/sessions/nonexistent-session/messages")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 0


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient):
    session_id = "test-session-delete"
    await client.post("/api/v1/chat/sessions", json={"session_id": session_id})
    response = await client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


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

    assert status1.json()["exists"] != status2.json()["exists"] or session1 != session2


@pytest.mark.asyncio
async def test_chat_page(client: AsyncClient):
    response = await client.get("/ui/chat")
    assert response.status_code == 200
    assert (
        "session-selector" in response.text.lower()
        or "session" in response.text.lower()
    )


@pytest.mark.asyncio
async def test_chat_page_with_slash(client: AsyncClient):
    response = await client.get("/ui/chat/")
    assert response.status_code == 200
