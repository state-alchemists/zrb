"""Dictation config mixin: speech-to-text input for `enable_dictation`.

Two modes. ``ptt``: the dictation command starts recording, and the same
command or a pause stops it; the transcript lands in the input box.
``hands_free``: the microphone stays open and every utterance is submitted as
a turn, or answers a pending approval or question. With wake words set, only
utterances starting with one count. The hands-free command switches between
the two during a session.

Read when a chat session starts, not at import, so `zrb_init.py` may change
any of these after importing zrb. Audio dependencies (sounddevice, numpy,
vosk) load only when the microphone is first opened. A negative listening
duration counts as 0.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.config.mixins.llm_voice import get_voice_default
from zrb.util.string.conversion import to_boolean


class LLMDictationMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_DICTATION_MODE: str = "ptt"
        self.DEFAULT_LLM_DICTATION_COMMANDS: str = "/voice, /v"
        self.DEFAULT_LLM_DICTATION_HANDS_FREE_COMMANDS: str = "/handsfree"
        self.DEFAULT_LLM_DICTATION_BACKEND: str = "vosk"
        self.DEFAULT_LLM_DICTATION_WAKE_WORDS: str = ""
        self.DEFAULT_LLM_DICTATION_THRESHOLD: str = "0.01"
        self.DEFAULT_LLM_DICTATION_NOISE_MARGIN: str = "2.0"
        self.DEFAULT_LLM_DICTATION_SILENCE: str = "1.0"
        self.DEFAULT_LLM_DICTATION_MIN_SILENCE: str = "0.5"
        self.DEFAULT_LLM_DICTATION_WAKE_WINDOW: str = "8.0"
        self.DEFAULT_LLM_DICTATION_MIN_SPEECH: str = "0.25"
        self.DEFAULT_LLM_DICTATION_MIN_WORDS: str = "1"
        self.DEFAULT_LLM_DICTATION_MAX_UTTERANCE: str = "30.0"
        self.DEFAULT_LLM_DICTATION_MAX_BACKLOG: str = "30.0"
        self.DEFAULT_LLM_DICTATION_PRE_ROLL: str = "0.3"
        self.DEFAULT_LLM_DICTATION_ECHO_COOLDOWN: str = "0.4"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_ENABLED: str = "off"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_MIN_SPEECH: str = "0.3"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_MARGIN: str = "3.0"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_MIN_WORDS: str = "2"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_ACTION: str = "steer"
        self.DEFAULT_LLM_DICTATION_SELF_ECHO_MATCH: str = "0.8"
        self.DEFAULT_LLM_DICTATION_SELF_ECHO_TAIL: str = "1.0"
        self.DEFAULT_LLM_DICTATION_APPROVE_WORDS: str = (
            "yes, yeah, yep, ok, okay, sure, approve, accept, go ahead, do it"
        )
        self.DEFAULT_LLM_DICTATION_DENY_WORDS: str = (
            "no, nope, deny, cancel, stop, don't"
        )
        self.DEFAULT_LLM_DICTATION_OPENAI_MODEL: str = "whisper-1"
        self.DEFAULT_LLM_DICTATION_OPENAI_BASE_URL: str = ""
        self.DEFAULT_LLM_DICTATION_GOOGLE_MODEL: str = "gemini-2.5-flash"
        self.DEFAULT_LLM_DICTATION_VOSK_MODEL_NAME: str = "vosk-model-small-en-us-0.15"
        self.DEFAULT_LLM_DICTATION_VOSK_MODEL_URL: str = (
            "https://alphacephei.com/vosk/models"
        )
        self.DEFAULT_LLM_DICTATION_VOSK_DOWNLOAD_TIMEOUT: str = "120"
        self.DEFAULT_LLM_DICTATION_VOSK_MAX_DOWNLOAD_MB: str = "4096"
        self.DEFAULT_LLM_DICTATION_VOSK_MAX_UNCOMPRESSED_MB: str = "8192"
        self.DEFAULT_LLM_DICTATION_VOSK_MAX_FILE_MB: str = "4096"
        self.DEFAULT_LLM_DICTATION_VOSK_MAX_FILES: str = "10000"
        self.DEFAULT_LLM_DICTATION_VOSK_CONFIDENCE: str = "0.0"
        self.DEFAULT_LLM_DICTATION_STOP_WORDS: str = (
            "stop, wait, hold on, cancel, no, nope, deny, don't"
        )
        self.DEFAULT_LLM_DICTATION_POLITE_WORDS: str = "please, thanks, thank, you"
        self.DEFAULT_LLM_DICTATION_TRAILING_WORDS: str = (
            "a, an, the, my, your, our, this, that, these, those, and, but, or, so, because, if, then, than, when, while, which, who, where, whether, although, unless, to, of, for, with, in, on, at, from, into, about, by, as, is, are, was, be, can, could, should, would, will, um, uh, er, erm, hmm, like, also, maybe, let's"
        )
        self.DEFAULT_LLM_DICTATION_BLOCK_DURATION: str = "0.1"
        self.DEFAULT_LLM_DICTATION_TURN_END_TIMEOUT: str = "5.0"
        self.DEFAULT_LLM_DICTATION_TRANSCRIBE_PROMPT: str = (
            "Transcribe this audio to text. Return only the transcription."
        )
        super().__init__()

    LLM_DICTATION_MODE = EnvField(
        str,
        default_factory=lambda c: get_voice_default(c, "LLM_DICTATION_MODE"),
        doc=(
            "Mode a session starts in: 'ptt' (push-to-talk via the dictation "
            "command) or 'hands_free' (always listening). Default: ptt, or as "
            "{ENV_PREFIX}_LLM_VOICE sets it."
        ),
    )

    LLM_DICTATION_COMMANDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated command aliases that start and stop a push-to-talk "
            "recording."
        ),
    )

    LLM_DICTATION_HANDS_FREE_COMMANDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc="Comma-separated command aliases that switch hands-free on and off.",
    )

    LLM_DICTATION_BACKEND = EnvField(
        str,
        doc=(
            "Speech-to-text backend. One of:\n"
            "- 'vosk' (default): offline, cross-platform.\n"
            "- 'openai': OpenAI transcription API.\n"
            "- 'google': Google Gemini.\n"
            "- 'multimodal': uses {ENV_PREFIX}_LLM_MULTIMODAL_MODEL "
            "(slower / more expensive)."
        ),
    )

    LLM_DICTATION_WAKE_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated wake words for hands-free mode; each may be "
            "several words. Only utterances starting with one count, and it is "
            "stripped. Said alone, it accepts the next utterance spoken within "
            "{ENV_PREFIX}_LLM_DICTATION_WAKE_WINDOW seconds. Empty: every "
            "utterance counts."
        ),
    )

    LLM_DICTATION_THRESHOLD = EnvField(
        float,
        fallback=0.01,
        doc=(
            "RMS microphone level that counts as speech, and the lowest the "
            "bar under speech ever goes. Default: 0.01."
        ),
    )

    LLM_DICTATION_NOISE_MARGIN = EnvField(
        float,
        fallback=2.0,
        doc=(
            "How many times louder than the room's own background speech must "
            "be to be heard as speech at all, so a conversation going on "
            "around the microphone does not open a turn. It follows the room: "
            "in a quiet one it changes nothing, and in one with no quiet "
            "moment it lifts the bar over the noise itself. 0 counts the room "
            "not at all, leaving {ENV_PREFIX}_LLM_DICTATION_THRESHOLD alone. "
            "Default: 2."
        ),
    )

    LLM_DICTATION_SILENCE = EnvField(
        float,
        fallback=1.0,
        doc=(
            "Seconds of silence that end an utterance; at least one block "
            "({ENV_PREFIX}_LLM_DICTATION_BLOCK_DURATION). Default: 1.0."
        ),
    )

    LLM_DICTATION_MIN_SILENCE = EnvField(
        float,
        fallback=0.5,
        doc=(
            "With a backend that transcribes while you speak (vosk), seconds "
            "of silence that end an utterance whose words so far sound "
            "finished, rather than trailing off on 'and' or 'the'; 0 always "
            "waits {ENV_PREFIX}_LLM_DICTATION_SILENCE. Default: 0.5."
        ),
    )

    LLM_DICTATION_WAKE_WINDOW = EnvField(
        float,
        fallback=8.0,
        doc=(
            "Seconds a wake word said alone keeps listening for the command "
            "that follows it. Default: 8."
        ),
    )

    LLM_DICTATION_MIN_SPEECH = EnvField(
        float,
        fallback=0.25,
        doc=(
            "Shortest speech kept, in seconds; shorter bursts are coughs and "
            "clicks. Default: 0.25."
        ),
    )

    LLM_DICTATION_MIN_WORDS = EnvField(
        int,
        fallback=1,
        doc=(
            "Fewest words a hands-free utterance needs to reach the model when "
            "it is not interrupting zrb; over zrb or a running turn, "
            "{ENV_PREFIX}_LLM_DICTATION_BARGE_IN_MIN_WORDS applies instead. "
            "Raise it in a public place, where a stranger's single word would "
            "otherwise open a turn. A stop word, or an answer to the prompt "
            "being asked, always counts. Default: 1."
        ),
    )

    LLM_DICTATION_MAX_UTTERANCE = EnvField(
        float,
        fallback=30.0,
        doc=(
            "Longest utterance in seconds; longer speech is cut there. 0 means "
            "no limit. Default: 30."
        ),
    )

    LLM_DICTATION_MAX_BACKLOG = EnvField(
        float,
        fallback=30.0,
        doc=(
            "Seconds of hands-free audio kept while an utterance is being "
            "transcribed; older audio is dropped. 0 means no limit. Default: 30."
        ),
    )

    LLM_DICTATION_PRE_ROLL = EnvField(
        float,
        fallback=0.3,
        doc=(
            "Seconds of audio kept from before speech is detected, so the "
            "first word is not clipped. Default: 0.3."
        ),
    )

    LLM_DICTATION_ECHO_COOLDOWN = EnvField(
        float,
        fallback=0.4,
        doc=(
            "Seconds the microphone stays deaf after zrb stops speaking, "
            "since room echo outlives playback; with barge-in on, it hears "
            "them against the bar over zrb's voice instead. Default: 0.4."
        ),
    )

    LLM_DICTATION_BARGE_IN_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        default_factory=lambda c: get_voice_default(
            c, "LLM_DICTATION_BARGE_IN_ENABLED"
        ),
        doc=(
            "'on' lets hands-free hear you while zrb speaks, so you can talk "
            "over it: zrb pauses at once, and stops if what you said is "
            "words meant for it. On speakers the microphone hears zrb too, "
            "so speech over it must be "
            "{ENV_PREFIX}_LLM_DICTATION_BARGE_IN_MARGIN times louder than "
            "zrb's voice reaches the microphone, and at least "
            "{ENV_PREFIX}_LLM_DICTATION_BARGE_IN_MIN_WORDS words. 'off' "
            "keeps the microphone deaf while zrb speaks: zrb and you take "
            "turns. Default: off, or as {ENV_PREFIX}_LLM_VOICE sets it."
        ),
    )

    LLM_DICTATION_BARGE_IN_MARGIN = EnvField(
        float,
        fallback=3.0,
        doc=(
            "With barge-in on, how many times louder than zrb's own voice, "
            "as the microphone hears it, speech over zrb must be to count "
            "(3 is about 10 dB). It follows the volume and the room; on "
            "headphones zrb is not heard, and the usual "
            "{ENV_PREFIX}_LLM_DICTATION_THRESHOLD applies. Default: 3."
        ),
    )

    LLM_DICTATION_BARGE_IN_MIN_WORDS = EnvField(
        int,
        fallback=2,
        doc=(
            "With barge-in on, the fewest words said over zrb, or while a "
            "turn runs, that reach it: fewer are taken for zrb's own voice "
            "or noise, and zrb carries on. A stop word, or an answer to the "
            "prompt being asked, always counts. Default: 2."
        ),
    )

    LLM_DICTATION_BARGE_IN_MIN_SPEECH = EnvField(
        float,
        fallback=0.3,
        doc=(
            "Seconds of speech over zrb's voice that pause it, so a click "
            "does not; it then stops if what was said has words. Shorter "
            "words over zrb (a crisp 'stop') do not pause it but still stop "
            "it once transcribed. Default: 0.3."
        ),
    )

    LLM_DICTATION_BARGE_IN_ACTION = EnvField(
        str,
        doc=(
            "What talking over a running turn does with what you said. One "
            "of:\n"
            "- 'steer' (default): the turn goes on and takes it into account.\n"
            "- 'cancel': the turn stops and what you said starts a new one.\n"
            "A stop word said alone ({ENV_PREFIX}_LLM_DICTATION_STOP_WORDS) cancels the turn either way."
        ),
    )

    LLM_DICTATION_SELF_ECHO_MATCH = EnvField(
        float,
        fallback=0.8,
        doc=(
            "Share (0-1) of what hands-free heard over zrb's voice that must be "
            "words zrb was saying then for it to be taken as zrb's own voice "
            "coming back through the microphone, and dropped instead of "
            "becoming a turn. 0 turns this off. Default: 0.8."
        ),
    )

    LLM_DICTATION_SELF_ECHO_TAIL = EnvField(
        float,
        fallback=1.0,
        doc=(
            "Seconds after zrb says a sentence that hearing its words still "
            "counts as its echo ({ENV_PREFIX}_LLM_DICTATION_SELF_ECHO_MATCH): "
            "the room, and audio still on its way out of the speakers. "
            "Default: 1."
        ),
    )

    LLM_DICTATION_APPROVE_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated phrases that approve a tool approval when a "
            "hands-free answer is made only of them and polite words "
            "('yes please'). Anything else said then denies it, with what was "
            "said as the reason."
        ),
    )

    LLM_DICTATION_DENY_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated phrases that deny a tool approval when a "
            "hands-free answer is made only of them and polite words "
            "('no thanks'). An answer that does not approve denies too, with "
            "what was said as the reason."
        ),
    )

    LLM_DICTATION_STOP_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated phrases that, said alone (polite words "
            "allowed) over zrb or while a turn runs with "
            "{ENV_PREFIX}_LLM_DICTATION_BARGE_IN_ENABLED=on, stop "
            "zrb speaking and cancel the turn instead of reaching the "
            "model. Default: stop, wait, hold on, cancel, no, nope, deny, don't."
        ),
    )

    LLM_DICTATION_POLITE_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated words a yes, a no or a stop word may carry "
            "without changing it, as in 'yes please' or 'no thanks'. "
            "Default: please, thanks, thank, you."
        ),
    )

    LLM_DICTATION_TRAILING_WORDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated words a sentence rarely ends on: with "
            "{ENV_PREFIX}_LLM_DICTATION_MIN_SILENCE, an utterance whose "
            "words so far end on one is waited on for the full "
            "{ENV_PREFIX}_LLM_DICTATION_SILENCE, since the speaker is "
            "thinking, not done. Set it for your language. Default: English "
            "articles, conjunctions, prepositions and fillers (a, the, and, "
            "to, um, ...)."
        ),
    )

    LLM_DICTATION_BLOCK_DURATION = EnvField(
        float,
        fallback=0.1,
        doc=(
            "Seconds of audio in each microphone block: the step every "
            "other listening duration is counted in, and how often speech "
            "is checked. Default: 0.1."
        ),
    )

    LLM_DICTATION_TURN_END_TIMEOUT = EnvField(
        float,
        fallback=5.0,
        doc=(
            "With {ENV_PREFIX}_LLM_DICTATION_BARGE_IN_ACTION=cancel, "
            "seconds to wait for a cancelled turn to end before what was "
            "said starts the next one. Default: 5."
        ),
    )

    LLM_DICTATION_TRANSCRIBE_PROMPT = EnvField(
        str,
        doc=(
            "Instruction sent with the audio to the 'google' and "
            "'multimodal' backends. Default: Transcribe this audio to text. "
            "Return only the transcription."
        ),
    )

    LLM_DICTATION_OPENAI_MODEL = EnvField(
        str,
        doc=(
            "Model for the 'openai' backend, e.g. gpt-4o-transcribe. "
            "Default: whisper-1."
        ),
    )

    LLM_DICTATION_OPENAI_BASE_URL = EnvField(
        str,
        doc=(
            "API base URL for the 'openai' backend, for an OpenAI-compatible "
            "transcription server. Empty uses OpenAI's."
        ),
    )

    LLM_DICTATION_GOOGLE_MODEL = EnvField(
        str,
        doc="Model for the 'google' backend. Default: gemini-2.5-flash.",
    )

    LLM_DICTATION_VOSK_MODEL_NAME = EnvField(
        str,
        doc=(
            "Vosk model directory name (without .zip) for the 'vosk' backend. "
            "Default: vosk-model-small-en-us-0.15."
        ),
    )

    LLM_DICTATION_VOSK_MODEL_URL = EnvField(
        str,
        doc=(
            "Base URL the Vosk model zip is downloaded from: <url>/<model_name>.zip, "
            "extracted to ~/.cache/vosk/. "
            "Default: https://alphacephei.com/vosk/models."
        ),
    )

    LLM_DICTATION_VOSK_DOWNLOAD_TIMEOUT = EnvField(
        float,
        fallback=120.0,
        doc=(
            "Seconds to wait for the Vosk model server to answer; 0 means no "
            "limit. Default: 120."
        ),
    )

    LLM_DICTATION_VOSK_MAX_DOWNLOAD_MB = EnvField(
        float,
        fallback=4096.0,
        doc=(
            "Megabytes of zip to accept for a Vosk model; 0 means no limit. "
            "The largest published model is about 1.8 GB. Default: 4096."
        ),
    )

    LLM_DICTATION_VOSK_MAX_UNCOMPRESSED_MB = EnvField(
        float,
        fallback=8192.0,
        doc=(
            "Megabytes a Vosk model may take once extracted, summed over every "
            "file in the archive; 0 means no limit. Bounds a decompression "
            "bomb. Default: 8192."
        ),
    )

    LLM_DICTATION_VOSK_MAX_FILE_MB = EnvField(
        float,
        fallback=4096.0,
        doc=(
            "Megabytes for any single file in a Vosk model archive; 0 means no "
            "limit. A model's acoustic model is one large file. Default: 4096."
        ),
    )

    LLM_DICTATION_VOSK_MAX_FILES = EnvField(
        float,
        fallback=10000.0,
        doc=(
            "Files a Vosk model archive may contain; 0 means no limit. Bounds "
            "the many-tiny-files shape of a decompression bomb. Default: 10000."
        ),
    )

    LLM_DICTATION_VOSK_CONFIDENCE = EnvField(
        float,
        fallback=0.0,
        doc=(
            "With the 'vosk' backend, the lowest average word confidence (0-1) "
            "a hands-free transcript may have and still reach the model; vosk "
            "scores the words it makes out of noise low. Push-to-talk keeps "
            "every word. 0 uses no confidence floor. Default: 0."
        ),
    )
