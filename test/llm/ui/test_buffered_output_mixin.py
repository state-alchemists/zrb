import asyncio
from unittest.mock import AsyncMock

import pytest

from zrb.llm.ui.buffered_output_mixin import BufferedOutputMixin


class MockBufferedUI(BufferedOutputMixin):
    def __init__(self, flush_interval=0.1, max_buffer_size=10):
        super().__init__(flush_interval=flush_interval, max_buffer_size=max_buffer_size)
        self.sent = []
        self._send_mock = AsyncMock()

    async def _send_buffered(self, text: str):
        self.sent.append(text)
        await self._send_mock(text)


@pytest.mark.asyncio
async def test_buffer_output():
    ui = MockBufferedUI(max_buffer_size=100)

    ui.buffer_output("hello")
    assert ui.buffer == ["hello"]

    ui.buffer_output("\r⠇ ")
    assert ui.buffer == ["hello"]  # ignored

    ui.buffer_output("world \r")
    assert ui.buffer == ["hello", "world "]

    ui.buffer_output("spinner ⠇")
    assert ui.buffer == ["hello", "world ", "spinner"]

    ui.buffer_output("\r🔄 Prepare tool parameters ⠇")
    assert "Prepare tool parameters" not in ui.buffer[-1]


@pytest.mark.asyncio
async def test_auto_flush_on_max_size():
    ui = MockBufferedUI(max_buffer_size=5)

    ui.buffer_output("123")
    assert ui.buffer == ["123"]
    assert len(ui.sent) == 0

    ui.buffer_output("456")
    # Buffer is now 6 bytes > max_buffer_size=5, creates a task to flush

    # Wait for the background task to flush
    await asyncio.sleep(0.01)

    assert ui.buffer == []
    assert len(ui.sent) == 1
    assert ui.sent[0] == "123456"


@pytest.mark.asyncio
async def test_flush_loop_and_stop():
    ui = MockBufferedUI(flush_interval=0.01)

    assert not ui.has_flush_task
    assert ui.flush_interval == 0.01

    await ui.start_flush_loop()
    assert ui.has_flush_task

    ui.buffer_output("hello")

    # Wait for loop to flush
    await asyncio.sleep(0.02)
    assert ui.buffer == []
    assert ui.sent == ["hello"]

    ui.buffer_output("world")
    await ui.stop_flush_loop()

    # Stopping should do a final flush
    assert ui.buffer == []
    assert len(ui.sent) == 2
    assert ui.sent[1] == "world"


@pytest.mark.asyncio
async def test_send_buffered_not_implemented():
    class IncompleteUI(BufferedOutputMixin):
        pass

    ui = IncompleteUI(max_buffer_size=1)
    ui.buffer_output("test")
    # Buffer output should have created an auto-flush task
    # We can await stop_flush_loop which awaits the final flush task
    with pytest.raises(NotImplementedError):
        await ui.stop_flush_loop()
