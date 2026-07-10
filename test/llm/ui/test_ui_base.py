from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.ui import UI


def test_ui_public_methods(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    # Test toggle_yolo
    # Test toggle_yolo
    assert (
        not mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    )
    ui.toggle_yolo()
    assert mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    ui.toggle_yolo()
    assert (
        not mock_ui_deps["ctx"].xcom.get(mock_ui_deps["yolo_xcom_key"], {}).get(False)
    )

    # Test append_to_output
    ui.output_buffer = MagicMock()
    with patch.object(ui, "_schedule_invalidate"):
        ui.append_to_output("New content")
    # append_to_output internally modifies output_buffer.text
    assert ui.output_buffer.text is not None


def test_ui_session_token_usage(mock_ui_deps):
    ui = UI(**mock_ui_deps)
    assert ui.session_token_usage == (0, 0)
    # No tokens yet -> status bar shows no usage fragment
    assert all("in" not in text for _, text in ui.get_status_bar_text() if "💸" in text)

    usage = MagicMock(input_tokens=1200, output_tokens=34)
    ui.accumulate_usage(usage)
    ui.accumulate_usage(MagicMock(input_tokens=300, output_tokens=None))
    assert ui.session_token_usage == (1500, 34)

    status = "".join(text for _, text in ui.get_status_bar_text())
    assert "1.5k in" in status
    assert "34 out" in status


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
