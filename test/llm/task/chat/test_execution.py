from unittest.mock import MagicMock

from zrb.llm.task.chat.execution import ChatExecution


class MockLLMChatTask:
    """Stand-in for `LLMChatTask`, exposing only the public surface
    `ChatExecution.get_system_prompt` reads."""

    def __init__(self, prompt_manager=None):
        self.prompt_manager = prompt_manager
        self.name = "test-task"


def test_get_system_prompt_without_prompt_manager_returns_empty_string():
    llm_chat_task = MockLLMChatTask(prompt_manager=None)
    execution = ChatExecution(llm_chat_task)

    assert execution.get_system_prompt(MagicMock()) == ""


def test_get_system_prompt_with_prompt_manager_composes_prompt():
    prompt_manager = MagicMock()
    prompt_manager.compose_prompt.return_value = lambda ctx: "composed prompt"
    llm_chat_task = MockLLMChatTask(prompt_manager=prompt_manager)
    execution = ChatExecution(llm_chat_task)

    assert execution.get_system_prompt(MagicMock()) == "composed prompt"
