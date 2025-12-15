import json
import os
from collections.abc import Callable
from typing import Any

from zrb.attr.type import StrAttr
from zrb.config.llm_context.config import llm_context_config
from zrb.context.any_context import AnyContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_str_attr
from zrb.util.file import read_file, write_file
from zrb.util.markdown import make_markdown_section
from zrb.util.run import run_async
from zrb.xcom.xcom import Xcom


def _get_global_subagent_messages_xcom(ctx: AnyContext) -> Xcom:
    if "_global_subagents" not in ctx.xcom:
        ctx.xcom["_global_subagents"] = Xcom([{}])
    if not isinstance(ctx.xcom["_global_subagents"], Xcom):
        raise ValueError("ctx.xcom._global_subagents must be an Xcom")
    return ctx.xcom["_global_subagents"]


def inject_subagent_history_into_ctx(
    ctx: AnyContext, conversation_history: ConversationHistory
):
    subagent_messages_xcom = _get_global_subagent_messages_xcom(ctx)
    existing_subagent_history = subagent_messages_xcom.get({})
    subagent_messages_xcom.set(
        {**existing_subagent_history, **conversation_history.subagent_history}
    )


def set_ctx_subagent_history(ctx: AnyContext, subagent_name: str, messages: ListOfDict):
    subagent_messages_xcom = _get_global_subagent_messages_xcom(ctx)
    subagent_history = subagent_messages_xcom.get({})
    subagent_history[subagent_name] = messages
    subagent_messages_xcom.set(subagent_history)


def get_subagent_histories_from_ctx(ctx: AnyContext) -> dict[str, ListOfDict]:
    subagent_messsages_xcom = _get_global_subagent_messages_xcom(ctx)
    return subagent_messsages_xcom.get({})


def inject_conversation_history_notes(conversation_history: ConversationHistory):
    conversation_history.long_term_note = _fetch_long_term_note(
        conversation_history.project_path
    )
    conversation_history.contextual_note = _fetch_contextual_note(
        conversation_history.project_path
    )


def _fetch_long_term_note(project_path: str) -> str:
    contexts = llm_context_config.get_notes(cwd=project_path)
    return contexts.get("/", "")


def _fetch_contextual_note(project_path: str) -> str:
    contexts = llm_context_config.get_notes(cwd=project_path)
    return "\n".join(
        [
            make_markdown_section(header, content)
            for header, content in contexts.items()
            if header != "/"
        ]
    )


def get_history_file(
    ctx: AnyContext,
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
) -> str:
    """Gets the path to the conversation history file, rendering if configured."""
    return get_str_attr(
        ctx,
        conversation_history_file_attr,
        "",
        auto_render=render_history_file,
    )


async def _read_from_source(
    ctx: AnyContext,
    reader: (
        Callable[[AnyContext], ConversationHistory | dict[str, Any] | list | None]
        | None
    ),
    file_path: str | None,
) -> "ConversationHistory | None":
    # Priority 1: Reader function
    if reader:
        try:
            raw_data = await run_async(reader(ctx))
            if raw_data:
                instance = ConversationHistory.parse_and_validate(
                    ctx, raw_data, "reader"
                )
                if instance:
                    return instance
        except Exception as e:
            ctx.log_warning(
                f"Error executing conversation history reader: {e}. Ignoring."
            )
    # Priority 2: History file
    if file_path and os.path.isfile(file_path):
        try:
            content = read_file(file_path)
            raw_data = json.loads(content)
            instance = ConversationHistory.parse_and_validate(
                ctx, raw_data, f"file '{file_path}'"
            )
            if instance:
                return instance
        except json.JSONDecodeError:
            ctx.log_warning(
                f"Could not decode JSON from history file '{file_path}'. "
                "Ignoring file content."
            )
        except Exception as e:
            ctx.log_warning(
                f"Error reading history file '{file_path}': {e}. "
                "Ignoring file content."
            )
    # Fallback: Return default value
    return None


async def read_conversation_history(
    ctx: AnyContext,
    conversation_history_reader: (
        Callable[[AnyContext], ConversationHistory | dict | list | None] | None
    ),
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
    conversation_history_attr: (
        ConversationHistory
        | Callable[[AnyContext], ConversationHistory | dict | list]
        | dict
        | list
    ),
) -> ConversationHistory:
    """Reads conversation history from reader, file, or attribute, with validation."""
    history_file = get_history_file(
        ctx, conversation_history_file_attr, render_history_file
    )
    # Use the class method defined above
    history_data = await _read_from_source(
        ctx=ctx,
        reader=conversation_history_reader,
        file_path=history_file,
    )
    if history_data:
        return history_data
    # Priority 3: Callable or direct conversation_history attribute
    raw_data_attr: Any = None
    if callable(conversation_history_attr):
        try:
            raw_data_attr = await run_async(conversation_history_attr(ctx))
        except Exception as e:
            ctx.log_warning(
                f"Error executing callable conversation_history attribute: {e}. "
                "Ignoring."
            )
    if raw_data_attr is None:
        raw_data_attr = conversation_history_attr
    if raw_data_attr:
        # Use the class method defined above
        history_data = ConversationHistory.parse_and_validate(
            ctx, raw_data_attr, "attribute"
        )
        if history_data:
            return history_data
    # Fallback: Return default value
    return ConversationHistory()


async def write_conversation_history(
    ctx: AnyContext,
    history_data: ConversationHistory,
    conversation_history_writer: (
        Callable[[AnyContext, ConversationHistory], None] | None
    ),
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
):
    """Writes conversation history using the writer or to a file."""
    if conversation_history_writer is not None:
        await run_async(conversation_history_writer(ctx, history_data))
    history_file = get_history_file(
        ctx, conversation_history_file_attr, render_history_file
    )
    if history_file != "":
        write_file(history_file, json.dumps(history_data.to_dict(), indent=2))


def count_part_in_history_list(history_list: ListOfDict) -> int:
    """Calculates the total number of 'parts' in a history list."""
    history_part_len = 0
    for history in history_list:
        if "parts" in history:
            history_part_len += len(history["parts"])
        else:
            history_part_len += 1
    return history_part_len
