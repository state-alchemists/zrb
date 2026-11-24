"""The browser proxy resolves the target itself, and validates the answer."""

import socket
from unittest.mock import patch

import pytest

from zrb.llm.capabilities.tool.web.tools import (
    UnsafeWebUrlError,
    resolve_proxy_addresses,
)

PUBLIC_ADDRESS = "93.184.216.34"
PRIVATE_ADDRESS = "127.0.0.1"


def _resolving_to(address: str):
    """Make the process-wide lookup answer *address*, whatever it is asked."""
    return patch(
        "socket.getaddrinfo",
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 0))
        ],
    )


@pytest.mark.asyncio
async def test_the_proxy_refuses_a_name_that_resolves_privately(monkeypatch):
    # The URL guard approved this name a moment ago; the second lookup is the
    # one that can answer differently, so the proxy is where it is refused.
    monkeypatch.delenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", raising=False)
    with _resolving_to(PRIVATE_ADDRESS):
        with pytest.raises(UnsafeWebUrlError):
            await resolve_proxy_addresses("intranet.example", 443)


@pytest.mark.asyncio
async def test_the_proxy_takes_a_private_answer_when_opted_in(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", "on")
    with _resolving_to(PRIVATE_ADDRESS):
        assert await resolve_proxy_addresses("intranet.example", 443) == [
            PRIVATE_ADDRESS
        ]


@pytest.mark.asyncio
async def test_the_proxy_takes_a_public_answer(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", raising=False)
    with _resolving_to(PUBLIC_ADDRESS):
        assert await resolve_proxy_addresses("example.com", 443) == [PUBLIC_ADDRESS]
