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

        res = await analyze_code(temp_code_dir, "What does main() do?", use_lsp=False)

        assert "Analysis result" in res
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_analyze_code_with_lsp(temp_code_dir):
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch(
        "zrb.llm.tool.code.run_agent", new_callable=AsyncMock
    ) as mock_run, patch(
        "zrb.llm.lsp.manager.lsp_manager.list_available_servers",
        return_value={"python": "pylsp"},
    ), patch(
        "zrb.llm.lsp.manager.lsp_manager.get_document_symbols", new_callable=AsyncMock
    ) as mock_sym, patch(
        "zrb.llm.lsp.manager.lsp_manager.get_diagnostics", new_callable=AsyncMock
    ) as mock_diag, patch(
        "zrb.llm.lsp.manager.lsp_manager.shutdown_all", new_callable=AsyncMock
    ):

        mock_run.return_value = ("LSP Analysis result", [])
        mock_sym.return_value = {
            "found": True,
            "symbols": [{"name": "main", "kind": 12, "line": 1}],
        }
        mock_diag.return_value = {"found": True, "count": 0, "diagnostics": []}

        res = await analyze_code(temp_code_dir, "What symbols are there?", use_lsp=True)

        assert "LSP Analysis result" in res
        mock_run.assert_called()
        mock_sym.assert_called()


@pytest.mark.asyncio
async def test_analyze_code_multi_chunk(temp_code_dir):
    from unittest.mock import AsyncMock, patch

    # Force multi-chunk by mocking CFG in the module
    with patch(
        "zrb.llm.tool.code.run_agent", new_callable=AsyncMock
    ) as mock_run, patch("zrb.llm.tool.code.CFG") as mock_cfg:

        mock_cfg.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = 10
        mock_cfg.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = 1000
        mock_run.return_value = ("Chunk result", [])

        res = await analyze_code(temp_code_dir, "query", use_lsp=False)

        assert "Chunk result" in res
        # Should be called at least twice
        assert mock_run.call_count >= 2


@pytest.mark.asyncio
async def test_analyze_code_summarization_loop(temp_code_dir):
    from unittest.mock import AsyncMock, patch

    # Mock extract_info to return multiple results, forcing summarization
    with patch(
        "zrb.llm.tool.code._extract_info", new_callable=AsyncMock
    ) as mock_extract, patch(
        "zrb.llm.tool.code._run_repo_agent", new_callable=AsyncMock
    ) as mock_run_agent:

        mock_extract.return_value = ["info1", "info2"]
        mock_run_agent.side_effect = lambda agent, q, content, key, out: out.append(
            "summarized"
        )

        res = await analyze_code(temp_code_dir, "query", use_lsp=False)

        assert res == "summarized"
        mock_run_agent.assert_called()


@pytest.mark.asyncio
async def test_get_lsp_context_error(temp_code_dir):
    from unittest.mock import AsyncMock, patch

    from zrb.llm.tool.code import _get_lsp_context

    with patch(
        "zrb.llm.lsp.manager.lsp_manager.get_document_symbols",
        side_effect=Exception("LSP error"),
    ):
        res = await _get_lsp_context("main.py", temp_code_dir)
        assert res is None


@pytest.mark.asyncio
async def test_analyze_code_path_not_found():
    res = await analyze_code("/non/existent/path", "query")
    assert "Error" in res
    assert "not found" in res


def test_get_file_metadatas_patterns(temp_code_dir):
    from zrb.llm.tool.code import _get_file_metadatas

    # Test exclude pattern - use wildcard to match main.py
    metadatas = _get_file_metadatas(temp_code_dir, ["py"], None, ["main*"])
    assert len(metadatas) == 1
    assert metadatas[0]["path"] == "util.py"

    # Test include pattern
    metadatas = _get_file_metadatas(temp_code_dir, ["py"], ["main*"], [])
    assert len(metadatas) == 1
    assert metadatas[0]["path"] == "main.py"
