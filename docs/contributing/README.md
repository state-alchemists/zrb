🔖 [Documentation Home](../README.md) > Contributing

# Contributing to Zrb

Where to look, in the order you will need it. This page is the task index: start from the job you have, not the file. The rules themselves live in [Coding Conventions](coding-conventions.md) and [Framework Conventions](framework-conventions.md); the code's location is in the [Code Map](code-map.md); a symptom-to-file lookup is the [Change Map](../architecture/change-map.md).

| I want to… | Read |
| --- | --- |
| Set up a dev environment, run the tests, and understand why a gate failed | [Maintainer Guide → Getting Started](maintainer-guide.md#getting-started) |
| Know which pattern zrb expects for the code I am adding | [Which pattern do I reach for?](which-pattern.md) |
| Know which rules a test will hold me to | [Framework Conventions (R1–R13)](framework-conventions.md) |
| Read the coding conventions in one place (style, naming, imports, tests, docs) | [Coding Conventions](coding-conventions.md) |
| Find the module that owns a behavior | [Code Map](code-map.md) |
| Hitting an unfamiliar term | [Glossary](glossary.md) |
| Branch, open a PR, get the review and the checks green | [Agent Workflow](agent-workflow.md) |
| Write a changelog entry, compact a version line, or publish a release | [Releasing](releasing.md) |
| Measure imports or profile a command | [Performance](performance.md) |
| Judge the agent's results, or run a one-on-one session | [Evaluating the Agent](evaluating-the-agent.md) |
| Understand the philosophy behind the codebase | [Architecture, Philosophy, & Conventions](architecture.md) |
| Understand how a subsystem is designed, part by part | [Architecture: The Design of Zrb](../architecture/README.md) |
| Find out why something was decided, or record a new decision | [Architecture Decision Records](../adr/README.md) |
| Go deep on context propagation, memory or history sanitization | [Context Propagation](../technical-specs/context-propagation.md), [LLM Memory](../technical-specs/llm-memory.md), [LLM History Sanitization](../technical-specs/llm-history-sanitization.md) |

Before you open a PR: activate `.venv`, run `./zrb-test.sh`, update the docs and examples the change affects, add a changelog entry, and write or rewrite an ADR if you made a design decision. See [Maintainer Guide → Submitting a Change](maintainer-guide.md#submitting-a-change) and [Agent Workflow](agent-workflow.md).

---

🔖 [Documentation Home](../README.md) > Contributing
