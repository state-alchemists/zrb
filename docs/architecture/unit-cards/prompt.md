# prompt · L1

One-line: Compose the system prompt from sections, profiles and live context.

- Layer: L1
- Purpose: Build the model’s instruction text; manage profiles and dynamic inserts.
- Public entry points: `src/zrb/llm/prompt/*`
- Depends on: config, tool surfaces for live context (L0–L1)
- Used by: agent/common (L2), task (L3)
- Key ADRs: ADR-0044..0050, ADR-0120
- Tests: `test/llm/prompt/*`
