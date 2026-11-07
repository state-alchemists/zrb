"""UI implementations for LLM chat applications.

Four levels of abstraction over the same contract, in increasing order of
control: `SimpleUI` (implement `print`/`get_input`), `EventDrivenUI`
(callback-driven backends: Telegram, Discord, HTTP/WebSocket), `BaseUI` (full
control), and the default prompt_toolkit `UI`. `AnyUI` and its five role
contracts sit beside them in `any_ui.py` and `any_ui_<role>.py`; `MultiUI` fans
one session out to several channels at once.

Every name resolves through PEP 562 `__getattr__` instead of an import here.
Importing any submodule of this package runs this module first, and the contract
in `any_ui.py` must stay importable from a headless run — an eager re-export
would load `BaseUI`, the message queue and prompt_toolkit behind
`from zrb.llm.ui.any_ui import AnyUI`. `fallback/` holds the pieces an L0 caller
may construct without the rest of this package.

`docs/llm/llm-custom-ui.md` owns the how-to — per-level method contracts,
dual-mode (CLI + external channel) wiring, and complete examples — with
`examples/chat-minimal-ui/`, `examples/chat-telegram/` and
`examples/chat-sse/` as the runnable versions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI  # noqa: F401
    from zrb.llm.ui.any_ui_display import AnyUIDisplay  # noqa: F401
    from zrb.llm.ui.any_ui_input import AnyUIInput  # noqa: F401
    from zrb.llm.ui.any_ui_picker import (  # noqa: F401
        AnyUIPicker,
        ChoiceOption,
        ChoiceSpec,
    )
    from zrb.llm.ui.any_ui_session import AnyUISession  # noqa: F401
    from zrb.llm.ui.any_ui_tools import AnyUITools  # noqa: F401
    from zrb.llm.ui.base.ui import BaseUI  # noqa: F401
    from zrb.llm.ui.buffered_output import BufferedOutputMixin  # noqa: F401
    from zrb.llm.ui.buffered_ui import BufferedUI  # noqa: F401
    from zrb.llm.ui.default.ui import UI  # noqa: F401
    from zrb.llm.ui.event_driven_ui import EventDrivenUI  # noqa: F401
    from zrb.llm.ui.multi import MultiUI  # noqa: F401
    from zrb.llm.ui.simple_ui_base import SimpleUI  # noqa: F401
    from zrb.llm.ui.trigger import (  # noqa: F401
        TriggerInput,
        TriggerMessage,
        TriggerReply,
    )
    from zrb.llm.ui.ui_config import UIConfig  # noqa: F401
    from zrb.llm.ui.ui_factory import create_ui_factory  # noqa: F401

#: Name -> module that defines it, resolved on first use.
_SOURCES = {
    # The contract and its five roles
    "AnyUI": "zrb.llm.ui.any_ui",
    "AnyUIDisplay": "zrb.llm.ui.any_ui_display",
    "AnyUIInput": "zrb.llm.ui.any_ui_input",
    "AnyUIPicker": "zrb.llm.ui.any_ui_picker",
    "AnyUISession": "zrb.llm.ui.any_ui_session",
    "AnyUITools": "zrb.llm.ui.any_ui_tools",
    "ChoiceOption": "zrb.llm.ui.any_ui_picker",
    "ChoiceSpec": "zrb.llm.ui.any_ui_picker",
    # Advanced API
    "BaseUI": "zrb.llm.ui.base.ui",
    "BufferedOutputMixin": "zrb.llm.ui.buffered_output",
    "BufferedUI": "zrb.llm.ui.buffered_ui",
    # Multi-channel support
    "MultiUI": "zrb.llm.ui.multi",
    # Simple API (RECOMMENDED)
    "SimpleUI": "zrb.llm.ui.simple_ui_base",
    "EventDrivenUI": "zrb.llm.ui.event_driven_ui",
    "UIConfig": "zrb.llm.ui.ui_config",
    "TriggerInput": "zrb.llm.ui.trigger",
    "TriggerMessage": "zrb.llm.ui.trigger",
    "TriggerReply": "zrb.llm.ui.trigger",
    "create_ui_factory": "zrb.llm.ui.ui_factory",
    # The default terminal UI
    "UI": "zrb.llm.ui.default.ui",
}

__all__ = [
    # The contract and its five roles
    "AnyUI",
    "AnyUIDisplay",
    "AnyUIInput",
    "AnyUIPicker",
    "AnyUISession",
    "AnyUITools",
    "ChoiceOption",
    "ChoiceSpec",
    # Advanced API
    "BaseUI",
    "BufferedOutputMixin",
    "BufferedUI",
    # Multi-channel support
    "MultiUI",
    # Simple API (RECOMMENDED)
    "SimpleUI",
    "EventDrivenUI",
    "UIConfig",
    "TriggerInput",
    "TriggerMessage",
    "TriggerReply",
    "create_ui_factory",
    # The default terminal UI
    "UI",
]


def __getattr__(name: str):
    source = _SOURCES.get(name)
    if source is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # lazy: heavy third-party — the default UI pulls prompt_toolkit, and the
    # rest of the package pulls each other; this module must cost nothing.
    import importlib

    value = getattr(importlib.import_module(source), name)
    globals()[name] = value
    return value
