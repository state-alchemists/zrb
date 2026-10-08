🔖 [Documentation Home](../README.md) > [LLM](./) > Programming the Voice

# Programming the Voice

A voice assistant has three separate pieces: it hears speech, decides what the
agent should do, and turns the agent's output into audio. Zrb exposes each
piece independently. Use `DictationConfig` to program voice input, `SpeechConfig`
to program spoken interaction, and `AnySpeechBackend` when you need to replace
text-to-speech itself.

This page is the practical companion to [Voice and Camera](voice-camera.md):
it starts with working configurations, then shows the Python extension points.
The exhaustive environment-variable reference is [LLM Configuration → Voice
and Camera](../configuration/llm-config.md#21-voice-and-camera).

## Table of contents

- [A local conversation](#a-local-conversation)
- [Voice recipes](#voice-recipes)
- [The three programming layers](#the-three-programming-layers)
- [Program voice input](#program-voice-input)
- [Program spoken responses](#program-spoken-responses)
- [Program audio rendering](#program-audio-rendering)
- [Attach voice to your own chat task](#attach-voice-to-your-own-chat-task)
- [Use any Pipecat STT or TTS service](#use-any-pipecat-stt-or-tts-service)
- [Choosing the right extension point](#choosing-the-right-extension-point)

## A local conversation

This is a practical starting point for a hands-free conversation on a noisy
room microphone: Moonshine transcribes each finished utterance, Piper speaks
locally, and barge-in stays possible without pausing speech on every loud sound.

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
| `ZRB_LLM_DICTATION_BARGE_IN_HOLD=off` | Keeps barge-in without pausing speech whenever loud audio crosses the bar. A stop word or wake word stops zrb once the utterance is transcribed; it lands while you are still speaking only with `vosk`. |
| `ZRB_LLM_DICTATION_BACKEND=moonshine` | Uses a local Pipecat speech-to-text service, which transcribes a finished utterance. |
| `ZRB_LLM_DICTATION_STT_MODEL=medium-streaming` | Selects the Moonshine model variant to run. |
| `ZRB_LLM_SPEECH_BACKEND=piper` | Uses local text-to-speech instead of a cloud voice. |
| `ZRB_LLM_SPEECH_VOICE=en_US-kristin-medium` | Selects the Piper voice. |
| `ZRB_LLM_DICTATION_WAKE_WORDS=...` | Limits hands-free turns to utterances beginning with one of the configured spellings. |

**Live interruption needs `vosk`.** Moonshine, like the other Pipecat services
and the cloud backends, transcribes the utterance after you stop speaking, so a
stop word or a wake word takes effect only then — the barge-in it triggers still
works, just a beat later. `vosk` is the only built-in backend that transcribes
while you speak, so switch `ZRB_LLM_DICTATION_BACKEND` to `vosk` when a stop word
must land the moment it is said.

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

`vosk` is the only built-in backend that transcribes while you speak: it
exposes a streaming transcription interface, so a stop word or wake word can be
acted on before the utterance ends. Every other backend — the Pipecat services
(`whisper`, `moonshine`, `funasr`) and the cloud backends (`openai`, `google`,
`multimodal`) — transcribes the finished utterance, so those words take effect
only after it ends.

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
    # Read only when a question carries no text of its own.
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
- `question` — a question raised by the agent or UI; its own text is read, and
  `question_message` is used only when it has none;
- `progress` — a tool call announced after the configured silence interval.

`approval_message` supports `{action}` and `{target}`. The action and progress
maps use tool-name patterns, with `*` and `?` wildcards; the first matching
pattern wins. These are templates for fixed UI events, not additional model
calls, so they are predictable and inexpensive.

For a response's general tone and structure, use the agent's `system_prompt`
or the `speech_live` prompt. `approval_message`, `approval_actions`,
`progress_phrases` and `question_message` control words zrb composes itself, so
they take effect exactly as written. They do not rewrite an existing question: a
question that carries text is read as the agent or UI wrote it, and only an empty
one falls back to `question_message`. To change those words, change the message
where it is produced, or intercept it with a hook.

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
import json
import urllib.request

from zrb.llm.speech import AnySpeechBackend, SpeechConfig, enable_speech
from zrb.llm.speech.backend import create_wav_utterance


class LocalTTS(AnySpeechBackend):
    def create_utterance(self, text: str):
        request = urllib.request.Request(
            "http://localhost:5002/api/tts",
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
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

## Use any Pipecat STT or TTS service

zrb's speech and dictation run on [Pipecat](https://docs.pipecat.ai) services, so any provider Pipecat supports can be used: see Pipecat's lists of [speech-to-text](https://docs.pipecat.ai/api-reference/server/services/supported-services#speech-to-text) and [text-to-speech](https://docs.pipecat.ai/api-reference/server/services/supported-services#text-to-speech) services, plus community packages such as Floe. Three steps:

1. Install `zrb[voice]` (it brings `pipecat-ai`), then the provider's extra or package — the provider's Pipecat page names it (`pip install "pipecat-ai[elevenlabs]"`, `pip install pipecat-floe`) — and set the API key it reads.
2. In `zrb_init.py`, register a factory that builds the service, under a name of your choosing: `tts_manager` for text-to-speech, `stt_manager` for speech-to-text.
3. Select it by that name with `ZRB_LLM_SPEECH_BACKEND` or `ZRB_LLM_DICTATION_BACKEND` (or `SpeechConfig(backend=...)` / `DictationConfig(backend=...)` in code).

OpenAI and Gemini need none of this: `openai` and `gemini` (and `openai` / `google` for dictation) are built-in backends, selected by name with no registration — see [Voice and Camera](voice-camera.md). This section is for the providers zrb does not cover.

This registers [Floe](https://docs.pipecat.ai/api-reference/server/services/tts/floe) for both directions (`pip install pipecat-floe`, and `FLOE_API_KEY` set):

```python
from zrb import stt_manager, tts_manager
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec


def create_floe_tts(config):
    from pipecat_floe import FloeTTSService  # imported only when selected

    return FloeTTSService(model="openai/tts-1", voice=config.voice or "alloy")


def create_floe_stt(config):
    from pipecat_floe import FloeSTTService

    return FloeSTTService(model="deepgram/nova-3", language=config.language or "en")


tts_manager.register(
    "floe",
    TTSServiceSpec(
        name="floe",
        provider="pipecat_floe",
        is_local=False,
        doc="Floe, OpenAI-compatible voices",
        factory=create_floe_tts,
    ),
)
stt_manager.register(
    "floe",
    STTServiceSpec(
        name="floe",
        provider="pipecat_floe",
        is_local=False,
        doc="Floe, streaming transcription",
        factory=create_floe_stt,
    ),
)
```

```bash
export ZRB_LLM_SPEECH_BACKEND=floe      # text-to-speech
export ZRB_LLM_DICTATION_BACKEND=floe   # speech-to-text
export ZRB_LLM_SPEECH_VOICE=nova        # reaches the factory as config.voice
zrb llm chat
```

The two registries are separate, so one name can mean a TTS and an STT service at once, and you can mix providers — Floe for speech, a local `whisper` for dictation. Any other provider follows the same shape: import its class from `pipecat.services.<provider>.tts` or `.stt` (or its own package) inside the factory and return an instance.

Many Pipecat services take a `Settings` object instead of keyword arguments. Set only what zrb's config names, so an unset model or language keeps the service's own default. Check how the service finds its API key, too: Groq's speech-to-text, below, is built on the OpenAI client and does not read `GROQ_API_KEY` by itself:

```python
import os

from zrb import stt_manager
from zrb.llm.voice.spec import STTServiceSpec


def create_groq_stt(config):
    from pipecat.services.groq.stt import GroqSTTService

    settings = GroqSTTService.Settings()
    if config.stt_model:
        settings.model = config.stt_model
    if config.language:
        settings.language = config.language
    return GroqSTTService(api_key=os.environ["GROQ_API_KEY"], settings=settings)


stt_manager.register(
    "groq",
    STTServiceSpec(
        name="groq",
        provider="openai",  # the client it imports
        is_local=False,
        doc="Groq's hosted Whisper",
        factory=create_groq_stt,
    ),
)
```

| Spec field | Meaning |
|---|---|
| `name` | The name the env var or `backend=` selects |
| `factory` | Called with the resolved `SpeechConfig` or `DictationConfig` when the service is first needed; returns the Pipecat service. Read `config.voice`, `config.language` or `config.stt_model` from it so the usual settings keep working |
| `provider` | The importable module the service needs. If it is missing, zrb names it instead of failing inside the factory |
| `is_local`, `doc` | How the service is labelled when zrb lists the choices |

Pick a name zrb does not already handle itself. A registration replaces a Pipecat built-in of the same name (`kokoro`, `piper`, `pocket`; `whisper`, `moonshine`, `funasr`), but the backends zrb implements directly are matched first, so a service registered as `auto`, `termux`, `say`, `espeak-ng`, `openai` or `gemini` for speech, or `vosk`, `openai`, `google` or `multimodal` for dictation, is never used.

Import the provider inside the factory, as above: `zrb_init.py` loads on every `zrb` command, and Pipecat takes seconds to import.

### Which services fit

zrb drives a service in its own small pipeline rather than a Pipecat transport.

**Text-to-speech: every Pipecat TTS service fits.** zrb sends one sentence at a time, plays the returned audio at its own sample rate, and ends the sentence at `TTSStoppedFrame`. Pipecat's TTS services all emit it (or set `push_stop_frames=True`); a service you write yourself must do the same, or each sentence waits 60 seconds before it is cut off.

**Speech-to-text: segmented services fit as they are.** zrb cuts the microphone audio into finished utterances itself, sends one at a time framed by `VADUserStartedSpeakingFrame` and `VADUserStoppedSpeakingFrame`, and takes the first final `TranscriptionFrame` as the whole utterance. In Pipecat 1.12 these are segmented (`SegmentedSTTService`):

| Provider | Class |
|---|---|
| OpenAI | `pipecat.services.openai.stt.OpenAISTTService` |
| Groq (Whisper) | `pipecat.services.groq.stt.GroqSTTService` |
| ElevenLabs | `pipecat.services.elevenlabs.stt.ElevenLabsSTTService` |
| AssemblyAI | `pipecat.services.assemblyai.stt.AssemblyAISyncSTTService` |
| Fal (Wizper) | `pipecat.services.fal.stt.FalSTTService` |
| Moonshine, Whisper, FunASR | built in: `moonshine`, `whisper`, `funasr` |

A streaming service — Deepgram, AssemblyAI's and ElevenLabs' realtime ones, Cartesia, Gladia, Soniox, Floe and most WebSocket services — fits only if it finalizes its transcript when it sees the stop frame. One that waits for its server's own end-of-speech detection may answer late or with only the first phrase of the utterance. Test a streaming service on your own audio before relying on it, and switch to a segmented one if transcripts arrive late or cut short. Live interruption while you are still speaking needs `vosk` either way.

A service that is not built on Pipecat at all is a different extension point: implement [`AnySpeechBackend`](#program-audio-rendering) for speech or `AnyDictationBackend` for dictation.

## Choosing the right extension point

| If you want to… | Use… |
|---|---|
| Change who the agent is or how it reasons | `system_prompt`, `PromptManager`, or a prompt file |
| Add a wake word or change interruption words | `DictationConfig` |
| Make the microphone transcribe with another service | A [registered Pipecat STT service](#use-any-pipecat-stt-or-tts-service), or an `AnyDictationBackend` for one outside Pipecat |
| Turn replies, approvals, questions, or progress into speech | `SpeechConfig(events=...)` |
| Change approval or progress wording | `SpeechConfig` message and phrase mappings |
| Change a question's wording | The agent or UI that produced it; `SpeechConfig(question_message=...)` covers only a question with no text |
| Make a stop word act while you are still speaking | `vosk`; every other backend transcribes the finished utterance first |
| Change the voice, rate, style, or playback behavior | `SpeechConfig` |
| Send text to a different TTS service | A [registered Pipecat TTS service](#use-any-pipecat-stt-or-tts-service), or `AnySpeechBackend` for one outside Pipecat |
| Add a new spoken command or a voice-specific action | A custom command or trigger on `LLMChatTask` |
| Rewrite every final response immediately before TTS | Currently use the prompt/backend boundaries; there is no general public speech-text transformation hook |

For microphone setup, device permissions, and platform-specific failures, see
[Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

🔖 [Documentation Home](../README.md) > [LLM](./) > Programming the Voice
