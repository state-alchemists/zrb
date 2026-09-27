🔖 [Documentation Home](../../README.md) > [LLM Integration](llm-integration.md) > Voice and Camera

# Voice and Camera

`zrb llm chat` can take a photo, take dictation, and read its replies aloud. Each is an optional feature added to the chat task with one call; the built-in `llm_chat` makes all three calls, so they work out of the box.

| Feature | Commands | Needs |
|---|---|---|
| Camera | `/photo [device]` | `ffmpeg`, or Termux:API on Android |
| Dictation | `/voice`, `/handsfree` | `pip install 'zrb[voice]'` |
| Speech | `/speech` | nothing on macOS; Termux:API on Android; `espeak-ng` on Linux and Windows; or a cloud key |

Every setting is an environment variable, listed in [LLM Configuration § 23](../configuration/llm-config.md#23-voice-and-camera). Platform problems are covered in [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

## Table of Contents

- [Camera](#camera)
- [Dictation](#dictation)
- [Speech](#speech)
- [Configuring in code](#configuring-in-code)
- [Your own backend](#your-own-backend)
- [On your own chat task](#on-your-own-chat-task)

## Camera

`/photo` captures one photo and attaches it to your next message, so you can say what to do with it: `/photo`, then "what does this error on my screen mean?". `/photo 1` picks a device; press Tab after `/photo ` to list them.

## Dictation

**Push-to-talk.** Type `/voice` and talk. A pause of about a second, or `/voice` again, stops the recording. The transcript is inserted at the cursor, where you can edit it before pressing Enter. `/voice` works while the model is still answering.

**Hands-free.** `/handsfree` keeps the microphone open. Every utterance is sent as a turn, and while zrb waits for a tool approval, what you say answers it:

- "Yes", "yes please", "go ahead" approve.
- Anything else denies, and what you said becomes the reason: "no, use pytest instead" tells the agent what to do. A hedge or a "no" anywhere ("yes, but wait", "okay, no") never approves.
- An answer to a multiple-choice question picks the option you name, by its label or its number; for a question that takes several, name them all ("one and three", "cheese, olives").

Set `ZRB_LLM_DICTATION_MODE=hands_free` to start every session this way. Set `ZRB_LLM_DICTATION_WAKE_WORDS` so that only utterances starting with a wake word count. Without one, anything the microphone hears becomes a turn, including a conversation in the room.

zrb ignores the microphone while it is speaking, so its own voice is not taken as yours.

The default transcriber is vosk, which runs offline and downloads its model on first use, but mangles technical terms. With an OpenAI key, `ZRB_LLM_DICTATION_BACKEND=openai` and `ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe` are far more accurate. [`examples/voice-interaction`](../../examples/voice-interaction/README.md) compares the backends on one clip.

## Speech

Speech starts off. Turn it on with `ZRB_LLM_SPEECH_ENABLED=on`, or with `/speech` during a session. zrb then reads aloud:

- the reply at the end of each turn (not a sub-agent's),
- "I need to write a file /tmp/a.py. I need your approval." when a tool waits for approval,
- a question the agent asks you.

Code, tables and links are not read. A reply longer than 400 characters (`ZRB_LLM_SPEECH_MAX_CHARS`) is cut at a sentence end, followed by "The full answer is on screen." With `ZRB_LLM_SPEECH_SUMMARIZE=on`, the small model summarizes it instead, at the cost of one model call per long reply.

Switching speech off with `/speech` drops whatever has not been said yet.

Each chat session gets its own speaker, microphone and hands-free flag, so one session switching speech off does not silence the next. Two zrb processes still take turns rather than talk over each other, through a lock file that a session claims while it is speaking and releases when it is closed.

Speech rides on the hook subsystem, so it needs hooks on: with `ZRB_HOOKS_ENABLED=off` nothing is spoken, and enabling speech says so. Each session's speaker, microphone and hooks are closed when that session ends — on exit in the terminal, on removal in the web chat — so a long-lived server does not accumulate them.

## Configuring in code

Each feature has a config dataclass whose fields mirror its environment variables; a field left `None` reads the variable when a session starts. To change the built-in chat from a `zrb_init.py`, set the variables:

```python
import os

from zrb import CFG

os.environ.setdefault(f"{CFG.ENV_PREFIX}_LLM_SPEECH_ENABLED", "on")
os.environ.setdefault(f"{CFG.ENV_PREFIX}_LLM_DICTATION_WAKE_WORDS", "hey zed")
```

`setdefault` leaves a value the user exported alone. The settings are read when the session starts, so setting them after `import zrb` still applies.

## Your own backend

Each feature takes a backend name or an object implementing its interface:

| Feature | Interface | Built-in names |
|---|---|---|
| Camera | `zrb.llm.camera.AnyCameraBackend` — `async capture(device) -> bytes \| None` | `auto`, `termux`, `ffmpeg` |
| Dictation | `zrb.llm.dictation.AnyDictationBackend` — `async transcribe(audio) -> str` | `vosk`, `openai`, `google`, `multimodal` |
| Speech | `zrb.llm.speech.AnySpeechBackend` — `create_utterance(text) -> Utterance` | `auto`, `termux`, `say`, `espeak-ng`, `openai`, `gemini` |

A speech backend that talks to a local TTS server and plays the WAV it returns:

```python
import json
import urllib.request

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.speech import AnySpeechBackend, SpeechConfig, enable_speech
from zrb.llm.speech.backend import create_wav_utterance


class LocalTTS(AnySpeechBackend):
    def create_utterance(self, text):
        request = urllib.request.Request(
            "http://localhost:5002/api/tts",
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return create_wav_utterance(response.read())


enable_speech(llm_chat, SpeechConfig(backend=LocalTTS(), enabled=True))
```

`llm_chat` already called `enable_speech` with the default config; calling it again replaces that call, so there is still one `/speech` per session and the earlier session's speaker is closed. The same holds for `enable_camera` and `enable_dictation`.

If your backend fails, the local engine (`termux`, `say` or `espeak-ng`) speaks instead. zrb-extras adds a pyttsx3 backend. Audio passed to `transcribe` is 16 kHz mono 16-bit PCM; `zrb.llm.dictation.backend.wav.pcm16_to_wav_bytes` wraps it for an API that wants a file.

## On your own chat task

A custom `LLMChatTask` gets none of these until it asks:

```python
from zrb import LLMChatTask
from zrb.llm.camera import enable_camera
from zrb.llm.dictation import DictationConfig, enable_dictation
from zrb.llm.speech import enable_speech

chat = LLMChatTask(name="assistant")
enable_camera(chat)
enable_dictation(chat, DictationConfig(mode="hands_free", wake_words=["hey zed"]))
enable_speech(chat)
```

`enable_speech` also works on an `LLMTask`, which has no commands: it speaks the task's final reply.

The three features are built only from `LLMChatTask`'s public extension points — `append_custom_command`, `append_trigger`, `append_hook_factory` — so the same shapes are open to your own features. [LLMChatTask → Triggers & Custom Commands](../task-types/llmchat-task.md#triggers--custom-commands) describes them; ADR-0102 records the design.

🔖 [Documentation Home](../../README.md) > [LLM Integration](llm-integration.md) > Voice and Camera
