# agent · L2

One-line: Agent construction and the run loop (pydantic-ai), lazily exported.

- Layer: L2 (engine)
- Purpose: Build pydantic-ai Agents and run them with rate limiting, history, UI, and approvals.
- Public entry points: `src/zrb/llm/agent/__init__.py`, `run/runner.py`, `common.py`
- Depends on: prompt, tool_call, permission, sandbox, agent_state, config (L0–L1)
- Used by: task (L3), summarizer (L2), agent_runner (L0 registration)
- Key ADRs: ADR-0036, ADR-0096, ADR-0120
- Tests: `test/llm/agent/run/*`, `test/llm/history_manager/*`
