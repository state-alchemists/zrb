import os
from unittest import mock

import pytest

from zrb import __main__


@pytest.fixture
def mock_os_path(tmp_path):
    """Fixture to mock os.path functions within a temporary directory."""
    original_abspath = os.path.abspath
    original_dirname = os.path.dirname

    # Create a nested structure
    nested_dir = tmp_path / "level1" / "level2"
    nested_dir.mkdir(parents=True)
    (tmp_path / "zrb_init.py").touch()
    (nested_dir / "zrb_init.py").touch()

    # Mock functions
    def mock_getcwd():
        return str(nested_dir)

    def mock_abspath(path):
        if path == ".":
            return str(nested_dir)
        return original_abspath(path)  # Keep original for other uses if needed

    def mock_dirname(path):
        # Simulate walking up the directory tree relative to the mock structure
        if path == str(nested_dir):
            return str(nested_dir.parent)
        if path == str(nested_dir.parent):
            return str(tmp_path)
        if path == str(tmp_path):
            return str(tmp_path.parent)  # Go one level above tmp_path for root check
        return original_dirname(path)

    def mock_isfile(path):
        # Check against the created files
        if path == str(tmp_path / "zrb_init.py"):
            return True
        if path == str(nested_dir / "zrb_init.py"):
            return True
        return False  # Default to false for other paths

    def mock_expanduser(path):
        # Simple mock, assuming no ~ usage in tests or handle specific cases
        return path

    with mock.patch("os.getcwd", mock_getcwd), mock.patch(
        "os.path.abspath", mock_abspath
    ), mock.patch("os.path.dirname", mock_dirname), mock.patch(
        "os.path.isfile", mock_isfile
    ), mock.patch(
        "os.path.expanduser", mock_expanduser
    ):
        yield tmp_path, nested_dir


def test_get_init_path_list_finds_files(mock_os_path):
    """Test that get_init_path_list finds zrb_init.py files correctly."""
    tmp_path, nested_dir = mock_os_path
    expected_paths = [
        str(tmp_path / "zrb_init.py"),
        str(nested_dir / "zrb_init.py"),
    ]
    # Mock logger to avoid side effects during test
    with mock.patch(
        "zrb.config.Config.LOGGER", new_callable=mock.MagicMock
    ) as mock_logger:
        found_paths = __main__.get_init_path_list()
        assert found_paths == expected_paths
        # Check if logger was called for finding attempts
        assert mock_logger.info.call_count > 0


def test_get_init_path_list_no_files(tmp_path):
    """Test that get_init_path_list returns empty list when no files exist."""
    original_abspath = os.path.abspath
    original_dirname = os.path.dirname

    nested_dir = tmp_path / "level1" / "level2"
    nested_dir.mkdir(parents=True)

    def mock_getcwd():
        return str(nested_dir)

    def mock_abspath(path):
        if path == ".":
            return str(nested_dir)
        return original_abspath(path)

    def mock_dirname(path):
        if path == str(nested_dir):
            return str(nested_dir.parent)
        if path == str(nested_dir.parent):
            return str(tmp_path)
        if path == str(tmp_path):
            return str(tmp_path.parent)
        return original_dirname(path)

    def mock_isfile(path):
        return False  # No files exist

    with mock.patch("os.getcwd", mock_getcwd), mock.patch(
        "os.path.abspath", mock_abspath
    ), mock.patch("os.path.dirname", mock_dirname), mock.patch(
        "os.path.isfile", mock_isfile
    ):
        # Mock logger to avoid side effects during test
        patch_target_logger = "zrb.config.Config.LOGGER"
        with mock.patch(
            patch_target_logger, new_callable=mock.MagicMock
        ) as mock_logger:
            found_paths = __main__.get_init_path_list()
            assert found_paths == []
            # Check if logger was called for finding attempts
            assert mock_logger.info.call_count > 0


@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
@mock.patch("zrb.__main__.FaintFormatter")
@mock.patch("zrb.__main__.load_module")
@mock.patch("zrb.__main__.load_file")
@mock.patch("zrb.__main__.get_init_path_list")
@mock.patch("zrb.__main__.cli.run")
@mock.patch("sys.argv", ["zrb", "test-task"])
@mock.patch(
    "zrb.config.Config.INIT_MODULES",
    new_callable=mock.PropertyMock,
    return_value=["init.module1"],
)
@mock.patch(
    "zrb.config.Config.INIT_SCRIPTS",
    new_callable=mock.PropertyMock,
    return_value=["init.script1"],
)
def test_serve_cli_normal_execution(
    mock_init_scripts_prop,
    mock_init_modules_prop,
    mock_cli_run,
    mock_get_zrb_init,
    mock_load_file,
    mock_load_module,
    mock_formatter,
    mock_handler,
    mock_logger,
):
    """Test the normal execution flow of serve_cli."""
    mock_get_zrb_init.return_value = ["/path/to/zrb_init.py"]
    __main__.serve_cli()

    mock_logger.setLevel.assert_called_once()
    mock_handler.assert_called_once()
    mock_formatter.assert_called_once()
    mock_logger.addHandler.assert_called_once_with(mock_handler.return_value)
    mock_load_module.assert_called_once_with("init.module1")
    # Check load_file calls for init script and zrb_init
    assert mock_load_file.call_count == 2
    mock_load_file.assert_any_call(
        os.path.abspath(os.path.expanduser("init.script1")), -1
    )
    mock_load_file.assert_any_call("/path/to/zrb_init.py")
    mock_cli_run.assert_called_once_with(["test-task"])


@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
@mock.patch("zrb.__main__.FaintFormatter")
@mock.patch("zrb.__main__.load_module")
@mock.patch("zrb.__main__.load_file")
@mock.patch("zrb.__main__.get_init_path_list")
@mock.patch("zrb.__main__.cli.run", side_effect=KeyboardInterrupt)
@mock.patch("sys.argv", ["zrb", "test-task"])
@mock.patch("sys.exit")
@mock.patch("builtins.print")
def test_serve_cli_keyboard_interrupt(
    mock_print,
    mock_exit,
    mock_cli_run,
    mock_get_zrb_init,
    mock_load_file,
    mock_load_module,
    mock_formatter,
    mock_handler,
    mock_logger,
):
    """Test serve_cli handling KeyboardInterrupt."""
    __main__.serve_cli()
    mock_print.assert_called_once()  # Check if warning message is printed
    mock_exit.assert_called_once_with(1)


@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
@mock.patch("zrb.__main__.FaintFormatter")
@mock.patch("zrb.__main__.load_module")
@mock.patch("zrb.__main__.load_file")
@mock.patch("zrb.__main__.get_init_path_list")
@mock.patch("zrb.__main__.cli.run", side_effect=RuntimeError("event loop is closed"))
@mock.patch("sys.argv", ["zrb", "test-task"])
@mock.patch("sys.exit")
def test_serve_cli_runtime_error_event_loop_closed(
    mock_exit,
    mock_cli_run,
    mock_get_zrb_init,
    mock_load_file,
    mock_load_module,
    mock_formatter,
    mock_handler,
    mock_logger,
):
    """Test serve_cli handling specific RuntimeError 'event loop is closed'."""
    __main__.serve_cli()
    mock_exit.assert_called_once_with(1)


@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
@mock.patch("zrb.__main__.FaintFormatter")
@mock.patch("zrb.__main__.load_module")
@mock.patch("zrb.__main__.load_file")
@mock.patch("zrb.__main__.get_init_path_list")
@mock.patch("zrb.__main__.cli.run", side_effect=RuntimeError("Some other error"))
@mock.patch("sys.argv", ["zrb", "test-task"])
@mock.patch("sys.exit")
def test_serve_cli_runtime_error_other(
    mock_exit,
    mock_cli_run,
    mock_get_zrb_init,
    mock_load_file,
    mock_load_module,
    mock_formatter,
    mock_handler,
    mock_logger,
):
    """Test serve_cli handling other RuntimeErrors."""
    with pytest.raises(RuntimeError, match="Some other error"):
        __main__.serve_cli()
    mock_exit.assert_not_called()


@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
@mock.patch("zrb.__main__.FaintFormatter")
@mock.patch("zrb.__main__.load_module")
@mock.patch("zrb.__main__.load_file")
@mock.patch("zrb.__main__.get_init_path_list")
@mock.patch(
    "zrb.__main__.cli.run", side_effect=__main__.NodeNotFoundError("Node not found")
)
@mock.patch("sys.argv", ["zrb", "test-task"])
@mock.patch("sys.exit")
@mock.patch("builtins.print")
def test_serve_cli_node_not_found_error(
    mock_print,
    mock_exit,
    mock_cli_run,
    mock_get_zrb_init,
    mock_load_file,
    mock_load_module,
    mock_formatter,
    mock_handler,
    mock_logger,
):
    """Test serve_cli handling NodeNotFoundError."""
    __main__.serve_cli()
    mock_print.assert_called_once()  # Check if error message is printed
    mock_exit.assert_called_once_with(1)
