# tool_call · L1

One-line: Render tool-call messages, argument formatting, and safety framing.

- Layer: L1
- Purpose: Serialize/deserialize tool calls and untrusted data framing.
- Public entry points: `src/zrb/llm/tool_call/*`
- Depends on: message, util (L0)
- Used by: agent/run (L2)
- Key ADRs: ADR-0043, ADR-0048, ADR-0120
- Tests: `test/llm/tool_call/*`
