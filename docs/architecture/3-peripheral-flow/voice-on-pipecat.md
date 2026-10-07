🔖 [Documentation Home](../../../README.md) > [Architecture](../README.md) > Voice on Pipecat

# Voice on Pipecat

> **Tier 3 · Peripheral flow** · Code: `src/zrb/llm/dictation/`, `src/zrb/llm/speech/` · Read first: [Dictation & Barge-in](dictation-barge-in.md)

zrb's voice runs its models on Pipecat: the speech-to-text a session listens through and the text-to-speech it speaks through are Pipecat services ([ADR-0107](../../adr/adr-0107.md)). This page is the boundary that may not be crossed. The idea to take away: **Pipecat runs the models, zrb decides the meaning.** Pipecat answers "what audio event is happening"; zrb answers "what does that mean for this chat session".

## Table of Contents

- [Design](#design)
  - [The boundary](#the-boundary)
  - [Principles](#principles)
  - [Invariants](#invariants)
- [Realization](#realization)
  - [The parts](#the-parts)
  - [What zrb keeps, and why](#what-zrb-keeps-and-why)
  - [The stages](#the-stages)
  - [Regression gates](#regression-gates)
  - [Change it here](#change-it-here)
- [See Also](#see-also)

## Design

### The boundary

| Pipecat runs | zrb decides |
| --- | --- |
| The speech-to-text service a session listens through, and the text-to-speech service it speaks through | The microphone device, and the only code that opens it |
| A service's model: loading it, running it, releasing it | Where an utterance begins and ends, and the bar under the user's speech |
| The frames inside a service, and the order they travel in | Whether a transcript is meant for zrb at all: wake words, stop words, approvals, minimum-word guards |
| A worker and its pipeline, once zrb has built one | How long a pipeline lives, and pause, resume or stop, per chat session |
| Interruption inside one synthesis, when zrb asks for one | The pydantic-ai agent, the UI, and the prompt |

A conversation is one pass through both columns: the user speaks, zrb cuts the utterance and hands it to the service, the service answers with a transcript, and zrb decides whether those words are a turn, an answer to a prompt, a stop, or noise.

### Principles

1. **zrb keeps the microphone.** The pipeline never opens the device. zrb captures as it does today and pushes frames in, so `listen` stays the only thing that touches the sound card. → [ADR-0107](../../adr/adr-0107.md)
2. **Pipecat owns the media, zrb owns the meaning.** A media stage replaces audio work; it never absorbs a decision about what the user meant. → [ADR-0107](../../adr/adr-0107.md)
3. **A stage lands only when the tree is green with both paths.** Each stage is behind a flag until its replacement is proven, so a half-migrated voice is never the only voice. → [ADR-0107](../../adr/adr-0107.md)
4. **What the user hears is decided by the words, not by the transport.** The hold-first, decide-on-the-words shape survives the move. → [ADR-0105](../../adr/adr-0105.md)
5. **Playback stays in-process and pausable.** Speech is played by zrb so it can be paused and stopped out of the microphone; a transport may not take that away. → [ADR-0103](../../adr/adr-0103.md)
6. **Features stay unknown to the UI.** The pipeline is installed through the same extension points as today, and config is still read when a session starts. → [ADR-0102](../../adr/adr-0102.md)

### Invariants

Each one fails quietly: the chat keeps working, but zrb answers itself, talks over the user, or stops hearing anyone.

| Invariant | Pinned by |
| --- | --- |
| The microphone is opened by zrb and by nothing else | `test/llm/dictation/test_listen.py` |
| A stop said over zrb still cancels the turn, and is still sent nowhere | `test/llm/dictation/test_feature_barge_in.py` |
| A hold taken over zrb's voice is still given back when the words are not meant for it | `test/llm/dictation/test_feature_barge_in_pause.py` |
| A spoken yes or no still answers a pending approval rather than steering the turn | `test/llm/dictation/test_feature_barge_in.py` |
| Speech can still be paused and stopped mid-utterance | `test/llm/speech/test_player_in_process.py` |
| A streamed reply is still spoken sentence by sentence as it is written | `test/llm/speech/test_feature_stream.py` |
| A turn ends when the user is done, and a slow transcript does not stall it | **unpinned** — the semantic turn end has no test yet |

## Realization

### The parts

```mermaid
sequenceDiagram
    participant C as UtteranceCutter
    participant S as DictationSession
    participant A as Agent
    participant P as Speaker
    C->>S: audio
    S->>A: command
    A-->>P: reply
```

The framework names below are Pipecat's, not zrb's. The two services shipped; the rest is what the plan named, kept here with what became of it, so a reader can tell a decision from a hope.

| Part | What it does | Replaces |
| --- | --- | --- |
| zrb capture | Keeps the microphone, cuts the utterance, and hands that over | nothing — stays zrb's |
| STT service — **shipped** | The Pipecat service `ZRB_LLM_DICTATION_BACKEND` names (`whisper`, `moonshine`, `funasr`), handed a finished segment and answering with a `TranscriptionFrame` | the hand-rolled transcript backends |
| TTS service — **shipped** | The Pipecat service ZRB_LLM_SPEECH_BACKEND names (`kokoro`, `piper`, `pocket`), asked for a sentence's audio (`TTSSpeakFrame` → `TTSAudioRawFrame`), which zrb plays | the hand-rolled speech backends |
| Registry and managers — **shipped** | `stt_registry`/`tts_registry` and the managers that build a named service (ADR-0090) | the fixed name-to-backend lookup |
| Input transport | Takes audio pushed in rather than from a device, through the readiness call Pipecat's own base input transport omits; without it the pushed frames are never drained. **Built for stage 1 and gone with it** — the shipped path uses no transport | nothing |
| Voice-activity detection | Tells speech from silence per 32 ms frame, from a model that ships inside Pipecat and runs offline. **Built for stage 1 and gone with it** — it was never in the decision path, and `UtteranceCutter` still cuts | nothing |
| Turn strategies | VAD-triggered and minimum-word turn starts, the second applying its threshold only while zrb speaks. **Not built** | nothing yet |
| vosk STT | A custom STT service: Pipecat ships none, and this keeps the wake-word gate and per-word confidence. **Not built** — vosk is still zrb's own backend | nothing |
| zrb agent | pydantic-ai, unchanged | nothing |
| Output transport | A Pipecat output-transport subclass overriding its audio write to play through `PcmUtterance`. **Not built** — zrb asks the TTS service for audio and plays it itself, so no transport is involved | nothing |

Stage 1 was built, ran for one release behind a flag, and was removed. It fed every captured block to a pipeline of zrb's own — `[transport, detector, metrics stage, counter]`, with a readiness call the shipped path never learned to make — and decided nothing; its whole output was one line per listening, `Pipecat input pipeline: 2 speech segment(s), 1.5s of detected speech`.

It went because nothing took it up. The detector's turn — replacing the cutter's loudness bars, then replacing the silence-based turn end with a semantic one — was the reason the tap existed, and it was never built; with the cutter staying zrb's, the tap measured a path no session took. What it measured left with it, so those two stages would begin by rebuilding the instrument. The line it printed has a replacement for the one thing it was actually useful for: `zrb voice mic-test` in `examples/voice-interaction` measures a device against the same threshold dictation uses.

The services that did ship are held up by `test/llm/dictation/test_pipecat_stt.py`, `test/llm/dictation/backend/test_pipecat_backend.py`, `test/llm/speech/test_pipecat_tts.py` and `test/llm/speech/backend/test_pipecat_backend.py`, and the registry they resolve through by `test/llm/voice/`.

### What zrb keeps, and why

These are the parts a "full" adoption must not remove, because each carries behavior Pipecat has no notion of. Dropping one is a product change, not a refactor.

| Kept | The behavior it carries |
| --- | --- |
| `DictationSession`'s guards | A stop, an approval, a denial, a wake word, a minimum word count, a transcriber's guess |
| `TriggerReply` and the trigger adapter | A transcript that answers the pending prompt instead of steering the turn |
| Push-to-talk's input path | A transcript that lands in the editable box, unsent |
| The wake-word gate | Stripping the wake word, arming the next utterance, and reading it beside the stop and approval rules |
| vosk as a custom STT service | Offline transcription, partials, and per-word confidence, which Pipecat's transcription frames do not carry |
| `Speaker` and `PcmUtterance` | Pause, resume, interrupt, external-player fallback, and per-session isolation |
| The pydantic-ai agent and the stream observer | Tools, history, permissions, hooks, and muting the rest of a reply that was talked over |
| The bounded capture backlog | Continuing to capture while a turn is answered, and dropping the oldest rather than splicing across a gap |

The echo-aware bar is the sharpest of these. zrb measures the room under ordinary speech and zrb's own voice over it separately, and holds speech on loudness before it knows the words. A generic detector supplies confidence and state transitions, not that distinction, so the bar stays zrb's.

### The stages

| Stage | What comes out | Order |
| --- | --- | --- |
| 1 | Input only, behind a flag. **Built and removed**: the flag fed the capture to a pipeline of zrb's own, from a task beside `listen`'s reading loop, and that pipeline owned a transport, a detector and a metrics stage for as long as a listening lasted. Nothing after it was built, so it was removed in 3.15.0 | First, because it can run beside what exists |
| 2 | `UtteranceCutter` and its loudness bars, once the detector's boundaries are shown to match the cutter's on recorded audio. **Abandoned** — there is no detector to show anything with, and the cutter is still zrb's | Second, because it needs stage 1 |
| 3 | The silence-based end of a turn, replaced by a semantic turn analyzer. **Abandoned**, and it followed stage 2: there was never a detector driving turn starts to build it on | Third, because it needs the detector driving turn starts |
| 4 | The STT backends behind STT services, vosk first. **Partly taken, and out of this order**: `whisper`, `moonshine` and `funasr` are Pipecat services behind a name, while vosk is still zrb's own backend. The services landed *before* stages 2 and 3 rather than after them | Fourth, because it is what the guards read |
| 5 | Output, through a Pipecat output-transport subclass over `PcmUtterance`. **Not taken**: zrb asks a TTS service for a sentence's audio and plays it itself, so there is no transport to interrupt | Last, because it is the least measured, and the one that must not break a pause |

What landed is therefore the services and not the stages, and stage 1 was retired with the stages it was to enable. The order changed because the driven path needs nothing from the detector: zrb already knows where the utterance ended, because it cut it, so a service can be put behind that boundary without waiting for the detector to reproduce it. The detector's turn — stages 2 and 3 — is what would let zrb stop cutting, and it is unbuilt and abandoned.

One rule the plan did not have to state, because it only appears once a pipeline outlives an utterance: **a pipeline's lifetime is zrb's, and idle is its normal state.** A service loads its model in its constructor, so one pipeline is built per backend and kept for the session; between utterances it receives nothing, and only a transcript or a spoken frame tells Pipecat's worker the pipeline is still wanted. Left idle for five minutes it cancels itself, which took both pipelines down mid-session and failed every later utterance with "the Pipecat worker stopped". Every worker zrb builds therefore passes `idle_timeout_secs=None`, so the monitor is never started rather than merely muted, and zrb closes the pipeline at the session's teardown — on the loop that owns it, because a worker is a task of that loop and only that loop can await it (ADR-0107).

A worker that ends without that close is not kept either. `STTPipeline.is_closed` reads the worker's own run task beside the flag `close` sets, so a stopped pipeline counts as none and the backend starts the next one before the next utterance, rather than failing every one after it.

### Regression gates

No stage may replace the old path until these pass on both paths:

1. A stop over speech pauses immediately, cancels the turn, and is sent nowhere.
2. A cough, room conversation, or zrb echo pauses and then resumes speech.
3. A spoken approval or denial answers the pending prompt.
4. A wake word said alone arms the next utterance for its window.
5. A slow or failed transcription does not stop capture or leave speech paused.
6. vosk confidence drops hands-free noise but never push-to-talk text.
7. An interrupted reply is not spoken again when the turn ends.
8. Speech control in one chat session cannot reach another.
9. Push-to-talk inserts editable text rather than submitting a turn.
10. A failure while starting, feeding or tearing the pipeline down leaves the chat usable.

### Change it here

| To… | Open | Then run |
| --- | --- | --- |
| Change which service a session listens or speaks through, or what an unset voice falls back to | `src/zrb/llm/voice/builtin.py`, `src/zrb/llm/voice/registry.py` | `test/llm/voice/test_registry.py`, `test/llm/voice/test_builtin.py` |
| Change how a segment reaches an STT service, or what ends its transcription | `src/zrb/llm/dictation/pipecat_stt.py` | `test/llm/dictation/test_pipecat_stt.py` |
| Change how a sentence's audio is made, read or dropped | `src/zrb/llm/speech/pipecat_tts.py` | `test/llm/speech/test_pipecat_tts.py` |
| Change utterance cutting, the bar over zrb's voice, or the bar under ordinary speech | `src/zrb/llm/dictation/listen.py` | `test/llm/dictation/test_listen_barge_in.py`, `test/llm/dictation/test_listen.py` |
| Change the transcript guards or command routing | `src/zrb/llm/dictation/feature.py`, `src/zrb/llm/dictation/words.py` | `test/llm/dictation/test_feature_barge_in.py` |
| Change playback or pausing | `src/zrb/llm/speech/player.py` | `test/llm/speech/test_player_in_process.py` |

## See Also

- [Dictation & Barge-in](dictation-barge-in.md) — the flow this pipeline replaces and must keep
- [ADR-0107](../../adr/adr-0107.md) — the decision to build on Pipecat, and the boundary
- [ADR-0102](../../adr/adr-0102.md), [ADR-0103](../../adr/adr-0103.md), [ADR-0105](../../adr/adr-0105.md) — the clauses that survive and the ones that die
- [UI](../2-extension-surface/ui.md) — the extension points the pipeline installs through

🔖 [Documentation Home](../../../README.md) > [Architecture](../README.md) > Voice on Pipecat
