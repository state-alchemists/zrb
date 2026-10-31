# agent_state · L0

One-line: Ambient ContextVars and typed getters for the current agent run.

- Layer: L0
- Purpose: Hold per-run UI, approvals, YOLO flag, limiter, run scope, and model overrides.
- Public entry points: `src/zrb/llm/agent_state.py`
- Depends on: any_ui (L0)
- Used by: agent/run (L2), tools/hooks (L1), subagent/live_session (L3)
- Key ADRs: ADR-0004, ADR-0120
- Tests: `test/llm/agent_state/*`, `test/llm/agent/run/*`
