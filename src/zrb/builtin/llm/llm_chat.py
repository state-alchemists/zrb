import json
import os
from typing import Any

from zrb.builtin.group import llm_group
from zrb.builtin.llm.tool.api import get_current_location, get_current_weather
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.file import (
    apply_diff,
    list_files,
    read_from_file,
    search_files,
    write_to_file,
)
from zrb.builtin.llm.tool.web import (
    create_search_internet_tool,
    open_web_page,
    search_arxiv,
    search_wikipedia,
)
from zrb.config import (
    LLM_ALLOW_ACCESS_INTERNET,
    LLM_ALLOW_ACCESS_LOCAL_FILE,
    LLM_ALLOW_ACCESS_SHELL,
    LLM_HISTORY_DIR,
    SERP_API_KEY,
)
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.llm_task import LLMTask
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_pascal_case


class PreviousSessionInput(StrInput):

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(ctx)
        script = read_file(
            file_path=os.path.join(os.path.dirname(__file__), "previous-session.js"),
            replace_map={
                "CURRENT_INPUT_NAME": name,
                "CurrentPascalInputName": to_pascal_case(name),
            },
        )
        return "\n".join(
            [
                f'<input name="{name}" placeholder="{description}" value="{default}" />',
                f"<script>{script}</script>",
            ]
        )


def _read_chat_conversation(ctx: AnySharedContext) -> list[dict[str, Any]]:
    if ctx.input.start_new:
        return []
    previous_session_name = ctx.input.previous_session
    if previous_session_name == "" or previous_session_name is None:
        last_session_file_path = os.path.join(LLM_HISTORY_DIR, "last-session")
        if os.path.isfile(last_session_file_path):
            previous_session_name = read_file(last_session_file_path).strip()
    conversation_file_path = os.path.join(
        LLM_HISTORY_DIR, f"{previous_session_name}.json"
    )
    if not os.path.isfile(conversation_file_path):
        return []
    return json.loads(read_file(conversation_file_path))


def _write_chat_conversation(
    ctx: AnySharedContext, conversations: list[dict[str, Any]]
):
    os.makedirs(LLM_HISTORY_DIR, exist_ok=True)
    current_session_name = ctx.session.name
    conversation_file_path = os.path.join(
        LLM_HISTORY_DIR, f"{current_session_name}.json"
    )
    write_file(conversation_file_path, json.dumps(conversations, indent=2))
    last_session_file_path = os.path.join(LLM_HISTORY_DIR, "last-session")
    write_file(last_session_file_path, current_session_name)


llm_chat: LLMTask = llm_group.add_task(
    LLMTask(
        name="llm-chat",
        input=[
            StrInput(
                "model",
                description="LLM Model",
                prompt="LLM Model",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            StrInput(
                "base-url",
                description="LLM API Base URL",
                prompt="LLM API Base URL",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            StrInput(
                "api-key",
                description="LLM API Key",
                prompt="LLM API Key",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            TextInput(
                "system-prompt",
                description="System prompt",
                prompt="System prompt",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
            ),
            BoolInput(
                "start-new",
                description="Start new conversation (LLM will forget everything)",
                prompt="Start new conversation (LLM will forget everything)",
                default=False,
                allow_positional_parsing=False,
                always_prompt=False,
            ),
            TextInput("message", description="User message", prompt="Your message"),
            PreviousSessionInput(
                "previous-session",
                description="Previous conversation session",
                prompt="Previous conversation session (can be empty)",
                allow_positional_parsing=False,
                allow_empty=True,
                always_prompt=False,
            ),
        ],
        model=lambda ctx: None if ctx.input.model.strip() == "" else ctx.input.model,
        model_base_url=lambda ctx: (
            None if ctx.input.base_url.strip() == "" else ctx.input.base_url
        ),
        model_api_key=lambda ctx: (
            None if ctx.input.api_key.strip() == "" else ctx.input.api_key
        ),
        conversation_history_reader=_read_chat_conversation,
        conversation_history_writer=_write_chat_conversation,
        description="Chat with LLM",
        system_prompt=lambda ctx: (
            None if ctx.input.system_prompt.strip() == "" else ctx.input.system_prompt
        ),
        message="{ctx.input.message}",
        retries=0,
    ),
    alias="chat",
)


if LLM_ALLOW_ACCESS_LOCAL_FILE:
    llm_chat.add_tool(list_files)
    llm_chat.add_tool(read_from_file)
    llm_chat.add_tool(write_to_file)
    llm_chat.add_tool(search_files)
    llm_chat.add_tool(apply_diff)

if LLM_ALLOW_ACCESS_SHELL:
    llm_chat.add_tool(run_shell_command)

if LLM_ALLOW_ACCESS_INTERNET:
    llm_chat.add_tool(open_web_page)
    llm_chat.add_tool(search_wikipedia)
    llm_chat.add_tool(search_arxiv)
    if SERP_API_KEY != "":
        llm_chat.add_tool(create_search_internet_tool(SERP_API_KEY))
    llm_chat.add_tool(get_current_location)
    llm_chat.add_tool(get_current_weather)
