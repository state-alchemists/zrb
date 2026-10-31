"""`enable_camera`: a `/photo [device]` command that attaches a camera photo,
and, when enabled, a `TakePhoto` tool the agent calls to look on its own.

The command attaches the photo to the next message rather than sending it, so
the user can say what to do with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.builtin import get_camera_backend
from zrb.llm.camera.config import CameraConfig
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.permission.capability import Capability, tag
from zrb.llm.util.feature_config import replace_registration
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import BinaryContent, ToolFuncEither
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.ui.base.ui import BaseUI


def enable_camera(chat: "LLMChatTask", config: CameraConfig | None = None) -> None:
    """Add the camera command to *chat*'s sessions; an empty ``commands``
    list leaves it out. With ``enable_tool`` on, also give the agent the
    `TakePhoto` tool. Calling it again replaces the earlier call."""

    def create_commands() -> "list[AnyCustomCommand]":
        return create_camera_commands((config or CameraConfig()).resolve())

    def create_tools(_ctx: "AnyContext") -> "list[ToolFuncEither]":
        return create_camera_tools((config or CameraConfig()).resolve())

    replace_registration(
        chat,
        "camera",
        [
            ("append_custom_command", create_commands),
            ("append_tool_factory", create_tools),
        ],
    )


def create_camera_commands(config: CameraConfig) -> "list[AnyCustomCommand]":
    """One command per alias in the resolved *config*, sharing one backend."""
    backend = get_camera_backend(config.backend or "auto", config)

    def capture(kwargs: dict[str, str], ui: "BaseUI | None"):
        return attach_photo(ui, backend, kwargs.get("device") or config.device or None)

    def complete_device(prefix: str) -> list[str]:
        return [
            device for device in backend.list_devices() if device.startswith(prefix)
        ]

    return [
        ActionCommand(
            command,
            capture,
            args=["device"],
            description="Capture a photo from the camera and attach it",
            complete_arg=complete_device,
        )
        for command in config.commands or []
    ]


async def attach_photo(
    ui: "BaseUI | None", backend: AnyCameraBackend, device: str | None
) -> None:
    """Capture a photo from *device* and queue it for *ui*'s next message."""
    if ui is None:
        return
    ui.append_to_output(stylize_muted("\n  📷 Capturing photo...\n"))
    photo = await capture_photo(backend, device)
    if photo is None:
        ui.append_to_output(
            stylize_error(
                f"\n  ❌ Camera capture failed.\n{backend.get_failure_hint()}"
            )
        )
        return
    ui.pending_attachments.append(photo)
    ui.append_to_output(
        stylize_muted(f"\n  📷 Photo captured ({len(photo.data)} bytes)\n")
    )
    ui.invalidate_ui()


def create_camera_tools(config: CameraConfig) -> "list[ToolFuncEither]":
    """The `TakePhoto` tool for the resolved *config*, or none when
    ``enable_tool`` is off."""
    if not config.enable_tool:
        return []
    backend = get_camera_backend(config.backend or "auto", config)

    async def take_photo(
        device: Annotated[
            str | None,
            Field(description="Camera to use; omit for the configured default."),
        ] = None,
    ):
        """Takes a photo with the user's camera and shows it to you.

        Use it when seeing the user or their surroundings would help: they
        refer to something in front of them ("this", "look at", "what do you
        think of my...") or ask how they look. Do not use it to check on the
        user unprompted. The user approves each photo.
        """
        # lazy: transitively heavy — multimodal_describe loads pydantic_ai
        from zrb.llm.tool.multimodal_describe import create_image_tool_return

        photo = await capture_photo(backend, device or config.device or None)
        if photo is None:
            return (
                "Camera capture failed. [SYSTEM SUGGESTION]: Tell the user the "
                "camera did not deliver a photo and pass on this hint, rather "
                f"than retrying:\n{backend.get_failure_hint()}"
            )
        return await create_image_tool_return(photo, "Photo taken")

    take_photo.__name__ = "TakePhoto"
    # EXECUTE, not READ: plan mode allows READ without asking, and a photo
    # of the user must always be approved.
    return [tag(take_photo, Capability.EXECUTE)]


async def capture_photo(
    backend: AnyCameraBackend, device: str | None
) -> "BinaryContent | None":
    """A photo from *device*, scaled for a model, or ``None`` when the capture
    failed or the image is too large to decode safely."""
    # lazy: heavy transitive (pydantic_ai) via zrb.llm.agent.types
    from zrb.llm.agent.types import BinaryContent

    photo_bytes = await backend.capture(device)
    if photo_bytes is None:
        return None
    scaled = scale_image_bytes(photo_bytes, media_type="image/jpeg")
    if scaled.rejected is not None:
        return None
    return BinaryContent(data=scaled.data, media_type=scaled.media_type)
