# approval · L1

One-line: Approval channels and policies for tool-call confirmations.

- Layer: L1
- Purpose: Decide and route approvals; integrate with UI prompts.
- Public entry points: `src/zrb/llm/approval/*`
- Depends on: permission (L1), agent_state (L0)
- Used by: agent/run (L2)
- Key ADRs: ADR-0062, ADR-0135, ADR-0120
- Tests: `test/llm/approval/*`, `test/llm/agent/run/*`
