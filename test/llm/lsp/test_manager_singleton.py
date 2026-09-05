"""Tests for LSP manager functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.lsp.configs import LSPServerConfig, lsp_server_configs
from zrb.llm.lsp.manager import LSPManager, lsp_manager
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


class TestLspManagerSingleton:
    """Test singleton behavior."""

    def test_singleton_returns_same_instance(self):
        LSPManager.reset_singleton()
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

    def test_register_lsp_server_stores_config(self, manager):
        config = LSPServerConfig(
            name="test-lsp",
            command=["test-lsp"],
            language_ids=["test"],
            file_extensions=[".test"],
        )
        manager.register_lsp_server("test-lsp", config)
        from zrb.llm.lsp.configs import lsp_server_configs

        stored = lsp_server_configs.get("test-lsp")
        assert stored is not None
        assert stored.name == "test-lsp"
        assert stored.command == ["test-lsp"]

    def test_register_lsp_server_overrides_builtin(self, manager):
        override = LSPServerConfig(
            name="override-pyright",
            command=["override-pyright"],
            language_ids=["python"],
            file_extensions=[".py"],
        )
        manager.register_lsp_server("pyright", override)
        from zrb.llm.lsp.configs import lsp_server_configs

        stored = lsp_server_configs.get("pyright")
        assert stored is not None
        assert stored.name == "override-pyright"
        assert stored.command == ["override-pyright"]


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

    def test_detect_project_root_fallback(self, manager, tmp_path, monkeypatch):
        file_path = tmp_path / "standalone.py"
        file_path.write_text("print('hello')")
        # An ancestor of tmp_path may hold a real marker (e.g. a stray .git in
        # the system tmp dir), which would make the walk stop before the
        # fallback. Empty the marker list so the fallback is exercised hermetically.
        monkeypatch.setattr("zrb.llm.lsp.manager_lifecycle.PROJECT_MARKERS", [])
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
    async def test_shutdown_all_with_servers(self, manager):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_cfg,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
        ):
            mock_get_cfg.return_value = MagicMock(language_ids=["python"])
            await manager.get_server("test.py")

            await manager.shutdown_all()
            mock_server.stop.assert_called_once()

    async def _seed_server(self, manager, *, pid, returncode):
        """Register one running mock server via the public get_server path."""
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        mock_server.process = MagicMock(pid=pid, returncode=returncode)
        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_cfg,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
        ):
            mock_get_cfg.return_value = MagicMock(language_ids=["python"])
            await manager.get_server("test.py")
        return mock_server

    @pytest.mark.asyncio
    async def test_force_kill_all_empty_is_noop(self, manager):
        with patch("zrb.llm.lsp.manager_lifecycle.kill_pid") as mock_kill:
            manager.force_kill_all()
            mock_kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_kill_all_sigkills_running_server(self, manager):
        await self._seed_server(manager, pid=4321, returncode=None)
        with patch("zrb.llm.lsp.manager_lifecycle.kill_pid") as mock_kill:
            manager.force_kill_all()
            mock_kill.assert_called_once_with(4321, print_method=CFG.LOGGER.debug)
        # Servers are forgotten, so a second pass (e.g. atexit) does nothing.
        with patch("zrb.llm.lsp.manager_lifecycle.kill_pid") as mock_kill2:
            manager.force_kill_all()
            mock_kill2.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_kill_all_skips_already_exited_server(self, manager):
        await self._seed_server(manager, pid=4321, returncode=0)
        with patch("zrb.llm.lsp.manager_lifecycle.kill_pid") as mock_kill:
            manager.force_kill_all()
            mock_kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_kill_all_swallows_kill_errors(self, manager):
        await self._seed_server(manager, pid=99, returncode=None)
        with patch(
            "zrb.llm.lsp.manager_lifecycle.kill_pid",
            side_effect=ProcessLookupError,
        ):
            # Must not raise — it is an atexit handler.
            manager.force_kill_all()

    @pytest.mark.asyncio
    async def test_get_server_uses_cfg_preferred_servers(self, manager):
        """No explicit preference → CFG.LLM_LSP_PREFERRED_SERVERS is threaded in."""
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        mock_server.start.return_value = True
        CFG.LLM_LSP_PREFERRED_SERVERS = ["pyright", "pylsp"]
        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_cfg,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
        ):
            mock_get_cfg.return_value = MagicMock(language_ids=["python"])
            await manager.get_server("test.py")
            mock_get_cfg.assert_called_once_with("test.py", ["pyright", "pylsp"])

    @pytest.mark.asyncio
    async def test_get_server_explicit_preference_overrides_cfg(self, manager):
        """An explicit preferred_servers list wins over the CFG default."""
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        mock_server.start.return_value = True
        CFG.LLM_LSP_PREFERRED_SERVERS = ["pyright"]
        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_cfg,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
        ):
            mock_get_cfg.return_value = MagicMock(language_ids=["python"])
            await manager.get_server("test.py", preferred_servers=["gopls"])
            mock_get_cfg.assert_called_once_with("test.py", ["gopls"])

    @pytest.mark.asyncio
    async def test_get_server_lifecycle(self, manager, tmp_path):
        mock_server = AsyncMock(spec=LSPServer)
        mock_server.is_alive = True
        mock_server.start.return_value = True

        with (
            patch(
                "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file"
            ) as mock_get_cfg,
            patch(
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server,
            ),
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
                "zrb.llm.lsp.manager_lifecycle.LSPServer",
                return_value=mock_server2,
            ):
                server3 = await manager.get_server("test.py")
                assert server3 == mock_server2

    @pytest.mark.asyncio
    async def test_get_server_no_config(self, manager):
        with patch(
            "zrb.llm.lsp.manager_lifecycle.get_lsp_config_for_file",
            return_value=None,
        ):
            result = await manager.get_server("/path/to/file.unknown")
            assert result is None
