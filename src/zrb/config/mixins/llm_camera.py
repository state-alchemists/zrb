"""Camera config for the `/photo` command."""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.util.string.conversion import to_boolean


class LLMCameraMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_CAMERA_COMMANDS: str = "/photo, /p"
        self.DEFAULT_LLM_CAMERA_BACKEND: str = "auto"
        self.DEFAULT_LLM_CAMERA_DEVICE: str = ""
        self.DEFAULT_LLM_CAMERA_TIMEOUT: str = "15"
        self.DEFAULT_LLM_CAMERA_ENABLE_TOOL: str = "off"
        super().__init__()

    LLM_CAMERA_COMMANDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated command aliases to capture a photo from the "
            "camera and attach it to the next message (usage: {cmd} [device])."
        ),
    )

    LLM_CAMERA_BACKEND = EnvField(
        str,
        doc=(
            "Camera backend. One of:\n"
            "- 'auto' (default): Termux:API on Android when installed, else ffmpeg.\n"
            "- 'termux': termux-camera-photo.\n"
            "- 'ffmpeg': avfoundation (macOS), dshow (Windows), v4l2 (Linux)."
        ),
    )

    LLM_CAMERA_DEVICE = EnvField(
        str,
        doc=(
            "Camera device used when the command names none. Empty picks the "
            "platform default."
        ),
    )

    LLM_CAMERA_TIMEOUT = EnvField(
        float,
        fallback=15.0,
        doc=(
            "Seconds a capture may take, every attempt included, before it is "
            "abandoned; a camera that opens but never delivers a frame would "
            "otherwise hang. 0 means no limit. Default: 15."
        ),
    )

    LLM_CAMERA_ENABLE_TOOL = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Give the agent a TakePhoto tool, so it can look through the "
            "camera on its own instead of waiting for the camera command. "
            "Each call asks for approval like any other tool. Default: off."
        ),
    )
