![Zrb Logo](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

# 🤖 Zrb: A Coding Agent With a Build System Inside

**Zrb is a terminal coding agent you can wire into a build pipeline.**

The agent part you already know: `zrb llm chat` is a full coding session in your terminal.

The other half is why Zrb exists. A skill can *tell* an agent to run the tests before deploying; a DAG makes it impossible not to. Zrb ships both — same file, same language, one `pip install`.

[Contribution Guidelines](CONTRIBUTING.md) | [Report an Issue](https://github.com/state-alchemists/zrb/issues)

---

## 📑 Table of Contents

- Getting Started
  - [1. Start where you'd start with any coding agent](#1-start-where-youd-start-with-any-coding-agent)
  - [2. Then you hit the thing prompting can't fix](#2-then-you-hit-the-thing-prompting-cant-fix)
  - [3. And sometimes you just want the one command](#3-and-sometimes-you-just-want-the-one-command)
  - [4. A fuller example: let the agent draw your codebase](#4-a-fuller-example-let-the-agent-draw-your-codebase)
- [🔥 Why Zrb?](#-why-zrb)
- [🖥️ Try the Web UI](#️-try-the-web-ui)
- [🧩 Program Your AI Agent](#-program-your-ai-agent)
- [⚙️ Installation & Configuration](#️-installation--configuration)
- [🤝 CI/CD Integration](#-cicd-integration)
- [🗺️ Documentation Directory](#️-documentation-directory)
- [🎥 Demo Video](#-demo-video)
- [💖 Support Zrb](#-support-zrb)
- [🎉 Fun Fact](#-fun-fact)

---

## 1. Start where you'd start with any coding agent

```bash
pip install zrb
export OPENAI_API_KEY="your-key-here"   # or Anthropic, Gemini, Ollama, OpenRouter, ...

zrb llm chat
```

That's a full agent session: it reads and writes files, runs commands behind a permission gate, searches the web, and remembers the conversation across restarts. If you already have `.claude/skills/` or `CLAUDE.md` in the repo, it picks them up.

![Zrb Chat](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-chat.png)

For most days, this is the whole product. Stop reading here if that's what you came for.

---

## 2. Then you hit the thing prompting can't fix

You write a skill: *"always run the tests before deploying."* It works. Usually.

Then one run the model decides the tests are unrelated to the change. Another run it runs them, misreads a green summary under a red failure, and deploys anyway. A third run it deploys to staging because the prompt didn't say which environment. Nothing crashed — the agent did what it thought you meant, and you find out on Monday.

The problem isn't prompt quality. It's that a skill is **advice**, and some steps need to be a **guarantee**. So write those as a graph instead:

```python
# zrb_init.py
from zrb import cli, CmdTask, LLMTask

write_fix = LLMTask(
    name="write-fix",
    message="Read the failing test output and fix the bug in src/.",
)
run_tests = CmdTask(name="run-tests", cmd="pytest -x")
deploy = CmdTask(name="deploy", cmd="./deploy.sh production")

cli.add_task(deploy)

write_fix >> run_tests >> deploy   # the agent proposes; the pipeline decides
```

```bash
zrb deploy
```

`run-tests` is not a suggestion the model can reason its way around. It is an edge in a graph. If `pytest` exits non-zero, `deploy` never starts, and `zrb deploy` exits with `pytest`'s own exit code — which is what your CI actually branches on.

This is the part no amount of prompt engineering reaches, and it's why the agent lives inside an automation framework instead of the other way around:

- **The agent is one node, not the administrator.** Its answer flows downstream through [XCom](docs/core-concepts/session-and-context.md) and gets checked by the next step.
- **Readiness is a loop, not a request.** `HttpCheck`/`TcpCheck` wait for a service to actually come up. "Wait until it's ready" is not a prompt-able behavior.
- **Failure is a number.** Tasks exit with the underlying command's code, so CI can tell a lint failure from a deploy failure.
- **Scheduled and triggered runs have no one to ask.** At 3am there is nobody to approve a tool call, so the boundaries have to be structural.

---

## 3. And sometimes you just want the one command

No session, no pipeline, no config:

```bash
zrb please "find every file over 100MB in this repo"
```

```
find . -type f -size +100M
📋 Copied to clipboard
```

It runs on the small model, answers in a couple of seconds, and puts the result on your clipboard instead of running it. Same install, same API key, none of the ceremony.

---

## 4. A fuller example: let the agent draw your codebase

Same shape as section 2, with a real payoff: an `LLMTask` reads your source and writes a Mermaid diagram, then a `CmdTask` renders it to PNG. The agent does the part that needs judgment; the shell does the part that needs to be exact.

### Prerequisites
-   **An LLM API Key:** Zrb needs an API key to talk to an AI model (OpenAI is default, but others are supported).
    ```bash
    export OPENAI_API_KEY="your-key-here"
    ```
-   **Mermaid CLI:** This tool converts Mermaid diagram scripts into images. Install it via npm:
    ```bash
    npm install -g @mermaid-js/mermaid-cli
    ```

### Define the pipeline
Add the following to your existing `zrb_init.py` file (or create a new one if you prefer to keep examples separate):

```python
# zrb_init.py (continued)
from zrb import cli, LLMTask, CmdTask, StrInput, Group, Tpl
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

# Create a group for Mermaid-related tasks
mermaid_group = cli.add_group(Group(
    name="mermaid",
    description="🧜 Mermaid diagram related tasks"
))

# Task 1: Generate a Mermaid script from your source code using an LLM
make_mermaid_script = mermaid_group.add_task(
    LLMTask(
        name="make-script",
        description="Create a mermaid diagram from source code in the current directory",
        input=[
            StrInput(name="dir", default="./"),
            StrInput(name="diagram", default="state-diagram"),
        ],
        message=(
            "Read all necessary files in {ctx.input.dir}, "
            "make a {ctx.input.diagram} in mermaid format. "
            "Write the script into `{ctx.input.dir}/{ctx.input.diagram}.mmd`"
        ),
        tools=[analyze_code, write_file],
    )
)

# Task 2: Convert the Mermaid script into a PNG image using CmdTask
make_mermaid_image = mermaid_group.add_task(
    CmdTask(
        name="make-image",
        description="Create a PNG from a mermaid script",
        input=[
            StrInput(name="dir", default="./"),
            StrInput(name="diagram", default="state-diagram"),
        ],
        cmd=Tpl("mmdc -i '{ctx.input.diagram}.mmd' -o '{ctx.input.diagram}.png'"),
        cwd=Tpl("{ctx.input.dir}"),
    )
)

# Set up the dependency: the image task runs after the script is created
make_mermaid_script >> make_mermaid_image
```

### Run it

Navigate to any project with source code (e.g., a Python project). For instance, if you've cloned a repository:

```bash
git clone https://github.com/someuser/my-python-project.git
cd my-python-project
```

Now, run your new task:

```bash
zrb mermaid make-image
```

Zrb will interactively ask for the directory and diagram name. Just press **Enter** to accept the defaults (`./` and `state-diagram`). The AI will analyze your code, generate the Mermaid script, and `mmdc` will convert it to a PNG. In moments, you'll have a beautiful diagram of your code!

![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)

## 🔥 Why Zrb?

- 🤖 **A coding agent you program in Python.** Tools, hooks, prompts, permission policies and history processors are plain Python in your `zrb_init.py` — not a config format, not a separate SDK.
- 🔒 **Determinism where it matters.** Put the model between deterministic steps and keep approvals, sandboxing and ordering under your control instead of the model's judgment.
- 🐍 **Pure Python, no DSL.** Tasks are objects; `>>` is the dependency operator.
- 💻 **Terminal, web UI, or CI.** The same task definition runs in all three.
- 🧩 **Bring your Claude Code assets.** Skills, hooks and MCP servers work as-is.
- 🌍 **Open source, and white-labelable** into your own branded CLI.

---

## 🖥️ Try the Web UI

Prefer a graphical interface? Zrb has you covered. Explore the full details in the [Web UI Guide](docs/advanced-topics/web-ui.md).

```bash
zrb server start
```

By default, the server binds to `127.0.0.1`, so the UI is reachable only from the local machine. Then open your browser to `http://localhost:21213` to see your tasks in a clean, user-friendly interface.

> **Safety boundary:** Zrb's web UI can start and control automation tasks, so it is not intended to be exposed publicly without deliberate hardening. If you set `ZRB_WEB_HTTP_HOST` to a non-loopback address, enable authentication and replace the documented default admin password and secret key with unique values. Startup warnings call out unsafe network-exposed configurations; see the [Web UI Guide](docs/advanced-topics/web-ui.md) before using a shared or public bind.

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

---

## 🧩 Program Your AI Agent

`zrb llm chat` works out of the box — but the moment you need it to do something specific, you don't reach for a config file or a separate SDK. You write Python, in the same file where you define the rest of your automation.

Every part of the agent is a value you can supply or a callable you can register:

| You want to… | You write a… |
|---|---|
| Give the agent abilities | **custom tool** — a plain Python function it can call in-process |
| React to what it does | **lifecycle hook** — fires on tool calls, prompts, session start/end |
| Gate dangerous actions | **permission policy** / async **approval channel** |
| Inject live context into the prompt | **dynamic prompt section** — a `lambda ctx: ...` evaluated per request |
| Keep long conversations affordable | **history processor** — prune, redact, or summarize the message history |
| Route by cost or task | a **model callable** — pick the model per request |

### Example: a custom tool the agent calls in-process

```python
from zrb import cli, LLMChatTask

# A normal Python function becomes a tool — typed args + docstring are the spec.
async def get_open_incidents(team: str) -> str:
    """Return the current open incidents for a given team."""
    return my_oncall_db.query(team)  # your code, running in-process

chat = LLMChatTask(name="ops-chat", tools=[get_open_incidents])
cli.add_task(chat)
```

### The part nothing else does: the agent *is* a pipeline node

Because an `LLMTask` is just a Zrb task, you can wire it between deterministic steps. Its answer flows downstream through [XCom](docs/core-concepts/session-and-context.md), and your tools can call straight into your codebase:

```python
fetch_ticket >> triage_with_llm >> route_to_team
```

👉 Full walkthrough and every hook in one place: **[Programming the Agent](docs/llm/programming-the-agent.md)**. Runnable example: **[`examples/agent-in-pipeline`](examples/agent-in-pipeline)**.

---

## ⚙️ Installation & Configuration

Ready to dive deeper into getting Zrb set up and customized? Our comprehensive guides cover everything you need:

-   **[Installation Guide](docs/installation/installation.md)**: Details on `pip` install, the automated `install.sh` script, Docker images, and even running Zrb on Android (Termux/Proot).
-   **[Environment Variables & Overrides](docs/configuration/env-vars.md)**: An exhaustive list of all general environment variables to customize Zrb's behavior.
-   **[LLM & Rate Limiter Configuration](docs/configuration/llm-config.md)**: Everything you need to configure your LLM provider, manage token budgets, and fine-tune AI behavior.

---

## 🤝 CI/CD Integration

Integrate Zrb into your Continuous Integration/Continuous Deployment pipelines for robust, automated workflows. See the [CI/CD Integration Guide](docs/advanced-topics/ci-cd.md) for examples with GitHub Actions, GitLab CI, and Bitbucket Pipelines.

---

## 🗺️ Documentation Directory

Zrb scales from a one-line `zrb please` to a hundred-node pipeline with an agent in the middle.

> **Here for the agent?** [Programming the Agent](docs/llm/programming-the-agent.md) → [Extending the LLM](docs/llm/extending-the-llm.md) → [Permission Policy](docs/llm/permission-policy.md).
>
> **Here to write pipelines?** [Tasks & Execution Lifecycle](docs/core-concepts/tasks-and-lifecycle.md) → [CLI and Groups](docs/core-concepts/cli-and-groups.md) → [Inputs](docs/core-concepts/inputs.md).
>
> Prefer copy-pasting a working example? See [`examples/`](examples/README.md).
>
> `docs/adr/` and `docs/technical-specs/` are maintainer-facing design history, not part of the reading path below.

### I. The Agent
Shaping `zrb llm chat` and the LLM task types.
- [Choosing Between Agent Harnesses](docs/llm/harness-comparison.md) — zrb `llm chat` vs Claude Code, opencode, DeepSeek Harness, and Pi: when each is the right tool
- [Programming the Agent](docs/llm/programming-the-agent.md) — the overview: every way to shape agent behavior in Python (tools, hooks, dynamic prompts, history processors, agent-as-pipeline-node)
- [Programming the Prompt](docs/llm/programming-the-prompt.md) — the ladder from a plain-string `message` up to a composed `PromptManager`; feeding a `CmdTask`'s output into `LLMTask`/`LLMChatTask`
- [LLM Assistant & AI Tasks](docs/llm/llm-integration.md) — interactive chat, `LLMTask`/`LLMChatTask` usage, troubleshooting
- [Extending the LLM](docs/llm/extending-the-llm.md) — built-in tools, custom tools, sub-agents, model capabilities, context management
- [Custom UI](docs/llm/llm-custom-ui.md) — build a TUI, web/SSE, or chat-bot front end for `LLMChatTask`
- [Permission Policy System](docs/llm/permission-policy.md) — fine-grained tool control & security gates
- [Sandbox](docs/llm/sandbox.md) — filesystem containment for LLM tool calls
- [Plan Mode](docs/llm/plan-mode.md) — read-only discovery & strategy phase
- [LLMChatTask API Reference](docs/task-types/llmchat-task.md) — builder API, TUI configuration
- [LLM Chat Request Lifecycle](docs/llm/llm-chat-lifecycle.md) — end-to-end tour: CLI → agent run → UI → history persistence
- [Hook System (Claude Code Compatible)](docs/llm/hooks.md)
- [MCP Support (Model Context Protocol)](docs/llm/mcp-support.md)
- [LSP Support (Language Server Protocol)](docs/llm/lsp-support.md)
- [Technical Spec: LLM Journal System](docs/technical-specs/llm-context.md)
- [Claude Code Compatibility](docs/llm/claude-compatibility.md)

### II. Core Concepts
The foundational pillars of the framework.
- [Tasks & Execution Lifecycle](docs/core-concepts/tasks-and-lifecycle.md)
- [CLI and Groups](docs/core-concepts/cli-and-groups.md)
- [Inputs](docs/core-concepts/inputs.md)
- [Environments (Envs)](docs/core-concepts/environments.md)
- [Session, Context & XCom](docs/core-concepts/session-and-context.md)
- [The `@make_task` Decorator](docs/core-concepts/make-task.md) — (advanced) full parameter reference
- [XCom Deep Dive](docs/core-concepts/xcom-deep-dive.md) — (advanced) patterns & pitfalls

### III. Task Types
All task types available in Zrb, from basic to advanced.
- [Task & CmdTask](docs/task-types/basic-tasks.md) — Python actions and shell commands
- [Custom Tasks](docs/task-types/custom-tasks.md) — subclassing `BaseTask` with async patterns
- [Readiness: HttpCheck & TcpCheck](docs/task-types/readiness-checks.md)
- [Automation: Triggers & Schedulers](docs/task-types/triggers-and-schedulers.md)
- [File Ops: Scaffolder & RsyncTask](docs/task-types/file-ops.md)
- [Built-in Helper Tasks](docs/task-types/builtin-helpers.md) (Git, Base64, UUID, HTTP, etc.)

### IV. Advanced Topics
- [Web UI Guide](docs/advanced-topics/web-ui.md)
- [White-labeling: Create a Custom CLI](docs/advanced-topics/white-labeling.md)
- [CI/CD Integration](docs/advanced-topics/ci-cd.md)
- [Logging](docs/advanced-topics/logging.md) — Python logging vs. task-level context logging
- [Testing Zrb Tasks](docs/advanced-topics/testing-tasks.md) — mocking context, testing pipelines
- [Upgrading Guide](docs/advanced-topics/upgrading-guide.md)

### V. Contributing
- [Which pattern do I reach for?](docs/contributing/which-pattern.md) — lookup table for the pattern zrb expects when adding new code
- [Architecture & Conventions](docs/contributing/architecture.md) — for maintainers and contributors
- [Framework Conventions](docs/contributing/framework-conventions.md) — the enforced R1–R12 rules
- [Maintainer Guide](docs/contributing/maintainer-guide.md) — start here to contribute code

### VI. Configuration
- [Environment Variables & Overrides](docs/configuration/env-vars.md)
- [LLM & Rate Limiter Configuration](docs/configuration/llm-config.md)
- [LLM Component Collections](docs/configuration/llm-collections.md) — registries, managers, and the three configuration channels for skills, agents, hooks, prompts, and tools

### VII. Examples
- [`examples/`](examples/README.md) — runnable `zrb_init.py` for every topic above, grouped by category

### VIII. Changelog
- [Changelog](docs/changelog/README.md) — full release history

---

## 🎥 Demo Video

Watch a video demonstration of Zrb in action:

[![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)

---

## 💖 Support Zrb

If you find Zrb valuable, please consider showing your support:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com)

---

## 🎉 Fun Fact

**Did you know?** Zrb is named after `Zaruba`, a powerful, sentient Madou Ring that acts as a guide and support tool in the *Garo* universe.

> *Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor.* [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
