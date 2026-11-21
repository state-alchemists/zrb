"""The page's text box as a chat feature: a line typed there becomes a turn.

`enable_typed_input` adds it to a chat task; nothing is opened unless
`LLM_VOICE_REMOTE_URL` names a face server, since the page that holds the
microphone is the one that holds the box.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from zrb.llm.contracts.shared.feature_config import replace_registration
from zrb.llm.contracts.shared.input_source import WEB_INPUT
from zrb.llm.contracts.util.face_server import get_remote_headers, get_remote_url
from zrb.llm.presentation.typed.remote_typed import RemoteTyped
from zrb.llm.presentation.ui.trigger import TriggerInput

if TYPE_CHECKING:
    from zrb.llm.orchestration.task.chat.task import LLMChatTask


def enable_typed_input(chat: "LLMChatTask") -> None:
    """Make the page's text box a way into *chat*'s sessions.

    A line typed on the page is the user's own words, so it arrives with web
    provenance and becomes a turn the way a typed one does. It is never a
    `TriggerReply`: a remote source may not answer a tool approval, and a phone
    is not a reason to make an exception -- the approval is still answered at the
    keyboard that asked for it.
    """

    async def typed_lines() -> AsyncGenerator[TriggerInput, None]:
        url = get_remote_url()
        if url is None:
            return
        reader = RemoteTyped(url, get_remote_headers(), asyncio.get_running_loop())
        async for line in reader.lines():
            yield TriggerInput(text=line, source=WEB_INPUT)

    replace_registration(chat, "typed-input", [("append_trigger", typed_lines)])
