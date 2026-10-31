# hook · L1

One-line: Lifecycle hooks and hook manager with Claude-compatible protocol.

- Layer: L1
- Purpose: Execute hooks on chat events, including self-review and agent hooks.
- Public entry points: `src/zrb/llm/hook/*`, `agent/hook_agent.py`
- Depends on: tool, agent_runner (L1/L0)
- Used by: agent/run (L2), task (L3)
- Key ADRs: ADR-0071, ADR-0086, ADR-0116, ADR-0120
- Tests: `test/llm/hook/*`
