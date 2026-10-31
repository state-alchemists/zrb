# agent_runner · L0

One-line: Facade for building and running agents from lower layers without importing the engine.

- Layer: L0 (contracts and facades)
- Purpose: Expose `create_agent` and `run_agent` to tools/hooks/history via a stable L0 surface.
- Public entry points: `src/zrb/llm/agent_runner.py` (functions), `src/zrb/llm/any_agent*.py` (Protocols)
- Depends on: any_agent, any_agent_result, any_agent_runner (L0)
- Used by: tool, hook, history_manager (L1)
- Key ADR: ADR-0120 (LLM layered architecture with L0 facades)
- Tests: `test/architecture/test_llm_layering_ratchet.py`, tool and hook tests that patch `run_agent`
