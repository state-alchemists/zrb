from unittest.mock import MagicMock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.ui.ui_config import UIConfig


@pytest.fixture
def mock_ui_deps():
    return {
        "ctx": SharedContext(),
        "ui_config": UIConfig(yolo_xcom_key="yolo", assistant_name="Assistant"),
        "greeting": "Hello",
        "ascii_art": "ART",
        "jargon": "Jargon",
        "output_lexer": MagicMock(),
        "llm_task": MagicMock(),
        "history_manager": MagicMock(),
    }
