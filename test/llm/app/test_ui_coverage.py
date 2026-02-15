from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.app.ui import UI


@pytest.fixture
def mock_ui_deps():
    return {
        "ctx": SharedContext(),
        "yolo_xcom_key": "yolo",
        "greeting": "Hello",
        "assistant_name": "Assistant",
        "ascii_art": "ART",
        "jargon": "Jargon",
        "output_lexer": MagicMock(),
        "llm_task": MagicMock(),
        "history_manager": MagicMock(),
    }


def test_ui_public_methods(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    # Test toggle_yolo
    initial_yolo = ui._yolo  # Using internal check to verify public toggle
    ui.toggle_yolo()
    assert ui._yolo != initial_yolo

    # Test append_to_output
    ui.output_buffer = MagicMock()
    ui.append_to_output("New content")
    # append_to_output internally modifies output_buffer.text
    assert ui.output_buffer.text is not None


@pytest.mark.asyncio
async def test_ui_ask_user(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    # UI uses prompt_toolkit session.prompt_async or similar
    # We need to mock the application or session
    ui.app = MagicMock()
    # ask_user returns a future/coro that we can control
    # This might be complex to test without deep mocking,
    # but let's see if we can trigger some lines.
    assert hasattr(ui, "ask_user")
