# permission · L1

One-line: Capability ruleset and decision helpers that gate tool calls.

- Layer: L1
- Purpose: Evaluate `Capability` rules (allow/deny/ask) for tools.
- Public entry points: `src/zrb/llm/permission/*`
- Depends on: config (L0), tool metadata (L1)
- Used by: agent/run (L2), tools (L1)
- Key ADRs: ADR-0061, ADR-0063, ADR-0120
- Tests: `test/llm/permission/*`
