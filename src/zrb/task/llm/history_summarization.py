from zrb.attr.type import IntAttr
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_int_attr


def get_history_summarization_token_threshold(
    ctx: AnyContext,
    history_summarization_token_threshold_attr: IntAttr | None,
    render_history_summarization_token_threshold: bool,
) -> int:
    """Gets the history summarization token threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            history_summarization_token_threshold_attr,
            llm_config.default_history_summarization_token_threshold,
            auto_render=render_history_summarization_token_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert history_summarization_token_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1
