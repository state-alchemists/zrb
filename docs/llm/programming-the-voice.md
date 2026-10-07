🔖 [Documentation Home](../../README.md) > [LLM](./) > Programming the Voice

# Programming the Voice

A voice assistant has three separate pieces: it hears speech, decides what the
agent should do, and turns the agent's output into audio. Zrb exposes each
piece independently. Use `DictationConfig` to program voice input, `SpeechConfig`
to program spoken interaction, and `AnySpeechBackend` when you need to replace
text-to-speech itself.

This page is the practical companion to [Voice and Camera](voice-camera.md):
it starts with working configurations, then shows the Python extension points.
The exhaustive environment-variable reference is [LLM Configuration → Voice
and Camera](../configuration/llm-config.md#23-voice-and-camera).

## Table of contents

- [A local streaming conversation](#a-local-streaming-conversation)
- [Voice recipes](#voice-recipes)
- [The three programming layers](#the-three-programming-layers)
- [Program voice input](#program-voice-input)
- [Program spoken responses](#program-spoken-responses)
- [Program audio rendering](#program-audio-rendering)
- [Attach voice to your own chat task](#attach-voice-to-your-own-chat-task)
- [Choosing the right extension point](#choosing-the-right-extension-point)

## A local streaming conversation

This is a practical starting point for a hands-free conversation on a noisy
room microphone: Moonshine transcribes while you speak, Piper speaks locally,
and barge-in remains possible without pausing on every loud sound.

```bash
pip install 'zrb[voice]'
pip install 'pipecat-ai[moonshine]' 'pipecat-ai[piper]'

ZRB_LLM_VOICE=conversation \
ZRB_LLM_DICTATION_BARGE_IN_HOLD=off \
ZRB_LLM_DICTATION_BACKEND=moonshine \
ZRB_LLM_DICTATION_STT_MODEL=medium-streaming \
ZRB_LLM_SPEECH_BACKEND=piper \
ZRB_LLM_SPEECH_VOICE=en_US-kristin-medium \
ZRB_LLM_DICTATION_WAKE_WORDS='hi,hai,hey,hei,嗨' \
zrb llm chat
```

What each important setting does:

| Setting | Why it is here |
|---|---|
| `ZRB_LLM_VOICE=conversation` | Enables speech, hands-free dictation, and barge-in as a preset. |
| `ZRB_LLM_DICTATION_BARGE_IN_HOLD=off` | Keeps barge-in possible without pausing speech whenever loud audio crosses the bar. A live stop word or wake word can still interrupt immediately when the backend streams partials. |
| `ZRB_LLM_DICTATION_BACKEND=moonshine` | Uses a local Pipecat speech-to-text service. |
| `ZRB_LLM_DICTATION_STT_MODEL=medium-streaming` | Selects Moonshine's streaming model variant. |
| `ZRB_LLM_SPEECH_BACKEND=piper` | Uses local text-to-speech instead of a cloud voice. |
| `ZRB_LLM_SPEECH_VOICE=en_US-kristin-medium` | Selects the Piper voice. |
| `ZRB_LLM_DICTATION_WAKE_WORDS=...` | Limits hands-free turns to utterances beginning with one of the configured spellings. |

`ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on` is not needed in this recipe because
`conversation` already enables it. You may include it when you want the command
to state that choice explicitly:

```bash
ZRB_LLM_VOICE=conversation \
ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on \
ZRB_LLM_DICTATION_BARGE_IN_HOLD=off \
... \
zrb llm chat
```

## Voice recipes

### The simplest conversation

Use the preset when the built-in defaults are suitable:

```bash
ZRB_LLM_VOICE=conversation zrb llm chat
```

It enables replies read aloud, hands-free listening, and barge-in. The default
barge-in hold stays on, so zrb pauses quickly while it determines whether the
sound was an interruption or its own voice.

### Conversation without barge-in

Use `turns` when you want zrb and the user to take turns:

```bash
ZRB_LLM_VOICE=turns zrb llm chat
```

Speech is enabled and dictation stays hands-free, but the microphone is deaf
while zrb is speaking.

### Push-to-talk with spoken replies

Use `speak` when you want replies read aloud but prefer to start each recording
explicitly with `/voice`:

```bash
ZRB_LLM_VOICE=speak zrb llm chat
```

### A noisy room with cloud transcription

Keep local playback but use a hosted transcription backend when accuracy is
more important than an offline setup:

```bash
ZRB_LLM_VOICE=conversation \
ZRB_LLM_DICTATION_BARGE_IN_HOLD=off \
ZRB_LLM_DICTATION_BACKEND=openai \
ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe \
ZRB_LLM_SPEECH_BACKEND=piper \
zrb llm chat
```

Add `ZRB_LLM_DICTATION_WAKE_WORDS` in a shared room. Add a language hint with
`ZRB_LLM_DICTATION_LANGUAGE` when the transcription service supports it.

### Fully local speech and transcription

The exact model packages depend on the selected services. For example, a
Moonshine/Piper setup keeps both speech directions on the machine after the
models are downloaded:

```bash
pip install 'zrb[voice]'
pip install 'pipecat-ai[moonshine]' 'pipecat-ai[piper]'

ZRB_LLM_VOICE=conversation \
ZRB_LLM_DICTATION_BACKEND=moonshine \
ZRB_LLM_DICTATION_STT_MODEL=medium-streaming \
ZRB_LLM_SPEECH_BACKEND=piper \
zrb llm chat
```

See [Voice and Camera → Your own backend](voice-camera.md#your-own-backend)
for the available local services and their package names.

## The three programming layers

| Layer | Responsibility | Main extension point |
|---|---|---|
| Voice input | Microphone mode, wake words, stop words, approval answers, and transcription | `DictationConfig` and `enable_dictation()` |
| Spoken response | Which events are spoken and the words used for approvals, questions, and progress | `SpeechConfig` and its phrase mappings |
| Audio rendering | Voice, rate, provider, playback, and pause/interruption behavior | `SpeechConfig` and `AnySpeechBackend` |

The model prompt is a fourth, related concern. `system_prompt` and
`PromptManager` program what the agent thinks and does; the `speech_live` prompt
only tells the model that its response will be heard aloud, so it opens with a
spoken answer before code and tables. It does not choose the TTS voice or
rewrite every response.

## Program voice input

Pass a `DictationConfig` when enabling dictation. Fields left as `None` come
from `CFG` when the session starts, so this can be configured in `zrb_init.py`
without rebuilding the task:

```python
from zrb import LLMChatTask
from zrb.llm.dictation import DictationConfig, enable_dictation

chat = LLMChatTask(name="voice-assistant")

enable_dictation(
    chat,
    DictationConfig(
        mode="hands_free",
        backend="moonshine",
        stt_model="medium-streaming",
        wake_words=["hi", "hai", "hey", "hei", "嗨"],
        stop_words=["stop", "wait", "hold on", "cancel"],
        approve_words=["yes", "go ahead", "do it"],
        deny_words=["no", "cancel", "don't"],
        barge_in_enabled=True,
        barge_in_hold=False,
    ),
)
```

Use wake words when other people or media may be audible. Use stop words for
short, exact interruptions that should not reach the model. `barge_in_hold`
controls whether loudness pauses speech before the transcript is known; it does
not disable barge-in itself. The hold is on by default.

The dictation backend may also provide a streaming transcription interface.
Streaming backends can act on a live stop word or wake word before the utterance
ends; batch backends decide after the complete utterance is transcribed.

## Program spoken responses

`SpeechConfig` controls which events become speech and the templates used for
built-in notifications:

```python
from zrb.llm.speech import SpeechConfig, enable_speech

speech = SpeechConfig(
    enabled=True,
    backend="piper",
    voice="en_US-kristin-medium",
    events=["reply", "approval", "question", "progress"],
    approval_message="I need to {action}{target}. Should I continue?",
    approval_actions={
        "Write": "write",
        "Shell": "run a command",
        "*": "use {tool}",
    },
    question_message="I need your answer.",
    progress_phrases={
        "Lsp*": "Checking the code.",
        "Shell": "Running a command.",
        "*": "Working on it.",
    },
)

enable_speech(chat, speech)
```

The available speech events are:

- `reply` — the main agent's final response, streamed sentence by sentence when
  `stream` is enabled;
- `approval` — a tool approval request;
- `question` — a question raised by the agent or UI;
- `progress` — a tool call announced after the configured silence interval.

`approval_message` supports `{action}` and `{target}`. The action and progress
maps use tool-name patterns, with `*` and `?` wildcards; the first matching
pattern wins. These are templates for fixed UI events, not additional model
calls, so they are predictable and inexpensive.

For a response's general tone and structure, use the agent's `system_prompt`
or the `speech_live` prompt. For the exact approval, question, or progress
wording, use the `SpeechConfig` fields above.

## Program audio rendering

For built-in backends, `SpeechConfig` selects the voice and rendering behavior:

```python
SpeechConfig(
    backend="piper",
    voice="en_US-kristin-medium",
    rate=165,
    stream=True,
    player="auto",
)
```

Cloud `openai` and `gemini` backends also accept `style`, such as
`"calm, concise, and conversational"`. Local engines use their voice and rate
settings instead. `player="auto"` lets zrb play renderable audio itself, which
allows it to pause and stop playback precisely while the user talks; a separate
player command can only stop the sentence currently being played.

When the built-in backends are not enough, implement `AnySpeechBackend`:

```python
import urllib.request

from zrb.llm.speech import AnySpeechBackend, SpeechConfig, enable_speech
from zrb.llm.speech.backend import create_wav_utterance


class LocalTTS(AnySpeechBackend):
    def create_utterance(self, text: str):
        request = urllib.request.Request(
            "http://localhost:5002/api/tts",
            data=text.encode(),
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return create_wav_utterance(response.read())


enable_speech(chat, SpeechConfig(enabled=True, backend=LocalTTS()))
```

A speech backend returns an utterance that zrb can queue, interrupt, and close.
If it also provides renderable audio, zrb can play that audio itself and report
when playback starts, which lets dictation distinguish zrb's voice from the
user's speech as accurately as the backend permits. See the complete backend
contract and fallback behavior in [Voice and Camera → Your own backend](voice-camera.md#your-own-backend).

## Attach voice to your own chat task

The voice features are opt-in on a custom task:

```python
from zrb import LLMChatTask
from zrb.llm.dictation import DictationConfig, enable_dictation
from zrb.llm.speech import SpeechConfig, enable_speech

chat = LLMChatTask(
    name="voice-assistant",
    system_prompt=(
        "You are a concise voice assistant. Lead with the answer, "
        "avoid reading tables aloud, and ask one question at a time."
    ),
)

enable_dictation(
    chat,
    DictationConfig(mode="hands_free", wake_words=["hey zrb"]),
)
enable_speech(
    chat,
    SpeechConfig(
        enabled=True,
        backend="piper",
        voice="en_US-kristin-medium",
    ),
)
```

`enable_dictation()` adds the recording commands and microphone trigger.
`enable_speech()` adds speech hooks, response streaming, and the speech-live
context. Both functions can also be used on task objects built by an
application; they do not require the built-in `llm_chat` task.

## Choosing the right extension point

| If you want to… | Use… |
|---|---|
| Change who the agent is or how it reasons | `system_prompt`, `PromptManager`, or a prompt file |
| Add a wake word or change interruption words | `DictationConfig` |
| Make the microphone transcribe with another service | A dictation backend or `DictationConfig(backend=...)` |
| Turn replies, approvals, questions, or progress into speech | `SpeechConfig(events=...)` |
| Change approval or progress wording | `SpeechConfig` message and phrase mappings |
| Change the voice, rate, style, or playback behavior | `SpeechConfig` |
| Send text to a different TTS service | `AnySpeechBackend` |
| Add a new spoken command or a voice-specific action | A custom command or trigger on `LLMChatTask` |
| Rewrite every final response immediately before TTS | Currently use the prompt/backend boundaries; there is no general public speech-text transformation hook |

For microphone setup, device permissions, and platform-specific failures, see
[Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

🔖 [Documentation Home](../../README.md) > [LLM](./) > Programming the Voice
