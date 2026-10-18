"""`enable_screenshot`: a `/screenshot [display]` command that attaches a
capture of the user's screen, and, when enabled, a `TakeScreenshot` tool the
agent calls to look on its own.

The command attaches the screenshot to the next message rather than sending
it, so the user can say what to do with it. The tool is off by default and
asks for approval on every call: a screen can show anything, from a password
manager to a private chat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.agent_state import get_current_ui
from zrb.llm.permission.capability import Capability, tag
from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.screenshot.backend.builtin import get_screenshot_backend
from zrb.llm.screenshot.config import ScreenshotConfig
from zrb.llm.util.feature_config import replace_registration
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import BinaryContent, ToolFuncEither
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.ui.base.ui import BaseUI

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def enable_screenshot(
    chat: "LLMChatTask", config: ScreenshotConfig | None = None
) -> None:
    """Add the screenshot command to *chat*'s sessions; an empty ``commands``
    list leaves it out. With ``enable_tool`` on, also give the agent the
    `TakeScreenshot` tool. Calling it again replaces the earlier call."""

    def create_commands() -> "list[AnyCustomCommand]":
        return create_screenshot_commands((config or ScreenshotConfig()).resolve())

    def create_tools(_ctx: "AnyContext") -> "list[ToolFuncEither]":
        return create_screenshot_tools((config or ScreenshotConfig()).resolve())

    replace_registration(
        chat,
        "screenshot",
        [
            ("append_custom_command", create_commands),
            ("append_tool_factory", create_tools),
        ],
    )


def create_screenshot_commands(
    config: ScreenshotConfig,
) -> "list[AnyCustomCommand]":
    """One command per alias in the resolved *config*, sharing one backend."""
    backend = get_screenshot_backend(config.backend or "auto", config)

    def capture(kwargs: dict[str, str], ui: "BaseUI | None"):
        display = kwargs.get("display") or config.display or None
        return attach_screenshot(ui, backend, display)

    def complete_display(prefix: str) -> list[str]:
        return [
            display for display in backend.list_displays() if display.startswith(prefix)
        ]

    return [
        ActionCommand(
            command,
            capture,
            args=["display"],
            description="Capture the screen and attach it",
            complete_arg=complete_display,
        )
        for command in config.commands or []
    ]


async def attach_screenshot(
    ui: "BaseUI | None", backend: AnyScreenshotBackend, display: str | None
) -> None:
    """Capture *display* and queue the screenshot for *ui*'s next message.

    Refused on a non-local UI (the web chat, Telegram): the capture shows
    the machine zrb runs on, which that UI's user cannot see or intend.
    """
    if ui is None:
        return
    if not ui.is_local:
        ui.append_to_output(
            stylize_error(
                "\n  ❌ Screenshot refused: this chat is not on the machine "
                "zrb runs on, so a capture would show the server's screen, "
                "not yours. [SYSTEM SUGGESTION]: Attach the screenshot from "
                "your own device instead.\n"
            )
        )
        return
    ui.append_to_output(stylize_muted("\n  📸 Capturing the screen...\n"))
    screenshot = await capture_screenshot(backend, display)
    if screenshot is None:
        ui.append_to_output(
            stylize_error(
                f"\n  ❌ Screen capture failed.\n{backend.get_failure_hint()}"
            )
        )
        return
    ui.pending_attachments.append(screenshot)
    ui.append_to_output(
        stylize_muted(f"\n  📸 Screenshot captured ({len(screenshot.data)} bytes)\n")
    )
    ui.invalidate_ui()


def create_screenshot_tools(config: ScreenshotConfig) -> "list[ToolFuncEither]":
    """The `TakeScreenshot` tool for the resolved *config*, or none when
    ``enable_tool`` is off."""
    if not config.enable_tool:
        return []
    backend = get_screenshot_backend(config.backend or "auto", config)

    async def take_screenshot(
        display: Annotated[
            str | None,
            Field(description="Screen to capture; omit for the configured default."),
        ] = None,
    ):
        """Captures the user's screen and shows it to you.

        Use it when seeing the screen would help: the user refers to
        something on it ("this error", "look at my screen", "what's wrong
        with this page?") or asks about an app you cannot otherwise read. Do
        not use it to check on the user unprompted, and prefer reading a
        file or command output when that answers the question. The screen
        may show private things; the user approves each capture.
        """
        # lazy: transitively heavy — multimodal_describe loads pydantic_ai
        from zrb.llm.agent.run.multimodal_describe import create_image_tool_return

        # Refuse on a non-local UI (the web chat, Telegram): the capture shows
        # the machine zrb runs on, which that UI's user cannot see or intend.
        ui = get_current_ui()
        if ui is not None and not ui.is_local:
            return (
                "Screenshot refused: this chat is not on the machine zrb runs "
                "on, so a capture would show the server's screen, not yours. "
                "[SYSTEM SUGGESTION]: Attach the screenshot from your own "
                "device instead."
            )

        screenshot = await capture_screenshot(
            backend, display or config.display or None
        )
        if screenshot is None:
            return (
                "Screen capture failed. [SYSTEM SUGGESTION]: Tell the user the "
                "screen could not be captured and pass on this hint, rather "
                f"than retrying:\n{backend.get_failure_hint()}"
            )
        return await create_image_tool_return(screenshot, "Screenshot taken")

    take_screenshot.__name__ = "TakeScreenshot"
    # EXECUTE, not READ: plan mode allows READ without asking, and a capture
    # of the user's screen must always be approved.
    return [tag(take_screenshot, Capability.EXECUTE)]


async def capture_screenshot(
    backend: AnyScreenshotBackend, display: str | None
) -> "BinaryContent | None":
    """A screenshot of *display*, scaled for a model, or ``None`` when the
    capture failed or the image is too large to decode safely."""
    # lazy: heavy transitive (pydantic_ai) via zrb.llm.agent.types
    from zrb.llm.agent.types import BinaryContent

    image_bytes = await backend.capture(display)
    if image_bytes is None:
        return None
    media_type = "image/png" if image_bytes.startswith(_PNG_SIGNATURE) else "image/jpeg"
    scaled = scale_image_bytes(image_bytes, media_type=media_type)
    if scaled.rejected is not None:
        return None
    return BinaryContent(data=scaled.data, media_type=scaled.media_type)
