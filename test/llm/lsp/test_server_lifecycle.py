import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.lsp.configs import LSPServerConfig
from zrb.llm.lsp.protocol import LSPServerError, LSPTimeoutError
from zrb.llm.lsp.server import LSPServer


@pytest.fixture
def mock_config():
    return LSPServerConfig(
        name="test-lsp",
        language_ids=["python"],
        file_extensions=[".py"],
        command=["python", "-m", "pylsp"],
    )


@pytest.fixture
def lsp_server(mock_config):
    return LSPServer(config=mock_config, root_path="/test")


@pytest.mark.asyncio
async def test_start_when_alive_is_noop(lsp_server):
    """A second start() while the process is alive short-circuits."""
    queue = asyncio.Queue()
    queue.put_nowait(_frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}))
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = _queued_subprocess(queue)
        assert await lsp_server.start() is True
        assert await lsp_server.start() is True
        mock_exec.assert_called_once()
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_start_missing_executable_returns_false(lsp_server):
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        assert await lsp_server.start() is False
    assert lsp_server.process is None


@pytest.mark.asyncio
async def test_start_failure_with_stop_error_returns_false(lsp_server):
    lsp_server.config.timeout = 1
    proc = MagicMock()
    proc.returncode = None
    proc.stdout = AsyncMock()
    proc.stdout.read.return_value = b""
    proc.stderr = None
    proc.stdin = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.wait = AsyncMock()
    with (
        patch("asyncio.create_subprocess_exec", return_value=proc),
        patch.object(
            lsp_server, "stop", AsyncMock(side_effect=RuntimeError("stop boom"))
        ),
    ):
        assert await lsp_server.start() is False
    assert lsp_server.process is proc


@pytest.mark.asyncio
async def test_stop_force_kills_when_terminate_times_out(lsp_server, monkeypatch):
    queue = asyncio.Queue()
    queue.put_nowait(_frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}))
    proc = _queued_subprocess(queue)

    async def hang(*args):
        await asyncio.sleep(30)

    proc.wait = AsyncMock(side_effect=hang)
    proc.stderr = AsyncMock()
    proc.stderr.read = AsyncMock(side_effect=hang)

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        assert await lsp_server.start() is True

    monkeypatch.setattr(CFG, "LLM_SHELL_KILL_WAIT_TIMEOUT", 100)
    await lsp_server.stop()
    proc.kill.assert_called_once()
    assert lsp_server.process is None
    assert lsp_server.initialized is False


@pytest.mark.asyncio
async def test_initialize_null_result_leaves_server_uninitialized(lsp_server):
    queue = asyncio.Queue()
    queue.put_nowait(_frame({"jsonrpc": "2.0", "id": 1, "result": None}))
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = _queued_subprocess(queue)
        assert await lsp_server.start() is True
    assert lsp_server.initialized is False
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_read_loop_exits_without_stdout(lsp_server):
    lsp_server.config.timeout = 1
    proc = MagicMock()
    proc.returncode = None
    proc.stdout = None
    proc.stderr = None
    proc.stdin = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.wait = AsyncMock()
    proc.wait_closed = AsyncMock()
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        assert await lsp_server.start() is False
    assert lsp_server.process is None


@pytest.mark.asyncio
async def test_read_loop_breaks_on_eof(lsp_server):
    init_payload = _frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}})
    chunks = iter([init_payload, b""])

    async def read_chunks(n=-1):
        return next(chunks, b"")

    proc = MagicMock()
    proc.returncode = None
    proc.stdout = AsyncMock()
    proc.stdout.read.side_effect = read_chunks
    proc.stderr = AsyncMock()
    proc.stderr.read = AsyncMock(return_value=b"")
    proc.stdin = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.wait = AsyncMock()
    proc.wait_closed = AsyncMock()
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        assert await lsp_server.start() is True
    await asyncio.sleep(0.05)
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_read_loop_survives_bad_messages_then_times_out(lsp_server):
    queue = asyncio.Queue()
    queue.put_nowait(_frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}))
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = _queued_subprocess(queue)
        assert await lsp_server.start() is True

    queue.put_nowait(
        _frame(
            {
                "jsonrpc": "2.0",
                "method": "window/logMessage",
                "params": {"message": "hi"},
            }
        )
    )
    queue.put_nowait(b"Content-Length: 8\r\n\r\nnot json")
    queue.put_nowait(_frame({"id": [], "result": 1}))
    queue.put_nowait(b"Content-Length: abc\r\n\r\n{}")

    lsp_server.config.timeout = 1
    with pytest.raises(LSPTimeoutError):
        await lsp_server.goto_definition("/never/here.py", 0, 0)


@pytest.mark.asyncio
async def test_error_response_raises_server_error(lsp_server):
    queue = asyncio.Queue()
    queue.put_nowait(_frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}))
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = _queued_subprocess(queue)
        assert await lsp_server.start() is True

    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"error": {"code": -32601, "message": "Method Not Found", "data": None}}},
        )
    )
    with pytest.raises(LSPServerError):
        await lsp_server.goto_definition("/never/here.py", 0, 0)
    await feeder
def _frame(payload):
    body = json.dumps(payload)
    return f"Content-Length: {len(body)}\r\n\r\n{body}".encode()


def _queued_subprocess(queue):
    proc = MagicMock()
    proc.returncode = None
    proc.stdout = AsyncMock()

    async def mock_read(n=-1):
        return await queue.get()

    proc.stdout.read.side_effect = mock_read
    proc.stdin = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.wait = AsyncMock()
    proc.wait_closed = AsyncMock()
    return proc


async def _feed_when_pending(server, queue, responses):
    for request_id, payload in responses.items():
        while request_id not in server.pending_requests:
            await asyncio.sleep(0.005)
        queue.put_nowait(_frame({**payload, "id": request_id}))
