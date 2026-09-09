import re
from unittest import mock

import pytest

from zrb.builtin import config as config_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _printed_text(mock_print) -> str:
    """Joined, ANSI-stripped text of everything the task printed."""
    raw = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    return _ANSI.sub("", raw)


@pytest.fixture
def mock_print():
    return mock.MagicMock()


@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=mock.MagicMock())


@pytest.mark.asyncio
async def test_explain_config_all_entries(session, mock_print):
    await config_module.explain_config.async_run(session=session, kwargs={})

    printed = _printed_text(mock_print)
    # Every knob is rendered as a name line plus an indented description.
    assert "ZRB_" in printed
    assert "ZRB_LLM_MODEL" in printed


@pytest.mark.asyncio
async def test_explain_config_no_match(session, mock_print):
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "definitely-not-a-real-config-xyz"}
    )

    printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    assert "No matching configuration entries found." in printed


@pytest.mark.asyncio
async def test_explain_config_keyword_filters(session, mock_print):
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "llm"}
    )

    printed = _printed_text(mock_print)
    assert "LLM" in printed.upper()
    assert "ZRB_WEB_HTTP_PORT" not in printed


@pytest.mark.asyncio
async def test_explain_config_masks_set_secret(session, mock_print, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_API_KEY", "sk-super-secret-do-not-show")
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "llm_api_key"}
    )

    printed = _printed_text(mock_print)
    # The value is masked: shown as [set], never the actual secret.
    assert "sk-super-secret-do-not-show" not in printed
    assert "[set]" in printed


@pytest.mark.asyncio
async def test_explain_config_shows_unset_secret(session, mock_print, monkeypatch):
    monkeypatch.delenv("ZRB_LLM_API_KEY", raising=False)
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "llm_api_key"}
    )

    assert "[unset]" in _printed_text(mock_print)


@pytest.mark.asyncio
async def test_explain_config_renders_options_as_bullets(session, mock_print):
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "search_internet_method"}
    )

    printed = _printed_text(mock_print)
    # Enumerated options are rendered as a bulleted list (not collapsed prose),
    # each option on its own line.
    assert "Search backend" in printed
    assert "- 'google_rss'" in printed
    assert "- 'searxng'" in printed


@pytest.mark.asyncio
async def test_explain_config_single_match_shows_full_value(session, mock_print):
    """A filter narrowing to one knob prints its value untruncated."""
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "ZRB_BANNER"}
    )

    printed = _printed_text(mock_print)
    assert "Value:" in printed
    assert "Description:" in printed
    # The banner is multi-line and 330 chars; every line survives.
    assert "Coding Agent + Task Engine" in printed
    assert "…" not in printed


@pytest.mark.asyncio
async def test_explain_config_list_view_keeps_values_on_one_line(session, mock_print):
    """A long value is shortened in the list so the name column can't be squeezed."""
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "llm"}
    )

    printed = _printed_text(mock_print)
    for line in printed.splitlines():
        if line.startswith("ZRB_"):
            assert len(line) < 250


@pytest.mark.asyncio
async def test_explain_config_names_are_never_wrapped(session, mock_print):
    """The name is the lookup key, so it always starts its own line intact."""
    await config_module.explain_config.async_run(
        session=session, kwargs={"keyword": "summarization_token_threshold"}
    )

    printed = _printed_text(mock_print)
    assert "ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD" in printed
