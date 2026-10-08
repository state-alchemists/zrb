import asyncio
import re

from zrb.config.config import CFG


class BufferedOutputMixin:
    """Mixin for UIs that need to batch output.

    Use this when:
    - Your backend has rate limits (Telegram: ~30 messages/sec)
    - Streaming tokens would create too many API calls
    - You want cleaner message bundling

    Usage:
        class TelegramUI(EventDrivenUI, BufferedOutputMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                BufferedOutputMixin.__init__(self)

            async def send_buffered(self, text: str):
                await self.bot.send_message(self.chat_id, text)

    The print(text, kind) method will buffer output and flush periodically.
    Subclasses can use ``kind`` to decide whether to buffer or send immediately
    (e.g. send ``kind="progress"`` immediately without buffering).
    """

    def __init__(
        self,
        flush_interval: float | None = None,
        max_buffer_size: int | None = None,
    ):
        self._buffer: list[str] = []
        self._flush_interval = (
            flush_interval
            if flush_interval is not None
            else CFG.LLM_UI_FLUSH_INTERVAL / 1000
        )
        self._max_buffer_size = (
            max_buffer_size
            if max_buffer_size is not None
            else CFG.LLM_UI_MAX_BUFFER_SIZE
        )
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()
        # asyncio holds tasks weakly; keep fire-and-forget flushes alive.
        self._pending_flushes: set[asyncio.Task] = set()

    @property
    def buffer(self) -> list[str]:
        """Get the current buffer contents (read-only view)."""
        return list(self._buffer)

    @property
    def flush_interval(self) -> float:
        """Get the flush interval in seconds."""
        return self._flush_interval

    @property
    def has_flush_task(self) -> bool:
        """Check if a flush task is currently running."""
        return self._flush_task is not None

    async def start_flush_loop(self):
        """Start (or restart) the periodic flush task. Call this in run_async()."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop_flush_loop(self):
        """Stop the flush task and do final flush. Call this on exit."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self._flush_buffer()

    def buffer_output(self, text: str):
        """Add text to buffer, dropping spinner/progress noise. Flushes when full."""
        progress_chars = "⠇⠏⠋⠙⠹⠸⠼⠴⠦⠧⠇⠁⠂⠃"

        pure_spinner_pattern = re.compile(r"^\r[" + progress_chars + r"\s]*$")

        if pure_spinner_pattern.match(text):
            return

        text = text.replace("\r", "")
        if any(c in text for c in progress_chars):
            text = re.sub(r"[" + progress_chars + r"]+\s*$", "", text)
            text = text.rstrip()

        if not text.strip():
            return

        if "Prepare tool parameters" in text:
            return

        self._buffer.append(text)

        total_size = sum(len(s) for s in self._buffer)
        if total_size > self._max_buffer_size:
            task = asyncio.create_task(self._flush_buffer())
            self._pending_flushes.add(task)
            task.add_done_callback(self._pending_flushes.discard)

    async def _flush_buffer(self):
        """Send buffered content to user."""
        if not self._buffer:
            return

        async with self._flush_lock:
            content = "".join(self._buffer).strip()
            self._buffer = []

            if content:
                await self.send_buffered(content)

    async def send_buffered(self, text: str):
        """Override this to send buffered content."""
        raise NotImplementedError("BufferedOutputMixin requires send_buffered()")

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()
