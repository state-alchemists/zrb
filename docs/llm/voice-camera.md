🔖 [Documentation Home](../README.md) > [LLM Integration](llm-integration.md) > Voice and Camera

# Voice and Camera

`zrb llm chat` can take a photo, take dictation, and read its replies aloud. Each is an optional feature added to the chat task with one call; the built-in `llm_chat` makes all three calls, so they work out of the box. For copy-pasteable setups and the Python extension points behind voice input, spoken responses, and TTS, see [Programming the Voice](programming-the-voice.md).

| Feature | Commands | Needs |
|---|---|---|
| Camera | `/photo [device]` | `ffmpeg` (on WSL, Windows' `ffmpeg.exe`), or Termux:API on Android |
| Dictation | `/voice`, `/handsfree` | `pip install 'zrb[voice]'` |
| Speech | `/speech` | nothing on macOS; Termux:API on Android; `espeak-ng` on Linux and Windows; a cloud key; or a local Pipecat voice |

To talk with zrb, `export ZRB_LLM_VOICE=conversation` (or `turns` to take turns without interrupting, `speak` to only hear replies). Every setting is an environment variable, listed in [LLM Voice and Camera configuration](../configuration/llm-voice-camera.md#voice-and-camera). Platform problems are covered in [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md).

## Table of Contents

- [Camera](#camera)
- [Dictation](#dictation)
- [Speech](#speech)
- [Talking with zrb](#talking-with-zrb)
- [Emotion](#emotion)
- [Configuring in code](#configuring-in-code)
- [Programming the Voice](programming-the-voice.md)
- [Your own backend](#your-own-backend)
- [On your own chat task](#on-your-own-chat-task)

## Camera

`/photo` captures one photo and attaches it to your next message, so you can say what to do with it: `/photo`, then "what does this error on my screen mean?". `/photo 1` picks a device; press Tab after `/photo ` to list them.

**Installing ffmpeg.** On a desktop, the photo is taken by `ffmpeg`, which zrb does not install: `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` (or your distribution's package) on Linux, `winget install Gyan.FFmpeg` on Windows. On WSL, install it **on Windows** with `winget`, then run `wsl --shutdown` and check `which ffmpeg.exe`: zrb runs `ffmpeg.exe` to take the photo on the Windows side, which holds the camera only for the photo, so Windows apps keep using it. If that check is still empty, [Voice & Photo Troubleshooting](voice-photo-troubleshooting.md#wsl-camera) covers that, and how to tell a camera Windows cannot see from one zrb cannot open. A Linux `ffmpeg` with usbipd-win is the fallback; see [the usbipd-win build](voice-photo-troubleshooting.md#fallback-usbipd-win-passthrough-with-a-custom-kernel).

**Letting the agent look.** With `ZRB_LLM_CAMERA_ENABLE_TOOL=on`, the agent also gets a `TakePhoto` tool: when you say "what do you think of this?" with something held up, it can take the photo itself. Every call asks for approval like `Shell` does, and plan mode denies it. To skip the prompt, add `auto_approve("TakePhoto")` to your tool policies (see [Customizing Tool Approval](tool-approval.md)).

**On a text-only model.** A photo from `/photo` and one from `TakePhoto` reach the model by the same rule:

| The main model | What it gets |
|---|---|
| Reads images | The photo itself |
| Is text-only, and `ZRB_LLM_MULTIMODAL_MODEL` reads images | A description of the photo, written by that model |
| Is text-only, with no such model | Nothing. `/photo` prints `❗ Dropped image attachment`; `TakePhoto` tells the agent it cannot see the photo and to ask you to set `ZRB_LLM_MULTIMODAL_MODEL` |
| Is one zrb does not know | The photo itself, since zrb cannot tell whether it reads images |

The description costs one call to the multimodal model per photo. See [LLM Models](../configuration/llm-models.md#core-llm-routing) for setting it.

## Dictation

**Push-to-talk.** Type `/voice` and talk. A pause of about a second, or `/voice` again, stops the recording. The transcript is inserted at the cursor, where you can edit it before pressing Enter. `/voice` works while the model is still answering.

**Hands-free.** `/handsfree` keeps the microphone open. Every utterance is sent as a turn, and while zrb waits for a tool approval, what you say answers it:

- "Yes", "yes please", "go ahead" approve.
- Anything else denies, and what you said becomes the reason: "no, use pytest instead" tells the agent what to do. A hedge or a "no" anywhere ("yes, but wait", "okay, no") never approves.
- An answer to a multiple-choice question picks the option you name, by its label or its number; for a question that takes several, name them all ("one and three", "cheese, olives").

Set `ZRB_LLM_DICTATION_MODE=hands_free` to start every session this way. Set `ZRB_LLM_DICTATION_WAKE_WORDS` so that only utterances starting with a wake word count. Without one, anything the microphone hears becomes a turn, including a conversation in the room.

**In a place with other people talking.** Speech has to be louder than the room's own background, measured over the couple of seconds before it (`ZRB_LLM_DICTATION_NOISE_MARGIN`, 2), so the room's conversation does not open a turn of its own; a room that never falls quiet is measured at its own level, which is what lifts the bar over it. `ZRB_LLM_DICTATION_MIN_WORDS` (1) is the fewest words an ordinary utterance needs, so raising it makes one stray word not enough. With the `vosk` backend, `ZRB_LLM_DICTATION_VOSK_CONFIDENCE` drops a transcript whose words vosk heard too faintly on average. None of these tells a stranger's request from yours — only a wake word does, which is why it is the answer in a public place. In a room loud enough that zrb keeps hearing its own voice, `ZRB_LLM_DICTATION_BARGE_IN_HOLD=off` takes the stutter out of barge-in (see barge-in below).

Everything heard while zrb is silent measures as the room, your own voice included — nothing in the audio tells it from a room's. In a quiet room a long sentence with no breath in it can therefore hold the bar over your next words until a breath is heard. Set `ZRB_LLM_DICTATION_NOISE_MARGIN=0` if you would rather the room never lift the bar at all.

By default zrb ignores the microphone while it is speaking, so its own voice is not taken as yours, and anything you say over it is lost.

### Talking over zrb (barge-in)

With `ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on`, the microphone keeps listening while zrb speaks. About a third of a second of speech over it (`ZRB_LLM_DICTATION_BARGE_IN_MIN_SPEECH`) pauses zrb at once. If what you said turns out to be words meant for zrb, it stops and the rest of that reply is not read; if not, zrb carries on where it paused. Words too brief to pause it (a crisp "stop") stop it as soon as they are transcribed. On speakers the microphone hears zrb too, so a room loud enough to keep crossing the bar is heard as a stutter of pauses and resumes; set `ZRB_LLM_DICTATION_BARGE_IN_HOLD=off` for barge-in without it — nothing is held on loudness, so zrb speaks on until the words are known to be meant for it, and a stop word or a wake word seen in the live transcript (`vosk` transcribes while you speak) stops it as soon as it is heard. Then:

What zrb makes of the words is settled in this order, and a model is asked only at the end:

| What you said | What happens |
|---|---|
| A stop word alone ("stop", "wait", "hold on", "cancel", "never mind"; `ZRB_LLM_DICTATION_STOP_WORDS`), with fillers ("uh", "hey"), polite words ("please") and a sentence said twice ignored, so "stop please" and "wait wait" count | zrb goes quiet **and the turn is cancelled**, exactly as Esc does. The words are sent nowhere |
| A hush word alone ("okay", "got it", "I got it", "enough"; `ZRB_LLM_DICTATION_HUSH_WORDS`) | zrb goes quiet, **the turn goes on**, and the words are sent nowhere: you understood, nothing more |
| A stop word first, then more ("hold on, use postgres") | The turn is cancelled and your words are sent as a new message |
| More than five words that match none of the above (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_MAX_WORDS`) | A request: zrb goes quiet and the turn goes on, taking your words into account at its next step |
| Up to five words that match none | The small model reads them (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED`) and answers stop, hush or request, within 2 seconds (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_TIMEOUT`). A stop in other words ("please fucking stop", a stop in another language) cancels the turn. Off, slow or failing, the answer is "request" |
| Something not starting with a wake word (wake words set) | Nothing: the badge says `ignored … (no wake word)` and zrb carries on |

While a tool approval is waiting, what you say answers it, as usual: "no" denies the tool call, not the turn. "No" is not a stop word, so over zrb with nothing waiting it is a request or goes to the model.

That is why the same "stop" sometimes cancels and sometimes only hushes: the first row is a string comparison, and the last rows race a clock. Cancelling a turn loses work, so when zrb cannot tell, it does not cancel. When you want a guaranteed cancel, say the stop word alone, or press Esc.

With wake words, zrb stops only once it has heard one. Talk in the room holds its voice like anything else heard over it, on loudness alone, and the words give that hold back when they turn out not to be the user's.

**zrb's own voice.** On speakers the microphone hears zrb too. The operating system can take it out ([Hearing zrb in what you say](#hearing-zrb-in-what-you-say)); zrb does not subtract it itself, since what an echo canceller leaves on laptop speakers, transcribed, would become turns zrb answers itself. Either way, what hands-free hears has to pass the checks below before it reaches the model. None of them compares the words heard against what zrb was saying, so a word of zrb's own reply, loud enough to clear the bar, can still open a turn — keep the volume down, or wear headphones. Push-to-talk keeps every word: its transcript lands in the input box for you to edit.

| Check | What it keeps out | Setting |
|---|---|---|
| Louder than zrb: speech over zrb must be several times louder than zrb's voice reaches the microphone (measured as it speaks, so it follows the volume and the room) | zrb's voice and room noise starting an utterance at all | `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` (3) |
| Not the transcriber guessing, in anything heard hands-free: Whisper's own scores for a segment that is likely silence or repeating itself, phrases Whisper writes for silence ("Thank you for watching."), and one phrase over and over ("and this and this") | Words made up from noise | — |
| At least two words over zrb, or (with barge-in on) while a turn runs, unless a stop word or an answer to the prompt being asked | One-word leftovers ("sleep", "well") | `ZRB_LLM_DICTATION_BARGE_IN_MIN_WORDS` (2) |

On headphones the microphone hears no zrb, so the bar stays at `ZRB_LLM_DICTATION_THRESHOLD`. Speak up a little over laptop speakers. zrb plays its speech itself when it can (`ZRB_LLM_SPEECH_PLAYER=auto`, the default with the `zrb[voice]` extra), so it can pause while you talk; speech a player program plays cannot pause, and only the sentence playing is stopped.

#### Hearing zrb in what you say

The checks above decide whether what was heard reaches zrb; they cannot clean it. When you talk over zrb on speakers, your words and zrb's arrive in the same audio, and the transcript mixes them: "remind me to call my sister" comes back as "remind me to call it will be sunny in the morning". Echo cancellation takes zrb's voice out of the microphone before anything is transcribed. Each platform has its own, and headphones need none.

| Platform | Echo cancellation | What to do |
|---|---|---|
| macOS | The system's voice processing (what calls use), which an app has to ask for | `ZRB_LLM_DICTATION_ENABLE_ECHO_CANCEL=on`, already on under `ZRB_LLM_VOICE=conversation` |
| Linux | PulseAudio's or PipeWire's echo-cancel module, the WebRTC canceller browsers use. Off on most distributions | Load it, below. Nothing in zrb changes |
| Windows | Many laptops' audio drivers cancel echo for every recording | Usually nothing; if zrb's words show up in yours, use headphones |

**macOS.** zrb opens the default microphone through voice processing, which cancels whatever the speakers play, so zrb's voice stays out of the transcript while yours comes through. It also evens out your level and quiets the room, and keeps other apps' audio at full volume. It works on the default microphone only: with `ZRB_LLM_DICTATION_DEVICE` set, or without `pyobjc-framework-AVFoundation` (part of `zrb[voice]`), the microphone opens as usual, and zrb logs why once. For the first second or two zrb speaks, the canceller is still learning the room, which the checks above cover. While zrb listens this way, another app recording the microphone without voice processing hears it very faintly, as during a call.

**Linux.** Load the module and make its microphone and speakers the defaults. zrb records from the default microphone and plays to the default speakers, so both go through it:

```bash
# PulseAudio, or PipeWire's pulse server (pipewire-pulse); lasts until logout
pactl load-module module-echo-cancel aec_method=webrtc \
  source_name=ec_source sink_name=ec_sink
pactl set-default-source ec_source
pactl set-default-sink ec_sink
```

To keep it on PipeWire, put the module in `~/.config/pipewire/pipewire.conf.d/echo-cancel.conf`, run `systemctl --user restart pipewire`, and make `ec_source` and `ec_sink` the defaults as above (or in your desktop's sound settings):

```
context.modules = [
  { name = libpipewire-module-echo-cancel
    args = {
      library.name = aec/libspa-aec-webrtc
      source.props = { node.name = "ec_source" node.description = "Echo-cancelled microphone" }
      sink.props   = { node.name = "ec_sink" node.description = "Echo-cancelled speakers" }
    }
  }
]
```

The canceller removes only what it played, so zrb's voice must reach the speakers through `ec_sink`, and the microphone must be `ec_source`:

- Leave `ZRB_LLM_DICTATION_DEVICE` empty, or name `ec_source` (or `pulse`); a `hw:` device skips the canceller.
- zrb plays through the default speakers itself with `zrb[voice]`. Without it, a player program plays the speech, and `aplay` on a system whose ALSA default is not routed through PulseAudio or PipeWire skips the canceller.

**Transcribing while you speak.** vosk transcribes an utterance as you say it, and the status bar shows the last words heard. Once you pause for half a second (`ZRB_LLM_DICTATION_MIN_SILENCE`) once words have been heard, the utterance ends. The other backends transcribe the whole utterance after it ends and always wait the full second.

A line above the status bar shows what the microphone is doing, while hands-free is on:

| Badge | Meaning |
|---|---|
| `🎤 listening` | Waiting for you to speak |
| `👂 hearing you…` | You are speaking |
| `👂 …run the tests` | The last words heard so far (vosk) |
| `📝 transcribing…` | Turning what you said into text |
| `🎤 heard "Yes." · listening` | What it heard last; it is listening again |
| `🔇 mic paused while speaking` | zrb is talking; what you say now is not heard |
| `✋ paused · listening…` | You talked over zrb; it paused until it knows whether that was words. With `ZRB_LLM_DICTATION_BARGE_IN_HOLD=off` it keeps speaking instead, so this badge is not shown |
| `✋ interrupted · go on…` | It was words: zrb stopped (barge-in) |
| `✋ stopped · listening` | You said "stop" over it; the turn was cancelled |
| `🎤 ignored "…" (no wake word)` | Heard, but it did not start with a wake word |
| `🎤 ignored "…" (the transcriber guessing at noise)` | Words the transcriber made up from noise |
| `🎤 ignored "…" (too few words to interrupt)` | One word over zrb, or over a running turn, that was not a stop word or an answer |

Push-to-talk shows `🔴 recording…` and `📝 transcribing…` the same way.

The default transcriber is vosk, which runs offline and downloads its model on first use, but mangles technical terms. It is also the only one that transcribes while you speak. Three more run offline through Pipecat, each needing the package it ships in ([the installs](#your-own-backend)): `ZRB_LLM_DICTATION_BACKEND=whisper` runs Faster-Whisper, multilingual and the heaviest of the three, sized with `ZRB_LLM_DICTATION_STT_MODEL` (`tiny`, `base`, `small`, `medium`, `large-v3`); `moonshine` is the lightest and the only one with no GPU path at all; `funasr` is strongest on Chinese. `ZRB_LLM_DICTATION_BACKEND=sensevoice` runs the same SenseVoice model on sherpa-onnx instead of PyTorch, which is many times faster on a CPU (`pip install sherpa-onnx huggingface_hub`). Its model, too, downloads once and is read from the local cache afterwards. While a transcriber or the emotion model loads, the chat shows a 🎤 loading line, then `✅ <name> ready` once it is loaded, or `❗ <name> failed to load` with the reason. With an OpenAI key, `ZRB_LLM_DICTATION_BACKEND=openai` and `ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe` are far more accurate. [`examples/voice-interaction`](../../examples/voice-interaction/README.md) compares the backends on one clip.

## Speech

Speech starts off. Turn it on with `ZRB_LLM_SPEECH_ENABLED=on`, or with `/speech` during a session. zrb then reads aloud:

- the reply (not a sub-agent's), a sentence at a time while the model writes it,
- a tool call that starts after a silence, so a long one is not silent,
- "I need to write a file /tmp/a.py. I need your approval." when a tool waits for approval — not read if you answer first, and cut off if you answer while it is being read,
- a question the agent asks you.

**Speaking as it writes.** A reply is read a sentence at a time while the model is still writing it, and what it writes before a tool call ("Let me run the tests.") is read when the call starts. Code, tables and links are not read. By default it is read whole, however long it is; see *Summarizing a long reply* below to shorten it. The next sentence's audio is made while the current one plays, so a cloud voice has no gap between sentences.

With `ZRB_LLM_SPEECH_STREAM=off`, the reply is read once the turn ends instead, whole in one go.

**Summarizing a long reply.** Set `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` (default `0`, off) to a length such as `600`, and a reply whose speakable text is longer is spoken as a two-to-four-sentence summary from the small model instead (`ZRB_LLM_SPEECH_SUMMARY_MODEL`, else `ZRB_LLM_SMALL_MODEL`, else the main model); the reply on screen is unchanged. A summary needs the finished reply, so while this is set the reply is **not** streamed, whatever `ZRB_LLM_SPEECH_STREAM` says: a short reply is read whole and a long one summarized, once the turn ends. If the model fails or takes longer than `ZRB_LLM_SPEECH_SUMMARY_TIMEOUT` (15 seconds), the reply is read whole.

**Saying what it is doing.** A tool call that starts after 8 seconds of silence (`ZRB_LLM_SPEECH_PROGRESS_INTERVAL`) is announced: "Running a command.", "Searching the code." Nothing is announced while zrb is speaking, and an announcement still waiting when its tool finishes is dropped. Take `progress` out of `ZRB_LLM_SPEECH_EVENTS` to turn it off.

While speech is on, the model is told its reply is heard, so it opens with the answer in a sentence or two and puts code and detail after it.

Switching speech off with `/speech` drops whatever has not been said yet.

**How it sounds.** The `openai` and `gemini` voices take a direction in plain words, `ZRB_LLM_SPEECH_STYLE`. By default it asks for a capable colleague talking you through the work: warm, clear, conversational, engaged but not theatrical. Change it to taste ("brisk and matter-of-fact", "calm and slow") or set it empty for the voice's default manner. The direction is never read aloud. The local engines (`say`, `espeak-ng`, Termux) ignore it; their `ZRB_LLM_SPEECH_RATE` and voice are what you can change.

The `openai` backend starts playing as the audio arrives, through a player that reads standard input (`paplay`, `aplay` or `ffplay`), so a long reply starts as soon as a short one does. With `ZRB_LLM_SPEECH_WAV_PLAYER` set, or only `afplay`, it waits for the whole file.

Three local voices run through Pipecat, each needing the package it ships in ([the installs](#your-own-backend)): `ZRB_LLM_SPEECH_BACKEND=piper` is the lightest and has the widest voice catalogue, `kokoro` is a fixed list of neural voices rather than a catalogue, and `pocket` is the one that clones a voice from a sample or a `.wav` you name. Their model downloads on first use and runs offline afterwards, and a service whose package is missing says which package to install instead of failing on a module import.

Each chat session gets its own speaker, microphone and hands-free flag, so one session switching speech off does not silence the next. Two zrb processes still take turns rather than talk over each other, through a lock file that a session claims while it is speaking and releases when it is closed.

Speech rides on the hook subsystem, so it needs hooks on: with `ZRB_HOOKS_ENABLED=off` nothing is spoken, and enabling speech says so. Each session's speaker, microphone and hooks are closed when that session ends — on exit in the terminal, on removal in the web chat — so a long-lived server does not accumulate them.

## Talking with zrb

`/speech` and `/handsfree` together make a voice conversation: you speak, and zrb answers aloud as it writes. To start every session that way:

```bash
ZRB_LLM_SPEECH_ENABLED=on ZRB_LLM_DICTATION_MODE=hands_free zrb llm chat
```

Add `ZRB_LLM_DICTATION_BARGE_IN_ENABLED=on` to talk over it, on speakers or headphones (see barge-in under [Dictation](#dictation)).

For the quickest replies, use vosk for dictation (it transcribes while you speak and ends an utterance half a second after you finish) and a fast model. Each part's delay can be tuned with the variables above.

## Emotion

With emotion on, zrb's replies carry how it feels, which picks the voice they are read in, and it hears the tone of a dictated message:

```bash
ZRB_LLM_EMOTION_ENABLED=on ZRB_LLM_DICTATION_DETECT_EMOTION=on ZRB_LLM_DICTATION_BACKEND=sensevoice zrb llm chat
```

`ZRB_LLM_DICTATION_DETECT_EMOTION` has emotion2vec+ hear your tone in each hands-free utterance while it is transcribed, locally and with any backend (`pip install funasr torch`). Your words stay as you said them: the tone rides on the turn, and the model reads it in its live context as how you sounded and how sure the detector is. Zaruba's own emotion is the emoji it opens its reply with. Each, yours and its, fires the `Emotion` hook, which an avatar such as zrb-face listens to ([Hooks → Emotion](hooks.md#emotion)). Recognition is reliable for happy, angry and sad, and rough beyond that. The model downloads from Hugging Face on first use and is read from the local cache afterwards, with no network needed.

## Configuring in code

Each feature has a config dataclass whose fields mirror its environment variables; a field left `None` reads the variable when a session starts. To change the built-in chat from a `zrb_init.py`, assign directly to `CFG`:

```python
from zrb import CFG

CFG.LLM_SPEECH_ENABLED = True
CFG.LLM_DICTATION_WAKE_WORDS = ["hey zed"]
```

You can also set environment variables (`os.environ`), but direct assignment to `CFG` is cleaner and ensures the values are serialized correctly. Settings are read when the session starts, so changes after `import zrb` still apply.

**Everything is a setting.** Every word zrb listens for and every phrase it says, apart from the status-bar badges, is a variable in [LLM configuration § Voice and Camera](../configuration/llm-voice-camera.md#voice-and-camera):

- **Words it listens for:** wake words, approve and deny words, stop words, and the polite words a yes or a no may carry. The defaults are English; set them for your language.
- **What it says:** the approval request and each tool's action in it, every progress line and the tools it keeps quiet about, the question notice, and the note after a cut reply. The two per-tool tables are JSON objects of tool-name patterns (`{"Read": "Membaca berkas.", "*": "Memakai {tool}."}`).
- **Prompts:** the transcription instruction for `google` and `multimodal`, Gemini's reading prompts, and the prompt files `speech_live` and `multimodal_audio` (through `ZRB_LLM_PROMPT_DIR`).
- **Timing:** every listening duration, the microphone block size, playback block and read-ahead, and timeouts.

## Your own backend

Each feature takes a backend name or an object implementing its interface:

| Feature | Interface | Built-in names |
|---|---|---|
| Camera | `zrb.llm.camera.AnyCameraBackend` — `async capture(device) -> bytes \| None` | `auto`, `termux`, `ffmpeg` |
| Dictation | `zrb.llm.dictation.AnyDictationBackend` — `async transcribe(audio) -> str`; optionally `async create_stream() -> AnyTranscriptionStream \| None` to transcribe while the user speaks | `vosk`, `openai`, `google`, `multimodal`, `sensevoice`, and the local Pipecat services `whisper`, `moonshine`, `funasr` |
| Speech | `zrb.llm.speech.AnySpeechBackend` — `create_utterance(text) -> Utterance` (an `Utterance` subclass overriding `play` calls `report_started()` once sound starts, so dictation knows zrb is heard); optionally `create_audio(text) -> SpeechAudio \| None` so zrb plays it itself (and can pause it while you talk) | `auto`, `termux`, `say`, `espeak-ng`, `openai`, `gemini`, and the local Pipecat services `kokoro`, `piper`, `pocket` |

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

**The local Pipecat services.** `whisper`, `moonshine`, `funasr`, `kokoro`, `piper` and `pocket` run their model on your machine. The `zrb[voice]` extra brings Pipecat itself but none of their model packages, and each is a Pipecat extra of its own:

| Name | Named by | Install |
|---|---|---|
| `whisper` | `ZRB_LLM_DICTATION_BACKEND` | `pip install 'pipecat-ai[whisper]'` |
| `moonshine` | `ZRB_LLM_DICTATION_BACKEND` | `pip install 'pipecat-ai[moonshine]'` |
| `funasr` | `ZRB_LLM_DICTATION_BACKEND` | `pip install 'pipecat-ai[funasr]'`, and PyTorch |
| `kokoro` | `ZRB_LLM_SPEECH_BACKEND` | `pip install 'pipecat-ai[kokoro]'`, on Python 3.13 or older |
| `piper` | `ZRB_LLM_SPEECH_BACKEND` | `pip install 'pipecat-ai[piper]'` |
| `pocket` | `ZRB_LLM_SPEECH_BACKEND` | `pip install 'pipecat-ai[pocket-tts]'`, and PyTorch |

Each model downloads once on first use and runs offline afterwards. `piper` carries wheels for Linux on glibc 2.17 and newer, both macOS architectures, and Windows; `moonshine` has no x86-64 macOS wheel; and none of the six ships a native-Termux wheel, so Termux keeps `vosk` for dictation and `termux`/`say`/`espeak-ng` for speech. `kokoro` cannot be installed on Python 3.14 at all — `kokoro-onnx`, the package it runs on, declares `requires_python <3.14` — so name `piper` or `pocket` there.

**A service of your own.** A name can also resolve to a service you register, which is how a vendor SDK goes in without zrb choosing anything for you. A registration replaces a Pipecat built-in of the same name without giving up the built-ins beside it (names zrb implements itself, such as `openai` or `vosk`, cannot be replaced this way), from `zrb_init.py`:

```python
from zrb import tts_manager
from zrb.llm.voice.spec import TTSServiceSpec

tts_manager.register(
    "my-voice",
    TTSServiceSpec(
        name="my-voice",
        provider="my_voice_sdk",
        factory=lambda config: MyTTSService(api_key="...", voice=config.voice),
    ),
)
```

then `ZRB_LLM_SPEECH_BACKEND=my-voice`. `provider` is the package the service imports, and is what tells zrb whether it can be built here. `stt_manager` and the two registries behind the managers come from `zrb.llm.voice`. [Programming the Voice → Use any Pipecat STT or TTS service](programming-the-voice.md#use-any-pipecat-stt-or-tts-service) has a worked cloud example and what a service must do to work here.

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

The three features are built only from `LLMChatTask`'s public extension points — `append_custom_command`, `append_trigger`, `append_hook_factory`, `append_stream_observer` — so the same shapes are open to your own features. A stream observer is called with every event a run streams, text deltas included, after the UI. [LLMChatTask → Triggers & Custom Commands](../task-types/llmchat-task.md#triggers--custom-commands) describes them.

🔖 [Documentation Home](../README.md) > [LLM Integration](llm-integration.md) > Voice and Camera
