from unittest.mock import AsyncMock, patch

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


@pytest.fixture
def lsp_env():
    """Patch LSP manager + run_agent so analyze_code takes the LSP code path.

    Tests configure the yielded mocks (symbols/diagnostics/servers/run) to steer
    which branch of `_get_file_metadatas_with_lsp` executes.
    """
    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.list_available_servers",
            return_value={"python": "pylsp"},
        ) as servers,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_document_symbols",
            new_callable=AsyncMock,
        ) as sym,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_diagnostics",
            new_callable=AsyncMock,
        ) as diag,
        patch("zrb.llm.lsp.manager.lsp_manager.shutdown_all", new_callable=AsyncMock),
    ):
        run.return_value = ("result", [])
        sym.return_value = {"found": False}
        diag.return_value = {"found": False}
        yield {"run": run, "servers": servers, "sym": sym, "diag": diag}


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
    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as mock_run,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.list_available_servers",
            return_value={"python": "pylsp"},
        ),
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_document_symbols",
            new_callable=AsyncMock,
        ) as mock_sym,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_diagnostics", new_callable=AsyncMock
        ) as mock_diag,
        patch("zrb.llm.lsp.manager.lsp_manager.shutdown_all", new_callable=AsyncMock),
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
async def test_analyze_code_does_not_shutdown_global_lsp_manager(temp_code_dir):
    """analyze_code must not tear down every LSP server process-wide —
    lsp_manager is a global singleton shared with post_write_check.py, and a
    global shutdown forced that unrelated caller to cold-start a server.
    """
    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as mock_run,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.list_available_servers",
            return_value={"python": "pylsp"},
        ),
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_document_symbols",
            new_callable=AsyncMock,
        ) as mock_sym,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.get_diagnostics", new_callable=AsyncMock
        ) as mock_diag,
        patch(
            "zrb.llm.lsp.manager.lsp_manager.shutdown_all", new_callable=AsyncMock
        ) as mock_shutdown_all,
    ):
        mock_run.return_value = ("LSP Analysis result", [])
        mock_sym.return_value = {"found": False}
        mock_diag.return_value = {"found": False}

        await analyze_code(temp_code_dir, "What symbols are there?", use_lsp=True)

        mock_shutdown_all.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_code_multi_chunk(temp_code_dir):
    from unittest.mock import AsyncMock, patch

    # Force multi-chunk by mocking CFG in the module
    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as mock_run,
        patch("zrb.llm.tool.code.CFG") as mock_cfg,
    ):

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
    with (
        patch("zrb.llm.tool.code.extract_info", new_callable=AsyncMock) as mock_extract,
        patch(
            "zrb.llm.tool.code.run_repo_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):

        mock_extract.return_value = ["info1", "info2"]
        mock_run_agent.side_effect = lambda agent, q, content, key, out: out.append(
            "summarized"
        )

        res = await analyze_code(temp_code_dir, "query", use_lsp=False)

        assert res == "summarized"
        mock_run_agent.assert_called()


@pytest.mark.asyncio
async def test_get_lsp_context_error(temp_code_dir):

    from zrb.llm.tool.code import get_lsp_context

    with patch(
        "zrb.llm.lsp.manager.lsp_manager.get_document_symbols",
        side_effect=Exception("LSP error"),
    ):
        res = await get_lsp_context("main.py", temp_code_dir)
        assert res is None


@pytest.mark.asyncio
async def test_analyze_code_path_not_found():
    res = await analyze_code("/non/existent/path", "query")
    assert "Error" in res
    assert "not found" in res
    assert "[SYSTEM SUGGESTION]" in res


def test_get_file_metadatas_patterns(temp_code_dir):
    from zrb.llm.tool.code import get_file_metadatas

    # Test exclude pattern - use wildcard to match main.py
    metadatas = get_file_metadatas(temp_code_dir, ["py"], None, ["main*"])
    assert len(metadatas) == 1
    assert metadatas[0]["path"] == "util.py"

    # Test include pattern
    metadatas = get_file_metadatas(temp_code_dir, ["py"], ["main*"], [])
    assert len(metadatas) == 1
    assert metadatas[0]["path"] == "main.py"


@pytest.mark.asyncio
async def test_file_pattern_known_extension(temp_code_dir):
    # "*.py" -> py is a known extension, extensions narrows to ["py"] (106-109)
    with patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run:
        run.return_value = ("ext result", [])
        res = await analyze_code(
            temp_code_dir, "query", file_pattern="*.py", use_lsp=False
        )
    assert "ext result" in res


@pytest.mark.asyncio
async def test_file_pattern_unknown_extension_uses_include(temp_code_dir):
    # "*.xyz" -> xyz not a known ext, becomes an include glob (110-111);
    # nothing matches -> "No files found" (142).
    with patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock):
        res = await analyze_code(
            temp_code_dir, "query", file_pattern="*.xyz", use_lsp=False
        )
    assert "No files found" in res


@pytest.mark.asyncio
async def test_file_pattern_literal_name(temp_code_dir):
    # "main.py" (no "*.") -> literal include pattern (112-113)
    with patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run:
        run.return_value = ("literal result", [])
        res = await analyze_code(
            temp_code_dir, "query", file_pattern="main.py", use_lsp=False
        )
    assert "literal result" in res


@pytest.mark.asyncio
async def test_lsp_requested_but_no_servers(temp_code_dir, lsp_env):
    # use_lsp=True but no servers -> falls back to plain file reading (128-129)
    lsp_env["servers"].return_value = {}
    res = await analyze_code(temp_code_dir, "query", use_lsp=True)
    assert "result" in res


@pytest.mark.asyncio
async def test_no_matching_files(tmp_path):
    # Directory with only a non-code file -> extension check skips it (192),
    # then "No files found" (142).
    d = tmp_path / "empty_code"
    d.mkdir()
    (d / "notes.xyz").write_text("not code")
    with patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock):
        res = await analyze_code(str(d), "query", use_lsp=False)
    assert "No files found" in res


@pytest.mark.asyncio
async def test_no_extracted_info(temp_code_dir):
    # extract_info yields nothing -> "No information could be extracted" (154)
    with patch("zrb.llm.tool.code.extract_info", new_callable=AsyncMock) as extract:
        extract.return_value = []
        res = await analyze_code(temp_code_dir, "query", use_lsp=False)
    assert "No information could be extracted" in res


@pytest.mark.asyncio
async def test_read_error_skips_file(tmp_path):
    d = tmp_path / "read_err"
    d.mkdir()
    (d / "main.py").write_text("def main(): pass")
    (d / "trap.py").write_text("def trap(): pass")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("trap.py"):
            raise OSError("boom")
        return real_open(path, *args, **kwargs)

    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run,
        patch("builtins.open", side_effect=fake_open),
    ):
        run.return_value = ("partial result", [])
        res = await analyze_code(str(d), "query", use_lsp=False)
    # main.py still analyzed; trap.py silently skipped (204-205)
    assert "partial result" in res
