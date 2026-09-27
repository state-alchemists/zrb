# Voice interaction

Talk to zrb and hear it answer. Responses, approval prompts and questions are read aloud.

```bash
cd examples/voice-interaction
zrb chat                   # /voice, Space, talk, Space, Enter
                           # or /handsfree, then just talk
zrb voice say "hello"      # hear the current speech backend
zrb voice mic-test         # check the microphone level for hands-free
```

Everything lives in `zrb_init.py`. zrb loads `zrb_init.py` from every directory between the filesystem root and where it starts, so it applies to sessions started here or in a subfolder, and nowhere else. Listening needs `zrb[voice]`; speaking needs nothing extra.

| File | Role |
|---|---|
| `zrb_init.py` | Everything: TTS backends, speaking hooks, `/handsfree`, hands-free listener, `zrb voice` tasks |
| `test_voice_interaction.py` | Unit tests |
| `test_concurrency.py` | Two sessions' speech must not overlap |

To use it in every session, add its absolute path to `ZRB_INIT_SCRIPTS` (colon-separated).

## Listening

**Push-to-talk** (default). `zrb_init.py` sets `ZRB_LLM_VOICE_ENABLED=true` unless you set it yourself. Type `/voice`, press Space to start recording, talk, press Space again to stop. The transcript lands in the input box; edit it or press Enter to send. Voice mode switches off after each recording, so type `/voice` again for the next one. Transcription uses `ZRB_LLM_VOICE_MODE` (offline vosk by default); the key is `ZRB_LLM_VOICE_PUSH_TO_TALK_KEY`.

**Hands-free**. Type `/handsfree` to switch it on or off; set `ZRB_VOICE_HANDS_FREE=1` to start with it on. While it is on, the microphone stays open; an utterance ends after a second of silence and is submitted as a turn. Audio captured while the agent is speaking is dropped, plus a 0.4 s echo cooldown. `/handsfree` is an `ActionCommand` (see [LLMChatTask → Triggers & Custom Commands](../../docs/task-types/llmchat-task.md#triggers--custom-commands)): it runs code instead of prompting the LLM.

| Variable | Default | Meaning |
|---|---|---|
| `ZRB_VOICE_HANDS_FREE` | off | `1` starts the session with hands-free on |
| `ZRB_VOICE_WAKE_WORD` | none | Comma-separated; only utterances starting with one count, and it is stripped. Said alone, it accepts the next utterance spoken within 8 s |
| `ZRB_VOICE_HANDS_FREE_THRESHOLD` | `0.01` | RMS level that counts as speech |
| `ZRB_VOICE_HANDS_FREE_SILENCE` | `1.0` | Seconds of silence that end an utterance |
| `ZRB_VOICE_DEBUG` | off | `1` writes what was heard to the side log |

List every spelling the transcriber may produce. With an Indonesian-accented
"Hi", `gpt-4o-transcribe` wrote `Hai` in 7 of 12 clips and once `嗨`; pinning
the language to English did not stop it. Avoid made-up words: vosk hears "zrb"
as "hazy are be". When an utterance is dropped, `ZRB_VOICE_DEBUG=1` shows what
the transcriber wrote.

Without a wake word, anything the microphone hears becomes a turn. Don't use push-to-talk while hands-free is on, or the words are submitted twice.

### Recommended transcription

zrb defaults to offline vosk, which mangles technical speech. With `OPENAI_API_KEY` set, use this instead:

```bash
export ZRB_LLM_VOICE_MODE=openai
export ZRB_LLM_VOICE_OPENAI_MODEL=gpt-4o-transcribe
export ZRB_VOICE_WAKE_WORD="hi,hai,hey,嗨"
```

One clip, generated with macOS `say`: *"Refactor the hook manager in zrb so pydantic AI streams the last assistant message, then run pytest and push to GitHub."*

| `ZRB_LLM_VOICE_MODE` / model | Time | Transcript |
|---|---|---|
| `vosk` (default) | 1.8 s | we factor the hook manager and zr be so pedantic ai streams … run dust and push to get up |
| `openai` / `whisper-1` (default) | 5.7 s | … in zrbsopydantic-aistreams … run pydest … GitHub |
| `openai` / `gpt-4o-mini-transcribe` | 2.9 s | … ZRB SOPyDantic AI streams … run pytest and push to GitHub |
| `openai` / `gpt-4o-transcribe` | 1.3 s | … ZRB so pylintic AI streams … run pytest and push to GitHub |
| `google` / `gemini-2.5-flash` (default) | 4.8 s | … ZRB Soap identic AI streams … run Pitest … |

A single run on synthetic speech: expect different timings and errors with a real voice and microphone.

## Speaking

| Backend | Needs | Default voice | First sound |
|---|---|---|---|
| `say` | macOS | system default | instant |
| `espeak-ng` | `espeak-ng` on PATH | `en-us+m3` | instant |
| `openai` | `OPENAI_API_KEY` | `alloy` | ~2 s |
| `gemini` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `Sulafat` | ~3.5 s |

`auto` (default) picks `say`, else `espeak-ng`. Cloud backends are opt-in (`ZRB_VOICE_BACKEND=openai`). If a backend fails, the utterance is spoken by the local engine instead. Cloud requests use `urllib`, so no packages are needed.

| Variable | Default | Meaning |
|---|---|---|
| `ZRB_VOICE_BACKEND` | `auto` | `auto`, `say`, `espeak-ng`, `openai`, `gemini` |
| `ZRB_VOICE_NAME` | per backend | Voice name for the chosen backend |
| `ZRB_VOICE_RATE` | `165` | Words per minute (`say`, `espeak-ng`) |
| `ZRB_VOICE_MAX_CHARS` | `400` | Longer text is cut at a sentence end |
| `ZRB_VOICE_SUMMARY` | `clean` | `llm` rewrites the response with a model first |
| `ZRB_VOICE_SUMMARY_MODEL` | `gpt-4o-mini` | Any OpenAI-compatible chat model |
| `ZRB_VOICE_SUMMARY_BASE_URL` | `https://api.openai.com/v1` | |
| `ZRB_VOICE_SUMMARY_API_KEY` | `$OPENAI_API_KEY` | |
| `ZRB_VOICE_OPENAI_MODEL` | `gpt-4o-mini-tts` | |
| `ZRB_VOICE_OPENAI_BASE_URL` | `https://api.openai.com/v1` | |
| `ZRB_VOICE_GEMINI_MODEL` | `gemini-2.5-flash-preview-tts` | |
| `ZRB_VOICE_CLOUD_TIMEOUT` | `15` | Seconds |
| `ZRB_VOICE_LOCK_TIMEOUT` | `30` | Seconds to wait for the audio device before dropping |
| `ZRB_VOICE_LOG` | `$TMPDIR/zrb-voice-speaker.log` | Side log: events and errors, never the spoken text; created `0600` |

What is said:

- **`Stop`**: `last_assistant_message`, with code blocks, tables (with or without outer pipes), URLs and markdown stripped. A sub-agent's turn (`event_data["nested_run"]`) is not spoken.
- **`PermissionRequest`**: "I need to write a file /tmp/a.py. I need your approval." A template, since you are waiting on it.
- **`Notification`**: only `elicitation_dialog` and `permission_prompt`.

## How speaking works

The hooks are Python functions registered with `llm_chat.append_hook_factory`, so they read `HookContext` fields directly: no subprocess, no stdin JSON, no env size limit. zrb awaits a Python hook inline, so each one only puts text on a queue and returns `HookResult(success=True)`. One background thread plays the queue in order. When zrb exits, it waits up to 30 s for queued speech to finish, since `zrb chat --message` exits right after the reply.

## Limitations

- Two zrb sessions speaking at once are serialized by a lock file, but not ordered.
- No barge-in: new speech waits for the current utterance, and hands-free does not listen while the agent speaks.
- `fcntl` makes this POSIX-only.

## Tests

Run them with the Python zrb is installed in, since the hooks import zrb:

```bash
~/.local/pipx/venvs/zrb/bin/python test_voice_interaction.py
~/.local/pipx/venvs/zrb/bin/python test_concurrency.py   # speakers must not overlap
```
