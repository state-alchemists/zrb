# Raspberry Pi Push-to-Talk + Camera Example

Drive `zrb llm chat` from two GPIO buttons: hold one to talk, hold the other to
attach a photo to what you just said. The keyboard keeps working throughout.

The mechanism is `LLMChatTask.append_trigger` — a callable returning an async
iterable whose items become user turns. Yield a string for text alone, or a
`TriggerMessage(text, attachments)` for text plus attachments.

## Hardware

Two momentary buttons, BCM numbering, each switching its pin to GND. gpiozero
enables the internal pull-ups, so no external resistors:

| Pin | Button |
|---|---|
| GPIO 17 | Push-to-talk — hold to record, release to send |
| GPIO 27 | Camera — hold as you release GPIO 17 to attach a photo |

Plus a USB microphone and a camera. A USB webcam works out of the box; a CSI
camera module needs libcamera's V4L2 compatibility layer exposing `/dev/video0`.
Check the camera on its own before running anything else:

```bash
ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 /tmp/test.jpg
```

## Setup

```bash
pip install zrb[llm] gpiozero
sudo apt install ffmpeg libportaudio2
```

Speech-to-text defaults to **vosk**, which runs offline with no API key — the
model (~50MB) downloads on first use. A Pi 4 or 5 handles it comfortably; a Zero
2 W will be slow. Set `ZRB_LLM_VOICE_MODE` to `openai` or `google` to transcribe
over the network instead.

## Usage

```bash
cd examples/chat-gpio-ptt
export ZRB_LLM_VOICE_ENABLED=true
zrb llm chat
```

Hold GPIO 17, speak, release. Your words arrive as a user turn. Hold GPIO 27 as
you release and the frame goes with them, so "what am I holding?" works.

## Notes

**Attachments take file paths.** `capture_photo` writes the frame to a fresh
`tempfile.mkstemp` file and yields the path; zrb resolves it, size-checks it and
scales the image — the same path `/attach` and `/photo` take. An already-built
`BinaryContent` works too, but it is passed through as-is: no size check, no
scaling, so a full-resolution frame counts against the attachment limit whole.

A path is read when the turn reaches the model, not when it is submitted, which
is why each capture gets its own file: a turn queued behind one still in flight
would otherwise be handed whatever the next press captured.

**gpiozero callbacks run on their own thread.** Every hop back into the event
loop goes through `loop.call_soon_threadsafe`; the `asyncio.Event` objects are
not thread-safe on their own.

**Empty items are skipped.** A `TriggerMessage` with neither text nor
attachments costs nothing, so a transcription that came back silent can be
yielded unguarded.

**A camera button is not the only way in.** If you want the *agent* to decide
when to look, register the camera as a tool instead and let it call one:

```python
from zrb.llm.agent.types import BinaryContent
from zrb.llm.util.camera import get_camera_photo

async def look() -> BinaryContent:
    """Capture a photo from the attached camera."""
    return BinaryContent(data=await get_camera_photo(), media_type="image/jpeg")

llm_chat.append_tool(look)
```

Then "have a look and tell me what you see" needs no second button.
