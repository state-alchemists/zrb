import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.util.conversation_naming import (
    ConversationNamingError,
    sanitize_slug,
    should_auto_name,
    suggest_slug,
    with_slug,
)


@pytest.fixture(autouse=True)
def _auto_naming_on(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_AUTO_NAME_ENABLED", "on")


def test_sanitize_slug_keeps_a_short_lowercase_slug():
    assert sanitize_slug('  "Fix: Login Timeout!" ') == "fix-login-timeout"
    assert len(sanitize_slug("a" * 100)) <= 40
    assert sanitize_slug("???") == ""


def test_a_slug_that_looks_like_a_sub_agent_transcript_is_refused():
    with pytest.raises(ConversationNamingError):
        with_slug("trim-coil-1234", "sub-reviewer-abcd1234")


def test_with_slug_appends_the_topic():
    assert with_slug("trim-coil-1234", "greetings") == "trim-coil-1234-greetings"


def test_only_a_generated_name_is_auto_named(monkeypatch):
    assert should_auto_name("bold-arch-1234") is True
    assert should_auto_name("my-session") is False
    assert should_auto_name("bold-arch-1234-greetings") is False
    monkeypatch.setenv("ZRB_LLM_AUTO_NAME_ENABLED", "off")
    assert should_auto_name("bold-arch-1234") is False


@pytest.mark.asyncio
async def test_suggest_slug_sanitises_the_model_answer():
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Greetings!"))
    with (
        patch("zrb.llm.agent.common.create_agent", return_value=agent),
        patch(
            "zrb.llm.util.conversation_naming.resolve_configured_small_model",
            return_value="m",
        ),
    ):
        assert await suggest_slug("hello there") == "greetings"


@pytest.mark.asyncio
async def test_suggest_slug_raises_when_the_model_fails():
    with patch(
        "zrb.llm.util.conversation_naming.resolve_configured_small_model",
        side_effect=RuntimeError("no credentials"),
    ):
        with pytest.raises(ConversationNamingError):
            await suggest_slug("hello")


def test_rename_moves_the_history_file_and_leaves_sub_agent_transcripts(tmp_path):
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    from zrb.llm.history_manager.file_history_manager import FileHistoryManager

    manager = FileHistoryManager(str(tmp_path))
    messages = [ModelRequest(parts=[UserPromptPart(content="hi")])]
    sub = "bold-arch-1234-sub-reviewer-abcd1234"
    for name in ("bold-arch-1234", sub):
        manager.update(name, messages)
        manager.save(name, write_backup=False)

    manager.rename("bold-arch-1234", "bold-arch-1234-greetings")

    assert manager.load("bold-arch-1234-greetings")
    assert not os.path.exists(tmp_path / "bold-arch-1234.json")
    assert manager.load(sub)  # keyed by the conversation key, untouched
