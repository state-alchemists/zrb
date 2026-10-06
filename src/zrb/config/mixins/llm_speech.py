"""Speech config mixin: text-to-speech output for `enable_speech`.

When enabled, replies are read aloud a sentence at a time as they stream
(`LLM_SPEECH_STREAM`), along with tool approvals, questions, and a tool call
that starts after a silence. With streaming off, the reply is read once the
turn ends. Either way it is read whole, however long it is.

Read when a chat session starts, not at import, so `zrb_init.py` may change
any of these after importing zrb.
"""

from __future__ import annotations

import os
import tempfile

from zrb.config.env_field import (
    EnvField,
    comma_join,
    comma_list,
    json_dump,
    json_object,
    on_off,
)
from zrb.config.mixins.llm_voice import get_voice_default
from zrb.util.string.conversion import to_boolean


class LLMSpeechMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_SPEECH_ENABLED: str = "false"
        self.DEFAULT_LLM_SPEECH_COMMANDS: str = "/speech"
        self.DEFAULT_LLM_SPEECH_BACKEND: str = "auto"
        self.DEFAULT_LLM_SPEECH_VOICE: str = ""
        self.DEFAULT_LLM_SPEECH_STYLE: str = (
            "Speak like a capable colleague talking a teammate through their "
            "work: warm, clear and natural, at a relaxed conversational pace, "
            "with the rise and fall of real speech. Sound engaged, not "
            "theatrical."
        )
        self.DEFAULT_LLM_SPEECH_RATE: str = "165"
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
        self.DEFAULT_LLM_SPEECH_EVENTS: str = "reply, approval, question, progress"
        self.DEFAULT_LLM_SPEECH_WAV_PLAYER: str = ""
        self.DEFAULT_LLM_SPEECH_PLAYER: str = "auto"
        self.DEFAULT_LLM_SPEECH_LOCK_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SPEECH_DRAIN_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SPEECH_PLAYER_TIMEOUT: str = "120"
        self.DEFAULT_LLM_SPEECH_QUESTION_MESSAGE: str = (
            "A question is waiting for your answer."
        )
        self.DEFAULT_LLM_SPEECH_APPROVAL_MESSAGE: str = (
            "I need to {action}{target}. I need your approval."
        )
        self.DEFAULT_LLM_SPEECH_APPROVAL_TARGET_KEYS: str = (
            "path, file_path, command, notebook_path"
        )
        self.DEFAULT_LLM_SPEECH_APPROVAL_TARGET_MAX_CHARS: str = "80"
        self.DEFAULT_LLM_SPEECH_PROGRESS_SILENT_TOOLS: str = (
            "TodoRead, TodoWrite, ActivateSkill, SearchSkill"
        )
        self.DEFAULT_LLM_SPEECH_GEMINI_PROMPT: str = "Say: {text}"
        self.DEFAULT_LLM_SPEECH_GEMINI_STYLE_PROMPT: str = (
            "{style}\n\nSay exactly this, and nothing else: {text}"
        )
        self.DEFAULT_LLM_SPEECH_RENDER_TIMEOUT: str = "60"
        self.DEFAULT_LLM_SPEECH_STALL_TIMEOUT: str = "30"
        self.DEFAULT_LLM_SPEECH_PLAYER_BLOCK_FRAMES: str = "1024"
        self.DEFAULT_LLM_SPEECH_PLAYER_READ_AHEAD: str = "32"
        self.DEFAULT_LLM_SPEECH_PROGRESS_PHRASES: str = (
            '{"Read": "Reading a file.", "AnalyzeFile": "Reading a file.", "LS": "Looking through the files.", "Glob": "Looking through the files.", "Grep": "Searching the code.", "AnalyzeCode": "Reading the code.", "Write": "Writing a file.", "Edit": "Editing a file.", "MV": "Moving a file.", "RM": "Removing a file.", "Shell": "Running a command.", "Bash": "Running a command.", "WebSearch": "Searching the web.", "WebFetch": "Reading a web page.", "DelegateToAgent": "Handing this to a sub-agent.", "DelegateToAgentBackground": "Handing this to a sub-agent.", "Lsp*": "Checking the code.", "": "Working on it.", "*": "Using the {tool} tool."}'
        )
        self.DEFAULT_LLM_SPEECH_APPROVAL_ACTIONS: str = (
            '{"Write": "write a file", "Edit": "edit a file", "NotebookEdit": "edit a notebook", "Shell": "run a shell command", "Bash": "run a shell command", "DelegateToAgent": "delegate work to a sub-agent", "DelegateToAgentBackground": "delegate background work to a sub-agent", "": "run a tool", "*": "use the {tool} tool"}'
        )
        super().__init__()

    LLM_SPEECH_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        default_factory=lambda c: get_voice_default(c, "LLM_SPEECH_ENABLED"),
        doc=(
            "Read replies, approvals and questions aloud from the start of a "
            "session; the speech command switches it during one. Default: "
            "false, or as {ENV_PREFIX}_LLM_VOICE sets it."
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
            "- 'kokoro', 'piper' or 'pocket': a local voice that runs in this "
            "process, with its model and voice named by "
            "{ENV_PREFIX}_LLM_SPEECH_VOICE. Needs the zrb[voice] extra for "
            "Pipecat, and the service's own package beside it; naming one "
            "without it says which package to install.\n"
            "A project may register its own under a name of its choosing "
            "(zrb.llm.voice).\n"
            "If a cloud backend fails, the local engine speaks instead; one "
            "that runs in process needs zrb to play its audio, so where zrb "
            "cannot, the local engine speaks instead of it too."
        ),
    )

    LLM_SPEECH_VOICE = EnvField(
        str,
        doc=(
            "Voice name for the chosen backend. Empty uses the backend's "
            "default (system voice, en-us+m3, alloy, Sulafat)."
        ),
    )

    LLM_SPEECH_STYLE = EnvField(
        str,
        doc=(
            "How the 'openai' and 'gemini' backends should sound: a direction "
            "in plain words (tone, pace, warmth), not read aloud. Empty reads "
            "in the voice's default manner. The local engines ignore it. "
            "Default: a warm, clear, conversational colleague."
        ),
    )

    LLM_SPEECH_RATE = EnvField(
        int,
        fallback=165,
        doc="Words per minute for 'say' and 'espeak-ng'. Default: 165.",
    )

    LLM_SPEECH_STREAM = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Speak a reply a sentence at a time while it is written, and the "
            "text before a tool call when the call starts, instead of the whole "
            "reply once the turn ends. Either way the whole reply is read. "
            "Default: true."
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

    LLM_SPEECH_QUESTION_MESSAGE = EnvField(
        str,
        doc=(
            "Said when the model asks a question with no text of its own to "
            "read. Default: A question is waiting for your answer."
        ),
    )

    LLM_SPEECH_APPROVAL_MESSAGE = EnvField(
        str,
        doc=(
            "Said when a tool call waits for approval. {action} is what the "
            "tool does (see {ENV_PREFIX}_LLM_SPEECH_APPROVAL_ACTIONS); "
            "{target} is a space and the file or command it acts on, or "
            "empty. Default: I need to {action}{target}. I need your "
            "approval."
        ),
    )

    LLM_SPEECH_APPROVAL_TARGET_KEYS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated tool arguments tried, in order, for the "
            "{target} of an approval request. Default: path, file_path, "
            "command, notebook_path."
        ),
    )

    LLM_SPEECH_APPROVAL_TARGET_MAX_CHARS = EnvField(
        int,
        fallback=80,
        doc=(
            "Longest {target} read out in an approval request; longer is "
            "cut. 0 leaves the target out. Default: 80."
        ),
    )

    LLM_SPEECH_PROGRESS_SILENT_TOOLS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated tools never announced by progress narration, "
            "being over too fast to be worth a word. Default: TodoRead, "
            "TodoWrite, ActivateSkill, SearchSkill."
        ),
    )

    LLM_SPEECH_GEMINI_PROMPT = EnvField(
        str,
        doc=(
            "Prompt the 'gemini' backend reads {text} from when no style is "
            "set; without an instruction Gemini may answer a short line "
            "instead of reading it. Default: Say: {text}"
        ),
    )

    LLM_SPEECH_GEMINI_STYLE_PROMPT = EnvField(
        str,
        doc=(
            "Prompt the 'gemini' backend uses with "
            "{ENV_PREFIX}_LLM_SPEECH_STYLE set: {style} is the style, "
            "{text} what to read. Default: {style}, a blank line, then: Say "
            "exactly this, and nothing else: {text}"
        ),
    )

    LLM_SPEECH_RENDER_TIMEOUT = EnvField(
        float,
        fallback=60.0,
        doc=(
            "Seconds 'say' or 'espeak-ng' may take to render a sentence for "
            "zrb to play; it only bounds one that hangs. 0 means no limit. Default: 60."
        ),
    )

    LLM_SPEECH_STALL_TIMEOUT = EnvField(
        float,
        fallback=30.0,
        doc=(
            "With {ENV_PREFIX}_LLM_SPEECH_TIMEOUT at 0 (no limit), seconds "
            "the 'openai' backend's audio may stop arriving before playback "
            "gives up on it. Default: 30."
        ),
    )

    LLM_SPEECH_PLAYER_BLOCK_FRAMES = EnvField(
        int,
        fallback=1024,
        doc=(
            "Samples per block when zrb plays speech itself; smaller pauses "
            "and stops sooner, larger is kinder to a slow machine. Default: "
            "1024."
        ),
    )

    LLM_SPEECH_PLAYER_READ_AHEAD = EnvField(
        int,
        fallback=32,
        doc=(
            "Chunks of downloaded or rendered speech read ahead of "
            "playback. Default: 32."
        ),
    )

    LLM_SPEECH_PROGRESS_PHRASES = EnvField(
        json_object,
        serialize=json_dump,
        doc=(
            "JSON object of what progress narration says when a tool call "
            "starts: tool-name patterns (* and ? wildcards, matched in "
            'order, the first match wins; "" matches a call with no tool '
            "name) to a line, where {tool} is the tool's name. Default: "
            'English lines for the built-in tools, then "Lsp*": "Checking '
            'the code.", "": "Working on it.", and "*": "Using the {tool} '
            'tool."'
        ),
    )

    LLM_SPEECH_APPROVAL_ACTIONS = EnvField(
        json_object,
        serialize=json_dump,
        doc=(
            "JSON object of the {action} in "
            "{ENV_PREFIX}_LLM_SPEECH_APPROVAL_MESSAGE: tool-name patterns "
            '(* and ? wildcards, matched in order, the first match wins; "" '
            "matches a call with no tool name) to what the tool does, where "
            "{tool} is the tool's name. Default: English actions for the "
            'built-in tools that ask, then "": "run a tool" and "*": "use '
            'the {tool} tool"'
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

    LLM_SPEECH_PLAYER = EnvField(
        str,
        doc=(
            "How speech is played. One of:\n"
            "- 'auto' (default): by zrb itself through sounddevice when the "
            "zrb[voice] extra is installed and the backend can render audio "
            "('say', 'espeak-ng', 'openai', 'gemini'), so dictation can cancel "
            "zrb's voice out of the microphone and pause it; else by a player "
            "program. A cloud backend with LLM_SPEECH_WAV_PLAYER set plays "
            "through that player, and an output device that cannot open "
            "sends the rest of the session to a player program.\n"
            "- 'command': always by a player program (say, espeak-ng, "
            "termux-tts-speak, a WAV player).\n"
            "Any other value is logged and read as 'auto'."
        ),
    )

    LLM_SPEECH_WAV_PLAYER = EnvField(
        str,
        doc=(
            "Command that plays a WAV file for the cloud backends, the file "
            "path appended, e.g. 'mpv --really-quiet'. Set, it plays every "
            "sentence, even under LLM_SPEECH_PLAYER 'auto' (so barge-in's echo "
            "cancellation does not see it). Empty picks the first of "
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
