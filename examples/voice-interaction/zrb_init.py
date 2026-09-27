"""
Voice interaction for zrb: it reads replies aloud and takes spoken input.
zrb loads this file for sessions started here or in a subfolder.

    zrb chat                   # replies are spoken; /voice or /handsfree to talk
    zrb voice say "hello"      # hear the current speech backend
    zrb voice mic-test         # check the microphone level

Speaking: Python hooks on Stop, PermissionRequest and Notification put text on
a queue that one background thread plays in order, so a turn never waits for
audio. Listening: `/voice` push-to-talk, or `/handsfree`, which drops audio
captured while the agent speaks so it does not answer its own voice.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import fcntl
import io
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import wave
from collections import deque
from pathlib import Path

from zrb import CFG, Group, StrInput, cli, make_task
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.custom_command import ActionCommand
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.voice import VoiceEngine

# Speech backends

DEFAULT_MAX_CHARS = 400
DEFAULT_RATE = 165
DEFAULT_LOCK_TIMEOUT = 30.0
DEFAULT_CLOUD_TIMEOUT = 15.0

DEFAULT_VOICES = {
    "say": "",  # the system default voice
    "espeak-ng": "en-us+m3",
    "openai": "alloy",
    "gemini": "Sulafat",
}
DEFAULT_OPENAI_MODEL = "gpt-4o-mini-tts"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-tts"

LOCK_PATH = Path(
    os.getenv(
        "ZRB_VOICE_LOCK",
        str(Path(tempfile.gettempdir()) / "zrb-voice-speaker.lock"),
    )
)
SPEAK_LOG = Path(
    os.getenv(
        "ZRB_VOICE_LOG",
        str(Path(tempfile.gettempdir()) / "zrb-voice-speaker.log"),
    )
)


def log(message: str) -> None:
    """Append to the side log; printing would garble the chat UI.

    The file is created 0600 and never followed through a symlink, and a log
    owned by another user is left alone.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(SPEAK_LOG), flags, 0o600)
    except OSError:
        return
    try:
        if os.fstat(fd).st_uid == os.getuid():
            os.write(fd, f"{time.strftime('%H:%M:%S')} {message}\n".encode())
    except OSError:
        pass
    finally:
        os.close(fd)


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
# A table's separator row, with or without outer pipes: `--- | :---:`.
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL_RE = re.compile(r"https?://\S+")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_QUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_RULE_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~)")
# espeak-ng reads some emoji aloud ("smiling face").
_NON_SPEECH_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]"
)


def clean_for_speech(text: str) -> str:
    """Reduce markdown to speakable prose.

    Fences go before inline code, and links before bare URLs, or the triple
    backticks and link labels are mangled.
    """
    text = _FENCE_RE.sub(" ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub(" ", text)
    text = _strip_tables(text)
    text = _TABLE_ROW_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _RULE_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    text = _QUOTE_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = _EMPHASIS_RE.sub("", text)
    text = _NON_SPEECH_RE.sub("", text)
    text = text.replace("→", " to ").replace("—", ", ").replace("–", ", ")
    # Paragraph breaks become sentence pauses.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", ".\n", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()


def _strip_tables(text: str) -> str:
    """Drop every table: its header, separator and pipe-separated rows."""
    lines = text.split("\n")
    kept: list[str] = []
    in_table = False
    for line in lines:
        if _TABLE_SEPARATOR_RE.match(line):
            if kept and "|" in kept[-1]:
                kept.pop()  # the header row
            in_table = True
            continue
        if in_table and "|" in line:
            continue
        in_table = False
        kept.append(line)
    return "\n".join(kept)


def truncate_for_speech(text: str, max_chars: int) -> str:
    """Cut at the last sentence end before *max_chars*, else hard-cut."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    window = text[:max_chars]
    best = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if best >= max_chars * 0.5:
        return window[: best + 1]
    return window.rstrip() + "..."


class Utterance:
    """The argv that plays the speech, plus a temp file to delete afterwards."""

    def __init__(self, argv: list[str], temp_path: str | None = None):
        self.argv = argv
        self.temp_path = temp_path

    def cleanup(self) -> None:
        if self.temp_path:
            try:
                os.remove(self.temp_path)
            except OSError:
                pass


def resolve_backend_name(name: str) -> str:
    """Map `auto` to the local engine this platform has."""
    if name != "auto":
        return name
    if shutil.which("say"):
        return "say"
    return "espeak-ng"


def prepare(backend: str, text: str, voice: str, rate: int) -> Utterance:
    """Synthesize outside the lock; only playback is serialized."""
    if backend == "say":
        return _prepare_say(text, voice, rate)
    if backend == "espeak-ng":
        return _prepare_espeak(text, voice, rate)
    if backend == "openai":
        return _wav_utterance(_synthesize_openai(text, voice))
    if backend == "gemini":
        return _wav_utterance(_pcm_to_wav(_synthesize_gemini(text, voice)))
    raise ValueError(f"unknown backend {backend!r}")


def _prepare_say(text: str, voice: str, rate: int) -> Utterance:
    _require_binary("say")
    argv = ["say", "-r", str(rate)]
    if voice:
        argv += ["-v", voice]
    return Utterance(argv + ["--", text])


def _prepare_espeak(text: str, voice: str, rate: int) -> Utterance:
    _require_binary("espeak-ng")
    argv = ["espeak-ng", "-s", str(rate)]
    if voice:
        argv += ["-v", voice]
    return Utterance(argv + ["--", text])


def _synthesize_openai(text: str, voice: str) -> bytes:
    """OpenAI /audio/speech. Returns a complete WAV file."""
    base_url = os.getenv("ZRB_VOICE_OPENAI_BASE_URL", "https://api.openai.com/v1")
    body = {
        "model": os.getenv("ZRB_VOICE_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "voice": voice,
        "input": text,
        "response_format": "wav",
    }
    headers = {"Authorization": f"Bearer {_require_env('OPENAI_API_KEY')}"}
    return _post(f"{base_url.rstrip('/')}/audio/speech", body, headers)


def _synthesize_gemini(text: str, voice: str) -> bytes:
    """Gemini TTS via generateContent. Returns raw 24 kHz 16-bit mono PCM."""
    key = os.getenv("GEMINI_API_KEY") or _require_env("GOOGLE_API_KEY")
    model = os.getenv("ZRB_VOICE_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    body = {
        # Without "Say:", Gemini may answer a short line instead of reading it.
        "contents": [{"parts": [{"text": f"Say: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    reply = json.loads(_post(url, body, {"x-goog-api-key": key}))
    part = reply["candidates"][0]["content"]["parts"][0]["inlineData"]
    return base64.b64decode(part["data"])


def _post(url: str, body: dict, headers: dict) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    timeout = float(os.getenv("ZRB_VOICE_CLOUD_TIMEOUT", str(DEFAULT_CLOUD_TIMEOUT)))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _wav_utterance(wav_bytes: bytes) -> Utterance:
    player = _wav_player()
    fd, path = tempfile.mkstemp(prefix="zrb-voice-", suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(wav_bytes)
    except BaseException:
        os.unlink(path)
        raise
    return Utterance(player + [path], temp_path=path)


def _wav_player() -> list[str]:
    players = (
        ["afplay"],
        ["paplay"],
        ["aplay", "-q"],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    )
    for argv in players:
        if shutil.which(argv[0]):
            return argv
    raise RuntimeError("no WAV player on PATH (afplay, paplay, aplay, ffplay)")


def _require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not on PATH")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def speak(text: str) -> None:
    """Speak *text*, falling back to the local engine if the backend fails."""
    text = text.strip()
    if not text:
        log("skip: empty after cleanup")
        return

    max_chars = int(os.getenv("ZRB_VOICE_MAX_CHARS", str(DEFAULT_MAX_CHARS)))
    spoken = truncate_for_speech(clean_for_speech(text), max_chars)
    if not spoken:
        log("skip: nothing left after truncation")
        return

    requested = resolve_backend_name(os.getenv("ZRB_VOICE_BACKEND", "auto"))
    utterance = _prepare_with_fallback(requested, spoken)
    if utterance is None:
        return
    try:
        run_player(utterance.argv, spoken)
    finally:
        utterance.cleanup()


def _prepare_with_fallback(requested: str, spoken: str) -> Utterance | None:
    rate = int(os.getenv("ZRB_VOICE_RATE", str(DEFAULT_RATE)))
    candidates = [requested]
    local = resolve_backend_name("auto")
    if local != requested:
        candidates.append(local)
    for index, backend in enumerate(candidates):
        # ZRB_VOICE_NAME is in the requested backend's vocabulary, not the fallback's.
        voice = DEFAULT_VOICES.get(backend, "")
        if index == 0:
            voice = os.getenv("ZRB_VOICE_NAME", voice)
        try:
            utterance = prepare(backend, spoken, voice, rate)
            log(f"speak[{backend}]: {len(spoken)} chars")
            return utterance
        except Exception as exc:
            log(f"error: backend {backend} failed: {type(exc).__name__}: {exc}")
    return None


def is_speaking() -> bool:
    """True while any process holds the audio lock, i.e. is playing speech."""
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def run_player(argv: list[str], label: str = "") -> None:
    """Run *argv* while holding the cross-process audio lock."""
    lock_timeout = float(os.getenv("ZRB_VOICE_LOCK_TIMEOUT", str(DEFAULT_LOCK_TIMEOUT)))
    deadline = time.monotonic() + lock_timeout

    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    # Another session holds the device; drop, don't fall behind.
                    log(
                        f"skip: lock busy >{lock_timeout}s, dropping {len(label)} chars"
                    )
                    return
                time.sleep(0.1)
        subprocess.run(
            argv,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except Exception as exc:
        log(f"error: player {argv[0]} failed: {type(exc).__name__}: {exc}")
    finally:
        try:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# LLM summary (ZRB_VOICE_SUMMARY=llm): an extra model call per turn, so off by default.

SUMMARY_PROMPT = (
    "Rewrite the following assistant response as something that sounds natural "
    "when read aloud by a text-to-speech engine. Keep only what a listener "
    "needs: the conclusion and any action they must take. Drop code, file "
    "paths, tables, and tool mechanics. At most 2 sentences, at most 60 words. "
    "Reply with the spoken text only, no preamble."
)


def summarize_with_llm(text: str) -> str:
    """Return a spoken-form summary of *text*, or '' to fall back to cleanup."""
    key = os.getenv("ZRB_VOICE_SUMMARY_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("ZRB_VOICE_SUMMARY_API_KEY / OPENAI_API_KEY is not set")
    base_url = os.getenv("ZRB_VOICE_SUMMARY_BASE_URL", "https://api.openai.com/v1")
    body = {
        "model": os.getenv("ZRB_VOICE_SUMMARY_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": text[:8000]},
        ],
        "temperature": 0.0,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    timeout = float(os.getenv("ZRB_VOICE_SUMMARY_TIMEOUT", "20"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        reply = json.loads(response.read())
    return (reply["choices"][0]["message"]["content"] or "").strip()


SAMPLE_RATE = 16000  # what VoiceEngine's transcribers expect
BLOCK_SECONDS = 0.1
PRE_ROLL_BLOCKS = 3  # keep 0.3 s before speech starts, or the first word clips
MIN_SPEECH_SECONDS = 0.4  # shorter bursts are coughs and clicks
MAX_UTTERANCE_SECONDS = 30.0
POST_SPEECH_COOLDOWN = 0.4  # room echo outlives the player process
WAKE_WINDOW_SECONDS = 8.0  # how long the wake word alone keeps listening
_WORD_RE = re.compile(r"[\w']+")


# Speaking


SPEECH_DRAIN_SECONDS = 30.0  # at exit, how long queued speech may still play

_speech: "queue.Queue[tuple[str, bool] | None]" = queue.Queue()
_speech_worker: list[threading.Thread] = []


def say_later(text: str, summarize: bool = False) -> None:
    """Queue *text* for the speech thread, starting it on first use."""
    if not _speech_worker:
        worker = threading.Thread(target=_play_speech, name="voice", daemon=True)
        worker.start()
        _speech_worker.append(worker)
        atexit.register(_finish_speech, worker)
    _speech.put((text, summarize))


def _finish_speech(worker: threading.Thread) -> None:
    """Let queued speech play out: `zrb chat --message` exits right after it."""
    _speech.put(None)
    worker.join(SPEECH_DRAIN_SECONDS)


def _play_speech() -> None:
    while (item := _speech.get()) is not None:
        text, summarize = item
        try:
            speak(_summarize(text) if summarize else text)
        except Exception as e:
            log(f"speak failed: {type(e).__name__}: {e}")


def _summarize(text: str) -> str:
    if os.getenv("ZRB_VOICE_SUMMARY", "clean").strip().lower() != "llm":
        return text
    try:
        return summarize_with_llm(text) or text
    except Exception as e:
        log(f"llm summary failed, speaking the cleaned text: {e}")
        return text


async def on_stop(context: HookContext) -> HookResult:
    """Speak the reply, but not a sub-agent's: only the main turn is for you."""
    event_data = context.event_data if isinstance(context.event_data, dict) else {}
    if not event_data.get("nested_run") and context.last_assistant_message:
        say_later(context.last_assistant_message, summarize=True)
    return HookResult(success=True)


async def on_permission_request(context: HookContext) -> HookResult:
    say_later(describe_tool_call(context.tool_name, context.tool_input))
    return HookResult(success=True)


async def on_notification(context: HookContext) -> HookResult:
    # Only the notifications the user has to act on.
    if context.notification_type in ("elicitation_dialog", "permission_prompt"):
        say_later(context.message or "A question is waiting for your answer.")
    return HookResult(success=True)


def describe_tool_call(tool: str | None, args: dict | None) -> str:
    """A template, not an LLM call: the user is waiting on this prompt."""
    friendly = {
        "Write": "write a file",
        "Edit": "edit a file",
        "NotebookEdit": "edit a notebook",
        "Shell": "run a shell command",
        "Bash": "run a shell command",
        "DelegateToAgent": "delegate work to a sub-agent",
        "DelegateToAgentBackground": "delegate background work to a sub-agent",
    }.get(tool or "", f"use the {tool} tool" if tool else "run a tool")
    target = ""
    for key in ("path", "file_path", "command", "notebook_path"):
        value = (args or {}).get(key)
        if isinstance(value, str) and value.strip():
            target = " " + value.strip()[:80]
            break
    return f"I need to {friendly}{target}. I need your approval."


def register_speaking_hooks(hook_manager: HookManager) -> None:
    hook_manager.add_hook(on_stop, events=[HookEvent.STOP])
    hook_manager.add_hook(on_permission_request, events=[HookEvent.PERMISSION_REQUEST])
    hook_manager.add_hook(on_notification, events=[HookEvent.NOTIFICATION])


# Listening


# Push-to-talk, unless the user set it either way.
os.environ.setdefault(f"{CFG.ENV_PREFIX}_LLM_VOICE_ENABLED", "true")

_hands_free = {
    "on": os.getenv("ZRB_VOICE_HANDS_FREE", "").strip().lower()
    in ("1", "true", "yes", "on")
}


def toggle_hands_free(kwargs: dict[str, str]) -> str:
    _hands_free["on"] = not _hands_free["on"]
    return f"🎤 Hands-free {'on' if _hands_free['on'] else 'off'}"


async def hands_free():
    """Yield one user turn per spoken utterance."""
    engine = VoiceEngine()
    wake_words = parse_wake_words(os.getenv("ZRB_VOICE_WAKE_WORD", ""))
    debug = os.getenv("ZRB_VOICE_DEBUG", "").strip().lower() in ("1", "true", "yes")
    armed_until = 0.0
    async for audio, started_at, ended_at in _utterances():
        try:
            text = (await engine.transcribe(audio)).strip()
            log(f"hands-free: heard {text!r}" if debug else "hands-free: transcribed")
        except Exception as e:
            # A background trigger has no UI to show this in, so say it.
            log(f"hands-free: transcription failed: {e}")
            await asyncio.to_thread(speak, "Sorry, transcription failed.")
            continue
        command = strip_wake_word(text, wake_words)
        # Compared against when this utterance was spoken, not when its
        # transcription finished: transcription alone can take seconds.
        if command is None and started_at < armed_until:
            command = text
        if command is None:
            log("hands-free: dropped an utterance without the wake word")
        elif not command:
            # The wake word alone: people pause after it, so the command
            # arrives as the next utterance.
            armed_until = ended_at + WAKE_WINDOW_SECONDS
        else:
            armed_until = 0.0
            yield command


def parse_wake_words(value: str) -> list[list[str]]:
    """Split "hi, hai, hey jarvis" into alternatives, each a list of words."""
    alternatives = (_WORD_RE.findall(part.lower()) for part in value.split(","))
    return [words for words in alternatives if words]


def strip_wake_word(text: str, wake_words: list[list[str]]) -> str | None:
    """Return *text* after a wake word, or None if it starts with none of them.

    Compared word by word, so "Hey, Jarvis." matches "hey jarvis".
    """
    if not wake_words:
        return text
    words = list(_WORD_RE.finditer(text))
    heard = [w.group().lower() for w in words]
    for wanted in wake_words:
        if heard[: len(wanted)] == wanted:
            return text[words[len(wanted) - 1].end() :].lstrip(" ,.!?;:，。")
    return None


async def _utterances():
    """Cut the microphone stream into utterances by energy and silence."""
    threshold = float(os.getenv("ZRB_VOICE_HANDS_FREE_THRESHOLD", "0.01"))
    max_silence = float(os.getenv("ZRB_VOICE_HANDS_FREE_SILENCE", "1.0"))
    while True:
        while not _hands_free["on"]:
            await asyncio.sleep(0.2)
        # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
        import numpy as np
        import sounddevice as sd

        async for utterance in _listen(np, sd, threshold, max_silence):
            yield utterance


async def _listen(np, sd, threshold: float, max_silence: float):
    """Yield (audio, started_at, ended_at) until hands-free is switched off.

    The times are `time.monotonic()` at capture. The mic closes on switch-off.
    """
    loop = asyncio.get_running_loop()
    blocks: asyncio.Queue = asyncio.Queue()

    def on_audio(indata, frames, time_info, status):
        # Sample the lock at capture: blocks queue up during transcription,
        # so checking at processing time would let playback audio through.
        captured = (indata.copy(), is_speaking(), time.monotonic())
        loop.call_soon_threadsafe(blocks.put_nowait, captured)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=int(SAMPLE_RATE * BLOCK_SECONDS),
        callback=on_audio,
    )
    pre_roll: deque = deque(maxlen=PRE_ROLL_BLOCKS)
    speech: list = []
    silent_for = 0.0
    started_at = 0.0
    cooldown_blocks = 0  # in blocks, not wall time, for the same reason
    with stream:
        log(f"hands-free: listening on {sd.query_devices(kind='input')['name']}")
        while _hands_free["on"]:
            block, agent_speaking, captured_at = await blocks.get()
            if agent_speaking:
                speech, silent_for = [], 0.0
                pre_roll.clear()
                cooldown_blocks = round(POST_SPEECH_COOLDOWN / BLOCK_SECONDS)
                continue
            if cooldown_blocks:
                cooldown_blocks -= 1
                continue
            loud = float(np.sqrt(np.mean(block**2))) >= threshold
            if not speech:
                pre_roll.append(block)
                if loud:
                    speech, silent_for = list(pre_roll), 0.0
                    started_at = captured_at
                    pre_roll.clear()
                continue
            speech.append(block)
            silent_for = 0.0 if loud else silent_for + BLOCK_SECONDS
            duration = len(speech) * BLOCK_SECONDS
            if silent_for < max_silence and duration < MAX_UTTERANCE_SECONDS:
                continue
            if duration - silent_for >= MIN_SPEECH_SECONDS:
                audio = np.concatenate(speech, axis=0)
                log(f"hands-free: heard {duration - silent_for:.1f} s of speech")
                pcm = (audio * 32767).astype(np.int16).tobytes()
                yield pcm, started_at, captured_at
            speech, silent_for = [], 0.0


llm_chat.append_hook_factory(register_speaking_hooks)
llm_chat.append_trigger(hands_free)
llm_chat.append_custom_command(
    ActionCommand(
        "/handsfree", toggle_hands_free, description="Toggle hands-free voice input"
    )
)


# CLI

voice_group = cli.add_group(Group("voice", description="🔊 Voice interaction"))


@make_task(
    name="say",
    description="Speak text with the current backend",
    input=StrInput("text", description="Text to speak", default="Hello from zrb"),
    retries=0,
    group=voice_group,
)
def say(ctx) -> None:
    speak(ctx.input.text)


@make_task(
    name="mic-test",
    description="Check the microphone level for hands-free",
    retries=0,
    group=voice_group,
)
def mic_test(ctx) -> str:
    """Record five seconds and report the level against the speech threshold."""
    # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
    import numpy as np
    import sounddevice as sd

    threshold = float(os.getenv("ZRB_VOICE_HANDS_FREE_THRESHOLD", "0.01"))
    ctx.print(f"Input: {sd.query_devices(kind='input')['name']}")
    ctx.print("Talk now for 5 seconds...")
    audio = sd.rec(SAMPLE_RATE * 5, samplerate=SAMPLE_RATE, channels=1)
    sd.wait()
    blocks = audio.reshape(-1, int(SAMPLE_RATE * BLOCK_SECONDS))
    levels = np.sqrt((blocks**2).mean(axis=1))
    loud = int((levels >= threshold).sum())
    return (
        f"Peak level {levels.max():.4f}, threshold {threshold}: "
        f"{loud} of {len(levels)} blocks count as speech"
    )
