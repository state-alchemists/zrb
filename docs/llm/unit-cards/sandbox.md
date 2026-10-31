# sandbox · L1

One-line: Filesystem sandbox checks and policies enforced at run time.

- Layer: L1
- Purpose: Guard file access for tools and model calls; opt-in layers.
- Public entry points: `src/zrb/llm/sandbox/*`
- Depends on: permission, config
- Used by: agent/run, tools
- Key ADRs: ADR-0065
- Tests: `test/llm/sandbox/*`
