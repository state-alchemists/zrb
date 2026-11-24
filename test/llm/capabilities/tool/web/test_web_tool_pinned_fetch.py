import ipaddress
import socket
from unittest.mock import MagicMock, patch

import pytest
import requests

from zrb.llm.capabilities.tool.web import open_web_page
from zrb.llm.capabilities.tool.web.tools import (
    UnsafeWebUrlError,
    _fetch_pinned_page,
    _PinnedAddressAdapter,
    get_pinned_web_page_response,
    is_public_address,
)


def _redirect_to(location: str) -> MagicMock:
    return MagicMock(is_redirect=True, status_code=302, headers={"Location": location})


def _ok_response() -> MagicMock:
    return MagicMock(is_redirect=False, status_code=200)


def _address_info(address: str):
    return (
        socket.AF_INET,
        socket.SOCK_STREAM,
        socket.IPPROTO_TCP,
        "",
        (address, 0),
    )


class _FakePinnedSession:
    """The slice of `requests.Session` the pinned fetch touches."""

    def __init__(self, responses: list):
        # Shared with the other fake sessions: each hop pops its own response.
        self.responses = responses
        self.requests: list = []
        self.adapter = None

    def mount(self, prefix: str, adapter) -> None:
        self.adapter = adapter

    def get(self, url: str, **kwargs):
        self.requests.append((url, self.adapter.address))
        self.headers = kwargs.get("headers", {})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        pass


def _patch_pinned_sessions(responses: list):
    sessions: list[_FakePinnedSession] = []

    pending = list(responses)

    def make_session():
        session = _FakePinnedSession(pending)
        sessions.append(session)
        return session

    return (
        patch(
            "zrb.llm.capabilities.tool.web.tools.requests.Session",
            side_effect=make_session,
        ),
        sessions,
    )


def test_pinned_fetch_connects_to_the_validated_address_even_if_dns_changes(
    monkeypatch,
):
    """The guard's answer is the address the socket opens, not a fresh lookup:
    a resolver that now returns a private address never gets that chance."""
    answers = [_address_info("93.184.216.34"), _address_info("10.1.2.3")]
    resolutions: list[str] = []

    def fake_getaddrinfo(hostname, port, *args, **kwargs):
        resolutions.append(hostname)
        return [answers.pop(0)]

    connected: list[str] = []

    def refuse_create_connection(address, *args, **kwargs):
        connected.append(address[0])
        raise OSError("stop before the network")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        "urllib3.util.connection.create_connection", refuse_create_connection
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        _fetch_pinned_page("http://rebind.example.com/page", "agent")

    assert connected == ["93.184.216.34"]
    assert resolutions == ["rebind.example.com"]


def test_pinned_adapter_keeps_tls_identity_on_the_url_hostname():
    """Connecting to the IP must not move SNI or certificate verification off
    the URL's hostname."""
    adapter = _PinnedAddressAdapter("93.184.216.34")
    request = requests.Request("GET", "https://example.com/page").prepare()

    connection = adapter.get_connection_with_tls_context(request, verify=True)

    assert connection.host == "93.184.216.34"
    assert connection.port == 443
    assert connection.conn_kw["server_hostname"] == "example.com"
    assert connection.assert_hostname == "example.com"


def test_pinned_fetch_resolves_and_pins_every_redirect_hop(monkeypatch):
    final_response = _ok_response()
    patcher, sessions = _patch_pinned_sessions(
        [_redirect_to("https://next.example/page"), final_response]
    )
    addresses = {
        "start.example": "93.184.216.34",
        "next.example": "93.184.216.35",
    }

    def fake_getaddrinfo(hostname, port, *args, **kwargs):
        return [_address_info(addresses[hostname])]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with patcher:
        response = get_pinned_web_page_response("https://start.example/", "agent")

    assert response is final_response
    assert len(sessions) == 1
    assert sessions[0].requests == [
        ("https://start.example/", "93.184.216.34"),
        ("https://next.example/page", "93.184.216.35"),
    ]


def test_pinned_fetch_refuses_a_private_redirect_hop():
    patcher, sessions = _patch_pinned_sessions(
        [_redirect_to("http://169.254.169.254/latest/meta-data/")]
    )
    with patcher:
        with pytest.raises(UnsafeWebUrlError, match="non-public"):
            get_pinned_web_page_response("https://start.example/", "agent")

    # The private hop is never connected to; only the public start was fetched.
    assert len(sessions) == 1
    assert len(sessions[0].requests) == 1


def test_pinned_fetch_writes_the_hostname_into_the_host_header():
    """The socket goes to the IP; the request must still name the virtual host
    (and its non-default port), or TLS-terminating hosts serve the wrong site."""
    patcher, sessions = _patch_pinned_sessions([_ok_response()])
    with patcher:
        get_pinned_web_page_response("https://example.com:8443/page", "agent")

    assert sessions[0].headers["Host"] == "example.com:8443"


def test_pinned_fetch_tries_the_next_validated_address_when_the_first_fails(
    monkeypatch,
):
    """Dual-stack host: an unreachable first address must not fail the fetch.
    The next validated address is tried, and only validated ones are used."""
    patcher, sessions = _patch_pinned_sessions(
        [
            requests.exceptions.ConnectionError("no route to host"),
            _ok_response(),
        ]
    )

    def fake_getaddrinfo(hostname, port, *args, **kwargs):
        return [_address_info("93.184.216.34"), _address_info("93.184.216.35")]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with patcher:
        response = get_pinned_web_page_response("https://dual.example/", "agent")

    assert response is not None
    assert sessions[0].requests == [
        ("https://dual.example/", "93.184.216.34"),
        ("https://dual.example/", "93.184.216.35"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [{}, {"Content-Type": "text/html"}, {"Content-Type": "application/octet-stream"}],
)
async def test_a_pdf_path_is_extracted_without_a_pdf_content_type(headers):
    """The `.pdf` suffix is the promise: a missing or wrong Content-Type must
    not turn a PDF into an HTML parse."""
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "PDF body text"
    fake_pdf = MagicMock()
    fake_pdf.pages = [fake_page]
    fake_pdf.__enter__.return_value = fake_pdf

    response = MagicMock(is_redirect=False)
    response.headers = headers
    response.content = b"%PDF-1.4 ..."
    patcher, _sessions = _patch_pinned_sessions([response])

    with patcher, patch("pdfplumber.open", return_value=fake_pdf) as mock_pdf_open:
        result = await open_web_page("https://example.com/doc.pdf", summarize=False)

    assert "PDF body text" in result["content"]
    assert result["links_on_page"] == []
    mock_pdf_open.assert_called_once()


def test_is_public_address_rejects_rfc6598_shared_space():
    """100.64.0.0/10 is not private by `ipaddress`, but it is not global either."""
    assert is_public_address(ipaddress.ip_address("100.64.0.1")) is False


def test_is_public_address_accepts_a_global_address():
    assert is_public_address(ipaddress.ip_address("93.184.216.34")) is True
