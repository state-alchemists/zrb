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
        self.DEFAULT_LLM_DICTATION_SILENCE: str = "1.0"
        self.DEFAULT_LLM_DICTATION_MIN_SILENCE: str = "0.5"
        self.DEFAULT_LLM_DICTATION_WAKE_WINDOW: str = "8.0"
        self.DEFAULT_LLM_DICTATION_MIN_SPEECH: str = "0.25"
        self.DEFAULT_LLM_DICTATION_MAX_UTTERANCE: str = "30.0"
        self.DEFAULT_LLM_DICTATION_MAX_BACKLOG: str = "30.0"
        self.DEFAULT_LLM_DICTATION_PRE_ROLL: str = "0.3"
        self.DEFAULT_LLM_DICTATION_ECHO_COOLDOWN: str = "0.4"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_ENABLED: str = "off"
        self.DEFAULT_LLM_DICTATION_ECHO_CANCELLER: str = "numpy"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_MIN_SPEECH: str = "0.3"
        self.DEFAULT_LLM_DICTATION_BARGE_IN_ACTION: str = "steer"
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
        self.DEFAULT_LLM_DICTATION_STOP_WORDS: str = (
            "stop, cancel, no, nope, deny, don't"
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
        self.DEFAULT_LLM_DICTATION_ECHO_LEAD: str = "0.04"
        self.DEFAULT_LLM_DICTATION_ECHO_MIN_DELAY: str = "-0.5"
        self.DEFAULT_LLM_DICTATION_ECHO_MAX_DELAY: str = "1.0"
        self.DEFAULT_LLM_DICTATION_ECHO_DELAY_WINDOW: str = "2.0"
        self.DEFAULT_LLM_DICTATION_ECHO_DELAY_INTERVAL: str = "1.0"
        self.DEFAULT_LLM_DICTATION_ECHO_MIN_PEAK: str = "0.05"
        self.DEFAULT_LLM_DICTATION_ECHO_MIN_PEAK_RATIO: str = "6.0"
        self.DEFAULT_LLM_DICTATION_ECHO_DELAY_AGREEMENT: str = "0.003"
        self.DEFAULT_LLM_DICTATION_ECHO_RELOCK: str = "0.025"
        self.DEFAULT_LLM_DICTATION_ECHO_MIN_REFERENCE_LEVEL: str = "0.01"
        self.DEFAULT_LLM_DICTATION_ECHO_READY_BLOCKS: str = "20"
        self.DEFAULT_LLM_DICTATION_ECHO_MAX_LOUD_LEFTOVERS: str = "1"
        self.DEFAULT_LLM_DICTATION_ECHO_PLAYING_LEVEL: str = "0.005"
        self.DEFAULT_LLM_DICTATION_ECHO_FRAME: str = "0.01"
        self.DEFAULT_LLM_DICTATION_ECHO_FILTER_LENGTH: str = "0.32"
        self.DEFAULT_LLM_DICTATION_ECHO_STEP: str = "0.5"
        self.DEFAULT_LLM_DICTATION_ECHO_SUPPRESS_RESIDUAL: str = "on"
        self.DEFAULT_LLM_DICTATION_ECHO_CONVERGE_AFTER: str = "2.0"
        super().__init__()

    LLM_DICTATION_MODE = EnvField(
        str,
        doc=(
            "Mode a session starts in: 'ptt' (push-to-talk via the dictation "
            "command) or 'hands_free' (always listening). Default: ptt."
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
        doc="RMS microphone level that counts as speech. Default: 0.01.",
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
            "since room echo outlives playback. Default: 0.4."
        ),
    )

    LLM_DICTATION_BARGE_IN_ENABLED = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "'on' lets hands-free hear you while zrb speaks, so you can talk "
            "over it: zrb pauses at once, and stops if what you said has "
            "words. zrb's own voice is removed from the microphone by "
            "{ENV_PREFIX}_LLM_DICTATION_ECHO_CANCELLER, which needs zrb to play "
            "its speech itself ({ENV_PREFIX}_LLM_SPEECH_PLAYER=auto) and a few "
            "seconds of zrb speaking to learn the room; until then the "
            "microphone stays deaf while zrb speaks. Default: off."
        ),
    )

    LLM_DICTATION_ECHO_CANCELLER = EnvField(
        str,
        doc=(
            "How zrb's own voice is removed from the microphone for barge-in. "
            "One of:\n"
            "- 'numpy' (default): an adaptive echo canceller in NumPy, "
            "working from the audio zrb plays; laptop speakers work.\n"
            "- 'none': trust the microphone: headphones, or the system "
            "already cancels echo (PipeWire/PulseAudio echo-cancel)."
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
            "model. Default: stop, cancel, no, nope, deny, don't."
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

    LLM_DICTATION_ECHO_LEAD = EnvField(
        float,
        fallback=0.04,
        doc=(
            "Echo cancellation: seconds the reference (what zrb played) is "
            "read ahead of the measured echo delay, so it never arrives "
            "after its echo. Default: 0.04."
        ),
    )

    LLM_DICTATION_ECHO_MIN_DELAY = EnvField(
        float,
        fallback=-0.5,
        doc=(
            "Echo cancellation: shortest echo delay searched, in seconds; "
            "negative because the audio driver's reported latencies can be "
            "off. Default: -0.5."
        ),
    )

    LLM_DICTATION_ECHO_MAX_DELAY = EnvField(
        float,
        fallback=1.0,
        doc=(
            "Echo cancellation: longest echo delay searched, in seconds "
            "(Bluetooth speakers can need more). Default: 1."
        ),
    )

    LLM_DICTATION_ECHO_DELAY_WINDOW = EnvField(
        float,
        fallback=2.0,
        doc=(
            "Echo cancellation: seconds of microphone audio each delay "
            "estimate correlates with what zrb played. Default: 2."
        ),
    )

    LLM_DICTATION_ECHO_DELAY_INTERVAL = EnvField(
        float,
        fallback=1.0,
        doc=("Echo cancellation: seconds between delay estimates. Default: " "1."),
    )

    LLM_DICTATION_ECHO_MIN_PEAK = EnvField(
        float,
        fallback=0.05,
        doc=(
            "Echo cancellation: weakest correlation peak taken as the echo "
            "rather than chance. Default: 0.05."
        ),
    )

    LLM_DICTATION_ECHO_MIN_PEAK_RATIO = EnvField(
        float,
        fallback=6.0,
        doc=(
            "Echo cancellation: how many times above the typical "
            "correlation the peak must stand. Default: 6."
        ),
    )

    LLM_DICTATION_ECHO_DELAY_AGREEMENT = EnvField(
        float,
        fallback=0.003,
        doc=(
            "Echo cancellation: seconds within which two delay estimates in "
            "a row agree, which is what locks the delay. Default: 0.003."
        ),
    )

    LLM_DICTATION_ECHO_RELOCK = EnvField(
        float,
        fallback=0.025,
        doc=(
            "Echo cancellation: once locked, a delay that moves more than "
            "this many seconds (another output device) re-locks and "
            "restarts the canceller; less is drift the canceller follows. "
            "Default: 0.025."
        ),
    )

    LLM_DICTATION_ECHO_MIN_REFERENCE_LEVEL = EnvField(
        float,
        fallback=0.01,
        doc=(
            "Echo cancellation: RMS level of what zrb played below which no "
            "delay is estimated (too quiet to correlate). Default: 0.01."
        ),
    )

    LLM_DICTATION_ECHO_READY_BLOCKS = EnvField(
        int,
        fallback=20,
        doc=(
            "Echo cancellation: recent microphone blocks of zrb speaking "
            "judged to decide whether cancellation is ready. Default: 20."
        ),
    )

    LLM_DICTATION_ECHO_MAX_LOUD_LEFTOVERS = EnvField(
        int,
        fallback=1,
        doc=(
            "Echo cancellation: of those blocks, how many may still be at "
            "or over {ENV_PREFIX}_LLM_DICTATION_THRESHOLD after cancelling "
            "for it to count as ready, so the microphone hears you over "
            "zrb. Default: 1."
        ),
    )

    LLM_DICTATION_ECHO_PLAYING_LEVEL = EnvField(
        float,
        fallback=0.005,
        doc=(
            "Echo cancellation: RMS level of what zrb played above which a "
            "block counts as zrb speaking. Default: 0.005."
        ),
    )

    LLM_DICTATION_ECHO_FRAME = EnvField(
        float,
        fallback=0.01,
        doc=(
            "The 'numpy' echo canceller: seconds of audio per filter step. "
            "Default: 0.01."
        ),
    )

    LLM_DICTATION_ECHO_FILTER_LENGTH = EnvField(
        float,
        fallback=0.32,
        doc=(
            "The 'numpy' echo canceller: seconds of echo path its filter "
            "covers, the lead plus the room's tail. Default: 0.32."
        ),
    )

    LLM_DICTATION_ECHO_STEP = EnvField(
        float,
        fallback=0.5,
        doc=(
            "The 'numpy' echo canceller: adaptation step, 0 to 1; larger "
            "learns the room faster but settles less. Default: 0.5."
        ),
    )

    LLM_DICTATION_ECHO_SUPPRESS_RESIDUAL = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "The 'numpy' echo canceller: damp what the filter leaves of "
            "zrb's voice. Default: on."
        ),
    )

    LLM_DICTATION_ECHO_CONVERGE_AFTER = EnvField(
        float,
        fallback=2.0,
        doc=(
            "The 'numpy' echo canceller: seconds of zrb speaking it adapts "
            "over before it may count as converged. Default: 2."
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
