![Zrb Logo](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

# 🤖 Zrb: Your Automation Powerhouse

**Zrb (Zaruba) is a Python-based tool that makes it easy to create, organize, and run automation tasks.** Think of it as a command-line sidekick, ready to handle everything from simple scripts to complex, AI-powered workflows.

Whether you're running tasks from the terminal or a sleek web UI, Zrb streamlines your process with task dependencies, environment management, and even inter-task communication.

[Contribution Guidelines](https://github.com/state-alchemists/zrb/pulls) | [Report an Issue](https://github.com/state-alchemists/zrb/issues)

---

## 📑 Table of Contents

- [🔥 Why Choose Zrb?](#-why-choose-zrb)
- [🚀 Quickstart Part 1: Your First Basic Pipeline](#-quickstart-part-1-your-first-basic-pipeline-in--2-minutes)
- [🚀 Quickstart Part 2: AI-Powered Workflow](#-quickstart-part-2-your-first-ai-powered-workflow-in--5-minutes)
- [🖥️ Try the Web UI](#️-try-the-web-ui)
- [💬 Interact with an LLM Directly](#-interact-with-an-llm-directly)
- [⚙️ Installation & Configuration](#️-installation--configuration)
- [🤝 CI/CD Integration](#-cicd-integration)
- [🗺️ Documentation Directory](#️-documentation-directory)
- [🎥 Demo Video](#-demo-video)
- [💖 Support Zrb](#-support-zrb)
- [🎉 Fun Fact](#-fun-fact)

---

## 🔥 Why Choose Zrb?

Zrb is designed to be powerful yet intuitive, offering a unique blend of features:

-   🤖 **Built-in LLM Integration:** Go beyond simple automation. Leverage Large Language Models to generate code, create diagrams, produce documentation, and more.
-   🐍 **Pure Python:** Write your tasks in Python. No complex DSLs or YAML configurations to learn.
-   🔗 **Smart Task Chaining:** Define dependencies between tasks to build sophisticated, ordered workflows.
-   💻 **Dual-Mode Execution:** Run tasks from the command line for speed or use the built-in web UI for a more visual experience.
-   ⚙️ **Flexible Configuration:** Manage inputs with defaults, prompts, or command-line arguments. Handle secrets and settings with environment variables from the system or `.env` files.
-   🗣️ **Cross-Communication (XCom):** Allow tasks to safely exchange small pieces of data.
-   🌍 **Open & Extensible:** Zrb is open-source. Feel free to contribute, customize, or extend it to meet your needs.

---

## 🚀 Quickstart Part 1: Your First Basic Pipeline in < 2 Minutes

Let's start with the absolute basics: defining simple units of work and chaining them together. You only need Python installed.

### 1. Define Your Tasks
Create a file named `zrb_init.py` in your project directory (or your home directory for global access!).

```python
# zrb_init.py
from zrb import cli, CmdTask, Task

# 1. Define tasks.
# CmdTask is perfect for running shell commands.
prepare_env = CmdTask(
    name="prepare-env", 
    cmd="echo 'Environment prepared!'"
)

# Task is for pure Python logic.
build_app = Task(
    name="build-app",
    action=lambda ctx: ctx.print("Building application in pure Python...")
)

deploy_app = CmdTask(
    name="deploy-app", 
    cmd="echo 'Deploying app to the cloud ☁️'"
)

# 2. Register tasks to the main 'cli' object so Zrb knows about them
cli.add_task(prepare_env, build_app, deploy_app)

# 3. Define the execution order (The Directed Acyclic Graph - DAG)
# prepare-env runs first, then build-app, then deploy-app
prepare_env >> build_app >> deploy_app
```

### 2. Run Your First Pipeline!

Now, open your terminal and run:

```bash
zrb deploy-app
```

Zrb will see that `deploy-app` depends on `build-app`, which depends on `prepare-env`. It will automatically run them in the correct sequential order:

```
[prepare-env] Environment prepared!
[build-app] Building application in pure Python...
[build-app] Build complete.
[deploy-app] Deploying app to the cloud ☁️
```

Congratulations! You've just built and run your first Zrb automation pipeline.

---

## 🚀 Quickstart Part 2: Your First AI-Powered Workflow in < 5 Minutes

Now that you understand the basics, let's unleash Zrb's full power. This example uses an LLM to analyze your code and generate a Mermaid diagram, then converts that diagram into a PNG image.

### 1. Prerequisites
-   **An LLM API Key:** Zrb needs an API key to talk to an AI model (OpenAI is default, but others are supported).
    ```bash
    export OPENAI_API_KEY="your-key-here"
    ```
-   **Mermaid CLI:** This tool converts Mermaid diagram scripts into images. Install it via npm:
    ```bash
    npm install -g @mermaid-js/mermaid-cli
    ```

### 2. Update Your `zrb_init.py`
Add the following to your existing `zrb_init.py` file (or create a new one if you prefer to keep examples separate):

```python
# zrb_init.py (continued)
from zrb import cli, LLMTask, CmdTask, StrInput, Group
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
        cmd="mmdc -i '{ctx.input.diagram}.mmd' -o '{ctx.input.diagram}.png'",
        cwd="{ctx.input.dir}",
    )
)

# Set up the dependency: the image task runs after the script is created
make_mermaid_script >> make_mermaid_image
```

### 3. Run Your AI-Powered Workflow!

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

---

## 🖥️ Try the Web UI

Prefer a graphical interface? Zrb has you covered. Explore the full details in the [Web UI Guide](docs/advanced-topics/web-ui.md).

```bash
zrb server start
```

Then open your browser to `http://localhost:21213` to see your tasks in a clean, user-friendly interface.

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

---

## 💬 Interact with an LLM Directly

Zrb brings AI capabilities right to your command line. For full details on configuring and using the AI assistant, see the [LLM Integration Guide](docs/advanced-topics/llm-integration.md).

### Interactive Chat

Start a chat session with an LLM to ask questions, brainstorm ideas, or get coding help.

```bash
zrb llm chat
```

---

## ⚙️ Installation & Configuration

Ready to dive deeper into getting Zrb set up and customized? Our comprehensive guides cover everything you need:

-   **[Installation Guide](docs/installation/installation.md)**: Details on `pip` install, the automated `install.sh` script, Docker images, and even running Zrb on Android (Termux/Proot).
-   **[Environment Variables & Overrides](docs/configuration/env-vars.md)**: An exhaustive list of all general environment variables to customize Zrb's behavior.
-   **[LLM & Rate Limiter Configuration](docs/configuration/llm-config.md)**: Everything you need to configure your LLM provider, manage token budgets, and fine-tune AI behavior.

---

## 🤝 CI/CD Integration

Integrate Zrb into your Continuous Integration/Continuous Deployment pipelines for robust, automated workflows. See the [CI/CD Integration Guide](./advanced-topics/ci-cd.md) for examples with GitHub Actions, GitLab CI, and Bitbucket Pipelines.

---

## 🗺️ Documentation Directory

Zrb scales from simple scripts to massive automation ecosystems. Explore the documentation to unlock its full potential:

### I. Core Concepts
The foundational pillars of the framework.
- [Tasks & Execution Lifecycle](docs/core-concepts/tasks-and-lifecycle.md)
- [CLI and Groups](docs/core-concepts/cli-and-groups.md)
- [Inputs](docs/core-concepts/inputs.md)
- [Environments (Envs)](docs/core-concepts/environments.md)
- [Session, Context & XCom](docs/core-concepts/session-and-context.md)
- [The `@make_task` Decorator](docs/core-concepts/make-task.md) — full parameter reference
- [XCom Deep Dive](docs/core-concepts/xcom-deep-dive.md) — advanced patterns & pitfalls

### II. Task Types
All task types available in Zrb, from basic to advanced.
- [Task & CmdTask](docs/task-types/basic-tasks.md) — Python actions and shell commands
- [Custom Tasks](docs/task-types/custom-tasks.md) — subclassing `BaseTask` with async patterns
- [Readiness: HttpCheck & TcpCheck](docs/task-types/readiness-checks.md)
- [Automation: Triggers & Schedulers](docs/task-types/triggers-and-schedulers.md)
- [File Ops: Scaffolder & RsyncTask](docs/task-types/file-ops.md)
- [Built-in Helper Tasks](docs/task-types/builtin-helpers.md) (Git, Base64, UUID, HTTP, etc.)

### III. LLM & AI Integration
- [LLM Assistant & AI Tasks](docs/advanced-topics/llm-integration.md) — `LLMTask`, tools, sub-agents, context management
- [Permission Policy System](docs/advanced-topics/permission-policy.md) — fine-grained tool control & security gates
- [Plan Mode](docs/advanced-topics/plan-mode.md) — read-only discovery & strategy phase
- [LLMChatTask API Reference](docs/task-types/llmchat-task.md) — builder API, TUI configuration
- [LLM Chat Request Lifecycle](docs/advanced-topics/llm-chat-lifecycle.md) — end-to-end tour: CLI → agent run → UI → history persistence
- [Hook System (Claude Code Compatible)](docs/advanced-topics/hooks.md)
- [MCP Support (Model Context Protocol)](docs/advanced-topics/mcp-support.md)
- [LSP Support (Language Server Protocol)](docs/advanced-topics/lsp-support.md)
- [Technical Spec: LLM Journal System](docs/technical-specs/llm-context.md)
- [Claude Code Compatibility](docs/advanced-topics/claude-compatibility.md)

### IV. Advanced Topics
- [Architecture & Conventions](docs/advanced-topics/architecture.md) — for maintainers and contributors
- [Web UI Guide](docs/advanced-topics/web-ui.md)
- [White-labeling: Create a Custom CLI](docs/advanced-topics/white-labeling.md)
- [CI/CD Integration](docs/advanced-topics/ci-cd.md)
- [Testing Zrb Tasks](docs/advanced-topics/testing-tasks.md) — mocking context, testing pipelines
- [Upgrading Guide](docs/advanced-topics/upgrading-guide.md)
- [Maintainer Guide](docs/advanced-topics/maintainer-guide.md)

### V. Configuration
- [Environment Variables & Overrides](docs/configuration/env-vars.md)
- [LLM & Rate Limiter Configuration](docs/configuration/llm-config.md)

### VI. Changelog
- [Changelog](docs/changelog.md) — full release history

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
