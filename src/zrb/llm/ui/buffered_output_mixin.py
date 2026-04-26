import asyncio

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

            async def send_text(self, text: str):
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
        """Start the periodic flush task. Call this in run_async()."""
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop_flush_loop(self):
        """Stop the flush task and do final flush. Call this on exit."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()

    def buffer_output(self, text: str):
        """Add text to buffer. Automatically flushes when full.

        Filters out redundant spinner/progress messages that would otherwise
        be duplicated in event-driven UIs (Telegram, Discord, etc.).
        """
        import re

        # Progress characters for spinner animation
        progress_chars = "⠇⠏⠋⠙⠹⠸⠼⠴⠦⠧⠇⠁⠂⠃"

        # Pattern 1: Pure spinner update - only \r and progress chars
        pure_spinner_pattern = re.compile(r"^\r[" + progress_chars + r"\s]*$")

        if pure_spinner_pattern.match(text):
            return

        # Pattern 2: Spinner at end with message like "\r🔄 Prepare tool parameters ⠇"
        if "\r" in text:
            text = text.replace("\r", "")

        # Pattern 3: Line ending with spinner (like "🔄 Prepare tool parameters ⠇")
        if any(c in text for c in progress_chars):
            text = re.sub(r"[" + progress_chars + r"]+\s*$", "", text)
            text = text.rstrip()

        # Remove remaining \r
        text = text.replace("\r", "")

        if not text.strip():
            return

        # Filter out redundant "Prepare tool parameters" messages
        # These are progress indicators that get repeated in event-driven UIs
        # We only want to show the actual tool call notification
        if "Prepare tool parameters" in text:
            # Skip this message - the tool call notification is what matters
            return

        self._buffer.append(text)

        # Auto-flush when buffer is large
        total_size = sum(len(s) for s in self._buffer)
        if total_size > self._max_buffer_size:
            asyncio.create_task(self._flush_buffer())

    async def _flush_buffer(self):
        """Send buffered content to user."""
        if not self._buffer:
            return

        async with self._flush_lock:
            content = "".join(self._buffer).strip()
            self._buffer = []

            if content:
                # Call the subclass send method
                await self._send_buffered(content)

    async def _send_buffered(self, text: str):
        """Override this to send buffered content."""
        raise NotImplementedError("BufferedOutputMixin requires _send_buffered()")

    async def _flush_loop(self):
        """Periodically flush buffer."""
        while True:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()
