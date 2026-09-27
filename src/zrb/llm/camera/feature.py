"""`enable_camera`: a `/photo [device]` command that attaches a camera photo.

The command attaches the photo to the next message rather than sending it, so
the user can say what to do with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.builtin import get_camera_backend
from zrb.llm.camera.config import CameraConfig
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.util.feature_config import replace_registration
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.ui.base.ui import BaseUI


def enable_camera(chat: "LLMChatTask", config: CameraConfig | None = None) -> None:
    """Add the camera command to *chat*'s sessions; an empty ``commands``
    list leaves it out. Calling it again replaces the earlier call."""

    def create_commands() -> "list[AnyCustomCommand]":
        return create_camera_commands((config or CameraConfig()).resolve())

    replace_registration(chat, "camera", [("append_custom_command", create_commands)])


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
    photo_bytes = await backend.capture(device)
    if photo_bytes is None:
        ui.append_to_output(
            stylize_error(
                f"\n  ❌ Camera capture failed.\n{backend.get_failure_hint()}"
            )
        )
        return
    # lazy: heavy transitive (pydantic_ai) via zrb.llm.agent.types
    from zrb.llm.agent.types import BinaryContent

    scaled = scale_image_bytes(photo_bytes, media_type="image/jpeg")
    ui.pending_attachments.append(
        BinaryContent(data=scaled.data, media_type=scaled.media_type)
    )
    ui.append_to_output(
        stylize_muted(f"\n  📷 Photo captured ({scaled.final_bytes} bytes)\n")
    )
    ui.invalidate_ui()
