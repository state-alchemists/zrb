"""Tests for LSP tools public API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLspTools:
    """Tests for LSP tool functions through public API."""

    @pytest.mark.asyncio
    async def test_find_definition_delegates_to_manager(self):
        """Test find_definition delegates to lsp_manager."""
        from zrb.llm.lsp.tools import find_definition

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.find_definition = AsyncMock(
                return_value={"file": "test.py", "line": 10}
            )

            result = await find_definition("MyClass", "test.py")

            mock_manager.find_definition.assert_called_once_with(
                "MyClass", "test.py", None
            )
            assert result == {"file": "test.py", "line": 10}

    @pytest.mark.asyncio
    async def test_find_definition_with_symbol_kind(self):
        """Test find_definition with symbol_kind parameter."""
        from zrb.llm.lsp.tools import find_definition

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.find_definition = AsyncMock(return_value={"found": True})

            result = await find_definition("my_func", "test.py", symbol_kind="function")

            mock_manager.find_definition.assert_called_once_with(
                "my_func", "test.py", "function"
            )
            assert result == {"found": True}

    @pytest.mark.asyncio
    async def test_find_references_delegates_to_manager(self):
        """Test find_references delegates to lsp_manager."""
        from zrb.llm.lsp.tools import find_references

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.find_references = AsyncMock(return_value={"references": []})

            result = await find_references("my_var", "test.py")

            mock_manager.find_references.assert_called_once()
            assert result == {"references": []}

    @pytest.mark.asyncio
    async def test_find_references_with_all_params(self):
        """Test find_references with all parameters."""
        from zrb.llm.lsp.tools import find_references

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.find_references = AsyncMock(return_value={"count": 5})

            result = await find_references(
                "my_var", "test.py", line=10, character=5, include_declaration=False
            )

            mock_manager.find_references.assert_called_once_with(
                "my_var", "test.py", 10, 5, False
            )
            assert result == {"count": 5}

    @pytest.mark.asyncio
    async def test_get_diagnostics_delegates_to_manager(self):
        """Test get_diagnostics delegates to lsp_manager."""
        from zrb.llm.lsp.tools import get_diagnostics

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_diagnostics = AsyncMock(return_value={"diagnostics": []})

            result = await get_diagnostics("test.py")

            mock_manager.get_diagnostics.assert_called_once_with("test.py", None)
            assert result == {"diagnostics": []}

    @pytest.mark.asyncio
    async def test_get_diagnostics_with_severity(self):
        """Test get_diagnostics with severity filter."""
        from zrb.llm.lsp.tools import get_diagnostics

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_diagnostics = AsyncMock(return_value={"errors": 0})

            result = await get_diagnostics("test.py", severity="error")

            mock_manager.get_diagnostics.assert_called_once_with("test.py", "error")
            assert result == {"errors": 0}

    @pytest.mark.asyncio
    async def test_get_document_symbols_delegates_to_manager(self):
        """Test get_document_symbols delegates to lsp_manager."""
        from zrb.llm.lsp.tools import get_document_symbols

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_document_symbols = AsyncMock(return_value={"symbols": []})

            result = await get_document_symbols("test.py")

            mock_manager.get_document_symbols.assert_called_once_with("test.py")
            assert result == {"symbols": []}

    @pytest.mark.asyncio
    async def test_get_workspace_symbols_delegates_to_manager(self):
        """Test get_workspace_symbols delegates to lsp_manager."""
        from zrb.llm.lsp.tools import get_workspace_symbols

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_workspace_symbols = AsyncMock(return_value={"symbols": []})

            result = await get_workspace_symbols("MyClass")

            mock_manager.get_workspace_symbols.assert_called_once_with("MyClass", ".")
            assert result == {"symbols": []}

    @pytest.mark.asyncio
    async def test_get_workspace_symbols_with_file_path(self):
        """Test get_workspace_symbols with file_path parameter."""
        from zrb.llm.lsp.tools import get_workspace_symbols

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_workspace_symbols = AsyncMock(return_value={"found": True})

            result = await get_workspace_symbols("MyClass", file_path="src/test.py")

            mock_manager.get_workspace_symbols.assert_called_once_with(
                "MyClass", "src/test.py"
            )
            assert result == {"found": True}

    @pytest.mark.asyncio
    async def test_get_hover_info_delegates_to_manager(self):
        """Test get_hover_info delegates to lsp_manager."""
        from zrb.llm.lsp.tools import get_hover_info

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.get_hover_info = AsyncMock(
                return_value={"type": "str", "docstring": "A string"}
            )

            result = await get_hover_info("test.py", 10, 5)

            mock_manager.get_hover_info.assert_called_once_with("test.py", 10, 5)
            assert result == {"type": "str", "docstring": "A string"}

    @pytest.mark.asyncio
    async def test_rename_symbol_delegates_to_manager(self):
        """Test rename_symbol delegates to lsp_manager."""
        from zrb.llm.lsp.tools import rename_symbol

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.rename_symbol = AsyncMock(
                return_value={"changes": {}, "dry_run": True}
            )

            result = await rename_symbol("old_name", "new_name", "test.py")

            mock_manager.rename_symbol.assert_called_once_with(
                "old_name", "new_name", "test.py", 0, 0, True
            )
            assert result == {"changes": {}, "dry_run": True}

    @pytest.mark.asyncio
    async def test_rename_symbol_with_all_params(self):
        """Test rename_symbol with all parameters."""
        from zrb.llm.lsp.tools import rename_symbol

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.rename_symbol = AsyncMock(return_value={"renamed": 5})

            result = await rename_symbol(
                "old_name", "new_name", "test.py", line=10, character=5, dry_run=False
            )

            mock_manager.rename_symbol.assert_called_once_with(
                "old_name", "new_name", "test.py", 10, 5, False
            )
            assert result == {"renamed": 5}

    @pytest.mark.asyncio
    async def test_list_available_servers(self):
        """Test list_available_servers returns server info."""
        from zrb.llm.lsp.tools import list_available_servers

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.list_available_servers = MagicMock(
                return_value={"pyright": "/usr/bin/pyright"}
            )

            with patch("zrb.llm.lsp.server.LSP_SERVER_CONFIGS") as mock_configs:
                mock_config = MagicMock()
                mock_config.language_ids = ["python"]
                mock_configs.get = MagicMock(return_value=mock_config)

                result = await list_available_servers()

                assert "servers" in result
                assert "language_support" in result
                assert "message" in result
                assert "suggestion" in result
                assert result["servers"] == {"pyright": "/usr/bin/pyright"}

    @pytest.mark.asyncio
    async def test_list_available_servers_multiple_languages(self):
        """Test list_available_servers with multiple languages per server."""
        from zrb.llm.lsp.tools import list_available_servers

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.list_available_servers = MagicMock(
                return_value={"typescript-language-server": "/usr/bin/tsserver"}
            )

            with patch("zrb.llm.lsp.server.LSP_SERVER_CONFIGS") as mock_configs:
                mock_config = MagicMock()
                mock_config.language_ids = ["typescript", "javascript"]
                mock_configs.get = MagicMock(return_value=mock_config)

                result = await list_available_servers()

                assert "typescript" in result["language_support"]
                assert "javascript" in result["language_support"]

    @pytest.mark.asyncio
    async def test_list_available_servers_no_config(self):
        """Test list_available_servers handles missing server config."""
        from zrb.llm.lsp.tools import list_available_servers

        with patch("zrb.llm.lsp.tools.lsp_manager") as mock_manager:
            mock_manager.list_available_servers = MagicMock(
                return_value={"unknown-server": "/usr/bin/unknown"}
            )

            with patch("zrb.llm.lsp.server.LSP_SERVER_CONFIGS") as mock_configs:
                mock_configs.get = MagicMock(return_value=None)

                result = await list_available_servers()

                assert "servers" in result
                assert result["servers"] == {"unknown-server": "/usr/bin/unknown"}
                # language_support should be empty for unknown servers
                assert result["language_support"] == {}

    def test_create_lsp_tools(self):
        """Test create_lsp_tools returns all tool functions."""
        from zrb.llm.lsp.tools import create_lsp_tools

        tools = create_lsp_tools()

        assert len(tools) == 8
        tool_names = [t.__name__ for t in tools]
        assert "LspFindDefinition" in tool_names
        assert "LspFindReferences" in tool_names
        assert "LspGetDiagnostics" in tool_names
        assert "LspGetDocumentSymbols" in tool_names
        assert "LspGetWorkspaceSymbols" in tool_names
        assert "LspGetHoverInfo" in tool_names
        assert "LspRenameSymbol" in tool_names
        assert "LspListServers" in tool_names
