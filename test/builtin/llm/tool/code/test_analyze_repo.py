import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.tool.code import analyze_repo
from zrb.context.any_context import AnyContext


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.mark.asyncio
async def test_analyze_repo_success(temp_dir):
    # Create dummy files
    os.makedirs(os.path.join(temp_dir, "src"))
    with open(os.path.join(temp_dir, "src", "main.py"), "w") as f:
        f.write("print('hello')")
    with open(os.path.join(temp_dir, "README.md"), "w") as f:
        f.write("# My Repo")

    ctx = MagicMock(spec=AnyContext)
    ctx.print = MagicMock()

    # Mock sub-agent creation
    mock_extract_agent_call_info = MagicMock()

    async def mock_extract_agent(*args, **kwargs):
        mock_extract_agent_call_info(*args, **kwargs)
        return "Extracted info"

    mock_summarize_agent_call_info = MagicMock()

    async def mock_summarize_agent(*args, **kwargs):
        mock_summarize_agent_call_info(*args, **kwargs)
        return "Summary"

    # We need to handle multiple calls to create_sub_agent_tool
    # First call is extraction, second is summarization (if needed)
    def side_effect_create_agent(*args, **kwargs):
        if kwargs.get("tool_name") == "extract":
            # Return a mock that acts as the agent function
            return mock_extract_agent
        return mock_summarize_agent

    with patch(
        "zrb.builtin.llm.tool.code.create_sub_agent_tool",
        side_effect=side_effect_create_agent,
    ):
        with patch("zrb.builtin.llm.tool.code.llm_rate_limitter") as mock_limiter:
            # Mock rate limiter to simulate token counts that trigger/don't trigger splitting
            mock_limiter.count_token.return_value = 10
            mock_limiter.clip_prompt.side_effect = lambda x, y: x

            # Test single pass (no summarization needed if one extraction result)
            # To force multiple extractions, we need rate limiter to report high usage or many files
            # Let's start with simple case: 1 extraction -> return result

            result = await analyze_repo(ctx, temp_dir, "Analyze this")
            assert result == "Extracted info"
            mock_extract_agent_call_info.assert_called()


@pytest.mark.asyncio
async def test_analyze_repo_with_summarization(temp_dir):
    # Create many files to force multiple extraction batches
    for i in range(5):
        with open(os.path.join(temp_dir, f"file{i}.py"), "w") as f:
            f.write(f"print({i})")

    ctx = MagicMock(spec=AnyContext)

    mock_extract_agent_call_info = MagicMock()

    async def mock_extract_agent(*args, **kwargs):
        mock_extract_agent_call_info(*args, **kwargs)
        return "Info part"

    mock_summarize_agent_call_info = MagicMock()

    async def mock_summarize_agent(*args, **kwargs):
        mock_summarize_agent_call_info(*args, **kwargs)
        return "Final Summary"

    with patch("zrb.builtin.llm.tool.code.create_sub_agent_tool") as mock_create:
        # Configure create to return extract agent then summarize agent?
        # Actually analyze_repo creates extract agent inside _extract_info and summarize in _summarize_info

        # We need _extract_info to return MULTIPLE items to trigger summarization loop
        # But _extract_info logic depends on token counting loop.

        # Easier path: mock _extract_info and _summarize_info directly?
        pass

    # Let's mock the internal helpers to test the loop logic in analyze_repo
    async def mock_extract(*args, **kwargs):
        return ["Part 1", "Part 2"]  # Force summarization

    async def mock_summarize(*args, **kwargs):
        return ["Final Summary"]  # Reduced to 1

    with patch(
        "zrb.builtin.llm.tool.code._extract_info", side_effect=mock_extract
    ) as mock_extract_patched:
        with patch(
            "zrb.builtin.llm.tool.code._summarize_info", side_effect=mock_summarize
        ) as mock_summarize_patched:
            with patch(
                "zrb.builtin.llm.tool.code._get_file_metadatas"
            ) as mock_get_meta:
                mock_get_meta.return_value = []

                result = await analyze_repo(ctx, temp_dir, "Query")

                assert result == "Final Summary"
                mock_extract_patched.assert_called_once()
                mock_summarize_patched.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_repo_no_files(temp_dir):
    ctx = MagicMock(spec=AnyContext)

    async def mock_extract(*args, **kwargs):
        return []  # No info

    with patch(
        "zrb.builtin.llm.tool.code._extract_info", side_effect=mock_extract
    ) as mock_extract_patched:
        with pytest.raises(RuntimeError, match="No info can be extracted"):
            await analyze_repo(ctx, temp_dir, "Query")
