import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.file_analyze import analyze_file


@pytest.fixture
def temp_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("file content")
    return str(f)


@pytest.mark.asyncio
async def test_analyze_file_success(temp_file):
    # We must patch the source module because analyze_file does a local import
    with (
        patch("zrb.llm.agent.run_agent", new_callable=AsyncMock) as mock_run,
        patch("zrb.llm.agent.create_agent") as mock_create,
    ):

        mock_run.return_value = ("Analysis result", [])

        result = await analyze_file(temp_file, "What is this?")

        assert result == "Analysis result"
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_file_not_found():
    result = await analyze_file("/non/existent", "query")
    assert "Error: File not found" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
async def test_analyze_file_read_error(temp_file):
    with patch(
        "zrb.llm.tool.file_analyze.read_file",
        new=AsyncMock(return_value="Error: Permission denied"),
    ):
        result = await analyze_file(temp_file, "query")
        assert "Error: Permission denied" in result


@pytest.mark.asyncio
async def test_analyze_file_truncation(temp_file):
    # Create a "large" file content
    content = "line\n" * 100
    with open(temp_file, "w") as f:
        f.write(content)

    with (
        patch("zrb.llm.agent.run_agent", new_callable=AsyncMock) as mock_run,
        patch("zrb.llm.agent.create_agent") as mock_create,
        patch("zrb.llm.tool.file_analyze.CFG") as mock_cfg,
    ):

        mock_cfg.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD = 10
        mock_run.return_value = ("Truncated analysis", [])

        result = await analyze_file(temp_file, "query")

        assert result == "Truncated analysis"
        user_msg = mock_run.call_args[1]["message"]
        assert "TRUNCATED" in user_msg


@pytest.mark.asyncio
async def test_analyze_file_points_an_image_at_read(tmp_path):
    from PIL import Image

    image = tmp_path / "shot.png"
    Image.new("RGB", (4, 4), "red").save(image)

    result = await analyze_file(str(image), "What is this?")

    assert "[SYSTEM SUGGESTION]" in result
    assert "Read the image" in result


@pytest.mark.asyncio
async def test_analyze_file_refuses_an_image_a_text_only_model_gets_described(
    tmp_path, monkeypatch
):
    from PIL import Image

    from zrb.llm.agent_state import current_model

    async def describe(binary, multimodal_model):
        return "a red square"

    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setattr(
        "zrb.llm.agent.run.multimodal_describe.describe_binary_attachment", describe
    )
    image = tmp_path / "shot.png"
    Image.new("RGB", (4, 4), "red").save(image)
    token = current_model.set("openai:gpt-3.5-turbo")
    try:
        with patch("zrb.llm.agent.run_agent", new_callable=AsyncMock) as mock_run:
            result = await analyze_file(str(image), "What is this?")
    finally:
        current_model.reset(token)

    assert "Read the image" in result
    mock_run.assert_not_called()
