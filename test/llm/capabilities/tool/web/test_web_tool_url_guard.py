import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.web import open_web_page
from zrb.llm.capabilities.tool.web.tools import (
    UnsafeWebUrlError,
    refuse_unsafe_web_url,
)


def _resolve_to(*addresses: str):
    """Patch the resolver so `hostname` answers with `addresses`."""
    return patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 0))
            for address in addresses
        ],
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,<h1>hello</h1>",
        "javascript:alert(1)",
        "blob:https://example.com/1234",
        "about:blank",
        "ftp://example.com/file.txt",
    ],
)
def test_refuse_unsafe_web_url_rejects_non_http_schemes(url):
    with pytest.raises(UnsafeWebUrlError, match="http and https"):
        refuse_unsafe_web_url(url)


def test_refuse_unsafe_web_url_rejects_a_url_without_a_hostname():
    with pytest.raises(UnsafeWebUrlError, match="no hostname"):
        refuse_unsafe_web_url("http:///no-host")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080/admin",
        "http://127.0.0.2/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://0.0.0.0/",
        "http://224.0.0.1/",
    ],
)
def test_refuse_unsafe_web_url_rejects_non_public_literal_hosts(url):
    with pytest.raises(UnsafeWebUrlError, match="non-public"):
        refuse_unsafe_web_url(url)


def test_refuse_unsafe_web_url_rejects_a_private_dns_answer():
    with _resolve_to("10.1.2.3"):
        with pytest.raises(UnsafeWebUrlError, match="intranet.example.com"):
            refuse_unsafe_web_url("https://intranet.example.com/admin")


def test_refuse_unsafe_web_url_allows_a_public_url():
    with _resolve_to("93.184.216.34"):
        refuse_unsafe_web_url("https://example.com/docs")


def test_refuse_unsafe_web_url_allows_a_public_literal():
    refuse_unsafe_web_url("https://93.184.216.34/docs")


def test_refuse_unsafe_web_url_refuses_a_host_that_does_not_resolve():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("no such host")):
        with pytest.raises(UnsafeWebUrlError, match="does not resolve"):
            refuse_unsafe_web_url("https://does-not-exist.example/")


def test_refuse_unsafe_web_url_refuses_an_empty_dns_answer():
    with _resolve_to():
        with pytest.raises(UnsafeWebUrlError, match="does not resolve"):
            refuse_unsafe_web_url("https://empty.example/")


def test_refuse_unsafe_web_url_rejects_private_hosts_by_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", raising=False)
    assert CFG.LLM_WEB_ALLOW_PRIVATE_HOSTS is False
    with pytest.raises(UnsafeWebUrlError, match="non-public"):
        refuse_unsafe_web_url("http://127.0.0.1:8080/")


def test_refuse_unsafe_web_url_allows_private_hosts_when_configured(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", "on")
    refuse_unsafe_web_url("http://127.0.0.1:8080/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1:8080/admin",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
async def test_open_web_page_refuses_an_unsafe_url_before_any_fetch(url):
    with (
        patch("playwright.async_api.async_playwright") as mock_playwright,
        patch("requests.get") as mock_get,
    ):
        result = await open_web_page(url, summarize=False)

    assert result["error"].startswith("Refusing to open")
    mock_playwright.assert_not_called()
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_open_web_page_refuses_a_private_dns_answer_before_any_fetch():
    with (
        _resolve_to("10.1.2.3"),
        patch("playwright.async_api.async_playwright") as mock_playwright,
        patch("requests.get") as mock_get,
    ):
        result = await open_web_page("https://intranet.example.com/", summarize=False)

    assert "non-public" in result["error"]
    mock_playwright.assert_not_called()
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_open_web_page_refuses_a_private_host_when_playwright_is_missing():
    with (
        patch(
            "playwright.async_api.async_playwright",
            side_effect=ImportError("No playwright"),
        ),
        patch("requests.get") as mock_get,
    ):
        result = await open_web_page("http://10.0.0.5/", summarize=False)

    assert "non-public" in result["error"]
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_open_web_page_opens_a_private_host_when_configured(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", "on")
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
        mock_page.content.return_value = "<html><body><p>local</p></body></html>"
        mock_page.eval_on_selector_all.return_value = []

        result = await open_web_page("http://127.0.0.1:8080/", summarize=False)

    assert "local" in result["content"]
