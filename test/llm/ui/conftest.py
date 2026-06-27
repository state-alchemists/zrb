from unittest.mock import MagicMock

import pytest

from zrb.context.shared_context import SharedContext


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
