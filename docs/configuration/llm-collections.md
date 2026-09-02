🔖 [Documentation Home](../../README.md) > [Configuration](./) > LLM Component Collections

# LLM Component Collections: Registries, Managers & the Three Channels

Skills, sub-agents, hooks, extra prompts, and tools are all **component families** of the same kind. Each family is built from the same three pieces, configured through the same three channels. Learn this page once and every family behaves predictably (ADR-0090, ADR-0091).

---

## Table of Contents

- [The one mental model](#the-one-mental-model)
- [The five component families](#the-five-component-families)
- [Three configuration channels](#three-configuration-channels)
- [Resolution order](#resolution-order)
- [Deferred defaults: seeds, deltas, and lazy reads](#deferred-defaults-seeds-deltas-and-lazy-reads)
- [Worked examples](#worked-examples)
- [`get_prompt(name)` vs `get_prompts()`](#get_promptname-vs-get_prompts)

---

## The one mental model

Every component family has:

| Piece | What it is | Instance |
|-------|-----------|----------|
| **`*Registry`** | The canonical, shared collection — the *source of defaults*. One per process. | `skill_registry`, `sub_agent_registry`, `hook_registry`, `prompt_registry`, `tool_registry` |
| **`*Manager` (or host)** | The per-task, resolved view that actually runs. Reads the registry as its default unless told otherwise; its own `append`/`prepend`/`remove` ops layer over that resolved base without freezing it. | `SkillManager`, `SubAgentManager`, `HookManager`, `PromptManager`, an agent host (`LLMChatTask`/`LLMTask`/`SubAgentManager`) |
| **CFG twin** | The env-var face of the registry — `CFG.LLM_*` reads as `ZRB_LLM_*`. | `LLM_SKILLS`, `LLM_AGENTS`, `LLM_HOOKS`, `LLM_PROMPT`, `LLM_TOOLS` |

The registry **stores** everything the family knows; the manager **consumes** it. `zrb_init.py` and env vars both configure the registry (or a manager's view of it); a task argument overrides one host.

## The five component families

| Family | Registry | Consumer | Collection kind | Mutation verbs | CFG twin | Twin semantics |
|--------|----------|----------|-----------------|----------------|----------|----------------|
| Prompts | `prompt_registry` | `PromptManager` | **Ordered** pipeline | `append_prompt` / `prepend_prompt` / `set_prompts` / `remove_prompt` | `LLM_PROMPT` | **Content**: extra sections appended after the built-ins. One prompt *is* a string, so the twin carries content rather than a name list |
| Tools | `tool_registry` | agent hosts | **Ordered** list | `append_tool` / `prepend_tool` / `set_tools` / `remove_tool` (+ `*_tool_factory`, `*_toolset_factory`) | `LLM_TOOLS` | **Name allowlist**: non-empty keeps only the named static tools visible to agents |
| Skills | `skill_registry` | `SkillManager` | **Unordered**, name-keyed | `add_skill` / `set_skills` / `remove_skill(name)` | `LLM_SKILLS` | **Name allowlist**: non-empty keeps only the named skills in the catalogue |
| Sub-agents | `sub_agent_registry` | `SubAgentManager` | **Unordered**, name-keyed | `add_agent` / `set_agents` / `remove_agent(name)` | `LLM_AGENTS` | **Name allowlist**: non-empty keeps only the named agents in the roster |
| Hooks | `hook_registry` | `HookManager` | **Event-keyed** accumulation | `add_hook` / `set_hooks(event, hooks)` / `remove_hook` | `LLM_HOOKS` | **Name allowlist**: non-empty dispatches only the named hooks |

The verbs differ by collection kind, and the split is deliberate:

- **Ordered** collections (prompts, tools) — *order is the semantics*. Appends land at the end, prepends at the front; there is no `add_` alias because `add` couldn't say where.
- **Unordered, name-keyed** collections (skills, agents) and **event-keyed** collections (hooks) — *names (or events) are the identity*. `add_skill(mine)` is idempotent by name, and `remove_skill("mine")` takes a name; `add_hook` accumulates onto an event the same way, with `set_hooks(event, hooks)` for a deliberate clean-slate swap of one event.

## Three configuration channels

There are exactly three ways to configure any family, and each does one thing:

### 1. Environment variables — *name things*

The `ZRB_LLM_*` twins restrict *which* members are visible/dispatched (or, for prompts, *what* gets appended). They are deliberately shallow: an env var names a thing, it can't build one.

```bash
# Only the named skills/agents/hooks survive. For tools, the list narrows the
# static set; per-run tools (plan mode, ask, journal, task, MCP, …) keep gates.
export ZRB_LLM_SKILLS="code-review,commit-helper"
export ZRB_LLM_AGENTS="debugger,build-dispatcher"
export ZRB_LLM_HOOKS="journal-compliance-judge"
export ZRB_LLM_TOOLS="Shell,Read,Write,Grep,Glob"

# Prompts are content, so the twin is content too.
export ZRB_LLM_PROMPT="Always answer in British English.,Prefer git over GUI."
```

An **empty** twin (the default) means **everything**: all built-in and discovered skills/agents/hooks/tools. Set it to list only what you want. The twin restricts only the *discovered/default* layer: something you `add_*`/`set_*` in `zrb_init.py` is manual content and always visible for skills and agents (env sets the baseline, code builds on it). Hooks form a single-layer registry, so `LLM_HOOKS` governs the whole hook registry. `LLM_TOOLS` is narrower — it filters the registry's **static** tools only. Per-run tools (`EnterPlanMode` / `AskUserQuestion` on interactive runs, the journal tools, `RunZrbTask`, `ActivateSkill`, `MonitorProcess`, and every MCP toolset) are not statically named and keep their own gates (interactive, journal, spill, MCP config) regardless of the allowlist; restricting *those* needs `tool_registry.remove_tool(...)` / `set_tools()` in `zrb_init.py`. `LLM_TOOLS` and the rosters still honor their independent toggles — `LLM_ENABLE_BUILTIN_AGENTS`, `LLM_ENABLE_BUILTIN_SKILLS`, `HOOKS_ENABLED` — which gate the built-in bulk independently of the allowlist.

### 2. `zrb_init.py` — *build and replace things*

Anything an env var can't express — a callable tool, a discovered-skill collision, a hook with a matcher, a runtime dependency — belongs here. Mutate the registry directly:

```python
# zrb_init.py — ran once at CLI startup, before any task runs.
from zrb import hook_registry, prompt_registry, skill_registry, sub_agent_registry
from zrb.llm.agent.subagent.definition import SubAgentDefinition
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.types import HookEvent
from zrb.llm.skill.manager import Skill

# Skills and sub-agents — add to what discovery found.
skill_registry.add_skill(Skill(name="my-skill", path=".", description="..."))
sub_agent_registry.add_agent(
    SubAgentDefinition(name="my-agent", path=".", description="...")
)

# A hook — attach to a lifecycle event; empty events = global.
async def guard(ctx) -> HookResult:
    return HookResult(success=True, output="ok")

hook_registry.add_hook(guard, events=[HookEvent.PRE_TOOL_USE])
```

Replace wholesale:

```python
# set_* takes a concrete list OR a zero-arg callable resolved at query time.
skill_registry.set_skills([Skill(name="only-this", path=".", description="...")])
prompt_registry.set_prompts(["Only these extra prompts run."])
```

Layer onto the shipped surface:

```python
from zrb.llm.tool.registry import tool_registry

def my_special_tool(ctx) -> dict:
    """..."""

tool_registry.append_tool(my_special_tool)   # after the built-ins
tool_registry.remove_tool("EnterWorktree")   # or drop a shipped one by name
```

> `zrb_init.py` is the *only* place user code runs at CLI startup. Customizing a family there means every `zrb llm chat` / `LLMTask` in the project sees it — exactly like registering a Zrb task in `zrb_init.py`.

### 3. Per-task / instance arguments — *override one host*

A manager or host constructor argument overrides the registry for that instance only. The most common example is a task's `prompt_manager`:

```python
from zrb import LLMChatTask

task = LLMChatTask(
    name="chat",
    prompt_manager=PromptManager(prompts=["Just this one bot."]),
)
task.append_tool(my_special_tool)   # this task only
```

Per-instance mutations (`task.append_tool`, `task.prompt_manager.append_prompt`) affect **that** manager's resolved list and never reach the shared registry.

## Resolution order

Components resolve by *layering*, not winner-take-all precedence. Each layer falls through to the layer below it (its default/fallback) and layers its own deltas on the result:

```
manager deltas — append/prepend/remove ops        layered over ↓
manager's own value — constructor arg, prompts=, set_*  (falls through ↓ when unset/None)
        ↓
registry contents — discovered + manual           (including everything zrb_init.py added)
        ↓
CFG twin (ZRB_LLM_* env var)                     (restricts the default/discovered layer; empty = all)
        ↓
code default                                     (lowest)
```

Concretely: `PromptManager(prompts=None)` reads `prompt_registry` *live* on every query; unless the registry was mutated in `zrb_init.py`, the registry's own default resolves `CFG.LLM_PROMPT`; the empty list is the code backstop. A manager's `append_prompt`/`remove_prompt` deltas are replayed over that live value, so registry or env changes *after* the append stay visible. `set_prompts` (or `prompts=`) replaces that layer's own value wholesale and clears its deltas — the layer below is then ignored. Same shape for skills (`SkillManager(registry=None)`), sub-agents, hooks, and tools.

## Deferred defaults: seeds, deltas, and lazy reads

Two behaviors keep the registry the source of truth without copying:

- **Seeds are lazy.** Tools (the heavy family — resolving the built-ins transitively imports `pydantic_ai`) ship as a *seed*: a stored zero-arg callable that is run the first time the registry is read, not at import. Skills/agents/hooks are discovered by their managers on first load, equally deferred. So `import zrb` never pays for content you don't use.
- **Deltas replay over the resolved base; nothing freezes.** `append_prompt`/`prepend_prompt`/`remove_prompt` on a registry or manager are stored as ordered ops and replayed over the freshly-resolved base on every read. A seed (or the `CFG.LLM_PROMPT` twin) keeps being honored underneath, so a later env change shows up in the appended prompts too. (Tools are the one exception: their lazy seed materializes on first access — the point of the seed is to keep heavy imports out of `import zrb`.)
- **The CFG twins are read at resolve time, not startup.** Changing `ZRB_LLM_TOOLS` (or `CFG.LLM_TOOLS`) takes effect on the next query, with no re-import. That's why the twins are "lazy reads": env var set → registry resolves → filter applies → agents get what's visible.

## Worked examples

**Pin the toolbox an agent may touch:**

```bash
export ZRB_LLM_TOOLS="Shell,Read,Write,Grep,Glob,TodoWrite"
# The STATIC tools are narrowed to these six. Per-run tools — plan mode, ask,
# journal, task, skill, monitor, and MCP — are gated by their own switches,
# not this list (see "Three configuration channels" above).
```

**Ship an org skill catalogue by name:** keep discovery, but narrow visibility:

```bash
export ZRB_LLM_SKILLS="code-review,commit-helper,oncall-handbook"
```

**Run a nightly hook roster:** hooks are global by default; gate them:

```bash
export ZRB_LLM_HOOKS="journal-compliance-judge"
```

**Append org-wide instructions without touching a task:**

```bash
export ZRB_LLM_PROMPT="Never quote stock without a warehouse."
```

## `get_prompt(name)` vs `get_prompts()`

Two lookalikes with one letter of difference, resolved differently:

- `PromptManager.get_prompt(name)` — the **section resolver**: finds a *markdown file* (persona, principle, workflow, …) by name on the prompt lookup path (`ZRB_LLM_PROMPT_DIR` → env → base dir → package). Used by composition; sections are fixed (ADR-0044).
- `.get_prompts()` (plural) on `PromptRegistry`/`PromptManager` — the **registry accessor**: returns the ordered *extra middleware list* configured via the registry or `set_prompts`/`append_prompt`.

`get_prompt` answers "what does the *persona* *section* read?"; `get_prompts` answers "what *extra* content is appended after the sections?". Plural spells the registry question.

---

🔖 [Documentation Home](../../README.md) > [Configuration](./) > LLM Component Collections