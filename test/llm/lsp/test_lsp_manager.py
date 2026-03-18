"""Tests for LSP manager functionality."""
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from zrb.llm.lsp.manager import LSPManager, lsp_manager

@pytest.fixture
def manager():
    """Create a fresh LSPManager for each test by resetting the singleton."""
    # Resetting singleton is a common test pattern; we'll keep it for isolation
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

class TestLspPublicAPI:
    """Test high-level public API methods."""
    def test_list_servers_returns_dict(self, manager):
        result = manager.list_available_servers()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_document_symbols_formatting(self, manager, tmp_path):
        """Test document symbols through the public API (indirectly tests formatter)."""
        test_file = tmp_path / "test.py"
        test_file.touch()
        
        mock_server = MagicMock()
        mock_server.is_alive = True
        mock_server.start = AsyncMock(return_value=True)
        # Mock raw LSP response
        mock_server.document_symbols = AsyncMock(return_value=[
            {
                "name": "my_func",
                "kind": 12,
                "selectionRange": {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 11}},
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 5, "character": 0}}
            }
        ])

        with patch("zrb.llm.lsp.manager.get_lsp_config_for_file") as mock_get_config, \
             patch("zrb.llm.lsp.manager.LSPServer", return_value=mock_server):
            mock_get_config.return_value = MagicMock()
            
            result = await manager.get_document_symbols(str(test_file))
            assert result["found"] is True
            assert result["symbols"][0]["name"] == "my_func"
            assert result["symbols"][0]["line"] == 1

class TestShutdown:
    """Test lifecycle methods."""
    @pytest.mark.asyncio
    async def test_shutdown_all_empty(self, manager):
        await manager.shutdown_all()

    @pytest.mark.asyncio
    async def test_shutdown_idle(self, manager):
        await manager.shutdown_idle()

@pytest.mark.asyncio
async def test_get_server_no_config(manager):
    with patch("zrb.llm.lsp.manager.get_lsp_config_for_file", return_value=None):
        result = await manager.get_server("/path/to/file.unknown")
        assert result is None
