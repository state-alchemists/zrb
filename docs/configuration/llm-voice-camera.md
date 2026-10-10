🔖 [Documentation Home](../README.md) > [Configuration](./) > [LLM Configuration](llm-config.md) > Voice and Camera

# LLM Voice and Camera

Dictation, spoken replies, and the camera.

## Table of Contents

- [Voice and Camera](#voice-and-camera)
  - [Voice preset](#voice-preset)
  - [Dictation (speech-to-text)](#dictation-speech-to-text)
  - [Speech (text-to-speech)](#speech-text-to-speech)
  - [Camera](#camera)

---

## Voice and Camera

Three optional features of `zrb llm chat`, each added with one call and read from these variables **when a session starts**, so `zrb_init.py` may change them after importing zrb. A setting passed to `CameraConfig`, `DictationConfig` or `SpeechConfig` in code wins over its variable; see [Voice and camera](../llm/voice-camera.md) for that, [Programming the Voice](../llm/programming-the-voice.md) for recipes and Python extension points, and [Voice & Photo Troubleshooting](../llm/voice-photo-troubleshooting.md) for platform setup. Audio dependencies (sounddevice, numpy, vosk) load only when the microphone first opens, costing nothing at startup.

### Voice preset

Most sessions need only one setting. `ZRB_LLM_VOICE` sets how a session talks with you by moving the defaults of the three settings that decide it; any of the three set on its own still wins.

| `ZRB_LLM_VOICE` | Replies read aloud (`ZRB_LLM_SPEECH_ENABLED`) | Always listening (`ZRB_LLM_DICTATION_MODE`) | Talk over zrb (`ZRB_LLM_DICTATION_BARGE_IN_ENABLED`) |
|---|---|---|---|
| `off` (default) | `off` | `ptt` | `off` |
| `speak` | `on` | `ptt` | `off` |
| `turns` | `on` | `hands_free` | `off` |
| `conversation` | `on` | `hands_free` | `on` |

```bash
export ZRB_LLM_VOICE=conversation   # talk with zrb, and interrupt it
```

### Dictation (speech-to-text)

`/voice` starts recording; a pause or `/voice` again stops it, and the transcript lands in the input box. `/handsfree` switches to always listening: each utterance is submitted as a turn, or answers the tool approval or question being asked. With speech on too (`/speech`), that is a voice conversation (see [Voice and camera § Talking with zrb](../llm/voice-camera.md#talking-with-zrb)).

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_DICTATION_MODE` | Mode a session starts in: `ptt` or `hands_free` | `ptt`, or as `ZRB_LLM_VOICE` sets it |
| `ZRB_LLM_DICTATION_COMMANDS` | Aliases that start and stop a push-to-talk recording | `/voice, /v` |
| `ZRB_LLM_DICTATION_HANDS_FREE_COMMANDS` | Aliases that switch hands-free on and off | `/handsfree` |
| `ZRB_LLM_DICTATION_BACKEND` | Speech-to-text service: `vosk` (offline, and the only one that transcribes while you speak), `whisper` / `moonshine` / `funasr` (local, on Pipecat), `openai`, `google`, or `multimodal` (uses `ZRB_LLM_MULTIMODAL_MODEL`) | `vosk` |
| `ZRB_LLM_DICTATION_STT_MODEL` | Which model of the named local service to run, e.g. `small` for `whisper` or `medium-streaming` for `moonshine`; empty uses the service's own default. Ignored by `vosk`, `openai`, `google` and `multimodal` | (empty) |
| `ZRB_LLM_DICTATION_WAKE_WORDS` | Comma-separated; in hands-free mode only utterances starting with one count. Said alone, one accepts the next utterance within `ZRB_LLM_DICTATION_WAKE_WINDOW` seconds | (none) |
| `ZRB_LLM_DICTATION_WAKE_WINDOW` | Seconds a lone wake word keeps listening | `8.0` |
| `ZRB_LLM_DICTATION_THRESHOLD` | RMS microphone level that counts as speech (`zrb voice mic-test` in `examples/voice-interaction` measures yours) | `0.01` |
| `ZRB_LLM_DICTATION_NOISE_MARGIN` | How many times louder than the room's own background speech must be to be heard at all, so a conversation going on around the microphone does not open a turn. It follows the room: it changes nothing in a quiet one, and lifts the bar over the noise in a loud one. Your own speech heard while zrb is silent measures as the room too, so a long sentence with no breath in it can hold the bar over your next words until one is heard. `0` counts the room not at all | `2.0` |
| `ZRB_LLM_DICTATION_SILENCE` | Seconds of silence that end an utterance; at least one block (`ZRB_LLM_DICTATION_BLOCK_DURATION`) | `1.0` |
| `ZRB_LLM_DICTATION_MIN_SILENCE` | With a backend that transcribes while you speak (`vosk`), seconds of silence that end an utterance once it has words; `0` always waits `ZRB_LLM_DICTATION_SILENCE` | `0.5` |
| `ZRB_LLM_DICTATION_MIN_SPEECH` | Shortest speech kept, in seconds; shorter is a cough or a click | `0.25` |
| `ZRB_LLM_DICTATION_MIN_WORDS` | Fewest words a hands-free utterance needs to reach the model when it is not interrupting zrb (`ZRB_LLM_DICTATION_BARGE_IN_MIN_WORDS` applies there); raise it in a public place, where a stranger's single word would otherwise open a turn. A stop word, a yes/no, or an answer to the prompt being asked always counts | `1` |
| `ZRB_LLM_DICTATION_MAX_UTTERANCE` | Longest utterance, in seconds; `0` means no limit | `30.0` |
| `ZRB_LLM_DICTATION_MAX_BACKLOG` | Seconds of hands-free audio kept while an utterance is being transcribed, so what you say meanwhile is not lost; older audio is dropped. `0` means no limit | `30.0` |
| `ZRB_LLM_DICTATION_PRE_ROLL` | Seconds kept from before speech is detected, so the first word is not clipped; `0` keeps none | `0.3` |
| `ZRB_LLM_DICTATION_BARGE_IN_ENABLED` | `on` lets hands-free hear you while zrb speaks, on speakers too: zrb's voice is held at once, stops if what you said is words meant for it, and carries on if not. Speech over zrb must be `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` times louder than zrb's voice reaches the microphone and at least `ZRB_LLM_DICTATION_BARGE_IN_MIN_WORDS` words. `off`: the microphone stays deaf while zrb speaks, and you take turns | `off`, or as `ZRB_LLM_VOICE` sets it |
| `ZRB_LLM_DICTATION_BARGE_IN_HOLD` | With barge-in on, whether speech heard over zrb holds its voice at once, before anything about it is known. `on`: zrb is paused as soon as the microphone hears loud speech over it, and the words then stop it or give the pause back — on speakers, zrb's own voice crossing the bar is heard as a brief stutter. `off`: nothing is held on loudness; a stop word or a wake word seen in the live transcript of a backend that transcribes while you speak (`vosk`) stops zrb as soon as it is heard, and anything else stops it once the utterance is transcribed, so a room loud enough to keep crossing the bar cannot make zrb stutter. Barge-in itself is unchanged either way | `on` |
| `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` | With barge-in on, how many times louder than zrb's own voice, as the microphone hears it (the median over its last few seconds), speech over zrb must be (3 is about 10 dB). It follows the volume and the room; on headphones zrb is not heard and `ZRB_LLM_DICTATION_THRESHOLD` applies | `3.0` |
| `ZRB_LLM_DICTATION_BARGE_IN_MIN_WORDS` | With barge-in on, the fewest words said over zrb, or while a turn runs, that reach it; fewer are taken for zrb's own voice or noise, and zrb carries on. A stop word, or an answer to the prompt being asked, always counts | `2` |
| `ZRB_LLM_DICTATION_BARGE_IN_MIN_SPEECH` | Seconds of speech over zrb's voice that pause it, so a click does not; it then stops only if what was said has words. Shorter words over zrb (a crisp "stop") do not pause it, but still stop it once transcribed | `0.3` |
| `ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED` | With barge-in on, whether the small model is asked what an interrupting utterance asks of zrb, so "please fucking stop", the same stop said twice, or a stop in another language cancels the turn instead of reaching the model. The word lists answer first, for free, and stand when the model is slow, unconfigured or unsure. `off`: the word lists decide alone | `on` |
| `ZRB_LLM_DICTATION_INTERRUPT_JUDGE_MODEL` | Model that decides that. Empty uses the small model (`ZRB_LLM_SMALL_MODEL`, else the main model). A cloud model costs a round trip on the words that stop zrb, so a fast local one answers sooner | |
| `ZRB_LLM_DICTATION_APPROVE_WORDS` | Phrases that approve a tool approval when a hands-free answer is made only of them and polite words ("yes please"). Any other answer denies it, with what was said as the reason | `yes, yeah, yep, ok, okay, sure, approve, accept, go ahead, do it` |
| `ZRB_LLM_DICTATION_DENY_WORDS` | Phrases that deny a tool approval when a hands-free answer is made only of them and polite words ("no thanks") | `no, nope, deny, cancel, stop, don't` |
| `ZRB_LLM_DICTATION_STOP_WORDS` | Phrases that, said alone over zrb or while a turn runs with barge-in on, stop zrb speaking and cancel the turn instead of reaching the model. A list of their own, so "no" can deny an approval without stopping anything. Anything else said over zrb is put to the small model when it reads as a stop | `stop, wait, hold on, cancel, no, nope, deny, don't` |
| `ZRB_LLM_DICTATION_POLITE_WORDS` | Words a yes or a no may carry without changing it ("yes please", "no thanks"). Approvals only: a stop word is taken as one only when it is said alone, so "stop please" goes to the small model | `please, thanks, thank, you` |
| `ZRB_LLM_DICTATION_BLOCK_DURATION` | Seconds of audio per microphone block: the step every other listening duration is counted in, and how often speech is checked | `0.1` |
| `ZRB_LLM_DICTATION_DEVICE` | Microphone PortAudio opens: a name, or the number `query_devices()` lists it under; `pulse` and `default` on a Linux or WSL machine are not the same microphone. Empty uses PortAudio's own default (`python -c "import sounddevice; sounddevice.query_devices()"` lists them) | (empty) |

Each backend uses only its own variables:

| Backend | Variable | Description | Default |
|---------|----------|-------------|---------|
| `openai` | `ZRB_LLM_DICTATION_OPENAI_MODEL` | Transcription model, e.g. `gpt-4o-transcribe` | `whisper-1` |
| `openai` | `ZRB_LLM_DICTATION_OPENAI_BASE_URL` | An OpenAI-compatible transcription server; empty is OpenAI's | (none) |
| `openai` | `ZRB_LLM_DICTATION_LANGUAGE` | Optional ISO-639-1 language hint, such as `en` or `id`; empty lets OpenAI detect the language | (empty) |
| `google` | `ZRB_LLM_DICTATION_GOOGLE_MODEL` | Gemini model | `gemini-2.5-flash` |
| `google`, `multimodal` | `ZRB_LLM_DICTATION_TRANSCRIBE_PROMPT` | Instruction sent with the audio; the default preserves the spoken language and does not translate | `Transcribe exactly what is spoken. Do not translate or paraphrase. Return only the transcription.` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MODEL_NAME` | Model directory name (without `.zip`), downloaded from `<VOSK_MODEL_URL>/<name>.zip` | `vosk-model-small-en-us-0.15` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MODEL_URL` | Base URL for the model zip (extracted to `~/.cache/vosk/`) | `https://alphacephei.com/vosk/models` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_DOWNLOAD_TIMEOUT` | Seconds to wait for the model server to answer; `0` means the transfer is not capped, though a stalled connection still gives up after 30 s | `120` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MAX_DOWNLOAD_MB` | Megabytes of model zip accepted; `0` means no limit | `4096` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MAX_UNCOMPRESSED_MB` | Megabytes the model may take once extracted, every file summed (bounds a decompression bomb); `0` means no limit | `8192` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MAX_FILE_MB` | Megabytes for any one file in the archive; `0` means no limit | `4096` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_MAX_FILES` | Files the archive may hold; `0` means no limit | `10000` |
| `vosk` | `ZRB_LLM_DICTATION_VOSK_CONFIDENCE` | Lowest average word confidence (0–1) a hands-free transcript may have and still reach the model; vosk scores the words it makes out of noise low. Push-to-talk keeps every word. `0` uses no floor | `0` |

The `multimodal` backend's system prompt is the `multimodal_audio` prompt file, overridable like any prompt through `ZRB_LLM_PROMPT_DIR`.

### Speech (text-to-speech)

Reads the reply a sentence at a time as it streams, tool approvals, questions, and a tool call that starts after a silence aloud. `/speech` switches it off and on during a session, dropping anything not yet said.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SPEECH_ENABLED` | Speak from the start of a session; `/speech` switches it either way | `off`, or as `ZRB_LLM_VOICE` sets it |
| `ZRB_LLM_SPEECH_COMMANDS` | Aliases that switch speech off and on | `/speech` |
| `ZRB_LLM_SPEECH_EVENTS` | What to speak: `reply`, `approval`, `question`, `progress` (a tool call starting after a silence: "Running a command.") | `reply, approval, question, progress` |
| `ZRB_LLM_SPEECH_BACKEND` | `auto` (`termux` on Termux, `say` on macOS, else `espeak-ng`), `termux`, `say`, `espeak-ng`, `openai`, `gemini`, or `kokoro` / `piper` / `pocket` (local, on Pipecat, with zrb playing the audio). A failing backend falls back to the local engine | `auto` |
| `ZRB_LLM_SPEECH_VOICE` | Voice name for the backend (for `termux`, the `-v` variant); empty uses its default (system voice, `en-us+m3`, `alloy`, `Sulafat`, `af_heart` for `kokoro`, `en_US-ryan-high` for `piper`, `alba` for `pocket`) | (none) |
| `ZRB_LLM_SPEECH_STYLE` | How `openai` and `gemini` should sound, in plain words (tone, pace, warmth); a direction, not read aloud. Empty uses the voice's default manner. The local engines ignore it | a warm, clear, conversational colleague |
| `ZRB_LLM_SPEECH_RATE` | Words per minute for `say` and `espeak-ng` | `165` |
| `ZRB_LLM_SPEECH_STREAM` | Speak a reply a sentence at a time while it is written, and the text before a tool call when the call starts. `off` reads the whole reply once the turn ends. Either way it is read whole, however long it is, unless `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` is set, which turns streaming of the reply off | `on` |
| `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` | A reply whose speakable text is longer than this many characters is spoken as a short summary from the small model instead of whole; the reply on screen is unchanged. Needs the finished reply, so the reply is not streamed while this is set. `0` reads every reply whole | `0` |
| `ZRB_LLM_SPEECH_SUMMARY_MODEL` | Model that writes the summary. Empty uses the small model (`ZRB_LLM_SMALL_MODEL`, else the main model) | empty |
| `ZRB_LLM_SPEECH_SUMMARY_TIMEOUT` | Seconds the summary may take before the reply is read whole; `0` means no limit | `15` |
| `ZRB_LLM_SPEECH_PROGRESS_INTERVAL` | With `progress` in `ZRB_LLM_SPEECH_EVENTS`, seconds of silence after which a tool call starting is announced; `0` announces nothing | `8` |
| `ZRB_LLM_SPEECH_OPENAI_MODEL` | Model for `openai` | `gpt-4o-mini-tts` |
| `ZRB_LLM_SPEECH_OPENAI_BASE_URL` | API base URL for `openai` | `https://api.openai.com/v1` |
| `ZRB_LLM_SPEECH_GEMINI_MODEL` | Model for `gemini` | `gemini-2.5-flash-preview-tts` |
| `ZRB_LLM_SPEECH_TIMEOUT` | Seconds a cloud backend may take; `0` means no limit | `15` |
| `ZRB_LLM_SPEECH_TERMUX_LANGUAGE` | Language for `termux` (`-l`), e.g. `en`; empty is the phone's | (none) |
| `ZRB_LLM_SPEECH_TERMUX_ENGINE` | Android TTS engine for `termux` (`-e`) | (none) |
| `ZRB_LLM_SPEECH_TERMUX_REGION` | Region for `termux` (`-n`), e.g. `US` | (none) |
| `ZRB_LLM_SPEECH_TERMUX_RATE` | Speech rate for `termux`; `1.0` is normal | `1.0` |
| `ZRB_LLM_SPEECH_TERMUX_PITCH` | Pitch for `termux`; `1.0` is normal | `1.0` |
| `ZRB_LLM_SPEECH_TERMUX_STREAM` | Android audio stream for `termux` (`-s`): `ALARM`, `MUSIC`, `NOTIFICATION`, `RING`, `SYSTEM`, `VOICE_CALL` | (none) |
| `ZRB_LLM_SPEECH_PLAYER` | `auto`: zrb plays speech itself through sounddevice when the `zrb[voice]` extra is installed and the backend can render audio (`say`, `espeak-ng`, `openai`, `gemini`), so speech can pause while you talk over it; else a player program. A cloud backend with `ZRB_LLM_SPEECH_WAV_PLAYER` set uses that player, and a device that cannot open sends the rest of the session to a player program. `command`: always a player program. Any other value is logged and read as `auto` | `auto` |
| `ZRB_LLM_SPEECH_WAV_PLAYER` | Command playing the cloud backends' WAV, the path appended (e.g. `mpv --really-quiet`); set, it plays every sentence even under `ZRB_LLM_SPEECH_PLAYER=auto` (and speech can then not pause); empty picks `afplay`, `paplay`, `aplay` or `ffplay` | (none) |
| `ZRB_LLM_SPEECH_LOCK_FILE` | File locked while speech plays, so sessions take turns and dictation ignores zrb's own voice | `<tmp>/<root group name>-speech.lock` |
| `ZRB_LLM_SPEECH_LOCK_TIMEOUT` | Seconds to wait for another session to finish before dropping an utterance | `30` |
| `ZRB_LLM_SPEECH_DRAIN_TIMEOUT` | Seconds queued speech may still play after zrb exits | `30` |
| `ZRB_LLM_SPEECH_PLAYER_TIMEOUT` | Seconds one utterance may play; `0` means no limit | `120` |
| `ZRB_LLM_SPEECH_PLAYER_BLOCK_FRAMES` | Samples per block when zrb plays speech itself; smaller pauses and stops sooner, larger is kinder to a slow machine | `1024` |
| `ZRB_LLM_SPEECH_PLAYER_READ_AHEAD` | Chunks of downloaded or rendered speech read ahead of playback | `32` |
| `ZRB_LLM_SPEECH_RENDER_TIMEOUT` | Seconds `say` or `espeak-ng` may take to render a sentence for zrb to play; `0` means no limit | `60` |
| `ZRB_LLM_SPEECH_STALL_TIMEOUT` | With `ZRB_LLM_SPEECH_TIMEOUT` at `0`, seconds `openai` audio may stop arriving before it is given up on | `30` |
| `ZRB_LLM_SPEECH_QUESTION_MESSAGE` | Said when the model asks a question with no text of its own | `A question is waiting for your answer.` |
| `ZRB_LLM_SPEECH_APPROVAL_MESSAGE` | Said when a tool call waits for approval: `{action}` is what the tool does, `{target}` a space and the file or command, or empty | `I need to {action}{target}. I need your approval.` |
| `ZRB_LLM_SPEECH_APPROVAL_TARGET_KEYS` | Tool arguments tried, in order, for `{target}` | `path, file_path, command, notebook_path` |
| `ZRB_LLM_SPEECH_APPROVAL_TARGET_MAX_CHARS` | Longest `{target}` read out; `0` leaves it out | `80` |
| `ZRB_LLM_SPEECH_PROGRESS_PHRASES` | JSON object of what progress narration says when a tool call starts: tool-name patterns (`*` and `?` wildcards, tried in order, the first match wins; `""` matches a call with no tool name) to a line, `{tool}` being the tool's name. A tool no pattern matches is not announced | English lines for the built-in tools, then `"Lsp*": "Checking the code."`, `"": "Working on it."`, `"*": "Using the {tool} tool."` |
| `ZRB_LLM_SPEECH_APPROVAL_ACTIONS` | JSON object of the `{action}` in `ZRB_LLM_SPEECH_APPROVAL_MESSAGE`: tool-name patterns, as above, to what the tool does. A tool no pattern matches is named as it is | English actions for the built-in tools that ask, then `"": "run a tool"`, `"*": "use the {tool} tool"` |
| `ZRB_LLM_SPEECH_PROGRESS_SILENT_TOOLS` | Tools never announced by progress narration | `TodoRead, TodoWrite, ActivateSkill, SearchSkill` |
| `ZRB_LLM_SPEECH_GEMINI_PROMPT` | What `gemini` is sent with no style: `{text}` is what to read. Without an instruction, Gemini may answer a short line instead of reading it | `Say: {text}` |
| `ZRB_LLM_SPEECH_GEMINI_STYLE_PROMPT` | What `gemini` is sent with `ZRB_LLM_SPEECH_STYLE` set: `{style}` and `{text}` | `{style}`, a blank line, `Say exactly this, and nothing else: {text}` |

A placeholder is replaced only where written; any other brace stays as it is. The prompts behind speech are prompt files, overridable like any prompt through `ZRB_LLM_PROMPT_DIR`: `speech_live` (while speech is on, asks the model to open with a spoken answer).

The cloud backends read `OPENAI_API_KEY`, and `GEMINI_API_KEY` or `GOOGLE_API_KEY`.

### Camera

`/photo [device]` attaches a camera photo to the next message.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_CAMERA_COMMANDS` | Aliases for the camera command | `/photo, /p` |
| `ZRB_LLM_CAMERA_BACKEND` | `auto` (Termux:API on Android when installed, else ffmpeg), `termux`, `ffmpeg` | `auto` |
| `ZRB_LLM_CAMERA_DEVICE` | Device used when the command names none; empty picks the platform default | (none) |
| `ZRB_LLM_CAMERA_TIMEOUT` | Seconds a capture may take, every attempt included, before it is abandoned; `0` means no limit | `15` |

```bash
# Hands-free with OpenAI transcription, a wake word, and replies read aloud
export ZRB_LLM_DICTATION_MODE=hands_free
export ZRB_LLM_DICTATION_BACKEND=openai
export ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe
export ZRB_LLM_DICTATION_WAKE_WORDS="hi,hai,hey,嗨"   # every spelling the transcriber writes
export ZRB_LLM_SPEECH_ENABLED=on
```

Every variable above can be set from `zrb_init.py` instead, since each is read when a session starts, not when zrb is imported:

```python
from zrb import CFG

# Indonesian: words to stop zrb, and the polite words a yes or a no around
# them may carry.
CFG.LLM_DICTATION_STOP_WORDS = ["berhenti", "stop", "tunggu", "sudah"]
CFG.LLM_DICTATION_POLITE_WORDS = ["tolong", "terima", "kasih", "please"]
CFG.LLM_SPEECH_APPROVAL_MESSAGE = "Boleh saya {action}{target}?"
CFG.LLM_SPEECH_APPROVAL_ACTIONS = {"Write": "menulis berkas", "*": "memakai {tool}"}
CFG.LLM_SPEECH_PROGRESS_PHRASES = {"Read": "Membaca berkas.", "*": "Memakai {tool}."}
```

From a shell, the two phrase tables are JSON:

```bash
export ZRB_LLM_SPEECH_PROGRESS_PHRASES='{"Read": "Membaca berkas.", "Shell": "Menjalankan perintah.", "*": "Memakai {tool}."}'
```
