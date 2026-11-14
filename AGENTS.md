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
| `runner/` | `cli.py`, `web_app.py` + `web_route/`, `web_bind.py` (the fail-closed bind check), and `chat/` (the chat session HTTP layer) |
| `task/` | The task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler`, `Scaffolder`, `RsyncTask`, and the `make_task` decorator. Shared constructor keywords live once in `base/params.py` |
| `contextvars.py` | Canonical index of every ambient `ContextVar`, its owning module, and its typed wrapper |

Inside `llm/`:

| Path | What is in it |
| --- | --- |
| `shared/` | The vocabulary every other package speaks, at L0: the ambient state a run publishes (`ambient_state`, `agent_state`, `agent_activity`, `agent_tool_result`), the two seams a higher package registers itself into (`agent_runner` to build and run an agent, `delegation_api` to reach the sub-agent manager and live-session registry), `tool_registry`, the message shapes (`message`, `message_text`), and the helpers that cut, observe and log a run (`shell_cut`, `stream_observer`, `input_source`, `factory_resolver`, `feature_config`, `usage_log`). A seam names the contracts it fronts under `if TYPE_CHECKING:` only — the engine and the subagent package register into them while they load, so a runtime import back would close the cycle (`test/architecture/test_seam_module_imports.py`). Moved here from the top of `llm/` (ADR-0088) |
| `agent/` | Agent construction and the run loop. `run/runner.py` is the entry point; `gates.py` enforces permission denials and the sandbox. Its contracts are `any_agent.py`, `any_agent_result.py` and `any_agent_runner.py`. The L0 facade `shared/agent_runner.py` names `create_agent`/`run_agent` for lower layers, and the two protocols under `if TYPE_CHECKING:` |
| `subagent/` | Sub-agent definitions, discovery and delegation sessions — a layer above `agent/`. Its contracts are `any_sub_agent_definition.py`, `any_sub_agent_manager.py`, `any_live_sub_agent_session.py` and `any_live_session_registry.py`. `agent/` imports it from one place only, `hook_agent.py`, to resolve an agent hook's tools; both edges are listed in `KNOWN_UPWARD_EDGES` (`test/architecture/test_llm_layering_ratchet.py`), which may only shrink |
| `ui/` | The UI implementations; `AnyUI` and its five role contracts live in `ui/any_ui.py` and `ui/any_ui_<role>.py`. Every role is reached as an accessor — `ui.display`, `ui.input`, `ui.picker`, `ui.session`, `ui.tools` — so the aggregate declares nine members, not fifty. `MultiUI` — the composite that fans one turn out to several interfaces — is a package, `ui/multi/`, with one module per job (`state`, `fanout`, `tools`, `turn`, `streaming`, `input`, `run`). The prompt_toolkit TUI lives under `ui/default/app/` |
| `ui/fallback/` | The UI pieces L0 may construct (`StdUI`, `UIStateDefaultsMixin`, the `resolve_ui`/`create_combined_ui` resolver). It is a floor inside `ui/`: `ui/__init__.py` imports nothing eagerly and the layering ratchet scores this prefix as L0, so a headless run reaches it without loading prompt_toolkit |
| `approval/`, `permission/` | The approval channel, and the permission ruleset (`policy.py`, `state.py`) |
| `config/` | LLM-specific config: model resolution, the rate limiter |
| `custom_command/` | Slash commands built from skills and markdown |
| `history_manager/`, `summarizer/` | Conversation persistence and two-tier summarization |
| `hook/` | Claude-compatible lifecycle hooks |
| `lsp/`, `sandbox/`, `snapshot/` | Language-server clients, the opt-in FS sandbox, filesystem snapshots |
| `memory/` | The persistent store behind `Remember`/`Forget`/`SearchMemory` — `paths`, `model` (the fact and diary shapes), `store` (the locked write transaction), `render` (the core, `## Recent` and the delta), `search`, and `migrate` (a notes directory → memory, on first use or by `zrb memory migrate`). A leaf: it imports `config` and `util` only. It replaced the journal, whose code was deleted in 3.33.0 (ADR-0138) |
| `camera/`, `screenshot/`, `dictation/`, `speech/`, `emotion/` | Optional chat features — `/photo`, `/screenshot`, speech-to-text input, replies read aloud, the reply's and the prompt's emotion fired as a hook. Each is one `enable_*` call plus a config dataclass; all but `emotion/` also have a `backend/` package. None is known to the UI (ADR-0102) |
| `voice/` | The Pipecat STT/TTS service registry that `dictation/` and `speech/` select their backend from |
| `prompt/` | System-prompt composition — `manager.py`, `profile.py`, `live_context/`, and the `markdown/` section files |
| `skill/` | Skill discovery and activation |
| `task/` | `llm_task.py` (`LLMTask`) and `task/chat/` (`LLMChatTask`) — both `BaseTask` subclasses that build pydantic-ai agents internally |
| `tool/` | Agent-callable tools, grouped by domain: `file/`, `delegate/`, `shell/`, `plan/`, `web/` and `code/` are packages whose `__init__` re-exports the names their flat module used to export; a tool that is one module stays a module |
| `tool_call/` | Tool-call rendering, argument formatting, and tool policies |
| `util/` | LLM-side helpers: streaming, PDF/clipboard capture, history formatting, model capabilities. A leaf: it imports nothing from `zrb.llm` at runtime but the `agent/types.py` contract, so `shared/` can depend on it without a cycle |
| `common_tools.py` | Registers the shared baseline used by `LLMChatTask`, `LLMTask` and `SubAgentManager` |

`llm_plugin/` is split into core and optional content: `core_skills/` (always-on methodology baseline), `skills/` (utility skills, gated by `CFG.LLM_BUILTIN_SKILLS_ENABLED`), `core_agents/` (always-on sub-agents), and `agents/` (optional sub-agents, gated by `CFG.LLM_BUILTIN_AGENTS_ENABLED`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only optional built-in content — user, project and plugin skills and agents always load (ADR-0054).

One layout rule the tables above do not state: an `__init__.py` is optional here, and 79 directories under `src/zrb` have none against 62 that do — including packages a reader works in daily (`cmd/`, `util/`, `config/`, `group/`, `runner/`), which are implicit namespace packages. The file earns its place two ways: it curates names with a re-export (`llm/ui/`, `llm/tool/`), or it carries a package-level note (`llm/shared/` explains its layer rule; `llm/agent/run/`'s is empty). `zrb/llm/` itself has none, so that a narrow `zrb.llm.sandbox` import does not pull the whole LLM stack (changelog 2.58.0). Add one when the package has something to curate or say — not to make it "real".

`test/` mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a completeness claim: where a test exists it sits at the mirrored path, but many modules are covered through a caller instead.

**Two registration steps that are easy to forget. Both now fail as test failures rather than silently:**
- A new task under `builtin/` must also be imported in `builtin/__init__.py` and added to its `__all__`, or it simply never appears in the CLI. Guarded by `test/builtin/test_registration_completeness.py` — including the tree scan for a module `__init__.py` never imports. A task that exists only as another task's `upstream=` dependency belongs in that file's `INTERNAL_TASKS` map, with its reason.
- A new tool under `llm/tool/` must also be registered *and* `tag()`-ed with a `Capability` in `llm/common_tools.py::_seed_default_tools`, or it resolves to `Capability.UNKNOWN` (denied in plan mode). Guarded by `test_every_registered_tool_carries_a_known_capability` in `test/llm/test_common_tools.py`. Leaving a *third-party* or MCP tool untagged is still fine — `UNKNOWN` is deliberately safe-by-default there.

`hook/manager/manager.py` builds a `HookType.AGENT` hook through a registration seam (`hook/agent_hook_registry.py`), because `zrb.llm.agent` itself depends on `hook.manager`. The real builder (`agent/hook_agent.py`) registers when any name re-exported by `zrb.llm.agent` is first resolved (ADR-0096); if it is missing, the hook fails with a logged warning instead of crashing. The engine also registers its `AgentRunner` adapter at import so lower layers can call `zrb.llm.shared.agent_runner.create_agent`/`run_agent`.

> For the design of each subsystem, see [`docs/architecture/README.md`](docs/architecture/README.md); for a top-down code tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/llm/llm-chat-lifecycle.md`.

## LLM Prompt System (where to look)

See `src/zrb/llm/prompt/manager.py` and `docs/architecture/2-extension-surface/prompts.md` for the design, defaults and profile ladder. Section wording lives in `src/zrb/llm/prompt/markdown/`. ADR-0049 records the invariants.

## References

- Architecture overview and reading paths: `docs/architecture/README.md`
- LLM layering quick map: `docs/llm/quick-map.md`
- ADR index: `docs/adr/README.md`
- Contributing and conventions: `docs/contributing/README.md`, `docs/contributing/framework-conventions.md`
