"""
Listening half of the voice-interaction example (the hooks in .zrb/hooks.json
are the speaking half).

    zrb llm chat                          # /voice, Space, talk, Space, Enter
    ZRB_VOICE_HANDS_FREE=1 zrb llm chat   # start with hands-free on

`/handsfree` toggles hands-free during a session. It drops microphone audio
captured while the speaker holds its playback lock, so the agent does not
answer its own voice.
"""

import asyncio
import os
import re
import sys
import time
from collections import deque

from zrb import CFG
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.custom_command import ActionCommand
from zrb.llm.voice import VoiceEngine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice_speaker import is_speaking, log, speak  # noqa: E402

SAMPLE_RATE = 16000  # what VoiceEngine's transcribers expect
BLOCK_SECONDS = 0.1
PRE_ROLL_BLOCKS = 3  # keep 0.3 s before speech starts, or the first word clips
MIN_SPEECH_SECONDS = 0.4  # shorter bursts are coughs and clicks
MAX_UTTERANCE_SECONDS = 30.0
POST_SPEECH_COOLDOWN = 0.4  # room echo outlives the player process
WAKE_WINDOW_SECONDS = 8.0  # how long the wake word alone keeps listening
_WORD_RE = re.compile(r"[\w']+")


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
    wake_word = os.getenv("ZRB_VOICE_WAKE_WORD", "")
    armed_until = 0.0
    async for audio in _utterances():
        try:
            text = (await engine.transcribe(audio)).strip()
        except Exception as e:
            # A background trigger has no UI to show this in, so say it.
            log(f"hands-free: transcription failed: {e}")
            await asyncio.to_thread(speak, "Sorry, transcription failed.")
            continue
        command = _strip_wake_word(text, wake_word)
        if command is None and time.monotonic() < armed_until:
            command = text
        if command is None:
            log("hands-free: dropped an utterance without the wake word")
        elif not command:
            # The wake word alone: people pause after it, so the command
            # arrives as the next utterance.
            armed_until = time.monotonic() + WAKE_WINDOW_SECONDS
        else:
            armed_until = 0.0
            yield command


def _strip_wake_word(text: str, wake_word: str) -> str | None:
    """Return *text* after the wake word, or None if it does not start with it.

    Compared word by word, so "Hey, Jarvis." matches "hey jarvis".
    """
    wanted = _WORD_RE.findall(wake_word.lower())
    if not wanted:
        return text
    words = list(_WORD_RE.finditer(text))
    if [w.group().lower() for w in words[: len(wanted)]] != wanted:
        return None
    return text[words[len(wanted) - 1].end() :].lstrip(" ,.!?;:")


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

        async for audio in _listen(np, sd, threshold, max_silence):
            yield audio


async def _listen(np, sd, threshold: float, max_silence: float):
    """Yield utterances until hands-free is switched off; the mic closes then."""
    loop = asyncio.get_running_loop()
    blocks: asyncio.Queue = asyncio.Queue()

    def on_audio(indata, frames, time_info, status):
        # Sample the lock at capture: blocks queue up during transcription,
        # so checking at processing time would let playback audio through.
        captured = (indata.copy(), is_speaking())
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
    cooldown_blocks = 0  # in blocks, not wall time, for the same reason
    with stream:
        while _hands_free["on"]:
            block, agent_speaking = await blocks.get()
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
                    pre_roll.clear()
                continue
            speech.append(block)
            silent_for = 0.0 if loud else silent_for + BLOCK_SECONDS
            duration = len(speech) * BLOCK_SECONDS
            if silent_for < max_silence and duration < MAX_UTTERANCE_SECONDS:
                continue
            if duration - silent_for >= MIN_SPEECH_SECONDS:
                audio = np.concatenate(speech, axis=0)
                yield (audio * 32767).astype(np.int16).tobytes()
            speech, silent_for = [], 0.0


llm_chat.append_trigger(hands_free)
llm_chat.append_custom_command(
    ActionCommand(
        "/handsfree", toggle_hands_free, description="Toggle hands-free voice input"
    )
)
