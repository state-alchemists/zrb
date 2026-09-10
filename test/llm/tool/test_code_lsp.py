import json
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.config.limiter import llm_limiter
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


def _extractor_payloads(run_mock) -> list[dict]:
    """The per-file JSON payloads the extractor agent was sent.

    Reads them off the mocked `run_agent` boundary — the extraction batch is an
    implementation detail, but what reaches the model is observable behavior.
    """
    payloads = []
    for call in run_mock.await_args_list:
        message = json.loads(call.kwargs["message"])
        for entry in message.get("files", []):
            payloads.append(json.loads(entry))
    return payloads


@pytest.mark.asyncio
async def test_lsp_uses_symbols_and_diagnostics(temp_code_dir, lsp_env):
    # Symbols found + diagnostics with count>0 -> LSP context used (61-62, 279)
    lsp_env["sym"].return_value = {
        "found": True,
        "symbols": [{"name": "main", "kind": 12, "line": 1}],
    }
    lsp_env["diag"].return_value = {
        "found": True,
        "count": 2,
        "diagnostics": [
            {"severity": 1, "message": "err", "line": 3},
            {"severity": 2, "message": "warn", "line": 5},
        ],
    }
    res = await analyze_code(temp_code_dir, "query", use_lsp=True)
    assert "result" in res


@pytest.mark.asyncio
async def test_lsp_exclude_and_include_and_ext_skip(tmp_path, lsp_env):
    # Exercise 234 (ext skip), 239 (excluded), 243 (not included),
    # plus 40 + 284-291 (no LSP data -> read file) for the included file.
    d = tmp_path / "mix"
    d.mkdir()
    (d / "a.py").write_text("def a(): pass")  # included -> lsp -> None -> read
    (d / "b.py").write_text("def b(): pass")  # excluded (239)
    (d / "d.py").write_text("def d(): pass")  # not included (243)
    (d / "c.xyz").write_text("nope")  # ext skip (234)
    # sym/diag default to found=False -> get_lsp_context returns None (40)
    res = await analyze_code(
        str(d),
        "query",
        file_pattern="a.py",
        exclude_patterns=["b*"],
        use_lsp=True,
    )
    assert "result" in res


@pytest.mark.asyncio
async def test_lsp_no_data_read_error(tmp_path, lsp_env):
    # LSP returns None and the fallback read fails (292-293)
    d = tmp_path / "lsp_read_err"
    d.mkdir()
    (d / "main.py").write_text("def main(): pass")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("main.py"):
            raise OSError("boom")
        return real_open(path, *args, **kwargs)

    with patch("builtins.open", side_effect=fake_open):
        res = await analyze_code(str(d), "query", use_lsp=True)
    # Only file was unreadable -> nothing collected
    assert "No files found" in res


@pytest.mark.asyncio
async def test_lsp_non_supported_extension_read(tmp_path, lsp_env):
    # A known-but-non-LSP extension (.md) is read directly (253-254)
    d = tmp_path / "md_dir"
    d.mkdir()
    (d / "readme.md").write_text("# hello")
    res = await analyze_code(str(d), "query", use_lsp=True)
    assert "result" in res


@pytest.mark.asyncio
async def test_lsp_non_supported_extension_read_error(tmp_path, lsp_env):
    # Non-LSP file read raises -> skipped (256-257)
    d = tmp_path / "md_err"
    d.mkdir()
    (d / "readme.md").write_text("# hello")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("readme.md"):
            raise OSError("boom")
        return real_open(path, *args, **kwargs)

    with patch("builtins.open", side_effect=fake_open):
        res = await analyze_code(str(d), "query", use_lsp=True)
    assert "No files found" in res


@pytest.mark.asyncio
async def test_lsp_task_exception_fallback_read(tmp_path, lsp_env):
    # get_lsp_context raises -> gather returns Exception -> fallback read (267-274)
    d = tmp_path / "lsp_exc"
    d.mkdir()
    (d / "main.py").write_text("def main(): pass")
    with patch(
        "zrb.llm.tool.code.get_lsp_context",
        new_callable=AsyncMock,
        side_effect=RuntimeError("lsp down"),
    ):
        res = await analyze_code(str(d), "query", use_lsp=True)
    assert "result" in res


@pytest.mark.asyncio
async def test_lsp_task_exception_fallback_read_error(tmp_path, lsp_env):
    # get_lsp_context raises AND the fallback read fails (275-276)
    d = tmp_path / "lsp_exc_err"
    d.mkdir()
    (d / "main.py").write_text("def main(): pass")

    real_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("main.py"):
            raise OSError("boom")
        return real_open(path, *args, **kwargs)

    with (
        patch(
            "zrb.llm.tool.code.get_lsp_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("lsp down"),
        ),
        patch("builtins.open", side_effect=fake_open),
    ):
        res = await analyze_code(str(d), "query", use_lsp=True)
    assert "No files found" in res


@pytest.mark.asyncio
async def test_summarization_flushes_buffer(temp_code_dir):
    big = "info segment " * 40  # ~130 tokens, exceeds the low threshold
    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run,
        patch("zrb.llm.tool.code.extract_info", new_callable=AsyncMock) as extract,
        patch("zrb.llm.tool.code.CFG") as cfg,
    ):
        run.return_value = ("x", [])
        extract.return_value = [big, big]
        cfg.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = 100000
        cfg.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = 150
        res = await analyze_code(temp_code_dir, "query", use_lsp=False)
    # Two large infos force a buffer flush during summarization; converges to one.
    assert res == "x"


@pytest.mark.asyncio
async def test_oversized_file_is_truncated_before_reaching_the_model(tmp_path):
    """A file larger than the batch budget is truncated to fit, so it can never
    become a request the rate limiter refuses forever (the WebFetch livelock)."""
    d = tmp_path / "big_repo"
    d.mkdir()
    (d / "big.py").write_text("x" * 500_000)

    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run,
        patch("zrb.llm.tool.code.CFG") as cfg,
    ):
        run.return_value = ("info", [])
        cfg.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = 1000
        cfg.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = 100_000
        await analyze_code(str(d), "query", use_lsp=False)

    payloads = _extractor_payloads(run)
    assert payloads, "the extractor was never given the file"
    big = next(p for p in payloads if p["path"].endswith("big.py"))
    # Truncation happens inside the content field, not by cutting the serialized
    # string — the payload must always still parse as JSON (it did, above).
    assert big["content"].endswith("[TRUNCATED]")
    assert llm_limiter.count_tokens(json.dumps(big)) <= 1000


@pytest.mark.asyncio
async def test_fitting_files_are_tokenized_once_each(tmp_path):
    """Tokenizing is the expensive step; a file that fits is counted once.

    Regression: the fit check counted the payload and the caller counted the
    returned string again, doubling tokenizer work on every AnalyzeCode.
    """
    d = tmp_path / "small_repo"
    d.mkdir()
    for i in range(5):
        (d / f"f{i}.py").write_text("x")

    with (
        patch("zrb.llm.tool.code.run_agent", new_callable=AsyncMock) as run,
        patch("zrb.llm.tool.code.CFG") as cfg,
        patch.object(
            llm_limiter, "count_tokens", side_effect=llm_limiter.count_tokens
        ) as spy,
    ):
        run.return_value = ("info", [])
        cfg.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = 100_000
        cfg.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = 100_000
        await analyze_code(str(d), "query", use_lsp=False)

    # One count per file during extraction. Anything more means the payload is
    # being re-tokenized after the fit check.
    assert spy.call_count == 5, spy.call_count
