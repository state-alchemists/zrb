🔖 [Documentation Home](../../../README.md) > [Architecture](../README.md) > Voice on Pipecat

# Voice on Pipecat

> **Tier 3 · Peripheral flow** · Code: `src/zrb/llm/dictation/`, `src/zrb/llm/speech/` · Read first: [Dictation & Barge-in](dictation-barge-in.md)

zrb's voice moves off its hand-rolled path and onto Pipecat's pipeline, one stage at a time ([ADR-0107](../../adr/adr-0107.md)). This page is the plan and the boundary it may not cross. The idea to take away: **Pipecat owns the media pipeline, zrb owns the meaning.** Pipecat answers "what audio event is happening"; zrb answers "what does that mean for this chat session". A stage lands only while both answers stay the same.

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

| Pipecat owns | zrb owns |
| --- | --- |
| Audio frames, input and output queues | The microphone device, and the only code that opens it |
| Voice activity detection | The bar over zrb's own voice, and the room's |
| Turn-start and turn-end signalling | Wake words, stop words, approvals, minimum-word guards |
| Speech-to-text and text-to-speech frame flow | Whether a transcript is meant for zrb at all |
| Interruption propagation | Pause, resume or stop, per chat session |
| Media-pipeline lifecycle and voice metrics | The pydantic-ai agent, the UI, and the prompt |

A conversation is one pass through both columns: the user speaks, Pipecat says speech happened and where it ended, and zrb decides whether those words are a turn, an answer to a prompt, a stop, or noise.

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
| A pipeline that fails, while it starts, while a block is handed to it, or while it is torn down, is closed and leaves the listening going | `test/llm/dictation/test_feature_pipecat.py` |
| Every captured block still reaches the pipeline's far end, with the detector in front of it | `test/llm/dictation/test_pipecat_input.py::test_a_pipeline_fed_silence_reports_no_speech_and_keeps_every_byte`, `::test_closing_hands_every_block_over_before_it_stops_the_worker` |
| The one thing the pipeline is turned on for — what it heard — is reported once, when the listening ends | `test/llm/dictation/test_feature_pipecat.py::test_what_the_pipeline_heard_is_reported_when_the_listening_ends` |
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

The framework names below are Pipecat's, not zrb's. What is built in `src/` today is the tap: the transport, the detector, the metrics stage and the sink.

| Part | What it does | Replaces |
| --- | --- | --- |
| zrb capture | Keeps the microphone and cuts nothing; pushes an `InputAudioRawFrame` into the pipeline | nothing — stays zrb's |
| `create_input_transport` | A `BaseInputTransport` subclass whose `start` calls `set_transport_ready`, the call the base class omits; without it the pushed frames are never drained | the front of `listen` |
| `create_voice_activity_detector` | A `VADProcessor` over `SileroVADAnalyzer`, which tells speech from silence per 32 ms frame. The model ships inside Pipecat and runs offline | `UtteranceCutter`'s loudness bars |
| Turn strategies | VAD-triggered and minimum-word turn starts, the second applying its threshold only while zrb speaks | the barge-in state machine's start logic |
| vosk STT | A custom STT service: Pipecat ships none, and this keeps the wake-word gate and per-word confidence | the vosk backend |
| zrb agent | pydantic-ai, unchanged | nothing |
| zrb speech | zrb's speech backends behind a TTS service | the speech backends |
| Output transport | A Pipecat output-transport subclass overriding its audio write to play through `PcmUtterance` | `Speaker`'s playback loop |

Stage 1 has landed, in `src/zrb/llm/dictation/pipecat_input.py`: `create_input_transport` is the subclass, `push_audio` hands one captured block over at the rate the pipeline is running at, `create_audio_counter` writes what reaches the far end into an `AudioTally`, and `AudioPipeline` (`start`, `push`, `close`, `get_speech_metrics`) owns the pipeline and its worker task for as long as a listening lasts. `push` only queues a block, so `close` reads the tally against what it pushed before it stops the worker: a teardown that stopped first would cut off a listening's last blocks, the trailing silence among them, and the count this stage is measured on would be short.

It is off unless the flag, ZRB_LLM_DICTATION_PIPECAT_ENABLED, is on. With it on, the capture is fed to `[transport, detector, metrics stage, counter]`: the detector decides speech against silence, `create_speech_metrics_stage` times what it reports into a `SpeechMetricsRecorder` — from the audio the frames carry, and not from the clock the pipeline runs on — and the session says the total once when the listening ends. Nothing in the pipeline decides anything zrb acts on — what the flag proves is the transport and the detector, and the dictation and speech paths are untouched either way.

Three suites hold it up. `test/llm/dictation/test_pipecat_input.py` covers the transport, the detector and the metrics: fifty blocks pushed from outside are all counted at the sink, byte for byte, while the loop the pipeline was started on keeps ticking; a speech frame pushed at the source reaches the metrics stage; silence reports no speech and still arrives whole; a burst is caught up with before the worker is told to stop, so a listening's last blocks are analysed rather than cut off; a block carries the rate the pipeline is running at and not this module's default; the metrics stage times the audio the frames carry, so a burst worked through in milliseconds still reports the speech it heard; the recorder's arithmetic is pinned without a pipeline. A start that fails, or a cancel the worker will not take, ends its task and raises nothing.

`test/llm/dictation/test_feature_pipecat.py` covers the hand-off: a session with the flag on feeds the pipeline from the same capture, reports what it heard when the listening stops, and closes it; an install without the extra listens on and says so; and a start, a hand-over or a close that fails is reported and given up on rather than ending hands-free.

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
| 1 | Input only, behind a flag. **Landed**: the flag is ZRB_LLM_DICTATION_PIPECAT_ENABLED, `listen` hands every captured block over through `on_captured` from a task of its own, `AudioPipeline` owns the pipeline for the listening, and the detector and metrics stage report what was heard | First, because it can run beside what exists |
| 2 | `UtteranceCutter` and its loudness bars, once the detector's boundaries are shown to match the cutter's on recorded audio. Exit: the pinned rows still pass on the detector's path, and a mid-sentence pause still cuts where the cutter cut | Second, because it needs stage 1 |
| 3 | The silence-based end of a turn, replaced by a semantic turn analyzer. Exit: a turn does not end at a mid-sentence pause, and a slow transcript still ends inside the latency budget | Third, because it needs the detector driving turn starts |
| 4 | The STT backends behind STT services, vosk first. Exit: partials, finalization, confidence and cancellation behave as they do now, per mode | Fourth, because it is what the guards read |
| 5 | Output, through a Pipecat output-transport subclass over `PcmUtterance`. **Unverified**: nothing yet shows a pipeline interruption reaches zrb's pause fast enough, so this stage has no exit criterion that can be met today | Last, because it is the least measured, and the one that must not break a pause |

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
| Change the tap, its detector, or what it measures | `src/zrb/llm/dictation/pipecat_input.py` | `test/llm/dictation/test_pipecat_input.py` |
| Change how a session feeds the tap or reports it | `src/zrb/llm/dictation/feature.py` | `test/llm/dictation/test_feature_pipecat.py` |
| Change utterance cutting, the bar over zrb's voice, or the bar under ordinary speech | `src/zrb/llm/dictation/listen.py` | `test/llm/dictation/test_listen_barge_in.py`, `test/llm/dictation/test_listen.py` |
| Change the transcript guards or command routing | `src/zrb/llm/dictation/feature.py`, `src/zrb/llm/dictation/words.py` | `test/llm/dictation/test_feature_barge_in.py` |
| Change playback or pausing | `src/zrb/llm/speech/player.py` | `test/llm/speech/test_player_in_process.py` |

## See Also

- [Dictation & Barge-in](dictation-barge-in.md) — the flow this pipeline replaces and must keep
- [ADR-0107](../../adr/adr-0107.md) — the decision to build on Pipecat, and the boundary
- [ADR-0102](../../adr/adr-0102.md), [ADR-0103](../../adr/adr-0103.md), [ADR-0105](../../adr/adr-0105.md) — the clauses that survive and the ones that die
- [UI](../2-extension-surface/ui.md) — the extension points the pipeline installs through

🔖 [Documentation Home](../../../README.md) > [Architecture](../README.md) > Voice on Pipecat
