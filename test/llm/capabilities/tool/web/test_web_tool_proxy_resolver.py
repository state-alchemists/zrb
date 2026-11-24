"""The browser proxy resolves the target itself, and validates the answer."""

import ipaddress

import pytest

from zrb.llm.capabilities.tool.web import tools
from zrb.llm.capabilities.tool.web.tools import UnsafeWebUrlError

PUBLIC_ADDRESS = "93.184.216.34"
PRIVATE_ADDRESS = "127.0.0.1"


def _resolving_to(monkeypatch, address: str) -> None:
    """Make the proxy's own lookup answer *address*, whatever it is asked."""
    monkeypatch.setattr(
        tools,
        "_get_host_addresses",
        lambda hostname: [ipaddress.ip_address(address)],
    )


@pytest.mark.asyncio
async def test_the_proxy_refuses_a_name_that_resolves_privately(monkeypatch):
    # The URL guard approved this name a moment ago; the second lookup is the
    # one that can answer differently, so the proxy is where it is refused.
    monkeypatch.delenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", raising=False)
    _resolving_to(monkeypatch, PRIVATE_ADDRESS)
    with pytest.raises(UnsafeWebUrlError):
        await tools._resolve_proxy_addresses("intranet.example", 443)


@pytest.mark.asyncio
async def test_the_proxy_takes_a_private_answer_when_opted_in(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", "on")
    _resolving_to(monkeypatch, PRIVATE_ADDRESS)
    assert await tools._resolve_proxy_addresses("intranet.example", 443) == [
        PRIVATE_ADDRESS
    ]


@pytest.mark.asyncio
async def test_the_proxy_takes_a_public_answer(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_WEB_ALLOW_PRIVATE_HOSTS", raising=False)
    _resolving_to(monkeypatch, PUBLIC_ADDRESS)
    assert await tools._resolve_proxy_addresses("example.com", 443) == [PUBLIC_ADDRESS]
