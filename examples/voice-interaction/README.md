# Voice interaction

Talk to zrb and hear it answer. Replies, approval prompts and questions are read aloud, and in hands-free mode you can answer them by voice.

```bash
cd examples/voice-interaction
zrb chat                   # /voice, talk, pause (or /voice again); edit, Enter
                           # or /handsfree, then just talk
zrb voice say "hello"      # hear the current speech backend
zrb voice mic-test         # check the microphone level for hands-free
```

Speech and dictation are built into `zrb chat`. `zrb_init.py` only switches speech on (`ZRB_LLM_SPEECH_ENABLED`, unless you set it yourself) and adds the two `zrb voice` tasks. zrb loads `zrb_init.py` from every directory between the filesystem root and where it starts, so this applies to sessions started here or in a subfolder. To use it everywhere, add its absolute path to `ZRB_INIT_SCRIPTS`, or just export `ZRB_LLM_SPEECH_ENABLED=on`. Listening needs `zrb[voice]`; speaking needs nothing extra.

Every setting is listed in [LLM configuration](../../docs/configuration/llm-config.md) under `LLM_SPEECH_*` and `LLM_DICTATION_*`. To go further than the settings allow, pass your own backend to `enable_speech`/`enable_dictation` — see [Voice and camera](../../docs/llm/voice-camera.md).

## Listening

**Push-to-talk** (default). Type `/voice` and talk. A pause of `ZRB_LLM_DICTATION_SILENCE` seconds (default 1), or `/voice` again, stops the recording; the transcript lands in the input box to edit or send with Enter.

**Hands-free.** Type `/handsfree` to switch it on or off; `ZRB_LLM_DICTATION_MODE=hands_free` starts sessions with it on. The microphone stays open and every utterance is submitted as a turn. While zrb waits for a tool approval, a short "yes" (`ZRB_LLM_DICTATION_APPROVE_WORDS`) approves it; anything else denies it, with what you said as the reason, so "no, use pytest instead" tells the agent why. Audio captured while zrb is speaking is dropped.

With `ZRB_LLM_DICTATION_WAKE_WORDS` set (comma-separated), only utterances starting with a wake word count, and it is stripped. Said alone, the wake word accepts the next utterance spoken within `ZRB_LLM_DICTATION_WAKE_WINDOW` seconds. Without wake words, anything the microphone hears becomes a turn.

List every spelling the transcriber may produce. With an Indonesian-accented "Hi", `gpt-4o-transcribe` wrote `Hai` in 7 of 12 clips and once `嗨`; pinning the language to English did not stop it. Avoid made-up words: vosk hears "zrb" as "hazy are be".

### Recommended transcription

zrb defaults to offline vosk, which mangles technical speech. vosk is also the only backend that transcribes while you speak. With `OPENAI_API_KEY` set, use this instead:

```bash
export ZRB_LLM_DICTATION_BACKEND=openai
export ZRB_LLM_DICTATION_OPENAI_MODEL=gpt-4o-transcribe
export ZRB_LLM_DICTATION_WAKE_WORDS="hi,hai,hey,嗨"
```

Without a key, `whisper`, `moonshine` and `funasr` transcribe locally through Pipecat, each needing its own install (`pip install 'pipecat-ai[whisper]'`) — see [Voice and camera § Your own backend](../../docs/llm/voice-camera.md#your-own-backend). The table below was measured before they were added, so it does not cover them: set `ZRB_LLM_DICTATION_BACKEND` and run your own clip through them.

One clip, generated with macOS `say`: *"Refactor the hook manager in zrb so pydantic AI streams the last assistant message, then run pytest and push to GitHub."*

| Backend / model | Time | Transcript |
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

`auto` (default) picks `say`, else `espeak-ng`. If a cloud backend fails, the local engine speaks instead. `/speech` switches speech off and on during a session, dropping anything not yet said. `kokoro`, `piper` and `pocket` are local voices too, each needing its own install (`pip install 'pipecat-ai[piper]'`) — see [Voice and camera § Your own backend](../../docs/llm/voice-camera.md#your-own-backend) for what each is. They are not in the table above because it was measured before they were added.

A reply is read whole, however long it is; code, tables and links are skipped.

Two sessions on one machine take turns through a lock file, so they never talk over each other.
