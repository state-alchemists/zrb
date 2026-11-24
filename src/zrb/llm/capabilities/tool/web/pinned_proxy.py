"""A loopback CONNECT proxy that resolves, validates and pins each target.

Chromium cannot be handed the address the URL guard validated: it resolves the
hostname in its own process, so a name that answered publicly during the guard
can answer privately when the browser connects. Pointing Chromium at this
proxy removes its resolver from the decision. Every CONNECT (and plain HTTP
proxy request) is resolved here, every validated address is tried, and the
proxy opens the socket itself; the browser only sees a tunnel.

The proxy is intentionally small: it speaks CONNECT and absolute-form HTTP/1.1,
which is what Chromium sends to a proxy. It binds to loopback on an ephemeral
port and is closed with the browser fetch that started it.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Sequence
from urllib.parse import urlsplit

_HEAD_LIMIT = 64 * 1024
_CHUNK_SIZE = 64 * 1024
_CONNECT_TIMEOUT_SECONDS = 15
_HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

ResolveTarget = Callable[[str, int], Awaitable[Sequence[str]]]


class PinnedProxy:
    """A proxy whose outbound sockets connect only to resolved addresses.

    *resolve* receives ``(host, port)`` and returns the addresses the proxy may
    connect to, in preference order. An empty list refuses the target.
    """

    def __init__(self, resolve: ResolveTarget) -> None:
        self._resolve = resolve
        self._server: asyncio.AbstractServer | None = None
        self._port = 0
        self._tasks: set[asyncio.Task] = set()

    @property
    def port(self) -> int:
        """The loopback port the proxy is listening on."""
        return self._port

    async def start(self) -> int:
        """Listen on loopback; return the chosen port."""
        self._server = await asyncio.start_server(
            self._handle_client, host="127.0.0.1", port=0
        )
        socket = self._server.sockets[0]
        self._port = socket.getsockname()[1]
        return self._port

    async def close(self) -> None:
        """Stop accepting and cancel in-flight tunnels."""
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_client(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        try:
            await self._serve(client_reader, client_writer)
        except (asyncio.IncompleteReadError, ConnectionError, ValueError, OSError):
            # The client went away, sent a malformed target, or no validated
            # address accepted the connection. `_serve` sends its own error
            # response where one is still possible.
            pass
        finally:
            if task is not None:
                self._tasks.discard(task)
            client_writer.close()
            with contextlib.suppress(OSError):
                await client_writer.wait_closed()

    async def _serve(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        head, extra = await _read_head(client_reader)
        lines = head.split("\r\n")
        try:
            method, target, version = lines[0].split(" ", 2)
        except ValueError:
            await _send_error(client_writer, 400)
            return
        if method.upper() == "CONNECT":
            host, port = _parse_authority(target)
            remote = await self._open_target(host, port)
            if remote is None:
                await _send_error(client_writer, 502)
                return
            remote_reader, remote_writer = remote
            try:
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()
                if extra:
                    remote_writer.write(extra)
                    await remote_writer.drain()
                await _tunnel(
                    client_reader, client_writer, remote_reader, remote_writer
                )
            finally:
                await _close_pair(remote_writer)
            return
        if method.upper() not in _HTTP_METHODS:
            await _send_error(client_writer, 400)
            return
        parsed = urlsplit(target)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            await _send_error(client_writer, 400)
            return
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        remote = await self._open_target(parsed.hostname, port)
        if remote is None:
            await _send_error(client_writer, 502)
            return
        remote_reader, remote_writer = remote
        try:
            origin = parsed.path or "/"
            if parsed.query:
                origin = f"{origin}?{parsed.query}"
            forwarded = [f"{method} {origin} {version}"] + lines[1:]
            remote_writer.write(("\r\n".join(forwarded) + "\r\n\r\n").encode("latin-1"))
            if extra:
                remote_writer.write(extra)
            await remote_writer.drain()
            await _tunnel(client_reader, client_writer, remote_reader, remote_writer)
        finally:
            await _close_pair(remote_writer)

    async def _open_target(
        self, host: str, port: int
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        addresses = await self._resolve(host, port)
        for address in addresses:
            try:
                return await asyncio.wait_for(
                    asyncio.open_connection(address, port),
                    timeout=_CONNECT_TIMEOUT_SECONDS,
                )
            except (OSError, asyncio.TimeoutError):
                continue
        return None


async def _read_head(
    reader: asyncio.StreamReader,
) -> tuple[str, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = await reader.read(4096)
        if not chunk:
            raise ConnectionError("the proxy client closed before its headers")
        data += chunk
        if len(data) > _HEAD_LIMIT:
            raise ValueError(
                "the proxy request headers are too large; refusing the request"
            )
    head, _, extra = data.partition(b"\r\n\r\n")
    return head.decode("latin-1"), extra


def _parse_authority(target: str) -> tuple[str, int]:
    parsed = urlsplit(f"//{target}")
    if not parsed.hostname:
        raise ValueError("CONNECT has no host; refusing the proxy request")
    return parsed.hostname, parsed.port or 443


async def _tunnel(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    remote_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
) -> None:
    await asyncio.gather(
        _pipe(client_reader, remote_writer),
        _pipe(remote_reader, client_writer),
    )


async def _pipe(
    source: asyncio.StreamReader, destination: asyncio.StreamWriter
) -> None:
    try:
        while True:
            data = await source.read(_CHUNK_SIZE)
            if not data:
                break
            destination.write(data)
            await destination.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        with contextlib.suppress(OSError):
            destination.write_eof()


async def _send_error(writer: asyncio.StreamWriter, status: int) -> None:
    reason = {400: "Bad Request", 502: "Bad Gateway"}.get(status, "Error")
    writer.write(
        (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
    )
    with contextlib.suppress(OSError):
        await writer.drain()


async def _close_pair(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()
