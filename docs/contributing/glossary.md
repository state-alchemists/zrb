🔖 [Documentation Home](../README.md) > [Contributing](./) > Glossary

# Glossary

The words this repository uses as if they were ordinary English. Each entry is one line; follow the last column when the one line is not enough. For the rules behind the words, start at [Coding Conventions](coding-conventions.md) and [Which pattern do I reach for?](which-pattern.md).

| Term | What it means here | Read more |
| --- | --- | --- |
| **`Any*`** | An abstract extension point named `Any<Thing>` and kept in `any_<thing>.py` in the package that owns the concept. Callers type against it, never against an implementation. | [Framework Conventions](framework-conventions.md) R9, [Architecture, Philosophy & Conventions](architecture.md#interfaces-everywhere-the-any-pattern) |
| **Part** | A class that adds behavior to one host and reads state it does not own: `<Owner><Aspect>` in a file named for the aspect, held by the owner and reached through public accessors. | [Which pattern → Mixin vs. part](which-pattern.md#the-one-hard-call-mixin-vs-part) |
| **Mixin** | A class that reads only state it sets itself, so any class may inherit it (`BufferedOutputMixin`, the `CFG` mixins). | [Which pattern → Mixin vs. part](which-pattern.md#the-one-hard-call-mixin-vs-part) |
| **Seam** | A module that names the contracts a higher layer registers into, so a lower layer can call upward without importing upward (`llm.shared.agent_runner`, `llm.shared.delegation_api`). | [The LLM Turn](../architecture/1-spine/llm-turn.md) |
| **L0–L4** | The five layers of `zrb.llm`: L0 contracts, L1 capabilities, L2 engine, L3 orchestration, L4 presentation. A layer imports only itself and the layers below. | [LLM Layering](../architecture/README.md), ADR-0120 |
| **Registry** | An ordered or name-keyed collection users extend (`append_X`/`add_X`), owned by its manager. | [Framework Conventions](framework-conventions.md) R5/R6 |
| **Manager** | The object that owns one registry: it scans, holds and resolves that family of components. | [Which pattern](which-pattern.md) |
| **Factory** | A callable that builds a tool, prompt or UI for one run, so a config or permission change is read again on the next run. | [Tools](../architecture/2-extension-surface/tools.md) |
| **Capability** | The tag on a tool (`READ`, `EDIT`, `EXECUTE`, `UNKNOWN`) that permission and sandbox rules branch on. | [Tools](../architecture/2-extension-surface/tools.md) |
| **Ambient state** | State published in a `ContextVar` and read where needed instead of being threaded through every signature. | [Context Propagation](../technical-specs/context-propagation.md) |
| **SharedContext / Session / Context** | The three tiers of run state: data shared by a whole run, the task graph and per-task status, then one task's own view. | [The System](../architecture/0-system/system.md) |
| **Task / DAG** | A unit of work, and the dependency graph the engine walks (`upstream`, `successor`). | [The Task Model](../architecture/1-spine/task-model.md) |
| **XCom** | The per-task FIFO queue through which one task hands a value to another. | [XCom Deep Dive](../core-concepts/xcom-deep-dive.md) |
| **Env / Input / `*Attr`** | A user-supplied value, a declared input, and a deferred value evaluated against the live context at run time. `Tpl` is the rendered form of a string. | [Inputs](../core-concepts/inputs.md), [Environments](../core-concepts/environments.md) |
| **Scaffolder** | A task that generates files from templates, with `Tpl` rendering and content transformers. | [File Ops](../task-types/file-ops.md) |
| **Snapshot** | A copy of a file taken before a tool writes it, so `/rewind` can restore it. | [History & Compaction](../architecture/3-peripheral-flow/history-and-compaction.md) |
| **Sandbox** | Opt-in filesystem containment for tool calls: writes outside the writable roots and reads inside the deny-read list are refused. | [Sandbox](../llm/sandbox.md) |
| **Prompt section / preset / profile** | A named piece of the system prompt, a named set of sections, and the model-capability ladder that picks one. | [Prompts](../architecture/2-extension-surface/prompts.md) |
| **Sub-agent / delegation** | A child agent run started by a tool, with its own session and an authority snapshot taken when it was delegated. | [Sub-agents](../architecture/2-extension-surface/sub-agents.md) |
| **Skill** | A `SKILL.md` (or `SKILL.py`) methodology the agent activates for a turn when the task matches it. | [Skills & Commands](../architecture/2-extension-surface/skills-and-commands.md) |
| **Hook** | A handler on a lifecycle event (`PreToolUse`, `Stop`, …), compatible with Claude Code's hook shape. | [Hooks](../architecture/2-extension-surface/hooks.md) |
| **Toolset** | A group of tools pydantic-ai exposes as one unit, including MCP and LSP toolsets. | [Tools](../architecture/2-extension-surface/tools.md) |
| **Worktree** | A second checkout of the same git repository at another path, used to run a change without moving the one you are in. | [Agent Workflow](agent-workflow.md) |
| **Change Map / Code Map** | A symptom-to-file lookup, and a directory-to-contents map. They answer different questions; neither replaces the architecture pages. | [Change Map](../architecture/change-map.md), [Code Map](code-map.md) |

---

🔖 [Documentation Home](../README.md) > [Contributing](./) > Glossary
