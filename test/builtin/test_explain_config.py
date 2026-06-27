from unittest import mock

import pytest

from zrb.builtin import config as config_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


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
