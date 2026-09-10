import asyncio
import os
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.web import open_web_page, run_blocking, search_internet


@pytest.fixture
def mock_google_rss():
    with patch("zrb.llm.tool.search.google_rss.search_internet") as mock:
        yield mock


@pytest.mark.asyncio
async def test_open_web_page_truncates_oversized_page():
    """A page larger than LLM_MAX_OUTPUT_CHARS is capped before it becomes a
    message, so the rate limiter never sees an un-admittable request (the
    WebFetch livelock that froze the UI)."""
    huge_html = "<html><body>" + ("<p>spam paragraph</p>" * 5000) + "</body></html>"
    with (
        patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}),
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
    ):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = huge_html
        mock_page.eval_on_selector_all.return_value = []

        result = await open_web_page("https://example.com", summarize=False)

    assert result["truncated"] is True
    assert "[TRUNCATED]" in result["content"]
    # Bounded to the cap plus the short marker, not the multi-KB original.
    assert len(result["content"]) < 600


@pytest.mark.asyncio
async def test_open_web_page_summarizer_input_is_bounded():
    """The summarizer sub-agent must receive the capped content, not the raw
    page — this is the request the limiter would otherwise reject forever."""
    huge_html = "<html><body>" + ("<p>spam paragraph</p>" * 5000) + "</body></html>"
    with (
        patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}),
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("zrb.llm.agent.create_agent"),
        patch("zrb.llm.agent.run_agent", new_callable=AsyncMock) as mock_run_agent,
    ):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = huge_html
        mock_page.eval_on_selector_all.return_value = []
        mock_run_agent.return_value = ("summary", [])

        await open_web_page("https://example.com", summarize=True)

    sent_message = mock_run_agent.call_args.kwargs["message"]
    assert "[TRUNCATED]" in sent_message
    # Bounded to cap + json envelope + instruction, not the 100k+ raw page.
    assert len(sent_message) < 2000


@pytest.mark.asyncio
async def test_search_internet_does_not_block_the_event_loop(mock_google_rss):
    """A slow synchronous backend call must not freeze concurrent coroutines
    (e.g. the TUI's own redraw loop) -- it must actually run off-loop.

    A weak version of this test would just assert the heartbeat eventually
    completes -- true even if search_internet blocks, since asyncio.gather
    always finishes both eventually. What actually distinguishes "ran
    concurrently" from "ran after a blocking call" is *when* the heartbeat
    completes relative to the slow call's duration.
    """
    import time

    def slow_backend(query, page=1):
        time.sleep(0.3)
        return {"query": query, "results": [], "page": page}

    mock_google_rss.side_effect = slow_backend
    heartbeat_done_at = None

    async def heartbeat():
        nonlocal heartbeat_done_at
        await asyncio.sleep(0.05)
        # Absolute completion time, not a duration measured from whenever
        # this coroutine happened to get its first turn -- if search_internet
        # blocks the loop, this task simply doesn't run at all until the
        # blocking call releases control, and a *duration* measured from
        # that late start would still read ~0.05s either way.
        heartbeat_done_at = time.monotonic()

    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "other"}):
        overall_start = time.monotonic()
        await asyncio.gather(search_internet("query"), heartbeat())

    assert heartbeat_done_at is not None
    # A blocking search_internet delays this task's first turn until after its
    # own 0.3s finishes (~0.35s total). Running truly off-loop, it completes
    # close to 0.05s from the real start.
    assert heartbeat_done_at - overall_start < 0.2


@pytest.mark.asyncio
async def test_open_web_page_closes_browser_even_when_goto_fails():
    """A launched browser must always close, even when page.goto raises --
    otherwise every failed fetch leaks a headless Chromium process and its
    disk-backed profile, unboundedly, across a long research session."""
    with (
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("zrb.llm.tool.web.fetch_page_fallback", return_value=("f", [], False)),
    ):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.side_effect = RuntimeError("timeout")

        await open_web_page("https://example.com", summarize=False)

        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_web_page_closes_browser_on_success():
    """Regression guard for the fix itself: the success path must still
    close the browser exactly once (not skip it, not double-close)."""
    with patch("playwright.async_api.async_playwright") as mock_playwright_ctx:
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html><body><p>hi</p></body></html>"
        mock_page.eval_on_selector_all.return_value = []

        await open_web_page("https://example.com", summarize=False)

        mock_browser.close.assert_awaited_once()


def test_serpapi_request_has_a_timeout():
    """No timeout means a stalled connection hangs forever, freezing the
    whole (single-threaded) event loop for every concurrent sub-agent."""
    from zrb.llm.tool.search.serpapi import search_internet as serpapi_search

    with patch("zrb.llm.tool.search.serpapi.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        serpapi_search("query", api_key="fake-key")

    assert mock_get.call_args.kwargs.get("timeout") is not None


def test_brave_request_has_a_timeout():
    from zrb.llm.tool.search.brave import search_internet as brave_search

    with patch("zrb.llm.tool.search.brave.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        brave_search("query", api_key="fake-key")

    assert mock_get.call_args.kwargs.get("timeout") is not None


def test_notify_is_a_noop_with_no_current_ui():
    """No ambient UI (the common case outside a running agent turn, e.g. these
    tests) must not raise -- this is a courtesy message, never load-bearing."""
    from zrb.llm.tool.web import notify

    with patch("zrb.llm.tool.web.get_current_ui", return_value=None):
        notify("should not raise")  # must simply do nothing


def test_notify_forwards_to_the_current_uis_stream_to_parent():
    from zrb.llm.tool.web import notify

    mock_ui = MagicMock()
    with patch("zrb.llm.tool.web.get_current_ui", return_value=mock_ui):
        notify("hello")

    mock_ui.stream_to_parent.assert_called_once()
    assert "hello" in mock_ui.stream_to_parent.call_args.args[0]


def test_notify_swallows_a_broken_uis_exception():
    """A UI whose stream_to_parent raises must never break the actual tool
    call -- this is a best-effort courtesy message, not the result."""
    from zrb.llm.tool.web import notify

    mock_ui = MagicMock()
    mock_ui.stream_to_parent.side_effect = RuntimeError("ui exploded")
    with patch("zrb.llm.tool.web.get_current_ui", return_value=mock_ui):
        notify("should not raise either")  # must not propagate


@pytest.mark.asyncio
async def test_open_web_page_notifies_before_fetching():
    mock_ui = MagicMock()
    with (
        patch("zrb.llm.tool.web.get_current_ui", return_value=mock_ui),
        patch(
            "playwright.async_api.async_playwright",
            side_effect=ImportError("No playwright"),
        ),
        patch("requests.get") as mock_get,
    ):
        mock_get.return_value = MagicMock(
            text="<html><body>hi</body></html>", headers={}
        )
        await open_web_page("https://example.com/page", summarize=False)

    messages = [c.args[0] for c in mock_ui.stream_to_parent.call_args_list]
    assert any("https://example.com/page" in m for m in messages)


@pytest.mark.asyncio
async def test_open_web_page_notifies_on_playwright_to_fallback_transition():
    """Otherwise a Playwright failure is a second silent ~30s wait stacked
    right after the first, with nothing telling the user zrb moved on to a
    different attempt rather than being stuck on the same one."""
    mock_ui = MagicMock()
    with (
        patch("zrb.llm.tool.web.get_current_ui", return_value=mock_ui),
        patch(
            "playwright.async_api.async_playwright",
            side_effect=RuntimeError("browser launch failed"),
        ),
        patch("requests.get") as mock_get,
    ):
        mock_get.return_value = MagicMock(
            text="<html><body>hi</body></html>", headers={}
        )
        await open_web_page("https://example.com/page", summarize=False)

    messages = [c.args[0] for c in mock_ui.stream_to_parent.call_args_list]
    assert any("retrying via plain HTTP" in m for m in messages)


@pytest.mark.asyncio
async def test_search_internet_notifies_before_searching(mock_google_rss):
    mock_ui = MagicMock()
    mock_google_rss.return_value = {"query": "q", "results": [], "page": 1}
    with (
        patch("zrb.llm.tool.web.get_current_ui", return_value=mock_ui),
        patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "other"}),
    ):
        await search_internet("claude code vs opencode")

    messages = [c.args[0] for c in mock_ui.stream_to_parent.call_args_list]
    assert any("claude code vs opencode" in m for m in messages)


@pytest.mark.asyncio
async def test_run_blocking_times_out_even_if_the_call_never_returns():
    never_return = threading.Event()

    def blocks_forever():
        never_return.wait()  # would hang forever without run_blocking's timeout

    start = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            await run_blocking(blocks_forever, timeout=0.05)
        elapsed = time.monotonic() - start
        assert elapsed < 2  # bounded, not "forever"
    finally:
        never_return.set()  # let the orphaned thread finish, don't leak it


@pytest.mark.asyncio
async def test_run_blocking_runs_the_call_on_a_daemon_thread():
    """A non-daemon thread that outlives its timeout blocks interpreter exit
    forever (concurrent.futures' thread-exit hook joins it on shutdown) -- the
    exact "won't die even with repeated Ctrl+C" symptom reported."""
    never_return = threading.Event()
    was_daemon = {}

    def blocks_forever():
        was_daemon["value"] = threading.current_thread().daemon
        never_return.wait()

    try:
        with pytest.raises(TimeoutError):
            await run_blocking(blocks_forever, timeout=0.05)
    finally:
        never_return.set()

    # Give the spawned thread a moment to record its own daemon flag before
    # the test process moves on.
    for _ in range(20):
        if "value" in was_daemon:
            break
        await asyncio.sleep(0.01)
    assert was_daemon.get("value") is True


@pytest.mark.asyncio
async def test_search_internet_returns_promptly_even_if_backend_never_returns(
    mock_google_rss,
):
    """The actual reported incident, reproduced directly: a stalled backend
    call must not leave `search_internet` (and therefore the whole turn)
    hanging indefinitely."""
    never_return = threading.Event()
    mock_google_rss.side_effect = lambda *a, **k: never_return.wait()

    with (
        patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "other"}),
        patch("zrb.llm.tool.web.TIMEOUT_MARGIN_SECONDS", 0.05),
        patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_WEB_HTTP_TIMEOUT": "10"}),
    ):
        start = time.monotonic()
        result = await search_internet("query")
        elapsed = time.monotonic() - start

    never_return.set()
    assert elapsed < 2
    assert result["error"] is not None
