import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.lsp.configs import LSPServerConfig
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
async def test_lsp_server_lifecycle(lsp_server):
    """Test start and stop of LSPServer using public API."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdout = AsyncMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write = MagicMock()
        mock_proc.stdin.drain = AsyncMock()
        mock_proc.wait = AsyncMock()
        mock_proc.wait_closed = AsyncMock()
        mock_exec.return_value = mock_proc

        # 1. Start logic
        # Simulate initialize response arriving on stdout
        response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        res_str = json.dumps(response)
        res_payload = f"Content-Length: {len(res_str)}\r\n\r\n{res_str}".encode()

        # Track calls to read to simulate stream
        async def mock_read(*args, **kwargs):
            if mock_read.call_count == 0:
                mock_read.call_count += 1
                return res_payload
            await asyncio.sleep(0.1)  # Hang until stopped
            return b""

        mock_read.call_count = 0
        mock_proc.stdout.read.side_effect = mock_read

        # Test start()
        started = await lsp_server.start()
        assert started is True
        assert lsp_server.is_alive is True

        # 2. Stop logic
        await lsp_server.stop()
        assert lsp_server.is_alive is False


@pytest.mark.asyncio
async def test_lsp_server_queries(lsp_server):
    """Test public query methods by simulating server responses."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdout = AsyncMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.drain = AsyncMock()
        mock_proc.wait = AsyncMock()
        mock_proc.wait_closed = AsyncMock()
        mock_exec.return_value = mock_proc

        # Start the server first
        init_res = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        )
        init_payload = f"Content-Length: {len(init_res)}\r\n\r\n{init_res}".encode()

        # Queue for responses
        response_queue = asyncio.Queue()
        response_queue.put_nowait(init_payload)

        async def mock_read(n=-1):
            return await response_queue.get()

        mock_proc.stdout.read.side_effect = mock_read
        await lsp_server.start()

        # 1. Test document_symbols
        symbols_res = json.dumps(
            {"jsonrpc": "2.0", "id": 2, "result": [{"name": "test"}]}
        )
        symbols_payload = (
            f"Content-Length: {len(symbols_res)}\r\n\r\n{symbols_res}".encode()
        )
        response_queue.put_nowait(symbols_payload)

        with patch("pathlib.Path.exists", return_value=True):
            res = await lsp_server.document_symbols("/test/file.py")
            assert res == [{"name": "test"}]

        # 2. Test get_diagnostics (via pull diagnostics if supported)
        diag_res = json.dumps(
            {"jsonrpc": "2.0", "id": 3, "result": {"items": [{"msg": "err"}]}}
        )
        diag_payload = f"Content-Length: {len(diag_res)}\r\n\r\n{diag_res}".encode()
        response_queue.put_nowait(diag_payload)

        res = await lsp_server.get_diagnostics("/test/file.py")
        assert res == [{"msg": "err"}]

        await lsp_server.stop()
