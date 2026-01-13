import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.tool.file import analyze_file
from zrb.context.any_context import AnyContext


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.mark.asyncio
async def test_analyze_file_success(temp_dir):
    file_path = os.path.join(temp_dir, "test.py")
    with open(file_path, "w") as f:
        f.write("def foo():\n    pass")

    ctx = MagicMock(spec=AnyContext)

    # MagicMock the sub-agent creation and execution
    mock_agent_tool_call_info = MagicMock()

    async def mock_agent_tool(*args, **kwargs):
        mock_agent_tool_call_info(*args, **kwargs)
        return {"analysis": "good code"}

    with patch(
        "zrb.builtin.llm.tool.file.create_sub_agent_tool", return_value=mock_agent_tool
    ) as mock_create_agent:
        with patch("zrb.builtin.llm.tool.file.llm_rate_limitter") as mock_limitter:
            # MagicMock rate limiter behavior
            mock_limitter.clip_prompt.side_effect = lambda content, threshold: content

            result = await analyze_file(ctx, file_path, "Analyze this")

            assert result == {"analysis": "good code"}

            # Verify sub-agent was called with correct payload
            mock_agent_tool_call_info.assert_called_once()
            call_args = mock_agent_tool_call_info.call_args
            assert call_args[0][0] == ctx  # First arg is context
            payload = json.loads(call_args[0][1])
            assert payload["instruction"] == "Analyze this"
            assert payload["file_path"] == os.path.abspath(file_path)
            assert payload["file_content"] == "def foo():\n    pass"


@pytest.mark.asyncio
async def test_analyze_file_not_found():
    ctx = MagicMock(spec=AnyContext)
    with pytest.raises(FileNotFoundError):
        await analyze_file(ctx, "/non/existent/path/file.py", "Analyze")
