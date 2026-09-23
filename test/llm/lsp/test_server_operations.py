"""Response-shape and document-sync tests for ``LSPServerOperations``.

Runs through the public query API against a mocked subprocess transport
(``asyncio.create_subprocess_exec``) fed from an ``asyncio.Queue``, so every
JSON-RPC response shape arrives over the real read loop instead of being
short-circuited past the framing/parse layer.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.lsp.configs import LSPServerConfig
from zrb.llm.lsp.protocol import LSPTimeoutError
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
async def test_queries_require_initialized_server(lsp_server):
    assert await lsp_server.goto_definition("/x.py", 0, 0) is None
    assert await lsp_server.find_references("/x.py", 0, 0) is None
    assert await lsp_server.hover("/x.py", 0, 0) is None
    assert await lsp_server.workspace_symbols("Foo") is None
    assert await lsp_server.document_symbols("/x.py") is None
    assert await lsp_server.get_diagnostics("/x.py") is None
    assert await lsp_server.rename("/x.py", 0, 0, "new_name") is None


@pytest.mark.asyncio
async def test_goto_definition_normalizes_result_shapes(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {
                2: {"result": [{"uri": "file:///a.py", "range": {}}]},
                3: {"result": {"uri": "file:///b.py", "range": {}}},
                4: {"result": {"range": {}}},
                5: {"result": None},
            },
        )
    )
    assert await lsp_server.goto_definition("/never/here.py", 0, 0) == [
        {"uri": "file:///a.py", "range": {}}
    ]
    assert await lsp_server.goto_definition("/never/here.py", 0, 0) == [
        {"uri": "file:///b.py", "range": {}}
    ]
    assert await lsp_server.goto_definition("/never/here.py", 0, 0) is None
    assert await lsp_server.goto_definition("/never/here.py", 0, 0) is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_find_references_returns_list_only(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {
                2: {"result": [{"uri": "file:///r.py", "range": {}}]},
                3: {"result": {"uri": "file:///r.py"}},
            },
        )
    )
    assert await lsp_server.find_references("/never/here.py", 0, 0) == [
        {"uri": "file:///r.py", "range": {}}
    ]
    assert await lsp_server.find_references("/never/here.py", 0, 0) is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_did_open_requires_initialized(lsp_server):
    await lsp_server.did_open_text_document("/x.py")
    assert lsp_server.open_files == set()


@pytest.mark.asyncio
async def test_did_open_skips_already_open_file(lsp_server):
    lsp_server.initialized = True
    lsp_server.writer = MagicMock()
    lsp_server.writer.drain = AsyncMock()
    uri = lsp_server.path_to_uri("/x.py")
    lsp_server.open_files.add(uri)
    await lsp_server.did_open_text_document("/x.py")
    lsp_server.writer.write.assert_not_called()


@pytest.mark.asyncio
async def test_did_change_requires_initialized(lsp_server):
    await lsp_server.did_change_text_document("/x.py")
    assert lsp_server.open_files == set()


@pytest.mark.asyncio
async def test_did_change_opens_unopened_file(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    lsp_server.initialized = True
    lsp_server.writer = MagicMock()
    lsp_server.writer.drain = AsyncMock()
    await lsp_server.did_change_text_document(str(target))
    assert lsp_server.path_to_uri(str(target)) in lsp_server.open_files


@pytest.mark.asyncio
async def test_did_change_sends_full_document_replacement(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    lsp_server.initialized = True
    lsp_server.writer = MagicMock()
    lsp_server.writer.drain = AsyncMock()
    uri = lsp_server.path_to_uri(str(target))
    lsp_server.open_files.add(uri)
    await lsp_server.did_change_text_document(str(target))
    payload = lsp_server.writer.write.call_args.args[0].decode()
    notif = json.loads(payload.split("\r\n\r\n", 1)[1])
    assert notif["method"] == "textDocument/didChange"
    assert notif["params"]["contentChanges"] == [{"text": "x = 1\n"}]
    assert notif["params"]["textDocument"]["version"] == 2


@pytest.mark.asyncio
async def test_get_diagnostics_pull_fallback(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {
                2: {"result": {"items": [{"range": {}, "message": "pull"}]}},
                3: {"result": [{"range": {}, "message": "list"}]},
                4: {"error": {"code": -32601, "message": "no pull support"}},
            },
        )
    )
    assert await lsp_server.get_diagnostics(str(target), wait_for_publish=0) == [
        {"range": {}, "message": "pull"}
    ]
    assert await lsp_server.get_diagnostics(str(target), wait_for_publish=0) == [
        {"range": {}, "message": "list"}
    ]
    assert await lsp_server.get_diagnostics(str(target), wait_for_publish=0) is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_query_waits_for_first_analysis(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    uri = lsp_server.path_to_uri(str(target))
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)

    async def publish_diagnostics_then_feed():
        await asyncio.sleep(0.01)
        lsp_server.diagnostics[uri] = (None, [])
        await _feed_when_pending(
            lsp_server, queue, {2: {"result": [{"uri": "file:///d.py"}]}}
        )

    seed = asyncio.create_task(publish_diagnostics_then_feed())
    assert await lsp_server.goto_definition(str(target), 0, 0) == [
        {"uri": "file:///d.py"}
    ]
    await seed
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_workspace_symbols_returns_list_only(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"result": [{"name": "Foo"}]}, 3: {"result": {"name": "Foo"}}},
        )
    )
    assert await lsp_server.workspace_symbols("Foo") == [{"name": "Foo"}]
    assert await lsp_server.workspace_symbols("Foo") is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_hover_returns_dict_only(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"result": {"contents": "hi"}}, 3: {"result": ["hi"]}},
        )
    )
    assert await lsp_server.hover("/never/here.py", 0, 0) == {"contents": "hi"}
    assert await lsp_server.hover("/never/here.py", 0, 0) is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_rename_short_circuits_when_prepare_finds_nothing(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(lsp_server, queue, {2: {"result": None}})
    )
    assert await lsp_server.rename("/never/here.py", 0, 0, "new_name") is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_rename_continues_when_prepare_unsupported(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {
                2: {"error": {"code": -32601, "message": "no prepareRename"}},
                3: {"result": {"changes": {}}},
            },
        )
    )
    assert await lsp_server.rename("/never/here.py", 0, 0, "new_name") == {
        "changes": {}
    }
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_rename_returns_none_for_non_dict_result(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"result": {}}, 3: {"result": None}},
        )
    )
    assert await lsp_server.rename("/never/here.py", 0, 0, "new_name") is None
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_rename_apply_reports_false_for_empty_edit(lsp_server):
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"result": {}}, 3: {"result": {"unrelated": True}}},
        )
    )
    result = await lsp_server.rename("/never/here.py", 0, 0, "new_name", dry_run=False)
    assert result["applied"] is False
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_rename_applies_document_changes_to_disk(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("def old_name():\n    pass\n")
    uri = lsp_server.path_to_uri(str(target))
    workspace_edit = {
        "documentChanges": [
            "not-a-dict",
            {
                "textDocument": {"uri": uri},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 4},
                            "end": {"line": 0, "character": 12},
                        },
                        "newText": "new_name",
                    }
                ],
            },
        ]
    }
    queue = asyncio.Queue()
    assert await _start_server(lsp_server, queue)
    feeder = asyncio.create_task(
        _feed_when_pending(
            lsp_server,
            queue,
            {2: {"result": {}}, 3: {"result": workspace_edit}},
        )
    )
    result = await lsp_server.rename("/never/here.py", 0, 0, "new_name", dry_run=False)
    assert result["applied"] is True
    assert target.read_text() == "def new_name():\n    pass\n"
    await feeder
    await lsp_server.stop()


@pytest.mark.asyncio
async def test_send_request_without_writer_returns_none(lsp_server):
    lsp_server.initialized = True
    assert await lsp_server.goto_definition("/x.py", 0, 0) is None


@pytest.mark.asyncio
async def test_send_request_times_out(lsp_server):
    lsp_server.initialized = True
    lsp_server.config.timeout = 1
    lsp_server.writer = MagicMock()
    lsp_server.writer.drain = AsyncMock()
    with pytest.raises(LSPTimeoutError):
        await lsp_server.goto_definition("/never/here.py", 0, 0)


@pytest.mark.asyncio
async def test_send_request_write_failure_reaches_caller(lsp_server):
    lsp_server.initialized = True
    lsp_server.writer = MagicMock()
    lsp_server.writer.drain = AsyncMock(side_effect=RuntimeError("write boom"))
    with pytest.raises(RuntimeError):
        await lsp_server.goto_definition("/never/here.py", 0, 0)


@pytest.mark.asyncio
async def test_notification_without_writer_still_marks_file_open(lsp_server, tmp_path):
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    lsp_server.initialized = True
    await lsp_server.did_open_text_document(str(target))
    assert lsp_server.path_to_uri(str(target)) in lsp_server.open_files


async def _start_server(server, queue):
    queue.put_nowait(
        _frame({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}})
    )
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = _queued_subprocess(queue)
        return await server.start()


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
