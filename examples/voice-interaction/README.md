# Voice interaction

Talk to zrb and hear it answer. Responses, approval prompts and questions are read aloud.

```bash
cd examples/voice-interaction
zrb chat                                 # /voice, Space, talk, Space, Enter
                                         # or /handsfree, then just talk
```

zrb loads `zrb_init.py` and `.zrb/hooks.json` from every directory between the filesystem root and where it starts, so both apply to sessions started here and nowhere else. Listening needs `zrb[voice]`; speaking needs nothing extra.

| File | Role |
|---|---|
| `.zrb/hooks.json` | Speaking: `command` hooks on `Stop`, `PermissionRequest`, `Notification` |
| `hook_speak.py` | Hook entry point: reads the event, decides what to say |
| `voice_speaker.py` | Text cleanup, TTS backends, serialized playback |
| `llm_summary.py` | Optional LLM rewrite of the response before speaking |
| `zrb_init.py` | Listening: push-to-talk switch, hands-free listener, `/handsfree` |

The hook command is the relative `python3 hook_speak.py`, and hooks run in the session's working directory, so start zrb from this folder, not a subfolder. To speak in every session, copy the `hooks` block into `~/.zrb/hooks.json` with an absolute path, quoted in case it contains spaces: `python3 "/path/to/examples/voice-interaction/hook_speak.py" || exit 0`.

## Listening

**Push-to-talk** (default). `zrb_init.py` sets `ZRB_LLM_VOICE_ENABLED=true` unless you set it yourself. Type `/voice`, press Space to start recording, talk, press Space again to stop. The transcript lands in the input box; edit it or press Enter to send. Voice mode switches off after each recording, so type `/voice` again for the next one. Transcription uses `ZRB_LLM_VOICE_MODE` (offline vosk by default); the key is `ZRB_LLM_VOICE_PUSH_TO_TALK_KEY`.

**Hands-free**. Type `/handsfree` to switch it on or off; set `ZRB_VOICE_HANDS_FREE=1` to start with it on. While it is on, the microphone stays open; an utterance ends after a second of silence and is submitted as a turn. Audio captured while the agent is speaking is dropped, plus a 0.4 s echo cooldown. `/handsfree` is an `ActionCommand` (see [LLMChatTask → Triggers & Custom Commands](../../docs/task-types/llmchat-task.md#triggers--custom-commands)): it runs code instead of prompting the LLM.

| Variable | Default | Meaning |
|---|---|---|
| `ZRB_VOICE_HANDS_FREE` | off | `1` starts the session with hands-free on |
| `ZRB_VOICE_WAKE_WORD` | none | Only utterances starting with it count; it is stripped |
| `ZRB_VOICE_HANDS_FREE_THRESHOLD` | `0.01` | RMS level that counts as speech |
| `ZRB_VOICE_HANDS_FREE_SILENCE` | `1.0` | Seconds of silence that end an utterance |

Without a wake word, anything the microphone hears becomes a turn. Don't use push-to-talk while hands-free is on, or the words are submitted twice.

### Recommended transcription

zrb defaults to offline vosk, which mangles technical speech. With an OpenAI key, use this instead:

```bash
export ZRB_LLM_VOICE_MODE=openai
export ZRB_LLM_VOICE_OPENAI_MODEL=gpt-4o-transcribe
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

`auto` (default) picks `say`, else `espeak-ng`. Cloud backends are opt-in (`ZRB_VOICE_BACKEND=openai`). If a backend fails, the utterance is spoken by the local engine instead. Cloud requests use `urllib`, so the hook needs no packages.

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

- **`Stop`**: `last_assistant_message`, with code blocks, tables (with or without outer pipes), URLs and markdown stripped.
- **`PermissionRequest`**: "I need to write a file /tmp/a.py. I need your approval." A template, since you are waiting on it.
- **`Notification`**: only `elicitation_dialog` and `permission_prompt`.

## Hook safety

On `Stop`, exit code 2 makes zrb re-run the turn with stderr as the prompt, and stdout is parsed as JSON. So the hooks are `"async": true` (fire-and-forget, cannot block), the command ends in `|| exit 0`, and `hook_speak.py` always exits 0 and writes only to the side log.

## Limitations

- Sub-agent turns also fire `Stop` and are spoken; the hook cannot tell them apart from the main turn.
- Hooks run independently, so utterances are serialized but not ordered.
- No barge-in: new speech waits for the current utterance, and hands-free does not listen while the agent speaks.
- `fcntl` makes this POSIX-only.

## Tests

```bash
python3 test_voice_interaction.py
python3 test_concurrency.py          # three speakers must not overlap
python3 voice_speaker.py "hello"     # hear the current backend
```
