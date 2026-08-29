"""Voice-dictation session state for `BaseUI`.

Self-contained like `BaseUIUsage`: the push-to-talk recording logic lives in
`llm/ui/default/keybindings.py` and the `/voice` toggle in `commands.py`,
both of which reach this state only through `BaseUI`'s public properties
(`voice_mode_active`, `voice_recording_active`, `voice_task`,
`voice_stop_event`) — so this part needs no reference back to the owner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


class BaseUIVoiceState:
    """Whether voice-dictation mode/recording is active, and the task/event
    driving an in-progress recording."""

    def __init__(self) -> None:
        self.mode_active = False
        self.recording_active = False
        self.task: "asyncio.Task | None" = None
        self.stop_event: "asyncio.Event | None" = None
