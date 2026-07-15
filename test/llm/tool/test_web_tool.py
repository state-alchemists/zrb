import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.web import (
    normalize_search_result,
    open_web_page,
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
async def test_open_web_page_with_summarization():
    # Mock playwright and LLM orchestrators
    with (
        patch("playwright.async_api.async_playwright") as mock_playwright_ctx,
        patch("zrb.llm.tool.web.create_agent") as mock_create_agent,
        patch("zrb.llm.tool.web.run_agent", new_callable=AsyncMock) as mock_run_agent,
    ):

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

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
        mock_page.content.return_value = huge_html
        mock_page.eval_on_selector_all.return_value = []
        mock_run_agent.return_value = ("summary", [])

        await open_web_page("https://example.com", summarize=True)

    sent_message = mock_run_agent.call_args.kwargs["message"]
    assert "[TRUNCATED]" in sent_message
    # Bounded to cap + json envelope + instruction, not the 100k+ raw page.
    assert len(sent_message) < 2000
