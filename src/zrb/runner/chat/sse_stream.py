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
        self._closed = False

        async def event_generator():
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'session_id': session_id})}\n\n"

            while True:
                if self._closed:
                    break
                try:
                    get_task = asyncio.create_task(self._queue.get())
                    try:
                        item = await asyncio.wait_for(get_task, timeout=60)
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
