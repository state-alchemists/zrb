🔖 [Documentation Home](../README.md) > Contributing

# Contributing to Zrb

Where to look, in the order you will need it.

| I want to… | Read |
| --- | --- |
| Set up a dev environment, run the tests, and understand why a gate failed | [Maintainer Guide → Getting Started](maintainer-guide.md#getting-started) |
| Know which pattern zrb expects for the code I am adding | [Which pattern do I reach for?](which-pattern.md) |
| Know which rules a test will hold me to | [Framework Conventions (R1–R12)](framework-conventions.md) |
| Read the coding conventions in one place (naming, imports, tests, config knobs) | [`AGENTS.md`](../../AGENTS.md) — written for AI agents, binding for humans too |
| Understand the philosophy behind the codebase | [Architecture, Philosophy, & Conventions](architecture.md) |
| Understand how a subsystem is designed, part by part | [Architecture: The Design of Zrb](../architecture/README.md) |
| Find out why something was decided, or record a new decision | [Architecture Decision Records](../adr/README.md) |
| Go deep on context propagation or history sanitization | [Context Propagation](../technical-specs/context-propagation.md), [LLM Context](../technical-specs/llm-context.md), [LLM History Sanitization](../technical-specs/llm-history-sanitization.md) |
| Write a changelog entry, or publish a release | [Maintainer Guide → Changelog](maintainer-guide.md#changelog), [Publishing Zrb](maintainer-guide.md#publishing-zrb) |

Before you open a PR: run `./zrb-test.sh`, add a changelog entry, and write or rewrite an ADR if you made a design decision. See [Maintainer Guide → Submitting a Change](maintainer-guide.md#submitting-a-change).

---

🔖 [Documentation Home](../README.md) > Contributing
