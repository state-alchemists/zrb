from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.shared.feature_config import accepts_renamed_fields, resolve_from_cfg

if TYPE_CHECKING:
    from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend


@accepts_renamed_fields(enable_tool="tool_enabled")
@dataclass
class CameraConfig:
    """Settings for `enable_camera`. Each field mirrors `CFG.LLM_CAMERA_<FIELD>`;
    one left ``None`` is read from there when a session starts.

    *tool_enabled* adds the `TakePhoto` tool beside the command; ``enable_tool``,
    its name before the switch suffix, still works and warns.

    *backend* names a built-in backend (``auto``, ``termux``, ``ffmpeg``) or
    is an `AnyCameraBackend` of your own.
    """

    commands: list[str] | None = None
    backend: "str | AnyCameraBackend | None" = None
    device: str | None = None
    timeout: float | None = None
    tool_enabled: bool | None = None

    def resolve(self) -> "CameraConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_CAMERA_")
