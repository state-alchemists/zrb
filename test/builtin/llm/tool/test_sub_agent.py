import json
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.context.any_context import AnyContext


@pytest.fixture
def mock_context():
    return MagicMock(spec=AnyContext)


@pytest.mark.asyncio
async def test_sub_agent_execution(mock_context):
    async def mock_run_agent_iteration(*args, **kwargs):
        mock_agent_run = MagicMock()
        mock_agent_run.result.output = "Agent Result"
        mock_agent_run.result.all_messages_json.return_value = "[]"
        return mock_agent_run
    
    with patch("zrb.builtin.llm.tool.sub_agent.get_model") as mock_get_model, patch(
        "zrb.builtin.llm.tool.sub_agent.get_model_settings"
    ) as mock_get_settings, patch(
        "zrb.builtin.llm.tool.sub_agent.get_system_and_user_prompt"
    ) as mock_get_prompts, patch(
        "zrb.builtin.llm.tool.sub_agent.create_agent_instance"
    ) as mock_create_agent, patch(
        "zrb.builtin.llm.tool.sub_agent.run_agent_iteration", side_effect=mock_run_agent_iteration
    ) as mock_run_iteration, patch(
        "zrb.builtin.llm.tool.sub_agent.get_ctx_subagent_history", return_value=[]
    ) as mock_get_hist, patch(
        "zrb.builtin.llm.tool.sub_agent.set_ctx_subagent_history"
    ) as mock_set_hist:

        mock_get_prompts.return_value = ("system prompt", "query")

        sub_agent_tool = create_sub_agent_tool("my_tool", "my description")

        result = await sub_agent_tool(mock_context, "do something")

        assert result == "Agent Result"
        mock_create_agent.assert_called_once()
        mock_run_iteration.assert_called_once()
        mock_set_hist.assert_called_once()


@pytest.mark.asyncio
async def test_sub_agent_no_result(mock_context):
    async def mock_run_agent_iteration(*args, **kwargs):
        return None
    
    with patch("zrb.builtin.llm.tool.sub_agent.get_model"), patch(
        "zrb.builtin.llm.tool.sub_agent.get_model_settings"
    ), patch(
        "zrb.builtin.llm.tool.sub_agent.get_system_and_user_prompt",
        return_value=("sys", "user"),
    ), patch(
        "zrb.builtin.llm.tool.sub_agent.create_agent_instance"
    ), patch(
        "zrb.builtin.llm.tool.sub_agent.run_agent_iteration", side_effect=mock_run_agent_iteration
    ) as mock_run_iteration, patch(
        "zrb.builtin.llm.tool.sub_agent.get_ctx_subagent_history", return_value=[]
    ):

        sub_agent_tool = create_sub_agent_tool("my_tool", "my description")

        with pytest.raises(ValueError, match="not returning any result"):
            await sub_agent_tool(mock_context, "do something")
