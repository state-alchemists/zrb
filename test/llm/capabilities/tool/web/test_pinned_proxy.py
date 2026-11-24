"""The CONNECT proxy resolves and connects; Chromium never does."""

import asyncio

import pytest

from zrb.llm.capabilities.tool.web.pinned_proxy import PinnedProxy


async def _echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()


@pytest.mark.asyncio
async def test_connect_tunnels_to_the_resolved_address():
    echo_server = await asyncio.start_server(_echo, "127.0.0.1", 0)
    echo_port = echo_server.sockets[0].getsockname()[1]

    async def resolve(host: str, port: int) -> list[str]:
        return ["127.0.0.1"]

    proxy = PinnedProxy(resolve)
    proxy_port = await proxy.start()
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        writer.write(
            f"CONNECT example.test:{echo_port} HTTP/1.1\r\n"
            "Host: example.test\r\n\r\n".encode()
        )
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        assert b"200 Connection Established" in head

        writer.write(b"ping")
        await writer.drain()
        assert await reader.readexactly(4) == b"ping"
    finally:
        if writer is not None:
            writer.close()
        await proxy.close()
        echo_server.close()
        await echo_server.wait_closed()


@pytest.mark.asyncio
async def test_an_absolute_http_request_is_forwarded_as_origin_form():
    requests: list[bytes] = []

    async def handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        requests.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        await writer.drain()
        writer.close()

    origin = await asyncio.start_server(handler, "127.0.0.1", 0)
    origin_port = origin.sockets[0].getsockname()[1]

    async def resolve(host: str, port: int) -> list[str]:
        return ["127.0.0.1"]

    proxy = PinnedProxy(resolve)
    proxy_port = await proxy.start()
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        writer.write(
            f"GET http://example.test:{origin_port}/path?q=1 HTTP/1.1\r\n"
            "Host: example.test\r\n\r\n".encode()
        )
        await writer.drain()
        response = await reader.read()
        assert response.startswith(b"HTTP/1.1 200 OK")
        assert requests[0].startswith(b"GET /path?q=1 HTTP/1.1\r\n")
    finally:
        if writer is not None:
            writer.close()
        await proxy.close()
        origin.close()
        await origin.wait_closed()


@pytest.mark.asyncio
async def test_an_empty_resolution_is_refused():
    async def resolve(host: str, port: int) -> list[str]:
        return []

    proxy = PinnedProxy(resolve)
    proxy_port = await proxy.start()
    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        writer.write(b"CONNECT example.test:443 HTTP/1.1\r\nHost: example.test\r\n\r\n")
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        assert b"502 Bad Gateway" in head
    finally:
        if writer is not None:
            writer.close()
        await proxy.close()
