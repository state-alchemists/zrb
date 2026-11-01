"""The queue meets the run loop: a checkpoint hands the ready messages over.

`_build_event_stream_handler` registers the live run and, on a history that ends
in a `ModelRequest`, lets the UI deliver what the queue calls ready. What those
entries are is the queue's business (see `test_message_queue_delivery`); this
pins that the run loop asks, and asks at the right moment.
"""

from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse

from zrb.llm.agent.run.partial_run import PartialRunAccumulator
from zrb.llm.agent.run.runner import (
    _build_event_stream_handler,
    _deliver_queued_messages,
)
from zrb.llm.ui_fallback.std_ui import StdUI


def _handler(ui):
    return _build_event_stream_handler(
        effective_ui=ui,
        effective_event_handler=None,
        partial_run=PartialRunAccumulator(),
    )


async def _drive(handler, messages):
    ctx = MagicMock()
    ctx.messages = messages

    async def events():
        yield ModelResponse([])

    await handler(ctx, events())
    return ctx


def test_a_ui_that_cannot_deliver_is_skipped():
    """A UI with no queue moves nothing, and no UI at all is skipped: the run
    goes on."""
    _deliver_queued_messages(StdUI())
    _deliver_queued_messages(None)


def test_delivery_asks_the_ui_to_take_what_is_ready():
    ui = MagicMock()
    _deliver_queued_messages(ui)

    ui.deliver_queued_messages_early.assert_called_once_with()


@pytest.mark.asyncio
async def test_a_complete_history_lets_the_queue_join_the_turn():
    ui = MagicMock()
    handler = _handler(ui)

    await _drive(handler, [ModelRequest([]), ModelResponse([]), ModelRequest([])])

    ui.deliver_queued_messages_early.assert_called()


@pytest.mark.asyncio
async def test_a_half_built_step_is_not_a_delivery_point():
    """Only a history that ends in a request is complete enough to steer into;
    delivering mid-step would drop the message into a turn already under way."""
    ui = MagicMock()
    handler = _handler(ui)

    await _drive(handler, [ModelRequest([]), ModelResponse([])])

    ui.deliver_queued_messages_early.assert_not_called()


@pytest.mark.asyncio
async def test_each_boundary_delivers_at_most_once():
    """The handler runs per event; the checkpoint counter is what keeps one
    history length from being counted as a new boundary twice."""
    ui = MagicMock()
    handler = _handler(ui)
    ctx = MagicMock()
    ctx.messages = [ModelRequest([]), ModelResponse([]), ModelRequest([])]

    async def events():
        yield ModelResponse([])

    await handler(ctx, events())
    await handler(ctx, events())

    assert ui.deliver_queued_messages_early.call_count == 1
