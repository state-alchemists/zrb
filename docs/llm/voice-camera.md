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
- [Talking with zrb](#talking-with-zrb)
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

zrb ignores the microphone while it is speaking, so its own voice is not taken as yours. Anything you say over it is lost, so wait for it to finish, or answer by keyboard — unless you wear headphones and turn on barge-in.

**Talking over zrb (barge-in).** With `ZRB_LLM_DICTATION_BARGE_IN=headset`, the microphone keeps listening while zrb speaks. About a third of a second of speech over it (`ZRB_LLM_DICTATION_BARGE_IN_MIN_SPEECH`) stops it at once, before what you said is even transcribed, and the rest of that reply is not read. Then:

- "Stop" or "no" said alone cancels the turn, as Esc does, and is sent nowhere.
- Anything else steers the running turn: the agent takes it into account at its next step (`ZRB_LLM_DICTATION_BARGE_IN_ACTION=steer`). With `cancel`, the turn stops and what you said starts a new one.
- While a tool approval is waiting, what you say answers it, as usual: "no" denies the tool call, not the turn.

With wake words, zrb stops only once it has heard one, so talk in the room does not silence it. Use barge-in only with headphones: on speakers the microphone hears zrb's own voice, and it stops itself.

**Transcribing while you speak.** vosk transcribes an utterance as you say it, and the status bar shows the last words heard. Once you pause for half a second (`ZRB_LLM_DICTATION_MIN_SILENCE`) after words that sound finished, the utterance ends; after "and", "the" or "um" it waits the full second (`ZRB_LLM_DICTATION_SILENCE`), since you are still thinking. The other backends transcribe the whole utterance after it ends and always wait the full second.

The status bar shows what the microphone is doing:

| Badge | Meaning |
|---|---|
| `🎤 listening` | Waiting for you to speak |
| `🎙️ hearing you…` | You are speaking |
| `🎙️ …run the tests` | The last words heard so far (vosk) |
| `✍️ transcribing…` | Turning what you said into text |
| `🎤 heard "Yes." · listening` | What it heard last; it is listening again |
| `🔇 mic paused while speaking` | zrb is talking; what you say now is not heard |
| `✋ interrupted · go on…` | You talked over zrb and it stopped (barge-in) |
| `✋ stopped · listening` | You said "stop" over it; the turn was cancelled |
| `🎤 ignored "…" (no wake word)` | Heard, but it did not start with a wake word |

Push-to-talk shows `🎙️ recording…` and `✍️ transcribing…` the same way.

The default transcriber is vosk, which runs offline and downloads its model on first use, but mangles technical terms. With an OpenAI key, `ZRB_LLM_DICTATION_BACKEND=openai` and `ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe` are far more accurate. [`examples/voice-interaction`](../../examples/voice-interaction/README.md) compares the backends on one clip.

## Speech

Speech starts off. Turn it on with `ZRB_LLM_SPEECH_ENABLED=on`, or with `/speech` during a session. zrb then reads aloud:

- the reply (not a sub-agent's), a sentence at a time while the model writes it,
- a tool call that starts after a silence, so a long one is not silent,
- "I need to write a file /tmp/a.py. I need your approval." when a tool waits for approval — not read if you answer first, and cut off if you answer while it is being read,
- a question the agent asks you.

**Speaking as it writes.** A reply is read a sentence at a time while the model is still writing it, and what it writes before a tool call ("Let me run the tests.") is read when the call starts. Code, tables and links are not read. At most 400 characters (`ZRB_LLM_SPEECH_MAX_CHARS`) are read per turn: the sentence crossing the limit is finished, then "The full answer is on screen." The next sentence's audio is made while the current one plays, so a cloud voice has no gap between sentences.

With `ZRB_LLM_SPEECH_STREAM=off`, the reply is read once the turn ends instead, cut at a sentence end past 400 characters; `ZRB_LLM_SPEECH_SUMMARIZE=on` then has the small model summarize a long reply, at the cost of one model call per long reply.

**Saying what it is doing.** A tool call that starts after 8 seconds of silence (`ZRB_LLM_SPEECH_PROGRESS_INTERVAL`) is announced: "Running a command.", "Searching the code." Nothing is announced while zrb is speaking, and an announcement still waiting when its tool finishes is dropped. Take `progress` out of `ZRB_LLM_SPEECH_EVENTS` to turn it off.

While speech is on, the model is told its reply is heard, so it opens with the answer in a sentence or two and puts code and detail after it.

Switching speech off with `/speech` drops whatever has not been said yet.

The `openai` backend starts playing as the audio arrives, through a player that reads standard input (`paplay`, `aplay` or `ffplay`), so a long reply starts as soon as a short one does. With `ZRB_LLM_SPEECH_WAV_PLAYER` set, or only `afplay`, it waits for the whole file.

Each chat session gets its own speaker, microphone and hands-free flag, so one session switching speech off does not silence the next. Two zrb processes still take turns rather than talk over each other, through a lock file that a session claims while it is speaking and releases when it is closed.

Speech rides on the hook subsystem, so it needs hooks on: with `ZRB_HOOKS_ENABLED=off` nothing is spoken, and enabling speech says so. Each session's speaker, microphone and hooks are closed when that session ends — on exit in the terminal, on removal in the web chat — so a long-lived server does not accumulate them.

## Talking with zrb

`/speech` and `/handsfree` together make a voice conversation: you speak, and zrb answers aloud as it writes. To start every session that way:

```bash
ZRB_LLM_SPEECH_ENABLED=on ZRB_LLM_DICTATION_MODE=hands_free zrb llm chat
```

With headphones, add `ZRB_LLM_DICTATION_BARGE_IN=headset` so you can talk over it (see barge-in under [Dictation](#dictation)). It is off by default because on speakers zrb would hear itself.

For the quickest replies, use vosk for dictation (it transcribes while you speak and ends an utterance half a second after you finish) and a fast model. Each part's delay can be tuned with the variables above.

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
| Dictation | `zrb.llm.dictation.AnyDictationBackend` — `async transcribe(audio) -> str`; optionally `async create_stream() -> AnyTranscriptionStream \| None` to transcribe while the user speaks | `vosk`, `openai`, `google`, `multimodal` |
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

The three features are built only from `LLMChatTask`'s public extension points — `append_custom_command`, `append_trigger`, `append_hook_factory`, `append_stream_observer` — so the same shapes are open to your own features. A stream observer is called with every event a run streams, text deltas included, after the UI (ADR-0104). [LLMChatTask → Triggers & Custom Commands](../task-types/llmchat-task.md#triggers--custom-commands) describes them; ADR-0102 records the design.

🔖 [Documentation Home](../../README.md) > [LLM Integration](llm-integration.md) > Voice and Camera
