# tool · L1

One-line: Agent-callable tools, one module per family, imported by name or deferred.

- Layer: L1 (capabilities)
- Purpose: Provide the model with callable functions, each with JSON schema and capability tags.
- Public entry points: `src/zrb/llm/tool/__init__.py` (re-exports), individual tool modules
- Depends on: config, permission, sandbox, util, tool_call (L0/L1), agent_runner (L0)
- Used by: agent/run (L2), subagent (L3)
- Key ADRs: ADR-0056..0067, ADR-0089, ADR-0120
- Tests: `test/llm/tool/*`, `test/llm/test_common_tools.py`
