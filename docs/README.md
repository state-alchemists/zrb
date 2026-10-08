🔖 [Zrb README](../README.md) > Documentation Home

# Zrb Documentation

Zrb scales from a one-line `zrb please` to a hundred-node pipeline with an agent in the middle. Pick the path that matches what you came for.

## Start here

| You are… | Read, in order |
|---|---|
| **New to zrb** | [Installation](installation/installation.md) → [Verify: your first task](installation/installation.md#3-verify-installation) → [First LLM chat](installation/installation.md#first-llm-chat) |
| **Here for the agent** | [LLM docs index](llm/README.md) → [LLM Integration](llm/llm-integration.md) → [Programming the Agent](llm/programming-the-agent.md) → [Permission Policy](llm/permission-policy.md) |
| **Writing pipelines** | [Tasks & Execution Lifecycle](core-concepts/tasks-and-lifecycle.md) → [CLI and Groups](core-concepts/cli-and-groups.md) → [Inputs](core-concepts/inputs.md) → [Task Types](#iii-task-types) |
| **Running zrb for a team** (config, web UI, CI) | [Environment Variables](configuration/env-vars.md) → [Web UI Guide](advanced-topics/web-ui.md) → [CI/CD Integration](advanced-topics/ci-cd.md) |
| **Contributing to zrb** | [Contributing](contributing/README.md) → [Architecture](architecture/README.md) → [ADRs](adr/README.md) |

Prefer copy-pasting a working example? See [`examples/`](../examples/README.md).

---

## I. The Agent

See the [LLM docs index](llm/README.md) for every page about `zrb llm chat`, `LLMTask` and `LLMChatTask`, grouped into using, configuring, and programming the agent.

## II. Core Concepts

- [Tasks & Execution Lifecycle](core-concepts/tasks-and-lifecycle.md) — `zrb_init.py`, the three ways to define a task, dependencies, and flow control
- [CLI and Groups](core-concepts/cli-and-groups.md)
- [Inputs](core-concepts/inputs.md)
- [Environments (Envs)](core-concepts/environments.md)
- [Session, Context & XCom](core-concepts/session-and-context.md)
- [The `@make_task` Decorator](core-concepts/make-task.md) — full parameter reference
- [XCom Deep Dive](core-concepts/xcom-deep-dive.md) — queue methods, patterns and pitfalls

## III. Task Types

- [Task & CmdTask](task-types/basic-tasks.md) — Python actions and shell commands
- [Custom Tasks](task-types/custom-tasks.md) — subclassing `BaseTask`
- [Readiness: HttpCheck & TcpCheck](task-types/readiness-checks.md)
- [Automation: Triggers & Schedulers](task-types/triggers-and-schedulers.md)
- [File Ops: Scaffolder & RsyncTask](task-types/file-ops.md)
- [LLMChatTask API Reference](task-types/llmchat-task.md)
- [Built-in Helper Tasks](task-types/builtin-helpers.md) — Git, Base64, UUID, HTTP, and more

## IV. Configuration

- [Environment Variables](configuration/env-vars.md) — general, task-runtime, CLI colour, and web UI settings
- [LLM & Rate Limiter Configuration](configuration/llm-config.md) — providers, budgets, prompts, journal, rewind, chat TUI, voice
- [LLM Component Collections](configuration/llm-collections.md) — registries for skills, agents, hooks, prompts and tools

## V. Advanced Topics

- [Web UI Guide](advanced-topics/web-ui.md)
- [White-labeling: Create a Custom CLI](advanced-topics/white-labeling.md)
- [CI/CD Integration](advanced-topics/ci-cd.md)
- [Logging](advanced-topics/logging.md)
- [Testing Zrb Tasks](advanced-topics/testing-tasks.md)
- [Upgrading Guide](advanced-topics/upgrading-guide.md)

## VI. For Contributors

- [Contributing](contributing/README.md) — where to start, in the order you will need it
- [Architecture: The Design of Zrb](architecture/README.md) — each part's problem, principles and invariants
- [Architecture Decision Records](adr/README.md) — why things are the way they are
- [LLM Chat Request Lifecycle](llm/llm-chat-lifecycle.md) — one request traced through the source
- Technical specs: [Context Propagation](technical-specs/context-propagation.md), [LLM Journal System](technical-specs/llm-context.md), [LLM History Sanitization](technical-specs/llm-history-sanitization.md)

## VII. Changelog

- [Changelog](changelog/README.md) — full release history

---

🔖 [Documentation Home](../README.md) > Docs Index
