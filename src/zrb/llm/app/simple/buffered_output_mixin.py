import asyncio


class BufferedOutputMixin:
    def __init__(self, flush_interval: float = 0.5, max_buffer_size: int = 2000):
        self._buffer: list[str] = []
        self._flush_interval = flush_interval
        self._max_buffer_size = max_buffer_size
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()

    async def start_flush_loop(self):
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop_flush_loop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()

    def buffer_output(self, text: str):
        self._buffer.append(text)
        total_size = sum(len(s) for s in self._buffer)
        if total_size > self._max_buffer_size:
            asyncio.create_task(self._flush_buffer())

    async def _flush_buffer(self):
        if not self._buffer:
            return
        async with self._flush_lock:
            content = "".join(self._buffer).strip()
            self._buffer = []
            if content:
                await self._send_buffered(content)

    async def _send_buffered(self, text: str):
        raise NotImplementedError

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()
