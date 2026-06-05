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

        # 2. Test get_diagnostics — primary path is the push notification
        # textDocument/publishDiagnostics. The server cache reads from there;
        # the pull-diagnostics request is now only a fallback when no push
        # arrived within wait_for_publish.
        diag_uri = lsp_server._path_to_uri("/test/file.py")
        diag_notif = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": diag_uri, "diagnostics": [{"msg": "err"}]},
            }
        )
        diag_payload = f"Content-Length: {len(diag_notif)}\r\n\r\n{diag_notif}".encode()
        response_queue.put_nowait(diag_payload)

        res = await lsp_server.get_diagnostics("/test/file.py")
        assert res == [{"msg": "err"}]

        await lsp_server.stop()


def test_path_to_uri_encodes_special_characters(lsp_server):
    """B26: path_to_uri must quote #/?/%/non-ASCII, matching protocol encoder."""
    from zrb.llm.lsp.protocol import LSPProtocol

    for path in ["/tmp/a b.py", "/tmp/c#d.py", "/tmp/e?f.py", "/tmp/h%i.py", "/tmp/ünî.py"]:
        uri = lsp_server._path_to_uri(path)
        expected = LSPProtocol.create_text_document_identifier(path)["uri"]
        assert uri == expected
        # Round-trips back to the original absolute path.
        assert lsp_server._uri_to_path(uri).endswith(path.split("/")[-1])
        # Spaces and reserved chars are percent-encoded, not left raw.
        assert " " not in uri


@pytest.mark.asyncio
async def test_rename_applies_workspace_edit_to_disk(lsp_server, tmp_path):
    """B7 option (a): non-dry-run rename writes edits to disk and reports applied."""
    target = tmp_path / "mod.py"
    target.write_text("def old_name():\n    return old_name\n")

    workspace_edit = {
        "changes": {
            lsp_server._path_to_uri(str(target)): [
                {
                    "range": {
                        "start": {"line": 0, "character": 4},
                        "end": {"line": 0, "character": 12},
                    },
                    "newText": "new_name",
                },
                {
                    "range": {
                        "start": {"line": 1, "character": 11},
                        "end": {"line": 1, "character": 19},
                    },
                    "newText": "new_name",
                },
            ]
        }
    }

    lsp_server.initialized = True
    with patch.object(
        lsp_server, "_send_request_raw", AsyncMock(return_value=workspace_edit)
    ):
        result = await lsp_server.rename(str(target), 0, 4, "new_name", dry_run=False)

    assert result["applied"] is True
    assert target.read_text() == "def new_name():\n    return new_name\n"


@pytest.mark.asyncio
async def test_rename_dry_run_does_not_write(lsp_server, tmp_path):
    """B7: dry-run returns the edit unchanged without touching disk."""
    target = tmp_path / "mod.py"
    original = "def old_name():\n    pass\n"
    target.write_text(original)

    workspace_edit = {
        "changes": {
            lsp_server._path_to_uri(str(target)): [
                {
                    "range": {
                        "start": {"line": 0, "character": 4},
                        "end": {"line": 0, "character": 12},
                    },
                    "newText": "new_name",
                }
            ]
        }
    }

    lsp_server.initialized = True
    with patch.object(
        lsp_server, "_send_request_raw", AsyncMock(return_value=workspace_edit)
    ):
        result = await lsp_server.rename(str(target), 0, 4, "new_name", dry_run=True)

    assert "applied" not in result
    assert target.read_text() == original


@pytest.mark.asyncio
async def test_rename_apply_failure_reports_not_applied(lsp_server):
    """B7: when no edits can be written, applied is False (never silently True)."""
    workspace_edit = {
        "changes": {
            "file:///nonexistent/does_not_exist_xyz.py": [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 1},
                    },
                    "newText": "x",
                }
            ]
        }
    }

    lsp_server.initialized = True
    with patch.object(
        lsp_server, "_send_request_raw", AsyncMock(return_value=workspace_edit)
    ):
        result = await lsp_server.rename("/x.py", 0, 0, "x", dry_run=False)

    assert result["applied"] is False
