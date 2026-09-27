"""Speaker for the voice-interaction hook: clean text, synthesize, play.

Each hook event is its own process, so playback is serialized with a
cross-process file lock. Stdlib only, so it runs under any python3.
"""

from __future__ import annotations

import base64
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

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
    """Append to the side log; stderr is reserved for zrb's hook protocol.

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
                    # Better dropped than killed at the hook timeout.
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
    except Exception as exc:  # hooks must exit 0
        log(f"error: player {argv[0]} failed: {type(exc).__name__}: {exc}")
    finally:
        try:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


if __name__ == "__main__":
    speak(" ".join(sys.argv[1:]) or "voice speaker ready")
