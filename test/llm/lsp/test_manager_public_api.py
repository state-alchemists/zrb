"""Tests for LSP manager functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.lsp.configs import lsp_server_configs
from zrb.llm.lsp.manager import LSPManager
from zrb.llm.lsp.protocol import SymbolKind
from zrb.llm.lsp.server import LSPServer


@pytest.fixture(autouse=True)
def _cleanup_registry():
    """Clear user-registered LSP server configs between tests.

    Tests that call ``register_lsp_server`` write to the module-level
    ``lsp_server_configs`` singleton. Clearing before each test prevents
    cross-test pollution of the global config registry.

    Cleared after as well: clearing only on the way in protects *these* tests
    from everyone else while leaking their own registrations into whichever
    unrelated test pytest-xdist runs next in this worker.
    """
    lsp_server_configs.clear()
    yield
    lsp_server_configs.clear()


@pytest.fixture
def manager():
    """Create a fresh LSPManager for each test by resetting the singleton."""
    LSPManager.reset_singleton()
    return LSPManager()


class TestLspPublicAPI:
    """Test high-level public API methods."""

    def test_list_servers_returns_dict(self, manager):
        result = manager.list_available_servers()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_document_symbols_formatting(self, manager, tmp_path):
        """Test document symbols through the public API."""
        test_file = tmp_path / "test.py"
        test_file.touch()

        mock_server = MagicMock()
        mock_server.is_alive = True
        mock_server.start = AsyncMock(return_value=True)
        # Mock raw LSP response
        mock_server.document_symbols = AsyncMock(
            return_value=[
                {
                    "name": "my_func",
                    "kind": 12,
                    "selectionRange": {
                        "start": {"line": 0, "character": 4},
                        "end": {"line": 0, "character": 11},
                    },
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 5, "character": 0},
                    },
                }
            ]
        )

        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_config,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
        ):
            mock_get_config.return_value = MagicMock()

            result = await manager.get_document_symbols(str(test_file))
            assert result["found"] is True
            assert result["symbols"][0]["name"] == "my_func"
            assert result["symbols"][0]["line"] == 1

    @pytest.mark.asyncio
    async def test_find_definition_kind_filter(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.workspace_symbols.return_value = [
            {
                "name": "sym",
                "kind": SymbolKind.CLASS.value,
                "location": {"uri": "file://1", "range": {}},
            },
            {
                "name": "sym",
                "kind": SymbolKind.FUNCTION.value,
                "location": {"uri": "file://2", "range": {}},
            },
        ]

        with patch.object(manager, "get_server", return_value=mock_server):
            # Filter for function
            result = await manager.find_definition(
                "sym", "file.py", symbol_kind="function"
            )
            assert result["found"] is True
            assert result["kind"] == "function"

    @pytest.mark.asyncio
    async def test_find_definition_uses_goto_definition(self, manager, tmp_path):
        """find_definition resolves via textDocument/definition at the identifier's
        column (not workspace/symbol), which works on every LSP server."""
        f = tmp_path / "mod.py"
        f.write_text("class Foo:\n    pass\n")  # 'Foo' is at line 0, char 6

        mock_server = AsyncMock(spec=LSPServer)
        mock_server.document_symbols.return_value = []  # force regex column lookup
        mock_server.goto_definition.return_value = [
            {"uri": "file:///x/foo_def.py", "range": {"start": {"line": 2}}}
        ]

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.find_definition("Foo", str(f))

        assert result["found"] is True
        assert result["path"].endswith("foo_def.py")
        # Position passed to goto_definition must sit ON the identifier (col 6).
        line, char = mock_server.goto_definition.call_args.args[1:3]
        assert (line, char) == (0, 6)
        mock_server.workspace_symbols.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_definition_falls_back_to_workspace_symbols(
        self, manager, tmp_path
    ):
        """When textDocument/definition yields nothing, fall back to a
        workspace/symbol search (servers that support it)."""
        f = tmp_path / "mod.py"
        f.write_text("Foo()\n")

        mock_server = AsyncMock(spec=LSPServer)
        mock_server.document_symbols.return_value = []
        mock_server.goto_definition.return_value = None
        mock_server.workspace_symbols.return_value = [
            {
                "name": "Foo",
                "kind": SymbolKind.CLASS.value,
                "location": {"uri": "file:///ws/foo.py", "range": {}},
            }
        ]

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.find_definition("Foo", str(f))

        assert result["found"] is True
        assert result["path"].endswith("foo.py")

    @pytest.mark.asyncio
    async def test_get_workspace_symbols_file_fallback(self, manager, tmp_path):
        """When the server can't do workspace/symbol (pylsp Method Not Found, or
        pyright empty), fall back to the seed file's symbols filtered by query."""
        f = tmp_path / "mod.py"
        f.write_text("class LLMTask:\n    pass\n")

        mock_server = AsyncMock(spec=LSPServer)
        # Simulate an unsupported workspace/symbol.
        mock_server.workspace_symbols.side_effect = Exception("Method Not Found")
        mock_server.document_symbols.return_value = [
            {
                "name": "LLMTask",
                "kind": SymbolKind.CLASS.value,
                "location": {
                    "uri": "file:///x/mod.py",
                    "range": {"start": {"line": 0, "character": 6}},
                },
            }
        ]

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_workspace_symbols("LLMTask", str(f))

        assert result["found"] is True
        assert result["scope"] == "file"
        assert any(s["name"] == "LLMTask" for s in result["symbols"])

    @pytest.mark.asyncio
    async def test_find_references_no_pos(self, manager, tmp_path):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.find_references.return_value = [
            {"uri": "file://ref", "range": {"start": {"line": 0, "character": 0}}}
        ]

        file_path = tmp_path / "test.py"
        file_path.write_text("def my_func(): pass")

        with (
            patch.object(manager, "get_server", return_value=mock_server),
            patch.object(manager, "find_symbol_position", return_value=(0, 4)),
        ):
            result = await manager.find_references("my_func", str(file_path))
            assert result["found"] is True
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_diagnostics_unknown_severity(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.get_diagnostics.return_value = [
            {
                "severity": 99,
                "message": "msg",
                "range": {"start": {"line": 0, "character": 0}},
            }
        ]

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_diagnostics("file.py")
            assert result["diagnostics"][0]["severity"] == "unknown"

    @pytest.mark.asyncio
    async def test_get_hover_info_complex(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        # Hover content as list of dicts
        mock_server.hover.return_value = {
            "contents": [{"value": "part1"}, {"value": "part2"}]
        }

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_hover_info("file.py", 0, 0)
            assert "part1\npart2" in result["info"]

    @pytest.mark.asyncio
    async def test_rename_symbol_preview(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.return_value = {
            "changes": {"file://1": [{"newText": "new", "range": {}}]}
        }

        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.rename_symbol("old", "new", "file.py", dry_run=True)
            assert result["success"] is True
            assert result["total_edits"] == 1
            assert "changes" in result

    @pytest.mark.asyncio
    async def test_rename_symbol_apply_reports_applied(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.return_value = {
            "changes": {"file://1": [{"newText": "new", "range": {}}]},
            "applied": True,
        }
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.rename_symbol(
                "old", "new", "file.py", line=1, character=0, dry_run=False
            )
            assert result["success"] is True
            assert result["changes"] == "Applied"

    @pytest.mark.asyncio
    async def test_rename_symbol_not_applied_is_honest(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.return_value = {
            "changes": {"file://1": [{"newText": "new", "range": {}}]},
            "applied": False,
        }
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.rename_symbol(
                "old", "new", "file.py", line=1, character=0, dry_run=False
            )
            # Never claim success when nothing was written.
            assert result["success"] is False
            assert result["changes"] == "not_applied"

    @pytest.mark.asyncio
    async def test_find_definition_not_found(self, manager):
        with patch.object(manager, "get_server", return_value=None):
            result = await manager.find_definition("sym", "file.py")
            assert result["found"] is False
            assert "No LSP server available" in result["error"]

    @pytest.mark.asyncio
    async def test_get_diagnostics_filter(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.get_diagnostics.return_value = [
            {
                "severity": 1,
                "message": "error",
                "range": {"start": {"line": 0, "character": 0}},
            },
            {
                "severity": 2,
                "message": "warning",
                "range": {"start": {"line": 1, "character": 0}},
            },
        ]
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_diagnostics("file.py", severity="error")
            assert result["count"] == 1
            assert result["diagnostics"][0]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_get_workspace_symbols_empty(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.workspace_symbols.return_value = []
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_workspace_symbols("query", "file.py")
            assert result["found"] is False

    @pytest.mark.asyncio
    async def test_rename_symbol_failure(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.return_value = None
        with (
            patch.object(manager, "get_server", return_value=mock_server),
            patch.object(manager, "find_symbol_position", return_value=(0, 0)),
        ):
            result = await manager.rename_symbol("old", "new", "file.py")
            assert result["success"] is False
            assert "Could not rename" in result["error"]

    @pytest.mark.asyncio
    async def test_find_definition_with_kind(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.workspace_symbols.return_value = [
            {"name": "my_func", "kind": 12, "location": {"uri": "file.py", "range": {}}}
        ]
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.find_definition(
                "my_func", "file.py", symbol_kind="function"
            )
            assert result["found"] is True
            assert result["kind"] == "function"

    @pytest.mark.asyncio
    async def test_get_hover_info_list(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.hover.return_value = {"contents": [{"value": "part1"}, "part2"]}
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_hover_info("file.py", 0, 0)
            assert result["found"] is True
            assert "part1\npart2" in result["info"]

    @pytest.mark.asyncio
    async def test_rename_symbol_with_changes(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.return_value = {
            "changes": {"file://path/to/file.py": [{"range": {}, "newText": "new"}]}
        }
        with (
            patch.object(manager, "get_server", return_value=mock_server),
            patch.object(manager, "find_symbol_position", return_value=(0, 0)),
        ):
            result = await manager.rename_symbol("old", "new", "file.py")
            assert result["success"] is True
            assert result["files_affected"] == 1

    @pytest.mark.asyncio
    async def test_find_definition_error_handling(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.workspace_symbols.side_effect = Exception("workspace_symbols error")
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.find_definition("my_func", "file.py")
            assert result["found"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_find_references_error_handling(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.find_references.side_effect = Exception("find_references error")
        with (
            patch.object(manager, "get_server", return_value=mock_server),
            patch.object(manager, "find_symbol_position", return_value=(0, 0)),
        ):
            result = await manager.find_references("my_func", "file.py")
            assert result["found"] is False
            assert "No references found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_diagnostics_empty(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.get_diagnostics.return_value = []
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_diagnostics("file.py")
            assert result["found"] is False
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_get_document_symbols_error(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.document_symbols.side_effect = Exception("document_symbols error")
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_document_symbols("file.py")
            assert result["found"] is False
            assert "Could not retrieve" in result["error"]

    @pytest.mark.asyncio
    async def test_get_workspace_symbols_error(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.workspace_symbols.side_effect = Exception("workspace_symbols error")
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_workspace_symbols("query", "file.py")
            assert result["found"] is False

    @pytest.mark.asyncio
    async def test_get_hover_info_error(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.hover.side_effect = Exception("hover error")
        with patch.object(manager, "get_server", return_value=mock_server):
            result = await manager.get_hover_info("file.py", 0, 0)
            assert result["found"] is False

    @pytest.mark.asyncio
    async def test_rename_symbol_error(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.rename.side_effect = Exception("rename error")
        with (
            patch.object(manager, "get_server", return_value=mock_server),
            patch.object(manager, "find_symbol_position", return_value=(0, 0)),
        ):
            result = await manager.rename_symbol("old", "new", "file.py")
            assert result["success"] is False
