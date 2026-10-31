# ui · L4

One-line: Presentation layer UIs (terminal, web), rendering, and interaction.

- Layer: L4 (presentation)
- Purpose: Render output, capture input, stream events; MultiUI composition.
- Public entry points: `src/zrb/llm/ui/*`
- Depends on: any_ui, ui_fallback, message_queue (L0), tool/output types
- Used by: task/chat (L3), agent/run (L2)
- Key ADRs: ADR-0074..0079, ADR-0116..0133, ADR-0120
- Tests: `test/llm/ui/*`, `test/llm/agent/run/*` (integration)
