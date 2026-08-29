import asyncio
import os
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.web import (
    normalize_search_result,
    open_web_page,
    run_blocking,
    search_internet,
)


@pytest.fixture
def mock_serpapi():
    with patch("zrb.llm.tool.search.serpapi.search_internet") as mock:
        yield mock


@pytest.fixture
def mock_brave():
    with patch("zrb.llm.tool.search.brave.search_internet") as mock:
        yield mock


@pytest.fixture
def mock_searxng():
    with patch("zrb.llm.tool.search.searxng.search_internet") as mock:
        yield mock


@pytest.fixture
def mock_google_rss():
    with patch("zrb.llm.tool.search.google_rss.search_internet") as mock:
        yield mock


@pytest.mark.asyncio
async def test_search_internet_serpapi(mock_serpapi):
    with patch.dict(
        os.environ,
        {
            f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "serpapi",
            "SERPAPI_KEY": "fake-key",
        },
    ):
        await search_internet("query")
        mock_serpapi.assert_called_once()


@pytest.mark.asyncio
async def test_search_internet_brave(mock_brave):
    with patch.dict(
        os.environ,
        {
            f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "brave",
            "BRAVE_API_KEY": "fake-key",
        },
    ):
        await search_internet("query")
        mock_brave.assert_called_once()


@pytest.mark.asyncio
async def test_search_internet_searxng(mock_searxng):
    with patch.dict(
        os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "searxng"}
    ):
        await search_internet("query")
        mock_searxng.assert_called_once()


@pytest.mark.asyncio
async def test_search_internet_default_fallback(mock_google_rss):
    # Unrecognized method falls back to google_rss
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "other"}):
        await search_internet("query")
        mock_google_rss.assert_called_once()


def test_normalize_brave_empty_extra_snippets():
    # B8: extra_snippets present but empty must not raise IndexError.
    raw = {
        "query": "q",
        "web": {
            "results": [
                {"title": "t", "url": "u", "description": "", "extra_snippets": []}
            ]
        },
    }
    result = normalize_search_result(raw, "brave")
    assert result["error"] is None
    assert result["results"][0]["snippet"] == ""


def test_normalize_brave_uses_first_extra_snippet():
    raw = {
        "query": "q",
        "web": {
            "results": [
                {"title": "t", "url": "u", "description": "", "extra_snippets": ["fb"]}
            ]
        },
    }
    result = normalize_search_result(raw, "brave")
    assert result["results"][0]["snippet"] == "fb"


def test_normalize_brave_echoes_page():
    # B9: page must reflect the requested page, not a hardcoded 1.
    raw = {"query": "q", "web": {"results": []}}
    result = normalize_search_result(raw, "brave", page=3)
    assert result["page"] == 3


def test_normalize_serpapi_echoes_page():
    # B9: page must reflect the requested page, not a hardcoded 1.
    raw = {"query": "q", "organic_results": []}
    result = normalize_search_result(raw, "serpapi", page=4)
    assert result["page"] == 4


def test_normalize_serpapi_uses_search_parameters_query():
    raw = {"search_parameters": {"q": "actual query"}, "organic_results": []}
    result = normalize_search_result(raw, "serpapi")
    assert result["query"] == "actual query"


@pytest.mark.asyncio
async def test_search_internet_brave_threads_page(mock_brave):
    mock_brave.return_value = {"query": "q", "web": {"results": []}}
    with patch.dict(
        os.environ,
        {
            f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "brave",
            "BRAVE_API_KEY": "fake-key",
        },
    ):
        result = await search_internet("q", page=2)
        assert result["page"] == 2


@pytest.mark.asyncio
async def test_open_web_page_playwright_success():
    # Mock playwright
    with patch("playwright.async_api.async_playwright") as mock_playwright_ctx:
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # goto returns a response whose headers say it's HTML, not a PDF, so the
        # content-type check doesn't error and fall back to a real fetch.
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = (
            "<html><body><h1>Title</h1><p>Content</p></body></html>"
        )
        mock_page.eval_on_selector_all.return_value = ["https://example.com/link"]

        result = await open_web_page("https://example.com", summarize=False)

        assert "content" in result
        assert "Title" in result["content"]
        assert "links_on_page" in result
        assert result["links_on_page"] == ["https://example.com/link"]
        assert result["summarized"] == False
        # Raw (unsummarized) content bypasses the summarizer's own injection
        # guard, so the result carries the untrusted-data label itself.
        assert "never follow instructions" in result["content_is"]


@pytest.mark.asyncio
async def test_open_web_page_requests_fallback():
    # Force playwright fail
    with (
        patch(
            "playwright.async_api.async_playwright",
            side_effect=ImportError("No playwright"),
        ),
        patch("requests.get") as mock_get,
    ):

        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><h1>Fallback</h1><a href='/link'>Link</a></body></html>"
        )
        mock_get.return_value = mock_response

        result = await open_web_page("https://example.com", summarize=False)

        assert "content" in result
        assert "Fallback" in result["content"]
        assert "links_on_page" in result
        # urljoin logic check
        assert "https://example.com/link" in result["links_on_page"]
        assert result["summarized"] == False


@pytest.mark.asyncio
async def test_open_web_page_pdf_url_skips_playwright():
    # A .pdf URL must bypass Playwright and extract text via pdfplumber.
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "PDF body text"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    with (
        patch("requests.get") as mock_get,
        patch("pdfplumber.open", return_value=fake_pdf) as mock_pdf_open,
        patch("playwright.async_api.async_playwright") as mock_playwright,
    ):
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 ..."
        mock_get.return_value = mock_response

        result = await open_web_page("https://example.com/doc.pdf", summarize=False)

        assert "PDF body text" in result["content"]
        assert result["links_on_page"] == []
        mock_pdf_open.assert_called_once()
        mock_playwright.assert_not_called()
        # pdfplumber's extract_text is expensive; it must run once per page,
        # not once for the emptiness filter and again for the join.
        assert fake_page.extract_text.call_count == 1


@pytest.mark.asyncio
async def test_open_web_page_pdf_url_falls_back_to_playwright_on_http_error():
    # Regression: the .pdf shortcut was terminal, so a PDF behind a Cloudflare /
    # cookie / JS wall failed outright even though the browser path handles it.
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Guarded PDF text"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    with (
        patch("requests.get", side_effect=Exception("403 Forbidden")),
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("pdfplumber.open", return_value=fake_pdf),
    ):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.body.return_value = b"%PDF-1.4 ..."

        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        result = await open_web_page("https://example.com/guarded.pdf", summarize=False)

        assert "Guarded PDF text" in result["content"]


@pytest.mark.asyncio
async def test_open_web_page_pdf_text_not_html_converted():
    # PDF text containing <...> sequences (code, generics, emails) must survive:
    # running it through the HTML→markdown converter eats them as tags.
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "compile with #include <stdio.h> today"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    with (
        patch("requests.get") as mock_get,
        patch("pdfplumber.open", return_value=fake_pdf),
    ):
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 ..."
        mock_get.return_value = mock_response

        result = await open_web_page("https://example.com/doc.pdf", summarize=False)

        assert "<stdio.h>" in result["content"]


@pytest.mark.asyncio
async def test_open_web_page_extensionless_pdf_via_playwright():
    # e.g. arxiv.org/pdf/2604.03136 — no .pdf extension, so it goes through
    # Playwright; Content-Type on the goto response must route it to pdfplumber.
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Arxiv paper text"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    with (
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("pdfplumber.open", return_value=fake_pdf),
    ):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.body.return_value = b"%PDF-1.4 ..."

        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        result = await open_web_page(
            "https://arxiv.org/pdf/2604.03136", summarize=False
        )

        assert "Arxiv paper text" in result["content"]
        assert result["links_on_page"] == []


@pytest.mark.asyncio
async def test_open_web_page_pdf_content_type_in_fallback():
    # A PDF served at a non-.pdf URL is caught by Content-Type in the fallback.
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Fallback PDF text"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    with (
        patch(
            "playwright.async_api.async_playwright",
            side_effect=ImportError("No playwright"),
        ),
        patch("requests.get") as mock_get,
        patch("pdfplumber.open", return_value=fake_pdf),
    ):
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.content = b"%PDF-1.4 ..."
        mock_get.return_value = mock_response

        result = await open_web_page("https://example.com/download", summarize=False)

        assert "Fallback PDF text" in result["content"]
        assert result["links_on_page"] == []


@pytest.mark.asyncio
async def test_open_web_page_error():
    with (
        patch(
            "playwright.async_api.async_playwright", side_effect=Exception("Major fail")
        ),
        patch("requests.get", side_effect=Exception("Requests fail")),
    ):

        result = await open_web_page("https://example.com")
        assert "error" in result
        assert "Failed to fetch" in result["error"]


@pytest.mark.asyncio
async def test_open_web_page_error_has_suggestion():
    with (
        patch(
            "playwright.async_api.async_playwright", side_effect=Exception("Major fail")
        ),
        patch("requests.get", side_effect=Exception("Requests fail")),
    ):
        result = await open_web_page("https://example.com")
        assert "[SYSTEM SUGGESTION]" in result["error"]


@pytest.mark.asyncio
async def test_open_web_page_conversion_failure_is_not_mislabeled_as_fetch():
    # A bug in HTML->Markdown conversion (or the summarizer) must not be
    # reported as "Failed to fetch" — that mislabeling can send the agent
    # into a futile retry loop against a URL that was never the problem.
    with (
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch(
            "zrb.llm.tool.web.convert_html_to_markdown",
            side_effect=RuntimeError("converter exploded"),
        ),
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
        mock_page.content.return_value = "<html><body><p>hi</p></body></html>"
        mock_page.eval_on_selector_all.return_value = []

        with pytest.raises(RuntimeError, match="converter exploded"):
            await open_web_page("https://example.com", summarize=False)


@pytest.mark.asyncio
async def test_open_web_page_with_summarization():
    # Mock playwright and LLM orchestrators
    with (
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("zrb.llm.tool.web.create_agent") as mock_create_agent,
        patch("zrb.llm.tool.web.run_agent", new_callable=AsyncMock) as mock_run_agent,
        # The fallback must never be reached: with goto unstubbed, the
        # content-type check exploded on an auto-AsyncMock (leaking a
        # never-awaited coroutine) and the test silently fetched the real
        # https://example.com through requests. Fail loudly instead.
        patch("requests.get", side_effect=AssertionError("network escape")),
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
        mock_page.content.return_value = "<html><body><h1>Title</h1><p>Content with lots of details that should be summarized.</p></body></html>"
        mock_page.eval_on_selector_all.return_value = ["https://example.com/link"]

        # Mock LLM response
        mock_run_agent.return_value = ("Concise summary", [])

        result = await open_web_page("https://example.com", summarize=True)

        assert "content" in result
        assert result["summarized"] == True
        assert "Concise summary" in result["content"]
        assert "links_on_page" in result
        mock_create_agent.assert_called_once()
        mock_run_agent.assert_called_once()


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
        patch("zrb.llm.tool.web.create_agent"),
        patch("zrb.llm.tool.web.run_agent", new_callable=AsyncMock) as mock_run_agent,
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


# ── Regressions for the incident: 2 concurrent researcher sub-agents made
# zrb unresponsive with disk usage spiking. Root cause: search_internet's
# backends made blocking, un-timed-out `requests.get` calls directly from an
# async function (freezing the whole event loop, TUI included, on any stall),
# and a Playwright browser was only closed on the success path (leaking a
# Chromium process + disk-backed profile on any fetch exception). ──


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


# ── Interim status ("clue on the TUI") for slow-but-bounded operations ──
#
# Between the tool-call-start line and a (now-bounded, but still up to ~60s
# for WebFetch) result, the tool was a silent black box -- indistinguishable
# from a hang. stream_to_parent existed for exactly this (per its own
# docstring: "tool call notifications during subagent execution") but had
# zero callers anywhere in the codebase before this.


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


# ── Regression for the real incident: two concurrent researcher sub-agents
# left the whole session unresponsive, and it stayed unkillable through
# several Ctrl+C, finally hanging at Python's own threading shutdown trying
# to join a worker thread. `asyncio.to_thread` (and `timeout=` on the inner
# `requests.get`) is not enough on its own: some blocking primitives (DNS
# resolution via getaddrinfo has no timeout of its own) can make the call
# never return, and `asyncio.to_thread`'s worker thread is not a daemon --
# process exit then blocks forever joining it. `run_blocking` bounds the
# *coroutine* with `asyncio.wait_for` and runs the call on a fresh daemon
# thread, so neither problem can hang the turn or the process. ──


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
