"""Shared app/client fixtures for the chat API route tests.

The ASGI app is cached across tests: building it walks the whole route
tree, and every test here drives the same one.
"""

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
    with (
        patch(
            "zrb.runner.chat.chat_api_route.run_chat_session", new_callable=AsyncMock
        ),
        patch("zrb.llm.agent.common.create_agent"),
    ):
        yield


@pytest.fixture
def app():
    global _cached_app
    if _cached_app is None:
        mock_root = MagicMock()
        mock_root.name = "root"
        mock_root.tasks = []
        mock_root.groups = []
        mock_root.extract_node.return_value = (MagicMock(), ["llm", "chat"], [])
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


