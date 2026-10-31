# delegation_api · L0

One-line: Registry for sub-agent manager and live-session registry, so tools never import subagent/* directly.

- Layer: L0 (contracts and registries)
- Purpose: Provide `default_sub_agent_manager()`, `get_live_session_registry()`, and `start_titling(...)` for delegation tools.
- Public entry points: `src/zrb/llm/delegation_api.py`, `src/zrb/llm/any_sub_agent_*.py`, `src/zrb/llm/any_live_*.py`
- Depends on: any_sub_agent_manager/definition, any_live_session_registry/sub_agent_session (L0)
- Used by: tool/delegate*.py (L1)
- Key ADR: ADR-0120
- Tests: `test/architecture/test_llm_layering_ratchet.py`, delegate tool tests
