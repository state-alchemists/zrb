"""Runtime pydantic-ai type re-exports.

Agent construction remains in ``agent/common.py``; model/provider resolution
remains in ``llm/config/model_resolver.py``. Imports are intentionally eager
when this module is imported, so callers retain their existing lazy-import
or ``TYPE_CHECKING`` guards.
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
