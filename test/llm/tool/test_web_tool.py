import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.web import open_web_page, search_internet


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
    # Default fallback
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_SEARCH_INTERNET_METHOD": "other"}):
        await search_internet("query")
        mock_searxng.assert_called_once()


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
    with patch(
        "playwright.async_api.async_playwright",
        side_effect=ImportError("No playwright"),
    ), patch("requests.get") as mock_get:

        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><h1>Fallback</h1><a href='/link'>Link</a></body></html>"
        )
        mock_get.return_value = mock_response

        result = await open_web_page("https://example.com")

        assert "content" in result
        assert "Fallback" in result["content"]
        assert "links_on_page" in result
        # urljoin logic check
        assert "https://example.com/link" in result["links_on_page"]


@pytest.mark.asyncio
async def test_open_web_page_error():
    with patch(
        "playwright.async_api.async_playwright", side_effect=Exception("Major fail")
    ), patch("requests.get", side_effect=Exception("Requests fail")):

        result = await open_web_page("https://example.com")
        assert "error" in result
        assert "Failed to fetch" in result["error"]


@pytest.mark.asyncio
async def test_open_web_page_with_summarization():
    # Mock playwright
    with patch("playwright.async_api.async_playwright") as mock_playwright_ctx, patch(
        "zrb.llm.tool.web._summarize_web_content"
    ) as mock_summarize:

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright_ctx.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        mock_page.content.return_value = "<html><body><h1>Title</h1><p>Content with lots of details that should be summarized.</p></body></html>"
        mock_page.eval_on_selector_all.return_value = ["https://example.com/link"]

        # Mock summarization to return concise content
        mock_summarize.return_value = "## Summary\nConcise summary of the page.\n\n## Key Points\n1. Main point\n\n## References\n- https://example.com"

        result = await open_web_page("https://example.com", summarize=True)

        assert "content" in result
        assert "summarized" in result
        assert result["summarized"] == True
        assert "Concise summary" in result["content"]  # From mocked summary
        assert "links_on_page" in result
        mock_summarize.assert_called_once()
