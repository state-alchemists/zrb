from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.yolo import make_yolo_inheritance_checker


def test_yolo_inheritance_current_yolo_true():
    with patch("zrb.llm.agent.run.runtime_state.get_current_yolo", return_value=True):
        checker = make_yolo_inheritance_checker()
        assert checker() is True


def test_yolo_inheritance_via_ui_yolo():
    with (
        patch("zrb.llm.agent.run.runtime_state.get_current_yolo", return_value=False),
        patch("zrb.llm.agent.run.runtime_state.get_current_ui") as mock_get_ui,
    ):

        mock_ui = MagicMock()
        mock_ui.yolo = True
        mock_get_ui.return_value = mock_ui

        checker = make_yolo_inheritance_checker()
        assert checker() is True


def test_yolo_inheritance_via_ui_yolo_false():
    with (
        patch("zrb.llm.agent.run.runtime_state.get_current_yolo", return_value=False),
        patch("zrb.llm.agent.run.runtime_state.get_current_ui") as mock_get_ui,
    ):

        mock_ui = MagicMock()
        mock_ui.yolo = False
        mock_get_ui.return_value = mock_ui

        checker = make_yolo_inheritance_checker()
        assert checker() is False


def test_yolo_inheritance_default_false():
    with (
        patch("zrb.llm.agent.run.runtime_state.get_current_yolo", return_value=False),
        patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=None),
    ):

        checker = make_yolo_inheritance_checker()
        assert checker() is False


def test_yolo_inheritance_ui_exception():
    with (
        patch("zrb.llm.agent.run.runtime_state.get_current_yolo", return_value=False),
        patch(
            "zrb.llm.agent.run.runtime_state.get_current_ui",
            side_effect=Exception("error"),
        ),
    ):

        checker = make_yolo_inheritance_checker()
        assert checker() is False


def test_yolo_inheritance_frozenset_matches_tool():
    """Selective YOLO: tool name in frozenset → auto-approved."""
    with patch(
        "zrb.llm.agent.run.runtime_state.get_current_yolo",
        return_value=frozenset({"Read", "Write"}),
    ):
        checker = make_yolo_inheritance_checker()
        mock_tool = type("Tool", (), {"name": "Read"})()
        assert checker(mock_tool) is True


def test_yolo_inheritance_frozenset_no_match():
    """Selective YOLO: tool name NOT in frozenset → not auto-approved."""
    with patch(
        "zrb.llm.agent.run.runtime_state.get_current_yolo",
        return_value=frozenset({"Read", "Write"}),
    ):
        checker = make_yolo_inheritance_checker()
        mock_tool = type("Tool", (), {"name": "Bash"})()
        assert checker(mock_tool) is False


def test_yolo_inheritance_frozenset_no_tool_def():
    """Selective YOLO with no tool_def → False (can't determine tool name)."""
    with patch(
        "zrb.llm.agent.run.runtime_state.get_current_yolo",
        return_value=frozenset({"Read"}),
    ):
        checker = make_yolo_inheritance_checker()
        assert checker() is False


def test_yolo_inheritance_frozenset_fallback_ui():
    """Selective YOLO with no match but UI yolo is True → still approved via UI."""
    with (
        patch(
            "zrb.llm.agent.run.runtime_state.get_current_yolo",
            return_value=frozenset({"Write"}),
        ),
        patch("zrb.llm.agent.run.runtime_state.get_current_ui") as mock_get_ui,
    ):
        mock_ui = type("UI", (), {"yolo": True})()
        mock_get_ui.return_value = mock_ui
        checker = make_yolo_inheritance_checker()
        mock_tool = type("Tool", (), {"name": "Read"})()
        assert checker(mock_tool) is True
