"""Emotion config for `enable_emotion`: the model opens each reply with an
emoji for how it feels, and the emotions read from the user's prompt and the
model's reply fire the `Emotion` hook.

Read when a chat session starts, not at import, so `zrb_init.py` may change
any of these after importing zrb.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, on_off
from zrb.util.string.conversion import to_boolean


class LLMEmotionMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_EMOTION_ENABLED: str = "off"
        super().__init__()

    LLM_EMOTION_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "'on' asks the model to open each reply with an emoji for how it "
            "feels, which zrb takes out before the user sees it, and fires the "
            "Emotion hook with the emotion of each reply and with the tone "
            "dictation heard each prompt in "
            "({ENV_PREFIX}_LLM_DICTATION_DETECT_EMOTION). Default: off."
        ),
    )
