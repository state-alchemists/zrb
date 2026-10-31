# task · L3

One-line: The LLM task types, including LLMChatTask orchestration.

- Layer: L3
- Purpose: Drive the engine with configured tools, UIs, approvals, and hooks.
- Public entry points: `src/zrb/llm/task/*`
- Depends on: agent (L2), tool (L1), ui (L4)
- Used by: runners (CLI/web)
- Key ADRs: ADR-0072, ADR-0102, ADR-0120
- Tests: `test/llm/task/*`
