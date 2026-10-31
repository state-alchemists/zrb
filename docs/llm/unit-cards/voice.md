# voice · L4

One-line: Pipecat voice-service registry for dictation and speech.

- Layer: L4
- Purpose: Select/configure voice backends.
- Public entry points: `src/zrb/llm/voice/*`
- Depends on: dictation/speech backends
- Used by: dictation, speech
- Key ADRs: ADR-0107
- Tests: `test/llm/voice/*`
