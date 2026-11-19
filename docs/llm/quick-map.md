🔖 [Documentation Home](../README.md) > Architecture > Quick Map

# Quick Map (LLM at a glance)

Use this page as the short orientation to the LLM subsystem. For deep details, follow the links. It is the LLM slice only: the whole tree is in the [Code Map](../contributing/code-map.md), and the design is in [Architecture](../architecture/README.md).

- Layers: L0 (contracts/leafs), L1 (capabilities), L2 (engine), L3 (orchestration), L4 (presentation). Lower layers do not import higher ones, except the lazy edges named in `KNOWN_UPWARD_EDGES` (`test/architecture/test_llm_layering_ratchet.py`). Shared behaviour is exposed via L0 facades and registries. See ADR-0120.
- Build/run agents from lower layers: import `from zrb.llm.shared.agent_runner import create_agent, run_agent` (not `zrb.llm.agent`).
- Delegation from tools: `from zrb.llm.shared.delegation_api import default_sub_agent_manager, get_live_session_registry, start_titling`.
- Resume a delegated session as a chat task: `from zrb.llm.resumed_session import create_resumed_chat_task` (a third unit of the orchestration layer: it names `task/`, `subagent/` names it, and neither package names the other).
- Run one sub-agent turn (the delegate tool and a live-session continuation both do): `from zrb.llm.shared.subagent_turn import SubAgentTurn, run_subagent_turn`.
- Multimodal helper: `from zrb.llm.tool.multimodal_describe import ...`.

Key units (one-liners)

- L0: `shared/` (the vocabulary every other package speaks: the ambient state, the three seams, the tool registry, the message shapes), the `any_*.py` contracts, `ui/fallback` (the floor inside the UI package), and the `config`, `memory` and `util` packages.
- L0 too: `shared/prompt_text.py` reads a prompt section by name and fills its placeholders — the lookup a tool needs to prompt its own small agent, kept out of `prompt/` so the two packages do not import each other. Its section files are in `shared/markdown/`.
- L1: tool (callable functions), tool_call (rendering, untrusted data), prompt (compose), hook (lifecycle), permission/approval/sandbox, history_manager.
- L2: agent (engine, and the built-in tool seed), summarizer.
- L3: task (LLMChatTask), subagent (personas/live sessions), common_tools (host glue), custom_command.
- L4: ui (terminal/web), speech/dictation/camera/screenshot/voice/emotion, app.

Change map (do this → open this)

- Build/run agent from a tool: `src/zrb/llm/shared/agent_runner.py`.
- Delegate without importing subagent: `src/zrb/llm/shared/delegation_api.py`.
- Resume a sub-agent session without importing the chat task: `src/zrb/llm/resumed_session.py`.
- Add a tool: `src/zrb/llm/tool/<family>.py` and register via `agent/tool_seed.py`.
- Change the agent loop: `src/zrb/llm/agent/run/runner.py`.
- Change the prompt: `src/zrb/llm/prompt/manager.py`.
- Persist/compact history: `src/zrb/llm/history_manager/*`.
- UI behaviour: `src/zrb/llm/ui/*` and `src/zrb/llm/ui/fallback/*`.

Guards and tests

- Architecture layers/edges: `test/architecture/test_llm_layering_ratchet.py`.
- Circular import allowlist: `test/architecture/test_circular_import_allowlist.py`.
- Extension-point naming (Any*): `test/architecture/test_boundaries.py`.
