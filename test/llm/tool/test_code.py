import os

import pytest

from zrb.llm.tool.code import analyze_code


@pytest.fixture
def temp_code_dir(tmp_path):
    d = tmp_path / "test_code_tool"
    d.mkdir()
    # Create some dummy code files
    (d / "main.py").write_text("def main(): print('hello')")
    (d / "util.py").write_text("def helper(): return 42")
    return str(d)


@pytest.mark.asyncio
async def test_analyze_code_basic(temp_code_dir):
    from unittest.mock import AsyncMock, patch

    with patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = ("Analysis result", [])

        res = await analyze_code(temp_code_dir, "What does main() do?")

        assert "Analysis result" in res
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_analyze_code_path_not_found():
    res = await analyze_code("/non/existent/path", "query")
    assert "Error" in res
    assert "not found" in res
