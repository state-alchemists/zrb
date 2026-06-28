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

    printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    # A real config table has the header and at least one ZRB_ variable row.
    assert "Environment Variable" in printed
    assert "ZRB_" in printed


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

    printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    # Filtering by "llm" keeps LLM rows and the header.
    assert "Environment Variable" in printed
    assert "LLM" in printed.upper()


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
