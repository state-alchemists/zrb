"""Web-tool tests resolve every hostname to a public address.

`refuse_unsafe_web_url` resolves a hostname before either fetch path sees the
URL, so without this fixture a test written against `example.com` would need
real DNS. Tests that want a private (or unresolvable) answer patch
`socket.getaddrinfo` again with their own value, which overrides this one.
"""

import socket
from unittest.mock import patch

import pytest

PUBLIC_TEST_ADDRESS = "93.184.216.34"


@pytest.fixture(autouse=True)
def public_dns():
    def fake_getaddrinfo(hostname, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (PUBLIC_TEST_ADDRESS, port or 0),
            )
        ]

    with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
        yield
