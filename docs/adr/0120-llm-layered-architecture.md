---
title: ADR-0120 — LLM layered architecture and L0 facades
date: 2026-10-31
status: accepted
---

Rule: Lower layers do not import higher ones; shared behaviour reachable from lower layers is exposed via L0 contracts and registries.

Enforced by: test/architecture/test_llm_layering_ratchet.py (layers and upward edges), test/architecture/test_circular_import_allowlist.py (cycle allowlist), test/architecture/test_boundaries.py (Protocol naming in any_*.py).

Lives in: src/zrb/llm/any_*.py (contracts), src/zrb/llm/agent_runner.py, src/zrb/llm/delegation_api.py. Engine/subagent register implementations at import.

Context

The llm/ subsystem acts as an engine (agent), capabilities (tools, hooks, prompt), orchestration (tasks, subagents) and presentation (ui). Cross-imports raised contributor load and made changes risky. A ratchet first counted and then limited upward imports but left hot paths (tools → agent) coupled.

Decision

Expose shared behaviours via L0 facades and Protocols:

- Agent build/run: AnyAgentRunner (any_agent.py/any_agent_result.py/any_agent_runner.py) and facade agent_runner.py. Engine registers an adapter in agent/__init__.py.
- Delegation: AnySubAgentManager/AnySubAgentDefinition and AnyLiveSessionRegistry/AnyLiveSubAgentSession. The registry functions live in delegation_api.py; subagent/manager.py and subagent/live_session.py register their singletons.
- Multimodal helper moved under tool/.

Consequences

- Tools, hooks and history helpers call facades, not engine or subagent.
- Upward edges dropped (20 → 10 at the time of writing); behaviour unchanged.
- Protocols follow R9 naming (Any<Thing> in any_<thing>.py), counted by tests.

Notes

- agent/__init__.py resolves engine symbols lazily; two "# lazy: circular" imports are allowlisted.
- A list of 2+ UIs requires ui/multi_ui.py to register the combiner; the fallback lives in ui_fallback/.
