import asyncio
import json
from typing import Any

# Eager fastapi import, unlike the rest of this package: this class is a
# route's return annotation, and FastAPI must resolve it to a Response subclass
# (not a factory function) to skip building a pydantic response model.
from fastapi.responses import StreamingResponse

from zrb.config.config import CFG


class SSEStreamResponse(StreamingResponse):
    def __init__(  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
        self,
        session_id: str,
        session_manager: Any,
        **kwargs,
    ):
        session = session_manager.get_session(session_id)
        self.session_id = session_id
        self.output_queue = session.output_queue
        self._closed = False

        async def event_generator():
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'session_id': session_id})}\n\n"

            while True:
                if self._closed:
                    break
                try:
                    get_task = asyncio.create_task(self.output_queue.get())
                    try:
                        item = await asyncio.wait_for(
                            get_task, timeout=CFG.LLM_SSE_KEEPALIVE_TIMEOUT / 1000
                        )
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    except asyncio.CancelledError:
                        get_task.cancel()
                        try:
                            await get_task
                        except asyncio.CancelledError:
                            pass
                        raise

                    if isinstance(item, dict):
                        text = item.get("text", "")
                        kind = item.get("kind", "text")
                    else:
                        text = item
                        kind = "text"
                    yield f"data: {json.dumps({'type': kind, 'text': text}, ensure_ascii=False)}\n\n"
                except asyncio.CancelledError:
                    break

        super().__init__(
            content=event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def close(self):
        """Mark the stream as closed to stop the generator loop."""
        self._closed = True
