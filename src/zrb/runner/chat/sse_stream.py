import asyncio
import json
from typing import Any

from fastapi.responses import StreamingResponse


class SSEStreamResponse(StreamingResponse):
    def __init__(
        self,
        session_id: str,
        session_manager: Any,
        **kwargs,
    ):
        session = session_manager.get_session(session_id)
        self.session_id = session_id
        self._queue = session.output_queue

        async def event_generator():
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'session_id': session_id})}\n\n"

            while True:
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=60)
                    if isinstance(item, dict):
                        text = item.get("text", "")
                        kind = item.get("kind", "text")
                    else:
                        text = item
                        kind = "text"
                    yield f"data: {json.dumps({'type': kind, 'text': text}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
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
