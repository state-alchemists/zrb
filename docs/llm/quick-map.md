🔖 [Documentation Home](../README.md) > Architecture > Quick Map

# Quick Map (LLM at a glance)

Use this page as the short orientation to the LLM subsystem. For deep details, follow the links.

- Layers: L0 (contracts/leafs), L1 (capabilities), L2 (engine), L3 (orchestration), L4 (presentation). Lower layers do not import higher ones, except the lazy edges named in `KNOWN_UPWARD_EDGES` (`test/architecture/test_llm_layering_ratchet.py`). Shared behaviour is exposed via L0 facades and registries. See ADR-0120.
- Build/run agents from lower layers: import `from zrb.llm.agent_runner import create_agent, run_agent` (not `zrb.llm.agent`).
- Delegation from tools: `from zrb.llm.delegation_api import default_sub_agent_manager, get_live_session_registry, start_titling`.
- Multimodal helper: `from zrb.llm.tool.multimodal_describe import ...`.

Key units (one-liners)

- L0: any_ui, ui_fallback, agent_runner (facade), delegation_api (registry), agent_state (ContextVars), tool_registry, util, message, usage/journal logs.
- L1: tool (callable functions), tool_call (rendering, untrusted data), prompt (compose), hook (lifecycle), permission/approval/sandbox, history_manager.
- L2: agent (engine), summarizer.
- L3: task (LLMChatTask), subagent (personas/live sessions), common_tools (seed registry), custom_command.
- L4: ui (terminal/web), speech/dictation/camera/screenshot/voice/emotion, app.

Change map (do this → open this)

- Build/run agent from a tool: `src/zrb/llm/agent_runner.py`.
- Delegate without importing subagent: `src/zrb/llm/delegation_api.py`.
- Add a tool: `src/zrb/llm/tool/<family>.py` and register via `common_tools.py`.
- Change the agent loop: `src/zrb/llm/agent/run/runner.py`.
- Change the prompt: `src/zrb/llm/prompt/manager.py`.
- Persist/compact history: `src/zrb/llm/history_manager/*`.
- UI behaviour: `src/zrb/llm/ui/*` and `src/zrb/llm/ui_fallback/*`.

Guards and tests

- Architecture layers/edges: `test/architecture/test_llm_layering_ratchet.py`.
- Circular import allowlist: `test/architecture/test_circular_import_allowlist.py`.
- Extension-point naming (Any*): `test/architecture/test_boundaries.py`.
