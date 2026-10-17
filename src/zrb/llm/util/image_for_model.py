"""An image a tool captured (a camera photo, a screenshot), fitted to the
model that is running, by the rule a prompt attachment follows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.agent_state import get_current_model

if TYPE_CHECKING:
    from zrb.llm.agent.types import BinaryContent


async def get_image_for_current_model(
    image: "BinaryContent",
) -> "str | list[BinaryContent]":
    """*image* as the running model can take it: kept for a model that reads
    images, else described by `LLM_MULTIMODAL_MODEL`, else dropped (an empty
    string)."""
    # lazy: transitively heavy — multimodal_describe loads pydantic_ai
    from zrb.llm.agent.run.multimodal_describe import replace_unsupported_attachments
    from zrb.llm.config.model_resolver import resolve_configured_multimodal_model

    fitted = await replace_unsupported_attachments(
        [image],
        main_model=get_current_model(),
        multimodal_model=resolve_configured_multimodal_model(),
    )
    return fitted or ""
