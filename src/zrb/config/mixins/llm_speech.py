"""Speech config mixin: text-to-speech output for `enable_speech`.

When enabled, replies are read aloud a sentence at a time as they stream
(`LLM_SPEECH_STREAM`), along with tool approvals, questions, and a tool call
that starts after a silence. With streaming off, the reply is read at the end
of the turn: one longer than `LLM_SPEECH_MAX_CHARS` is cut at a sentence end,
or summarized by the small model with `LLM_SPEECH_SUMMARIZE`, and followed by
a note that the full answer is on screen.

Read when a chat session starts, not at import, so `zrb_init.py` may change
any of these after importing zrb.
"""

from __future__ import annotations

import os
import tempfile

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.util.string.conversion import to_boolean


class LLMSpeechMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_SPEECH_ENABLED: str = "false"
        self.DEFAULT_LLM_SPEECH_COMMANDS: str = "/speech"
        self.DEFAULT_LLM_SPEECH_BACKEND: str = "auto"
        self.DEFAULT_LLM_SPEECH_VOICE: str = ""
        self.DEFAULT_LLM_SPEECH_RATE: str = "165"
        self.DEFAULT_LLM_SPEECH_MAX_CHARS: str = "400"
        self.DEFAULT_LLM_SPEECH_SUMMARIZE: str = "false"
        self.DEFAULT_LLM_SPEECH_STREAM: str = "true"
        self.DEFAULT_LLM_SPEECH_PROGRESS_INTERVAL: str = "8"
        self.DEFAULT_LLM_SPEECH_OPENAI_MODEL: str = "gpt-4o-mini-tts"
        self.DEFAULT_LLM_SPEECH_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
        self.DEFAULT_LLM_SPEECH_GEMINI_MODEL: str = "gemini-2.5-flash-preview-tts"
        self.DEFAULT_LLM_SPEECH_TIMEOUT: str = "15"
        self.DEFAULT_LLM_SPEECH_TERMUX_LANGUAGE: str = ""
        self.DEFAULT_LLM_SPEECH_TERMUX_ENGINE: str = ""
        self.DEFAULT_LLM_SPEECH_TERMUX_REGION: str = ""
        self.DEFAULT_LLM_SPEECH_TERMUX_RATE: str = "1.0"
        self.DEFAULT_LLM_SPEECH_TERMUX_PITCH: str = "1.0"
        self.DEFAULT_LLM_SPEECH_TERMUX_STREAM: str = ""
        self.DEFAULT_LLM_SPEECH_SUMMARY_MODEL: str = ""
        self.DEFAULT_LLM_SPEECH_ON_SCREEN_NOTE: str = "The full answer is on screen."
        self.DEFAULT_LLM_SPEECH_EVENTS: str = "reply, approval, question, progress"
        self.DEFAULT_LLM_SPEECH_WAV_PLAYER: str = ""
        self.DEFAULT_LLM_SPEECH_LOCK_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SPEECH_DRAIN_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SPEECH_PLAYER_TIMEOUT: str = "120"
        super().__init__()

    LLM_SPEECH_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Read replies, approvals and questions aloud from the start of a "
            "session; the speech command switches it during one. Default: false."
        ),
    )

    LLM_SPEECH_COMMANDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated command aliases that switch speech on and off "
            "during a session, dropping anything not yet spoken."
        ),
    )

    LLM_SPEECH_BACKEND = EnvField(
        str,
        doc=(
            "Text-to-speech backend. One of:\n"
            "- 'auto' (default): 'termux' on Termux, 'say' on macOS, else "
            "'espeak-ng'.\n"
            "- 'termux': Android's voices through Termux:API.\n"
            "- 'say': macOS.\n"
            "- 'espeak-ng': needs espeak-ng on PATH.\n"
            "- 'openai': needs OPENAI_API_KEY.\n"
            "- 'gemini': needs GEMINI_API_KEY or GOOGLE_API_KEY.\n"
            "If a cloud backend fails, the local engine speaks instead."
        ),
    )

    LLM_SPEECH_VOICE = EnvField(
        str,
        doc=(
            "Voice name for the chosen backend. Empty uses the backend's "
            "default (system voice, en-us+m3, alloy, Sulafat)."
        ),
    )

    LLM_SPEECH_RATE = EnvField(
        int,
        fallback=165,
        doc="Words per minute for 'say' and 'espeak-ng'. Default: 165.",
    )

    LLM_SPEECH_MAX_CHARS = EnvField(
        int,
        fallback=400,
        doc=(
            "Longest reply spoken in full, in characters; 0 means no limit. "
            "Default: 400."
        ),
    )

    LLM_SPEECH_SUMMARIZE = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Speak a small-model summary of a reply longer than "
            "{ENV_PREFIX}_LLM_SPEECH_MAX_CHARS instead of its opening. Costs a "
            "model call per long reply. Default: false."
        ),
    )

    LLM_SPEECH_STREAM = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Speak a reply a sentence at a time while it is written, and the "
            "text before a tool call when the call starts, instead of the "
            "whole reply once the turn ends. {ENV_PREFIX}_LLM_SPEECH_MAX_CHARS "
            "then caps what one turn speaks, and "
            "{ENV_PREFIX}_LLM_SPEECH_SUMMARIZE does not apply. Default: true."
        ),
    )

    LLM_SPEECH_PROGRESS_INTERVAL = EnvField(
        float,
        fallback=8.0,
        doc=(
            "With 'progress' in {ENV_PREFIX}_LLM_SPEECH_EVENTS, the seconds of "
            'silence after which a tool call starting is announced ("Running '
            'a command."); 0 announces nothing. Default: 8.'
        ),
    )

    LLM_SPEECH_OPENAI_MODEL = EnvField(
        str, doc="Model for the 'openai' backend. Default: gpt-4o-mini-tts."
    )

    LLM_SPEECH_OPENAI_BASE_URL = EnvField(
        str,
        doc="API base URL for the 'openai' backend. Default: https://api.openai.com/v1.",
    )

    LLM_SPEECH_GEMINI_MODEL = EnvField(
        str,
        doc="Model for the 'gemini' backend. Default: gemini-2.5-flash-preview-tts.",
    )

    LLM_SPEECH_TERMUX_LANGUAGE = EnvField(
        str,
        doc="Language for the 'termux' backend (-l), e.g. 'en'. Empty: the phone's.",
    )

    LLM_SPEECH_TERMUX_ENGINE = EnvField(
        str, doc="Android TTS engine for the 'termux' backend (-e). Empty: the default."
    )

    LLM_SPEECH_TERMUX_REGION = EnvField(
        str, doc="Region for the 'termux' backend (-n), e.g. 'US'. Empty: the default."
    )

    LLM_SPEECH_TERMUX_RATE = EnvField(
        float, fallback=1.0, doc="Speech rate for the 'termux' backend; 1.0 is normal."
    )

    LLM_SPEECH_TERMUX_PITCH = EnvField(
        float, fallback=1.0, doc="Pitch for the 'termux' backend; 1.0 is normal."
    )

    LLM_SPEECH_TERMUX_STREAM = EnvField(
        str,
        doc=(
            "Android audio stream for the 'termux' backend (-s): ALARM, MUSIC, "
            "NOTIFICATION, RING, SYSTEM or VOICE_CALL. Empty: the default."
        ),
    )

    LLM_SPEECH_TIMEOUT = EnvField(
        float,
        fallback=15.0,
        doc=(
            "Seconds a cloud backend may take before the local engine speaks "
            "instead; 0 means no limit."
        ),
    )

    LLM_SPEECH_SUMMARY_MODEL = EnvField(
        str,
        doc=(
            "Model that summarizes long replies when "
            "{ENV_PREFIX}_LLM_SPEECH_SUMMARIZE is on. Empty uses the small model "
            "({ENV_PREFIX}_LLM_SMALL_MODEL, else the main model)."
        ),
    )

    LLM_SPEECH_ON_SCREEN_NOTE = EnvField(
        str,
        doc=(
            "Said after a reply that was cut or summarized. "
            "Default: The full answer is on screen."
        ),
    )

    LLM_SPEECH_EVENTS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated moments to speak: 'reply' (end of a turn), "
            "'approval' (a tool call waits for approval), 'question' (the "
            "agent asks something), 'progress' (a tool call starts after a "
            "silence, see {ENV_PREFIX}_LLM_SPEECH_PROGRESS_INTERVAL). Default: "
            "reply, approval, question, progress."
        ),
    )

    LLM_SPEECH_WAV_PLAYER = EnvField(
        str,
        doc=(
            "Command that plays a WAV file for the cloud backends, the file "
            "path appended, e.g. 'mpv --really-quiet'. Empty picks the first of "
            "afplay, paplay, aplay, ffplay on PATH."
        ),
    )

    LLM_SPEECH_LOCK_FILE = EnvField(
        str,
        default_factory=lambda host: os.path.join(
            tempfile.gettempdir(), f"{host.ROOT_GROUP_NAME}-speech.lock"
        ),
        doc=(
            "File locked while speech plays, so zrb sessions on this machine "
            "take turns and dictation ignores zrb's own voice. "
            "Default: <tmp>/<root group name>-speech.lock."
        ),
    )

    LLM_SPEECH_LOCK_TIMEOUT = EnvField(
        float,
        fallback=30.0,
        doc=(
            "Seconds to wait for another session to finish speaking before "
            "dropping an utterance. Default: 30."
        ),
    )

    LLM_SPEECH_DRAIN_TIMEOUT = EnvField(
        float,
        fallback=30.0,
        doc="Seconds queued speech may still play after zrb exits. Default: 30.",
    )

    LLM_SPEECH_PLAYER_TIMEOUT = EnvField(
        float,
        fallback=120.0,
        doc=(
            "Seconds one utterance may play before it is stopped; 0 means no "
            "limit. Default: 120."
        ),
    )
