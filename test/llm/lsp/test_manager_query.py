"""Query-branch tests for ``LSPManagerQuery``.

Covers the error/fallback/formatting branches that live in
``zrb.llm.lsp.manager_query``, driven through the manager's public query
methods with the server and symbol-position collaborators mocked.
"""

from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.lsp.configs import lsp_server_configs
from zrb.llm.lsp.manager import LSPManager
from zrb.llm.lsp.protocol import SymbolKind


@pytest.fixture(autouse=True)
def _cleanup_registry():
    lsp_server_configs.clear()
    yield
    lsp_server_configs.clear()


@pytest.fixture
def manager():
    LSPManager.reset_singleton()
    return LSPManager()


@pytest.mark.asyncio
async def test_queries_report_no_server_available(manager):
    """Every query method returns the no-server error shape."""
    with patch.object(manager, "get_server", return_value=None):
        refs = await manager.find_references("sym", "file.py")
        diags = await manager.get_diagnostics("file.py")
        doc = await manager.get_document_symbols("file.py")
        ws = await manager.get_workspace_symbols("query", "file.py")
        hover = await manager.get_hover_info("file.py", 0, 0)
        rename = await manager.rename_symbol("old", "new", "file.py")
    for result in (refs, diags, doc, ws, hover):
        assert result["found"] is False
        assert "No LSP server available" in result["error"]
    assert rename["success"] is False
    assert "No LSP server available" in rename["error"]


@pytest.mark.asyncio
async def test_find_definition_primary_path_error_falls_back(manager):
    """A failing goto_definition falls back to workspace symbols."""
    mock_server = AsyncMock()
    mock_server.goto_definition.side_effect = Exception("definition boom")
    mock_server.workspace_symbols.return_value = []
    with (
        patch.object(manager, "get_server", return_value=mock_server),
        patch.object(manager, "find_symbol_position", return_value=(0, 0)),
    ):
        result = await manager.find_definition("Foo", "file.py")
    assert result["found"] is False
    assert "not found" in result["error"]
    mock_server.workspace_symbols.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_definition_skips_nonmatching_workspace_symbols(manager):
    """Symbols whose name differs from the query are skipped."""
    mock_server = AsyncMock()
    mock_server.workspace_symbols.return_value = [
        {"name": "Other", "kind": SymbolKind.CLASS.value, "location": {}},
        {"name": "Foo", "kind": SymbolKind.CLASS.value, "location": {"uri": "file:///x.py"}},
    ]
    with (
        patch.object(manager, "get_server", return_value=mock_server),
        patch.object(manager, "find_symbol_position", return_value=None),
    ):
        result = await manager.find_definition("Foo", "file.py")
    assert result["found"] is True
    assert result["symbol"] == "Foo"


@pytest.mark.asyncio
async def test_get_diagnostics_query_error(manager):
    """A get_diagnostics failure yields the friendly empty result."""
    mock_server = AsyncMock()
    mock_server.get_diagnostics.side_effect = Exception("diag boom")
    with patch.object(manager, "get_server", return_value=mock_server):
        result = await manager.get_diagnostics("file.py")
    assert result["found"] is False
    assert "No diagnostics available" in result["message"]


@pytest.mark.asyncio
async def test_workspace_symbols_formats_found(manager):
    mock_server = AsyncMock()
    mock_server.workspace_symbols.return_value = [
        {
            "name": "Foo",
            "kind": SymbolKind.CLASS.value,
            "location": {"uri": "file:///x/foo.py", "range": {}},
            "containerName": "mod",
        }
    ]
    with patch.object(manager, "get_server", return_value=mock_server):
        result = await manager.get_workspace_symbols("Foo", "file.py")
    assert result["found"] is True
    assert result["symbols"][0]["path"].endswith("foo.py")
    assert result["symbols"][0]["kind"] == "class"
    assert result["symbols"][0]["container"] == "mod"


@pytest.mark.asyncio
async def test_hover_uses_dict_content(manager):
    mock_server = AsyncMock()
    mock_server.hover.return_value = {"contents": {"value": "dict content"}}
    with patch.object(manager, "get_server", return_value=mock_server):
        result = await manager.get_hover_info("file.py", 0, 0)
    assert result["found"] is True
    assert result["info"] == "dict content"


@pytest.mark.asyncio
async def test_find_symbol_position_prefers_candidate_line(manager, tmp_path):
    """The line from document symbols wins, with the exact col from the text."""
    target = tmp_path / "mod.py"
    target.write_text("class Foo:\n    pass\n")
    mock_symbols = {"found": True, "symbols": [{"name": "Foo", "line": 1}]}
    with patch.object(
        manager, "get_document_symbols", AsyncMock(return_value=mock_symbols)
    ):
        position = await manager.find_symbol_position(str(target), "Foo")
    assert position == (0, 6)


@pytest.mark.asyncio
async def test_find_symbol_position_falls_back_to_file_scan(manager, tmp_path):
    """When document symbols fail, the whole file is scanned for the name."""
    target = tmp_path / "mod.py"
    target.write_text("x = Foo()\n")
    with patch.object(
        manager, "get_document_symbols", AsyncMock(side_effect=Exception("boom"))
    ):
        position = await manager.find_symbol_position(str(target), "Foo")
    assert position == (0, 4)


@pytest.mark.asyncio
async def test_rename_symbol_counts_document_changes(manager):
    """documentChanges entries count toward total_edits."""
    mock_server = AsyncMock()
    mock_server.rename.return_value = {
        "documentChanges": [
            "not-a-dict",
            {
                "textDocument": {"uri": "file:///x/foo.py"},
                "edits": [{"newText": "new", "range": {}}],
            },
        ]
    }
    with (
        patch.object(manager, "get_server", return_value=mock_server),
        patch.object(manager, "find_symbol_position", return_value=(0, 0)),
    ):
        result = await manager.rename_symbol("old", "new", "file.py", dry_run=True)
    assert result["success"] is True
    assert result["total_edits"] == 1
    assert result["files_affected"] == 1