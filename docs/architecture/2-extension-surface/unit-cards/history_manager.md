# history_manager · L1

One-line: Conversation persistence, naming, loading and compaction.

- Layer: L1
- Purpose: Save/load histories, name new conversations, compact long ones.
- Public entry points: `src/zrb/llm/history_manager/*`
- Depends on: config, message, message_text, summarizer (L0–L2)
- Used by: agent/run (L2), ui (L4)
- Key ADRs: ADR-0041, ADR-0109, ADR-0130, ADR-0120
- Tests: `test/llm/history_manager/*`
