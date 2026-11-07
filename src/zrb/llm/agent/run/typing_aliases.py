"""Type aliases the run loop's modules share.

Every consumer imports these inside its own ``TYPE_CHECKING`` block and uses
them only in annotations, which are strings throughout the package (each module
has ``from __future__ import annotations``). So nothing here is imported at
runtime: no module gains a load-time pydantic-ai import by naming a type, and
the run loop keeps the lazy imports it is built around.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from pydantic_ai import AgentRunResultEvent, AgentStreamEvent
    from pydantic_ai.messages import ModelMessage, UserContent

    #: A conversation, in pydantic-ai's own message model.
    History: TypeAlias = list[ModelMessage]
    #: A prompt handed to `agent.run`: text, parts (text + attachments), or
    #: nothing, when the history alone carries the message.
    PromptMessage: TypeAlias = str | Sequence[UserContent] | None
    #: Progress output. The run never reads a print function's return value.
    PrintFn: TypeAlias = Callable[[str], object]
    #: Anything zrb's own event handler sees: a streamed event, or the trailing
    #: result event `agent.run()` returns rather than streaming.
    UIEvent: TypeAlias = AgentStreamEvent | AgentRunResultEvent[object]
    #: zrb's per-event handler. pydantic-ai's `EventStreamHandler` takes the run
    #: context as well; zrb's UIs key off the UI they already hold.
    StreamEventHandler: TypeAlias = Callable[[UIEvent], Awaitable[None]]
    #: Receives a history snapshot after every tool round trip.
    CheckpointFn: TypeAlias = Callable[[History], Awaitable[None]]
