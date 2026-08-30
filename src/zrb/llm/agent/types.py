"""Re-exported pydantic-ai types for use elsewhere in zrb.

`create_agent()` (`agent/common.py`) is the one place that constructs a real
`pydantic_ai.Agent` (ADR-0036). This module is its companion for the far more
common case: a file that only needs a pydantic-ai *type* — for an annotation,
an `isinstance` check, or building a message part — with no `Agent`
construction or run-loop logic of its own. Importing from here instead of
`pydantic_ai` directly collapses those call sites onto one import path.

Deliberately excluded: concrete model/provider classes and the `Agent` class
itself (`OpenAIChatModel`, `Provider`, `known_model_names`, `Agent`, ...).
Re-exporting the former would start to look like the "bespoke provider
abstraction" ADR-0037 rejects; `Agent` construction stays exclusively at
`create_agent()` so there is one place, not two, that builds a real agent.
`Model` itself is re-exported below because it's used purely as an
annotation everywhere it appears in zrb — actual provider/model
*resolution* stays exactly where ADR-0037 leaves it, in
`llm/config/config.py`, importing `pydantic_ai` directly.

Every name here is a plain re-export — zero logic, zero behavior change.
These are real (not `TYPE_CHECKING`-guarded) imports: this module pays
pydantic-ai's import cost when *it* is first imported, same as the direct
`pydantic_ai` imports it replaces — nothing in zrb imports this module
eagerly at start-up, so callers must still guard their own import of it the
same way they guarded the `pydantic_ai` import it replaces: inside
`if TYPE_CHECKING:` for annotation-only use, or behind a justified
in-function import for runtime use (ADR-0033's lazy-import categories).
"""

from __future__ import annotations

from pydantic_ai import (
    AgentRunResultEvent,
    AgentStreamEvent,
    BinaryContent,
    DeferredToolRequests,
    DeferredToolResults,
    FinalResultEvent,
    ModelRetry,
    PartDeltaEvent,
    PartStartEvent,
    Tool,
    ToolApproved,
    ToolCallEvent,
    ToolCallPart,
    ToolDenied,
    ToolResultEvent,
    ToolReturn,
    UsageLimits,
    UserContent,
)
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.exceptions import UserError as PydanticUserError
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    AudioUrl,
    BaseToolReturnPart,
    DocumentUrl,
    FilePart,
    ImageUrl,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPartDelta,
    ToolReturnPart,
    UserPromptPart,
    VideoUrl,
    is_multi_modal_content,
)
from pydantic_ai.models import Model
from pydantic_ai.output import OutputDataT, OutputSpec
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolFuncEither
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RequestUsage, RunUsage

__all__ = [
    "AbstractCapability",
    "AbstractToolset",
    "AgentRunResultEvent",
    "AgentStreamEvent",
    "AudioUrl",
    "BaseToolReturnPart",
    "BinaryContent",
    "DeferredToolRequests",
    "DeferredToolResults",
    "DocumentUrl",
    "FilePart",
    "FinalResultEvent",
    "ImageUrl",
    "MCPToolset",
    "Model",
    "ModelMessage",
    "ModelMessagesTypeAdapter",
    "ModelRequest",
    "ModelResponse",
    "ModelRetry",
    "ModelSettings",
    "OutputDataT",
    "OutputSpec",
    "PartDeltaEvent",
    "PartStartEvent",
    "PydanticUserError",
    "RequestUsage",
    "RetryPromptPart",
    "RunUsage",
    "SystemPromptPart",
    "TextPart",
    "TextPartDelta",
    "ThinkingPart",
    "ThinkingPartDelta",
    "Tool",
    "ToolApproved",
    "ToolCallEvent",
    "ToolCallPart",
    "ToolCallPartDelta",
    "ToolDenied",
    "ToolFuncEither",
    "ToolResultEvent",
    "ToolReturn",
    "ToolReturnPart",
    "UsageLimitExceeded",
    "UsageLimits",
    "UserContent",
    "UserPromptPart",
    "VideoUrl",
    "is_multi_modal_content",
]
