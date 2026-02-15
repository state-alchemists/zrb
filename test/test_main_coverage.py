import pytest
from unittest.mock import patch, MagicMock
from zrb.__main__ import serve_cli
from zrb.util.group import NodeNotFoundError

@patch("zrb.__main__.cli.run")
@patch("zrb.__main__.get_init_path_list")
@patch("zrb.__main__.load_file")
def test_serve_cli_success(mock_load_file, mock_get_init, mock_cli_run):
    mock_get_init.return_value = ["/path/to/init.py"]
    mock_cli_run.return_value = None
    
    with patch("sys.argv", ["zrb", "version"]):
        serve_cli()
    
    mock_cli_run.assert_called_with(["version"])
    mock_load_file.assert_called()

@patch("zrb.__main__.cli.run")
def test_serve_cli_node_not_found(mock_cli_run):
    mock_cli_run.side_effect = NodeNotFoundError("Node X not found")
    
    with patch("sys.argv", ["zrb", "X"]):
        with pytest.raises(SystemExit) as excinfo:
            serve_cli()
    assert excinfo.value.code == 1
