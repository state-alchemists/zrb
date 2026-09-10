"""UI implementations for LLM chat applications.

Four levels of abstraction over the same contract, in increasing order of
control: `SimpleUI` (implement `print`/`get_input`), `EventDrivenUI`
(callback-driven backends: Telegram, Discord, HTTP/WebSocket), `BaseUI` (full
control), and the default prompt_toolkit `UI`. `AnyUI` (`any_ui.py`) is the
minimal contract all of them satisfy; `MultiUI` fans one session out to
several channels at once.

`docs/llm/llm-custom-ui.md` owns the how-to — per-level method contracts,
dual-mode (CLI + external channel) wiring, and complete examples — with
`examples/chat-minimal-ui/`, `examples/chat-telegram/` and
`examples/chat-sse/` as the runnable versions.
"""

from typing import TYPE_CHECKING

from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.buffered_output import BufferedOutputMixin
from zrb.llm.ui.buffered_ui import BufferedUI

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI  # noqa: F401 — lazy-loaded via __getattr__
from zrb.llm.ui.event_driven_ui import EventDrivenUI
from zrb.llm.ui.multi_ui import MultiUI
from zrb.llm.ui.simple_ui_base import SimpleUI
from zrb.llm.ui.ui_config import UIConfig
from zrb.llm.ui.ui_factory import create_ui_factory

__all__ = [
    "BufferedOutputMixin",
    "BufferedUI",
    # Simple API (RECOMMENDED)
    "SimpleUI",
    "EventDrivenUI",
    "UIConfig",
    "create_ui_factory",
    # Advanced API
    "BaseUI",
    "UI",
    # Multi-channel support
    "MultiUI",
]


def __getattr__(name):
    if name == "UI":
        # lazy: default UI pulls prompt_toolkit (~25ms cold load); resolve
        # only when a caller actually does `from zrb.llm.ui import UI`.
        from zrb.llm.ui.default.ui import UI as _UI

        return _UI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
