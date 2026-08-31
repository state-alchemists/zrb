🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Harness Comparison

# Choosing Between Agent Harnesses

Zrb's AI assistant (`zrb llm chat`) is one face of a task-automation framework. Claude Code, opencode, DeepSeek Harness, and Pi are excellent standalone coding agents — for pure interactive coding sessions, any of them will serve you well. This page explains what actually differs, so you can tell when zrb is the right home for your agent and when another harness (or both) fits better.

---

## Table of Contents

- [The One-Sentence Version](#the-one-sentence-version)
- [At a Glance](#at-a-glance)
- [Prompt & Context: Override Granularity](#prompt--context-override-granularity)
- [Scenario Guide](#scenario-guide)
  - [Interactive coding session](#interactive-coding-session)
  - [An agent as a step in a pipeline](#an-agent-as-a-step-in-a-pipeline)
  - [Scheduled and triggered agent runs](#scheduled-and-triggered-agent-runs)
  - [Shipping an agent inside your own product](#shipping-an-agent-inside-your-own-product)
  - [You already have Claude Code assets](#you-already-have-claude-code-assets)
  - [Team access through a browser](#team-access-through-a-browser)
- [Choose Zrb When… / Choose Another Harness When…](#choose-zrb-when-choose-another-harness-when)

---

## The One-Sentence Version

The other tools on this page are **agents that can run tasks**; Zrb is a **task-automation framework that hosts an agent**. If your goal ends at the conversation, pick whichever interactive experience you like best. If the conversation is one step inside a larger automated workflow — builds, deployments, checks, scaffolding, triggers — that workflow is zrb's native territory.

## At a Glance

| | Zrb (`zrb llm chat`) | Claude Code | opencode | DeepSeek Harness (`dsh`) | Pi |
|---|---|---|---|---|---|
| Primary identity | Task-automation framework with a built-in agent | Anthropic's coding agent | Open-source coding agent (client/server) | Plugin-everything agent harness | Self-extensible coding agent |
| Language / runtime | Python | Node.js | Go + TypeScript | TypeScript (Cordis) | TypeScript |
| Interactive TUI | ✅ prompt-toolkit based | ✅ | ✅ | Web-first (SSH forwarding supported) | ✅ |
| Web UI | ✅ — serves **tasks and chat** with authentication | — | ✅ | ✅ | Via pi-chat (separate project) |
| Providers | Anything pydantic-ai resolves via `ZRB_LLM_MODEL` (`provider:model`) — OpenAI, Anthropic, Google, OpenRouter, Ollama, LiteLLM, … | Anthropic models | Multi-provider | DeepSeek-centric | Multi-provider (`pi-ai`) |
| Agent inside a DAG pipeline | ✅ `LLMTask` is a first-class node: `intake >> triage >> route` | — | — | — | — |
| Triggers / schedulers around the agent | ✅ built-in (`Scheduler`, triggers) | — | — | — | — |
| Values passed between steps | ✅ XCom queues | — | — | — | — |
| Permission policy + OS sandbox | ✅ Python-level FS gate + Seatbelt/bubblewrap | ✅ permission prompts | ✅ permission modes | Plugin-defined | Deliberately none — containerize instead |
| Claude Code assets reuse | ✅ `CLAUDE.md`, `SKILL.md`, `AGENT.md`, `hooks.json` load natively ([details](claude-compatibility.md)) | Native | Partial (AGENTS.md) | Own plugin format | AGENTS.md |
| White-labeling (your own CLI name/brand) | ✅ built-in | — | — | — | — |

Nothing in the table is a knock against any tool — they simply optimize for different centers of gravity. "—" means the capability isn't the tool's job, not that it's impossible to bolt on.

## Prompt & Context: Override Granularity

How much of the agent can you change, and at what resolution? The four harnesses span a spectrum, from per-section to whole-prompt.

**Zrb is the most granular.** The system prompt is seven named sections — five file-backed rule sections (`persona`, `principle`, `workflow`, `example`, `profile`) and two runtime-fact sections (`system_context`, `project_context`) — each overridable on its own:

- **Per-section wording** — drop a same-named `.md` file onto the override chain (project `LLM_PROMPT_DIR` → env → base prompt dir → packaged `markdown/`).
- **Section set and order** — `ZRB_LLM_INCLUDE_SECTIONS` / `include_sections=`.
- **Standing extra content** — `system_prompt=` / `append_prompt()`.
- **Per-turn volatile state** — `add_live_context()`.
- **Model-class phrasing** — `ZRB_LLM_PROFILE` (`minimal` / `standard` / `capable` / `auto`).
- **The whole prompt** — a full middleware can still rewrite everything.

You edit the one concern you care about and the rest keeps working. See [Programming the Prompt](programming-the-prompt.md).

**opencode is granular at a different unit — the agent.** Each agent (built-in or custom) is defined by a `prompt` file you can replace outright, stacked under layered config, rules (AGENTS.md), plugins, and skills. You author many independently-replaceable prompts, but within one agent's prompt there are no named sections to edit.

**Claude Code keeps its base prompt opaque and Anthropic-managed.** You can replace the whole prompt (`--system-prompt` / `--system-prompt-file`, which drops the default tool guidance and safety instructions) or append to it (`--append-system-prompt`). The fine-grained surface is additive rather than editorial: `CLAUDE.md` files in four scopes, path-scoped rules under `.claude/rules/`, `@` imports, and auto-memory.

**Pi is the coarsest, on purpose.** One small fixed prompt over a handful of tools: replace it whole (`--system-prompt`), append to it (`--append-system-prompt`), or rewrite it per turn via its extension API, with `AGENTS.md` injected as project context. There is no per-section knob because there are no sections — for a minimal core that trusts a frontier model to already know how to be an agent, that's the point, not a gap.

A separate axis worth naming: **can you read the whole prompt?** Zrb, opencode, and Pi ship their base prompts as visible files you can diff and replace; Claude Code's lives in a closed binary and changes frequently, so it's reverse-engineered after the fact. Fine-grained and transparent are not the same thing — and trimming Zrb toward Pi's size is a `minimal`-profile plus `ZRB_LLM_INCLUDE_SECTIONS` setting, not a rewrite.

## Scenario Guide

### Interactive coding session

*"Fix this bug", "refactor this module", "explain this codebase."*

All five handle this. Differences are ergonomic, not fundamental:

- **Claude Code** if you're on Anthropic models and want the most polished, widely-documented loop.
- **opencode** if you want an open-source, provider-neutral TUI with a client/server architecture.
- **Pi** if you want a small, hackable core that extends itself at runtime.
- **DeepSeek Harness** if you're building around DeepSeek models and like its everything-is-a-plugin composition model (note: developer preview, compatibility-breaking changes expected).
- **zrb** if the session keeps spilling into automation or if you want your agent's permissions bounded by a filesystem sandbox without setting up containers.

### An agent as a step in a pipeline

This is where zrb stops being comparable and starts being alone in the list. In zrb, an LLM call is just a task, so everything tasks can do, agents can do:

```python
triage = triage_group.add_task(
    LLMTask(
        name="triage",
        message="Triage this ticket:\n\n{ctx.xcom['intake'].peek()}",
        tools=[lookup_customer],
    )
)

_ = intake >> triage >> route_task
```

The agent's verdict lands in XCom; downstream deterministic tasks act on it; failures propagate like any other task failure. Claude Code, opencode, dsh, and Pi are all *conversational drivers* — you can script them from bash, but there is no notion of a typed task graph, per-node inputs, readiness checks, or inter-step queues. If you find yourself writing bash glue to chain agent runs, that glue is a zrb DAG.

See [Programming the Agent](programming-the-agent.md) and [`examples/agent-in-pipeline`](../../examples/agent-in-pipeline).

### Scheduled and triggered agent runs

*"Summarize new issues every morning", "run the triage agent whenever a webhook fires."*

Zrb ships `Scheduler` and trigger primitives, so the agent inherits cron-like and event-driven execution without external orchestration. With the other harnesses this is a crontab wrapping their CLI plus hand-rolled state handling — workable, but you own the plumbing. See [Triggers & Schedulers](../task-types/triggers-and-schedulers.md).

### Shipping an agent inside your own product

Zrb supports [white-labeling](white-labeling.md): rename the CLI, rebrand the UI, and ship the whole thing — task runner, chat TUI, web UI with auth — as your tool. If "our product has an AI assistant and also automates things," zrb gives you both from one dependency. The standalone harnesses assume *they* are the product, not a component of yours.

### You already have Claude Code assets

Skills, sub-agents, hooks, and `CLAUDE.md` instructions written for Claude Code largely load in zrb unchanged — see [Claude Code Compatibility](claude-compatibility.md). This makes trying zrb cheap rather than a rewrite: keep authoring against Claude Code conventions, and both tools consume them. Pi reads `AGENTS.md`; opencode and dsh use their own formats.

### Team access through a browser

Zrb's web UI serves **both** the task runner and the chat interface, behind authentication, with SSE streaming — one server for "run the deployment task" and "chat with the repo". DeepSeek Harness is web-first but chat-shaped; opencode has a server mode focused on the editor/agent experience. If your team needs shared access to *automation* plus an assistant, that combination is zrb's default posture. See [Web UI Guide](web-ui.md).

## Choose Zrb When… / Choose Another Harness When…

**Choose zrb when:**

- The agent is a step in a workflow, not the whole workflow — pipelines, XCom hand-offs, deterministic tasks before and after.
- Runs must be scheduled or event-triggered without bolting on an orchestrator.
- You want permission policies and OS-level sandboxing configured in Python/env vars, not containers.
- You're shipping a branded CLI/product with an embedded assistant.
- Your team needs authenticated web access to both tasks and chat.
- You already maintain Claude Code skills/agents/hooks and want them reused across tools.

**Choose another harness when:**

- The job is purely interactive pair-coding and you prefer that tool's specific editing UX or model integration — all of these are mature; pick the one that feels right.
- You need deep integration with a specific vendor ecosystem (Claude Code with Anthropic tooling; dsh with DeepSeek).
- You want a minimal, self-extensible agent core to hack on (Pi), or a plugin-composition runtime to build atop (dsh).
- Your stack is JavaScript-first and Python in the loop is a dealbreaker.

And the honest answer many teams land on: **they coexist.** Keep Claude Code or opencode open for hands-on coding; let zrb own the pipelines, schedules, and product embedding — sharing skills, agents, and hooks between them.

---

- Next: [LLM Integration](llm-integration.md) — using `zrb llm chat` day-to-day
- Next: [Programming the Agent](programming-the-agent.md) — tools, hooks, dynamic prompts
- Related: [Claude Code Compatibility](claude-compatibility.md) — reusing your existing assets
- Related: [Programming the Prompt](programming-the-prompt.md) — overriding the system prompt section by section
