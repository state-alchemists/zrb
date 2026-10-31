# shell_cut · L0

One-line: Cooperative "cut the turn" signal and helpers.

- Layer: L0
- Purpose: Allow a running tool/run to be moved aside cleanly.
- Public entry points: `src/zrb/llm/shell_cut.py`
- Depends on: contextvars
- Used by: agent/run, delegate tools
- Key ADRs: ADR-0123, ADR-0132
- Tests: `test/llm/agent/run/*`
