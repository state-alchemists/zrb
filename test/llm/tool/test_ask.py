"""Tests for zrb.llm.tool.ask — interactive user-question tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.ask import (
    _build_choice_spec,
    ask_user_question,
    format_choice_spec,
    get_interactive_mode,
    set_interactive_mode,
)


@pytest.fixture(autouse=True)
def _restore_interactive_mode():
    """Each test runs against a known interactive=True baseline."""
    set_interactive_mode(True)
    try:
        yield
    finally:
        set_interactive_mode(True)


def test_tool_name_matches_llm_visible_name():
    """The LLM sees this tool as 'AskUserQuestion', matching the guidance entry."""
    assert ask_user_question.__name__ == "AskUserQuestion"


def test_ask_user_question_registers_itself_as_always_auto_approve():
    """Importing the tool self-registers it as intrinsically auto-approved.

    This is what frees AskUserQuestion from relying on a per-runner policy list
    (e.g. the builtin chat's auto_approve registrations) — the approval cascade
    approves it in every path. See ADR-0062.
    """
    from zrb.llm.tool_call.always_approve import is_always_auto_approve

    assert is_always_auto_approve("AskUserQuestion") is True


def test_build_choice_spec_carries_counter_and_header():
    spec = _build_choice_spec(
        2, 3, {"question": "Pick a DB?", "options": [{"label": "PG"}]}
    )
    assert spec["index"] == 2
    assert spec["total"] == 3
    assert spec["multi_select"] is False
    # Header is derived from the question when not given (trailing '?' stripped).
    assert spec["header"] == "Pick a DB"


def test_format_choice_spec_renders_numbered_text():
    spec = _build_choice_spec(
        1,
        1,
        {
            "question": "Which one?",
            "options": [{"label": "A", "description": "first"}, {"label": "B"}],
        },
    )
    text = format_choice_spec(spec)
    assert "[Q1] Which one?" in text
    assert "1. A — first" in text
    assert "2. B" in text
    assert "number or free-form text" in text


def test_format_choice_spec_multi_select_hint_and_counter():
    spec = _build_choice_spec(
        2, 4, {"question": "Pick", "options": [{"label": "A"}], "multi_select": True}
    )
    text = format_choice_spec(spec)
    assert "[Q2/4]" in text
    assert "comma-separated numbers" in text


@pytest.mark.asyncio
async def test_short_circuits_in_non_interactive_mode():
    set_interactive_mode(False)
    result = await ask_user_question(
        [{"question": "pick", "options": [{"label": "A"}, {"label": "B"}]}]
    )
    assert "[SYSTEM SUGGESTION]" in result
    assert "non-interactive" in result.lower()


@pytest.mark.asyncio
async def test_returns_error_when_questions_empty():
    result = await ask_user_question([])
    assert "no questions" in result.lower()


@pytest.mark.asyncio
async def test_returns_error_when_ui_unavailable():
    """In interactive mode but with no current UI, fall back to guidance."""
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=None):
        result = await ask_user_question(
            [{"question": "x", "options": [{"label": "A"}]}]
        )
    assert "[SYSTEM SUGGESTION]" in result
    assert "No UI is available" in result


@pytest.mark.asyncio
async def test_missing_required_keys_surfaces_schema_error():
    fake_ui = AsyncMock()
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question([{"options": [{"label": "A"}]}])
    assert "missing required keys" in result
    assert "question" in result
    # UI must not be called when the schema is invalid.
    fake_ui.ask_user_choice.assert_not_called()


@pytest.mark.asyncio
async def test_empty_options_surfaces_error():
    fake_ui = AsyncMock()
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question([{"question": "x", "options": []}])
    assert "options is empty" in result
    fake_ui.ask_user_choice.assert_not_called()


@pytest.mark.asyncio
async def test_resolves_numeric_pick_to_label():
    """A UI that returns a number (text-fallback path) still maps to the label."""
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "2"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "Which framework?",
                    "header": "Framework",
                    "options": [
                        {"label": "FastAPI"},
                        {"label": "Flask"},
                    ],
                }
            ]
        )
    assert "Q1 (Framework): Flask" in result
    fake_ui.ask_user_choice.assert_awaited_once()


@pytest.mark.asyncio
async def test_widget_label_answer_is_returned_verbatim():
    """A widget UI returns the chosen label directly; it survives resolution."""
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "Flask"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "Which framework?",
                    "options": [{"label": "FastAPI"}, {"label": "Flask"}],
                }
            ]
        )
    assert "Flask" in result


@pytest.mark.asyncio
async def test_returns_free_form_text_when_not_a_number():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "actually use Django"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "Which framework?",
                    "options": [{"label": "FastAPI"}, {"label": "Flask"}],
                }
            ]
        )
    assert "actually use Django" in result


@pytest.mark.asyncio
async def test_out_of_range_index_falls_through_to_raw_text():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "99"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [{"question": "x", "options": [{"label": "A"}]}]
        )
    # "99" doesn't resolve to a real option — preserved as raw input.
    assert "Q1" in result and "99" in result


@pytest.mark.asyncio
async def test_multi_select_resolves_comma_separated_indexes():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "1,3"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "Pick all that apply",
                    "options": [
                        {"label": "Tests"},
                        {"label": "Docs"},
                        {"label": "Lint"},
                    ],
                    "multi_select": True,
                }
            ]
        )
    assert "Tests, Lint" in result


@pytest.mark.asyncio
async def test_multi_select_falls_back_to_raw_when_any_token_unresolved():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = "1, banana"
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "Pick",
                    "options": [{"label": "Tests"}, {"label": "Docs"}],
                    "multi_select": True,
                }
            ]
        )
    # Mixed/unresolved input is preserved verbatim, not partially decoded.
    assert "1, banana" in result


@pytest.mark.asyncio
async def test_empty_answer_renders_no_answer_marker():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.return_value = ""
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [{"question": "x?", "options": [{"label": "A"}]}]
        )
    assert "(no answer)" in result


@pytest.mark.asyncio
async def test_falls_back_to_ask_user_when_choice_unsupported():
    """A UI predating ask_user_choice still works via the text path."""

    class LegacyUI:
        def __init__(self):
            self.prompts: list[str] = []

        async def ask_user(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return "1"

    fake_ui = LegacyUI()
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [{"question": "Pick?", "options": [{"label": "Yes"}, {"label": "No"}]}]
        )
    assert "Yes" in result
    assert fake_ui.prompts and "[Q1] Pick?" in fake_ui.prompts[0]


@pytest.mark.asyncio
async def test_keyboard_interrupt_returns_cancellation_suggestion():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.side_effect = KeyboardInterrupt()
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [{"question": "x?", "options": [{"label": "A"}]}]
        )
    assert "[SYSTEM SUGGESTION]" in result
    assert "cancelled" in result.lower()


@pytest.mark.asyncio
async def test_multiple_questions_all_get_rendered():
    fake_ui = AsyncMock()
    fake_ui.ask_user_choice.side_effect = ["1", "free text"]
    with patch("zrb.llm.agent.run.runtime_state.get_current_ui", return_value=fake_ui):
        result = await ask_user_question(
            [
                {
                    "question": "First?",
                    "header": "First",
                    "options": [{"label": "Yes"}, {"label": "No"}],
                },
                {
                    "question": "Second?",
                    "header": "Second",
                    "options": [{"label": "X"}],
                },
            ]
        )
    assert "Q1 (First): Yes" in result
    assert "Q2 (Second): free text" in result
    assert fake_ui.ask_user_choice.await_count == 2


def test_get_set_interactive_mode_round_trip():
    set_interactive_mode(False)
    assert get_interactive_mode() is False
    set_interactive_mode(True)
    assert get_interactive_mode() is True
