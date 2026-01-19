import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.mcp import MCPServerStdio, MCPServerSSE
from zrb.llm.tool.mcp import load_mcp_config

@pytest.fixture
def mock_fs():
    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.path.join(temp_dir, "home")
        project_dir = os.path.join(home_dir, "project")
        sub_dir = os.path.join(project_dir, "subdir")
        
        os.makedirs(home_dir)
        os.makedirs(project_dir)
        os.makedirs(sub_dir)
        
        yield home_dir, project_dir, sub_dir

def test_mcp_toolset_factory_instantiation(mock_fs):
    home_dir, project_dir, sub_dir = mock_fs
    
    # Create mcp.json in home with Stdio server
    with open(os.path.join(home_dir, "mcp.json"), "w") as f:
        json.dump({
            "mcpServers": {
                "stdio_server": {
                    "command": "echo",
                    "args": ["${MY_VAR:-hello}"],
                    "env": {"TEST_ENV": "value"}
                }
            }
        }, f)
        
    # Create mcp.json in project with SSE server
    with open(os.path.join(project_dir, "mcp.json"), "w") as f:
        json.dump({
            "mcpServers": {
                "sse_server": {
                    "url": "http://localhost:8080/sse"
                }
            }
        }, f)
        
    # Mock os.path.expanduser and os.getcwd
    with patch("os.path.expanduser", return_value=home_dir), \
         patch("os.getcwd", return_value=sub_dir):
        
        servers = load_mcp_config()
        
        assert len(servers) == 2
        
        # Identify servers
        stdio = next((s for s in servers if isinstance(s, MCPServerStdio)), None)
        sse = next((s for s in servers if isinstance(s, MCPServerSSE)), None)
        
        assert stdio is not None
        assert sse is not None
        
        # Check Stdio config
        assert stdio.command == "echo"
        # Since we didn't set MY_VAR, it should be "hello"
        assert stdio.args == ["hello"]
        assert stdio.env == {"TEST_ENV": "value"}
        
        # Check SSE config
        assert sse.url == "http://localhost:8080/sse"

def test_mcp_toolset_factory_overrides(mock_fs):
    home_dir, project_dir, sub_dir = mock_fs
    
    with open(os.path.join(home_dir, "mcp.json"), "w") as f:
        json.dump({
            "mcpServers": {
                "server1": {"command": "cmd1"}
            }
        }, f)
        
    with open(os.path.join(project_dir, "mcp.json"), "w") as f:
        json.dump({
            "mcpServers": {
                "server1": {"command": "cmd2"}
            }
        }, f)
        
    with patch("os.path.expanduser", return_value=home_dir), \
         patch("os.getcwd", return_value=sub_dir):
         
        servers = load_mcp_config()
        
        assert len(servers) == 1
        assert isinstance(servers[0], MCPServerStdio)
        assert servers[0].command == "cmd2"
