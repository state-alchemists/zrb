# subagent · L3

One-line: Discovers agent personas and builds sub-agents; owns live delegation sessions.

- Layer: L3 (orchestration)
- Purpose: Scan/resolve agent definitions, build agents, manage live sessions and delegation.
- Public entry points: `src/zrb/llm/subagent/manager.py`, `live_session.py`
- Depends on: common_tools (L3), tool (L1), agent_runner (L0), agent (L2)
- Used by: delegate tools (L1) via delegation_api (L0)
- Key ADRs: ADR-0068..0069, ADR-0083, ADR-0108..0109, ADR-0120
- Tests: `test/llm/subagent/*`, `test/llm/tool/test_delegate_*`
