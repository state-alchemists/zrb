"""Speaker core for the voice-interaction hook.

Two jobs:

1. Turn a wall of agent output into something worth listening to.
2. Make sure only one thing is ever audible at a time.

Job 2 is not an optimization. Stop, PermissionRequest and Notification are
separate hook invocations, each a separate process; zrb runs hooks on a thread
pool and may fire them concurrently. Without a cross-process lock two espeak
processes fight over the audio device and the user hears garbled overlap.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (env-overridable so the prototype can be tuned without edits)
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHARS = 400
DEFAULT_VOICE = "en-us+m3"
DEFAULT_RATE = 165
DEFAULT_LOCK_TIMEOUT = 30.0

# Ceiling on how long we are willing to wait for the audio device. A stuck
# espeak must never hold a hook open past its timeout, because a hook that
# overruns gets its whole process tree killed and, on Stop, can look like a
# failure.
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
    """Append to a side log.

    Never stderr: on a Stop hook, stderr output participates in the block
    protocol, and we must never accidentally signal anything to zrb.
    """
    try:
        with open(SPEAK_LOG, "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------------------------

# Fenced code blocks: keep nothing. Reading source aloud is never useful.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# Inline code: keep the word, drop the backticks.
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
# Markdown tables: a row is mostly pipes and dashes.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
# Links: keep the label, drop the URL.
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
# Bare URLs.
_URL_RE = re.compile(r"https?://\S+")
# Headings, blockquotes, list bullets, emphasis.
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_QUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~)")
# Emoji and other pictographs: espeak-ng reads some as words ("smiling face").
_NON_SPEECH_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]"
)


def clean_for_speech(text: str) -> str:
    """Reduce markdown-ish agent output to speakable prose.

    Order matters: fences before inline code (triple backticks would otherwise
    be eaten as three inline spans), links before bare URLs so a link's label
    survives.
    """
    text = _FENCE_RE.sub(" ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub(" ", text)
    text = _TABLE_ROW_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _HEADING_RE.sub("", text)
    text = _QUOTE_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = _EMPHASIS_RE.sub("", text)
    text = _NON_SPEECH_RE.sub("", text)
    text = text.replace("→", " to ").replace("—", ", ").replace("–", ", ")
    # Collapse whitespace, but keep paragraph breaks as sentence pauses.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", ".\n", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()


def truncate_for_speech(text: str, max_chars: int) -> str:
    """Cut at a sentence boundary near *max_chars*.

    Cutting mid-sentence is the single most jarring failure mode of a speaker
    like this, so prefer the last sentence end before the budget and only fall
    back to a hard cut when the text has no sentence break at all.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    window = text[:max_chars]
    best = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if best >= max_chars * 0.5:
        return window[: best + 1]
    return window.rstrip() + "..."


# ---------------------------------------------------------------------------
# Serialized playback
# ---------------------------------------------------------------------------


def _speak_espeak(text: str, voice: str, rate: int) -> None:
    subprocess.run(
        ["espeak-ng", "-v", voice, "-s", str(rate), text],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )


def _speak_gemini(text: str, voice: str, rate: int) -> None:
    """Gemini TTS. Requires `pip install 'zrb-extras[google-genai]'`.

    Imported lazily so the hook keeps working on the espeak backend when
    zrb-extras is not installed (it is NOT installed on this machine -- see
    the README).
    """
    from zrb_extras.llm.tool import create_speak_tool  # noqa: F401

    raise NotImplementedError(
        "Gemini backend is not wired up in the prototype; use espeak-ng."
    )


def _resolve_backend(name: str):
    """Look the backend up by name on every call.

    Deliberately not a module-level dict of callables: that would capture each
    function object at import time, so patching or replacing a backend later
    would have no effect. Every backend takes the same (text, voice, rate)
    signature so the call site stays uniform.
    """
    return {
        "espeak-ng": _speak_espeak,
        "gemini": _speak_gemini,
    }.get(name)


def speak(text: str) -> None:
    """Speak *text*, serialized against every other speaking process."""
    text = text.strip()
    if not text:
        log("skip: empty after cleanup")
        return

    backend = os.getenv("ZRB_VOICE_BACKEND", "espeak-ng")
    voice = os.getenv("ZRB_VOICE_NAME", DEFAULT_VOICE)
    rate = int(os.getenv("ZRB_VOICE_RATE", str(DEFAULT_RATE)))
    max_chars = int(os.getenv("ZRB_VOICE_MAX_CHARS", str(DEFAULT_MAX_CHARS)))

    spoken = truncate_for_speech(clean_for_speech(text), max_chars)
    if not spoken:
        log("skip: nothing left after truncation")
        return

    if backend == "espeak-ng" and shutil.which("espeak-ng") is None:
        log("error: espeak-ng not on PATH")
        return

    fn = _resolve_backend(backend)
    if fn is None:
        log(f"error: unknown backend {backend!r}")
        return

    lock_timeout = float(os.getenv("ZRB_VOICE_LOCK_TIMEOUT", str(DEFAULT_LOCK_TIMEOUT)))
    deadline = time.monotonic() + lock_timeout

    # O_CREAT so two processes racing on first ever run both succeed.
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
                    # Dropping the utterance is the right call: a hook that
                    # blocks past its timeout gets killed, and on Stop that can
                    # be read as a failure.
                    log(f"skip: lock busy >{lock_timeout}s, dropping: {spoken[:60]!r}")
                    return
                time.sleep(0.1)
        log(f"speak[{backend}]: {spoken[:80]!r}")
        fn(spoken, voice, rate)
    except Exception as exc:  # never propagate: hooks must exit 0
        log(f"error: {type(exc).__name__}: {exc}")
    finally:
        try:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


if __name__ == "__main__":
    speak(" ".join(sys.argv[1:]) or "voice speaker ready")
