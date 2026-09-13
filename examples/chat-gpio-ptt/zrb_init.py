"""
Raspberry Pi Push-to-Talk + Camera Example

Drives the built-in `zrb llm chat` session from two GPIO buttons instead of the
keyboard, via `LLMChatTask.append_trigger`.

A trigger is a callable returning an async iterable; every item it yields
becomes a user turn, exactly as if it had been typed. Yield a string to send
text alone, or a `TriggerMessage` to send text WITH attachments — which is how
the photo reaches the model.

Wiring (BCM numbering), both buttons switching to GND. gpiozero enables the
internal pull-ups, so no external resistors are needed:

    GPIO 17 ── push-to-talk button ── GND
    GPIO 27 ── camera button       ── GND

Usage:
    pip install "zrb[voice]" gpiozero
    sudo apt install ffmpeg libportaudio2

    cd examples/chat-gpio-ptt
    export ZRB_LLM_VOICE_ENABLED=true    # vosk: offline, no API key
    zrb llm chat

    Hold GPIO 17, speak, release  → your words are submitted as a user turn.
    Hold GPIO 27 as you release   → a photo is attached to that same turn.

The keyboard keeps working throughout: a trigger adds a way in, it does not
take one away.
"""

import asyncio
import os
import tempfile

from zrb import TriggerMessage
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.util.camera import get_camera_photo
from zrb.llm.voice import VoiceEngine

try:
    from gpiozero import Button
except ImportError:
    Button = None

PTT_PIN = 17
CAMERA_PIN = 27


# =============================================================================
# Camera: one frame, handed over as a file path.
# =============================================================================


async def capture_photo() -> list[str]:
    """Grab one frame and return it as a one-item attachment list.

    Attachments take a file path as readily as a `BinaryContent`, and the path
    is the better of the two here: zrb size-checks and scales an image it reads
    from disk, while a `BinaryContent` is passed through as-is, so an unscaled
    frame would count against the attachment limit at full size. An empty list
    means "no attachment".

    Each capture gets its own file. The path is read when the turn reaches the
    model, not when it is submitted, so a turn waiting behind one still in
    flight would otherwise be handed whatever the next press captured.
    `mkstemp` also creates the file atomically with 0600 and an unguessable
    name, which a fixed path under the shared temp directory cannot do.

    ponytail: the frames are left for the OS temp reaper — the example has no
    hook for "this turn consumed its attachment". Delete each one from a
    post-turn callback if you adapt this into something long-running.
    """
    frame = await get_camera_photo()
    if frame is None:
        print("[gpio-ptt] camera capture failed; sending the turn without it.")
        return []
    handle, path = tempfile.mkstemp(prefix="zrb-gpio-photo-", suffix=".jpg")
    with os.fdopen(handle, "wb") as photo_file:
        photo_file.write(frame)
    return [path]


# =============================================================================
# The trigger: one user turn per push-to-talk press.
# =============================================================================


async def gpio_push_to_talk():
    """Record while GPIO 17 is held, then submit what was said."""
    loop = asyncio.get_running_loop()
    engine = VoiceEngine()
    # Bound for the lifetime of this generator: a garbage-collected Button
    # releases its pin and stops firing.
    talk, camera = Button(PTT_PIN), Button(CAMERA_PIN)

    pressed, released = asyncio.Event(), asyncio.Event()
    # gpiozero runs its callbacks on its own thread, and the event loop is not
    # thread-safe — every hop back into it goes through call_soon_threadsafe.
    talk.when_pressed = lambda: loop.call_soon_threadsafe(pressed.set)
    talk.when_released = lambda: loop.call_soon_threadsafe(released.set)

    while True:
        await pressed.wait()
        pressed.clear()
        released.clear()
        # `VoiceEngine.start_listening` is record + transcribe in one call; the
        # two halves are split here only so the camera button is sampled at the
        # moment of release, rather than after transcription has run.
        audio = await engine.record(released)
        attachments = await capture_photo() if camera.is_pressed else []
        text = await engine.transcribe(audio) if audio else ""
        # Silence with no photo yields ("", []), which the trigger loop skips.
        yield TriggerMessage(text, attachments)


# =============================================================================
# Register the trigger on the built-in chat task.
#
# Guarded so that a machine without gpiozero — your laptop, CI — still gets a
# working `zrb` in this directory instead of an import error on every command.
# =============================================================================

if Button is None:
    print("[gpio-ptt] gpiozero is not installed; GPIO trigger not registered.")
else:
    llm_chat.append_trigger(gpio_push_to_talk)
