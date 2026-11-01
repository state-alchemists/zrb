# Zrb Agent Guide

## Project Overview

Zrb (Zaruba) is a Python coding agent with a built-in task DAG (v3.x). An LLM agent (`zrb llm chat`) plus pure-Python task definitions, DAG-based execution, and CLI and web UI runners. Core in `src/zrb/`.

## Development Setup

See [Maintainer Guide → Getting Started](docs/contributing/maintainer-guide.md#getting-started) for environment setup, running tests, and troubleshooting a failing `zrb-test.sh`.

## Where the code lives

`ls src/zrb/` plus each module's docstring is the authority; this is the orientation map.

| Path | What is in it |
| --- | --- |
| `attr/`, `env/`, `input/` | Deferred-evaluation attribute types, `Env`, `Input` |
| `builtin/` | Pre-packaged user-executable tasks (`zrb <group> <task>`) |
| `callback/`, `xcom/` | Task callbacks, and the per-task FIFO queue tasks exchange values through |
| `cmd/`, `content_transformer/` | Building and running shell and SSH commands (`command.py`, `remote.py`), `Scaffolder` content rewriting |
| `config/` | The `CFG` singleton, composed from mixins under `mixins/`. `CFG.FOO` access stays flat regardless of which mixin owns it |
| `context/`, `session/`, `session_state_log*/` | Three-tier context (SharedContext → Session → Context) and run state |
| `dot_dict/`, `util/` | `DotDict`, plus string/file/truncation helpers. At runtime `util/` imports only `zrb.attr`'s type aliases and, for `util/load.py`'s `zrb_print`, `zrb.context`; package cycles are guarded by `test_packages_do_not_import_each_other` |
| `git/` | Git commands and subtree config behind the `zrb git` builtins |
| `group/`, `task_status/` | CLI group tree, per-task status tracking |
| `llm/` | Everything LLM — see below |
| `llm_plugin/` | The built-in skills and agents that ship with zrb |
| `remote/` | `Host`/`Target` inventories (`host_inventory`, `target_inventory`) and the fan-out executor behind `zrb remote run/check` (ADR-0110) |
| `runner/` | `cli.py`, `web_app.py` + `web_route/`, and `chat/` (the chat session HTTP layer) |
| `task/` | The task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler`, `Scaffolder`, `RsyncTask`, and the `make_task` decorator. Shared constructor keywords live once in `base/params.py` |
| `contextvars.py` | Canonical index of every ambient `ContextVar`, its owning module, and its typed wrapper |

Inside `llm/`:

| Path | What is in it |
| --- | --- |
| `agent/` | Agent construction and the run loop. `run/runner.py` is the entry point; `gates.py` enforces permission denials and the sandbox. The L0 facade `llm/agent_runner.py` names `create_agent`/`run_agent` for lower layers |
| `subagent/` | Sub-agent definitions, discovery and delegation sessions — a layer above `agent/`. `agent/` imports it from one place only, `hook_agent.py`, to resolve an agent hook's tools; both edges are listed in `KNOWN_UPWARD_EDGES` (`test/architecture/test_llm_layering_ratchet.py`), which may only shrink |
| `ui/` | The UI implementations; the `AnyUI` contract is the top-level `any_ui.py`, and the prompt_toolkit TUI lives under `ui/default/app/` |
| `any_ui.py`, `ui_fallback/` | The `AnyUI` contract and the UI pieces L0 may construct (`StdUI`, `UIStateDefaultsMixin`, the `resolve_ui`/`create_combined_ui` resolver). They live outside `ui/` so a headless run does not load the presentation package |
| `any_agent.py`, `any_agent_result.py`, `any_agent_runner.py`, `agent_runner.py` | L0 agent contracts and the facade lower layers call to build/run agents without importing the engine package |
| `any_sub_agent_definition.py`, `any_sub_agent_manager.py`, `any_live_sub_agent_session.py`, `any_live_session_registry.py`, `delegation_api.py` | L0 delegation contracts (sub-agent manager, live-session registry) and the registry functions lower layers call instead of importing `subagent/*` |
| `approval/`, `permission/` | The approval channel, and the permission ruleset (`policy.py`, `state.py`) |
| `config/` | LLM-specific config: model resolution, the rate limiter |
| `custom_command/` | Slash commands built from skills and markdown |
| `history_manager/`, `summarizer/` | Conversation persistence and two-tier summarization |
| `hook/` | Claude-compatible lifecycle hooks |
| `lsp/`, `sandbox/`, `snapshot/` | Language-server clients, the opt-in FS sandbox, filesystem snapshots |
| `camera/`, `screenshot/`, `dictation/`, `speech/`, `emotion/` | Optional chat features — `/photo`, `/screenshot`, speech-to-text input, replies read aloud, the reply's and the prompt's emotion fired as a hook. Each is one `enable_*` call plus a config dataclass; all but `emotion/` also have a `backend/` package. None is known to the UI (ADR-0102) |
| `voice/` | The Pipecat STT/TTS service registry that `dictation/` and `speech/` select their backend from |
| `prompt/` | System-prompt composition — `manager.py`, `profile.py`, `live_context.py`, and the `markdown/` section files |
| `skill/` | Skill discovery and activation |
| `task/` | `llm_task.py` (`LLMTask`) and `task/chat/` (`LLMChatTask`) — both `BaseTask` subclasses that build pydantic-ai agents internally |
| `tool/` | Agent-callable tools, one module per tool family |
| `tool_call/` | Tool-call rendering, argument formatting, and tool policies |
| `util/` | LLM-side helpers: streaming, PDF/clipboard capture, history formatting, model capabilities |
| `message.py`, `factory_resolver.py`, `input_source.py`, `stream_observer.py` | Message-history repair (role alternation, orphaned tool calls), merging static and factory-produced tools, user-turn provenance, and the outside-the-UI stream observers (`enable_speech` uses one) |
| `common_tools.py` | Registers the shared baseline used by `LLMChatTask`, `LLMTask` and `SubAgentManager` |
| `agent_state.py`, `agent_tool_result.py`, `agent_activity.py`, `ambient_state.py`, `tool_registry.py` | Leaf modules shared by `agent/`, `tool/` and `ui/`, kept at top level so a reader does not import the package that happens to write them (ADR-0088) |

`llm_plugin/` is split into core and optional content: `core_skills/` (always-on methodology baseline), `skills/` (utility skills, gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS`), `core_agents/` (always-on sub-agents), and `agents/` (optional sub-agents, gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only optional built-in content — user, project and plugin skills and agents always load (ADR-0054).

`test/` mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a completeness claim: where a test exists it sits at the mirrored path, but many modules are covered through a caller instead.

**Two registration steps that are easy to forget. Both now fail as test failures rather than silently:**
- A new task under `builtin/` must also be imported in `builtin/__init__.py` and added to its `__all__`, or it simply never appears in the CLI. Guarded by `test/builtin/test_registration_completeness.py` — including the tree scan for a module `__init__.py` never imports. A task that exists only as another task's `upstream=` dependency belongs in that file's `INTERNAL_TASKS` map, with its reason.
- A new tool under `llm/tool/` must also be registered *and* `tag()`-ed with a `Capability` in `llm/common_tools.py::_seed_default_tools`, or it resolves to `Capability.UNKNOWN` (denied in plan mode). Guarded by `test_every_registered_tool_carries_a_known_capability` in `test/llm/test_common_tools.py`. Leaving a *third-party* or MCP tool untagged is still fine — `UNKNOWN` is deliberately safe-by-default there.

`hook/manager.py` builds a `HookType.AGENT` hook through a registration seam (`hook/agent_hook_registry.py`), because `zrb.llm.agent` itself depends on `hook.manager`. The real builder (`agent/hook_agent.py`) registers when any name re-exported by `zrb.llm.agent` is first resolved (ADR-0096); if it is missing, the hook fails with a logged warning instead of crashing. The engine also registers its `AnyAgentRunner` adapter at import so lower layers can call `zrb.llm.agent_runner.create_agent`/`run_agent`.

> For the design of each subsystem, see [`docs/architecture/README.md`](docs/architecture/README.md); for a top-down code tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/llm/llm-chat-lifecycle.md`.

## LLM Prompt System (where to look)

See `src/zrb/llm/prompt/manager.py` and `docs/architecture/2-extension-surface/prompts.md` for the design, defaults and profile ladder. Section wording lives in `src/zrb/llm/prompt/markdown/`. ADR-0049 records the invariants.

## References

- Architecture overview and reading paths: `docs/architecture/README.md`
- LLM layering quick map: `docs/llm/quick-map.md`
- ADR index: `docs/adr/README.md`
- Contributing and conventions: `docs/contributing/README.md`, `docs/contributing/framework-conventions.md`
