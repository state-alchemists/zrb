"""Tests for LSP manager functionality."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.lsp.manager import LSPManager, lsp_manager
from zrb.llm.lsp.protocol import SymbolKind
from zrb.llm.lsp.server import LSPServer


@pytest.fixture
def manager():
    """Create a fresh LSPManager for each test by resetting the singleton."""
    LSPManager._instance = None
    return LSPManager()


class TestLspManagerSingleton:
    """Test singleton behavior."""

    def test_singleton_returns_same_instance(self):
        LSPManager._instance = None
        m1 = LSPManager()
        m2 = LSPManager()
        assert m1 is m2

    def test_lsp_manager_global_is_singleton(self):
        assert isinstance(lsp_manager, LSPManager)


class TestLspManagerInit:
    """Test LSPManager initialization."""

    def test_lock_property_creates_lock(self, manager):
        lock = manager.lock
        assert isinstance(lock, asyncio.Lock)

    def test_lock_property_returns_same_instance(self, manager):
        lock1 = manager.lock
        lock2 = manager.lock
        assert lock1 is lock2


class TestDetectProjectRoot:
    """Test detect_project_root method."""

    def test_detect_root_with_git(self, manager, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        test_file = tmp_path / "subdir" / "file.py"
        test_file.parent.mkdir()
        root = manager.detect_project_root(str(test_file))
        assert root == str(tmp_path)

    def test_detect_root_with_pyproject(self, manager, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        test_file = tmp_path / "src" / "module.py"
        test_file.parent.mkdir()
        root = manager.detect_project_root(str(test_file))
        assert root == str(tmp_path)

    def test_detect_project_root_markers(self, manager, tmp_path):
        markers = [
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "package.json",
            "go.mod",
        ]
        for marker in markers:
            proj_dir = tmp_path / f"proj_{marker}"
            proj_dir.mkdir()
            (proj_dir / marker).touch()
            file_path = proj_dir / "src" / "main.py"
            file_path.parent.mkdir()
            file_path.touch()

            root = manager.detect_project_root(str(file_path))
            assert root == str(proj_dir)

    def test_detect_project_root_fallback(self, manager, tmp_path):
        file_path = tmp_path / "standalone.py"
        file_path.write_text("print('hello')")
        root = manager.detect_project_root(str(file_path))
        assert root == str(tmp_path)

    def test_detect_project_root_git_deep(self, manager, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        sub_dir = tmp_path / "src" / "deep"
        sub_dir.mkdir(parents=True)
        file_path = sub_dir / "main.py"
        file_path.write_text("pass")

        root = manager.detect_project_root(str(file_path))
        assert root == str(tmp_path)

    def test_detect_project_root_glob(self, manager, tmp_path):
        (tmp_path / "test.csproj").touch()
        file_path = tmp_path / "main.py"
        file_path.touch()
        root = manager.detect_project_root(str(file_path))
        assert root == str(tmp_path)


class TestLspManagerLifecycle:
    """Test server lifecycle and shutdown methods."""

    @pytest.mark.asyncio
    async def test_shutdown_all_empty(self, manager):
        await manager.shutdown_all()

    @pytest.mark.asyncio
    async def test_shutdown_idle(self, manager):
        await manager.shutdown_idle()

    @pytest.mark.asyncio
    async def test_shutdown_all_with_servers(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        with patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.get_lsp_config_for_file"
        ) as mock_get_cfg, patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.LSPServer", return_value=mock_server
        ):
            mock_get_cfg.return_value = MagicMock(language_ids=["python"])
            await manager.get_server("test.py")

            await manager.shutdown_all()
            mock_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_server_lifecycle(self, manager, tmp_path):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        mock_server.start.return_value = True

        with patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.get_lsp_config_for_file"
        ) as mock_get_cfg, patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.LSPServer", return_value=mock_server
        ):

            mock_get_cfg.return_value = MagicMock(language_ids=["python"])

            # Test starting new server
            server = await manager.get_server("test.py")
            assert server == mock_server

            # Test getting existing alive server
            server2 = await manager.get_server("test.py")
            assert server2 == mock_server

            # Test cleaning up dead server
            mock_server.is_alive = False
            mock_server2 = AsyncMock(spec=LSPServer)
            mock_server2.is_alive = True
            mock_server2.start.return_value = True

            with patch(
                "zrb.llm.lsp.manager.lifecycle_mixin.LSPServer",
                return_value=mock_server2,
            ):
                server3 = await manager.get_server("test.py")
                assert server3 == mock_server2

    @pytest.mark.asyncio
    async def test_get_server_no_config(self, manager):
        with patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.get_lsp_config_for_file",
            return_value=None,
        ):
            result = await manager.get_server("/path/to/file.unknown")
            assert result is None


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

        with patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.get_lsp_config_for_file"
        ) as mock_get_config, patch(
            "zrb.llm.lsp.manager.lifecycle_mixin.LSPServer", return_value=mock_server
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
    async def test_find_references_no_pos(self, manager, tmp_path):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.find_references.return_value = [
            {"uri": "file://ref", "range": {"start": {"line": 0, "character": 0}}}
        ]

        file_path = tmp_path / "test.py"
        file_path.write_text("def my_func(): pass")

        with patch.object(
            manager, "get_server", return_value=mock_server
        ), patch.object(manager, "_find_symbol_position", return_value=(0, 4)):
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
        with patch.object(
            manager, "get_server", return_value=mock_server
        ), patch.object(manager, "_find_symbol_position", return_value=(0, 0)):
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
        with patch.object(
            manager, "get_server", return_value=mock_server
        ), patch.object(manager, "_find_symbol_position", return_value=(0, 0)):
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
        with patch.object(
            manager, "get_server", return_value=mock_server
        ), patch.object(manager, "_find_symbol_position", return_value=(0, 0)):
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
        with patch.object(
            manager, "get_server", return_value=mock_server
        ), patch.object(manager, "_find_symbol_position", return_value=(0, 0)):
            result = await manager.rename_symbol("old", "new", "file.py")
            assert result["success"] is False
