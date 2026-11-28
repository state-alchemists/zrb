"""The page's text box as a chat feature: a line typed there becomes a turn.

`enable_typed_input` adds it to a chat task; nothing is opened unless
`LLM_FACE_SERVER_URL` names a face server, since the page that holds the
microphone is the one that holds the box.

The setting is looked at again while the session lasts, not only when it starts:
`/set LLM_FACE_SERVER_URL ...` moves the speaker and the microphone without a
restart, and a box that stayed shut until the chat was reopened would be the one
part of the page that did not follow.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from zrb.llm.contracts.shared.feature_config import replace_registration
from zrb.llm.contracts.shared.input_source import WEB_INPUT
from zrb.llm.contracts.util.face_server import get_remote_headers, get_remote_url
from zrb.llm.presentation.typed.remote_typed import RemoteTyped
from zrb.llm.presentation.ui.trigger import TriggerInput

if TYPE_CHECKING:
    from zrb.llm.orchestration.task.chat.task import LLMChatTask

# How often the setting is looked at again. The page's own state is read once a second
# too, so a moved voice moves the box and the buttons in the same breath.
RECHECK_SECONDS = 1.0


class _TextBox:
    """The page's box, kept pointed at whichever server the setting names.

    One reader at a time, as the face server serves one reader at a time: two readers of
    one route would take a line each, and neither would read a message whole. The reader
    is kept while the setting stays put, so a page reload or a server restart is that
    reader's own reconnect rather than a new one here.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._url: "str | None" = None
        self._lines: "AsyncGenerator[str, None] | None" = None
        # The read waiting for the next line, held across looks at the setting:
        # cancelling it to look would end the route once a second.
        self._waiting: "asyncio.Future[str] | None" = None
        # A server that said it has no box at all. Asking it again would be asking a
        # page that cannot answer differently, so it is left alone until the setting
        # moves somewhere else.
        self._no_box: "str | None" = None

    async def follow(self, url: "str | None") -> None:
        """Point at *url*, letting go of the box that was there."""
        if url == self._url:
            return
        await self.close()
        self._url = url
        if url is not None and url == self._no_box:
            return  # the server that said it has no box is still the one named
        # Being sent to a different server forgets that answer: a page that had no box may have been
        # upgraded since, and coming back asks once more rather than staying shut for the session.
        self._no_box = None
        if url is not None:
            self._lines = RemoteTyped(url, get_remote_headers(), self._loop).lines()

    async def next_line(self, timeout: float) -> "str | None":
        """The next line typed, or ``None`` when none came within *timeout*."""
        if self._lines is None:
            await asyncio.sleep(timeout)
            return None
        if self._waiting is None:
            self._waiting = asyncio.ensure_future(anext(self._lines))
        done, _ = await asyncio.wait([self._waiting], timeout=timeout)
        if not done:
            return None
        waiting, self._waiting = self._waiting, None
        try:
            return waiting.result()
        except StopAsyncIteration:
            self._no_box = self._url
            await self.close()
            return None

    async def close(self) -> None:
        """Let go: the read waiting for a line first, then the route it waits on."""
        if self._waiting is not None:
            waiting, self._waiting = self._waiting, None
            waiting.cancel()
            with contextlib.suppress(BaseException):
                await waiting
        if self._lines is not None:
            lines, self._lines = self._lines, None
            await lines.aclose()


async def typed_lines() -> AsyncGenerator[TriggerInput, None]:
    box = _TextBox(asyncio.get_running_loop())
    try:
        while True:
            await box.follow(get_remote_url())
            line = await box.next_line(RECHECK_SECONDS)
            if line is not None:
                yield TriggerInput(text=line, source=WEB_INPUT)
    finally:
        await box.close()


def enable_typed_input(chat: "LLMChatTask") -> None:
    """Make the page's text box a way into *chat*'s sessions.

    A line typed on the page is the user's own words, so it arrives with web
    provenance and becomes a turn the way a typed one does. It is never a
    `TriggerReply`: a remote source may not answer a tool approval, and a phone
    is not a reason to make an exception -- the approval is still answered at the
    keyboard that asked for it.
    """
    replace_registration(chat, "typed-input", [("append_trigger", typed_lines)])
