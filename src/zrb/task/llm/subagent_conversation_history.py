from zrb.context.any_context import AnyContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.typing import ListOfDict
from zrb.xcom.xcom import Xcom


def inject_subagent_conversation_history_into_ctx(
    ctx: AnyContext, conversation_history: ConversationHistory
):
    subagent_messages_xcom = _get_global_subagent_history_xcom(ctx)
    existing_subagent_history = subagent_messages_xcom.get({})
    subagent_messages_xcom.set(
        {**existing_subagent_history, **conversation_history.subagent_history}
    )


def extract_subagent_conversation_history_from_ctx(
    ctx: AnyContext,
) -> dict[str, ListOfDict]:
    subagent_messsages_xcom = _get_global_subagent_history_xcom(ctx)
    return subagent_messsages_xcom.get({})


def get_ctx_subagent_history(ctx: AnyContext, subagent_name: str) -> ListOfDict:
    subagent_history = extract_subagent_conversation_history_from_ctx(ctx)
    return subagent_history.get(subagent_name, [])


def set_ctx_subagent_history(ctx: AnyContext, subagent_name: str, messages: ListOfDict):
    subagent_history = extract_subagent_conversation_history_from_ctx(ctx)
    subagent_history[subagent_name] = messages
    subagent_messages_xcom = _get_global_subagent_history_xcom(ctx)
    subagent_messages_xcom.set(subagent_history)


def _get_global_subagent_history_xcom(ctx: AnyContext) -> Xcom:
    if "_global_subagents" not in ctx.xcom:
        ctx.xcom["_global_subagents"] = Xcom([{}])
    if not isinstance(ctx.xcom["_global_subagents"], Xcom):
        raise ValueError("ctx.xcom._global_subagents must be an Xcom")
    return ctx.xcom["_global_subagents"]
