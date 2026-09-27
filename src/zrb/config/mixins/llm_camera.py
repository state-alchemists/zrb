"""Camera config mixin: the `/photo` command of `enable_camera`.

Read when a chat session starts, not at import, so `zrb_init.py` may change
any of these after importing zrb.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list


class LLMCameraMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_CAMERA_COMMANDS: str = "/photo, /p"
        self.DEFAULT_LLM_CAMERA_BACKEND: str = "auto"
        self.DEFAULT_LLM_CAMERA_DEVICE: str = ""
        self.DEFAULT_LLM_CAMERA_TIMEOUT: str = "15"
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
            "Seconds a capture may take before it is abandoned; a camera that "
            "opens but never delivers a frame would otherwise hang. Default: 15."
        ),
    )
