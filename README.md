![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

# 🤖 Zrb: Your Automation Powerhouse

**Zrb (Zaruba) is a Python-based tool that makes it easy to create, organize, and run automation tasks.** Think of it as a command-line sidekick, ready to handle everything from simple scripts to complex, AI-powered workflows.

Whether you're running tasks from the terminal or a sleek web UI, Zrb streamlines your process with task dependencies, environment management, and even inter-task communication.

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md) | [Contribution Guidelines](https://github.com/state-alchemists/zrb/pulls) | [Report an Issue](https://github.com/state-alchemists/zrb/issues)

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

## 🚀 Quick Start: Your First AI-Powered Workflow in 5 Minutes

Let's create a two-step workflow that uses an LLM to analyze your code and generate a Mermaid diagram, then converts that diagram into a PNG image.

### 1. Prerequisites: Get Your Tools Ready

Before you start, make sure you have the following:

-   **An LLM API Key:** Zrb needs an API key to talk to an AI model.
    ```bash
    export OPENAI_API_KEY="your-key-here"
    ```
    > Zrb defaults to OpenAI, but you can easily configure it for other providers like **Deepseek, Ollama, etc.** See the [LLM Integration Guide](https://github.com/state-alchemists/zrb/blob/main/docs/installation-and-configuration/configuration/llm-integration.md) for details.

-   **Mermaid CLI:** This tool converts Mermaid diagram scripts into images.
    ```bash
    npm install -g @mermaid-js/mermaid-cli
    ```

### 2. Install Zrb

The easiest way to get Zrb is with `pip`.

```bash
pip install zrb
# Or for the latest pre-release version:
# pip install --pre zrb
```

Alternatively, you can use an installation script that handles all prerequisites:
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

> For other installation methods, including **Docker 🐋** and **Android 📱**, check out the full [Installation Guide](https://github.com/state-alchemists/zrb/blob/main/docs/installation-and-configuration/README.md).

### 3. Define Your Tasks

Create a file named `zrb_init.py` in your project directory. Zrb automatically discovers this file.

> **💡 Pro Tip:** You can place `zrb_init.py` in your home directory (`~/zrb_init.py`), and the tasks you define will be available globally across all your projects!

Add the following Python code to your `zrb_init.py`:

```python
from zrb import cli, LLMTask, CmdTask, StrInput, Group
from zrb.builtin.llm.tool.code import analyze_repo
from zrb.builtin.llm.tool.file import write_to_file


# Create a group for Mermaid-related tasks
mermaid_group = cli.add_group(Group(
    name="mermaid",
    description="🧜 Mermaid diagram related tasks"
))

# Task 1: Generate a Mermaid script from your source code
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
        tools=[
            analyze_repo, write_to_file
        ],
    )
)

# Task 2: Convert the Mermaid script into a PNG image
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

### 4. Run Your Workflow!

Now, navigate to any project with source code. For example:

```bash
git clone git@github.com:jjinux/gotetris.git
cd gotetris
```

Run your new task to generate the diagram:

```bash
zrb mermaid make-image --diagram "state-diagram" --dir ./
```

You can also run it interactively and let Zrb prompt you for inputs:
```bash
zrb mermaid make-image
```
Zrb will ask for the directory and diagram name—just press **Enter** to accept the defaults.

In moments, you'll have a beautiful state diagram of your code!

![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)

---

## 🖥️ Try the Web UI

Prefer a graphical interface? Zrb has you covered. Start the web server:

```bash
zrb server start
```

Then open your browser to `http://localhost:21213` to see your tasks in a clean, user-friendly interface.

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

---

## 💬 Interact with an LLM Directly

Zrb brings AI capabilities right to your command line.

### Interactive Chat

Start a chat session with an LLM to ask questions, brainstorm ideas, or get coding help.

```bash
zrb llm chat
```

### Quick Questions

For a single question, use the `ask` command for a fast response.

```bash
zrb llm ask "What is the capital of Indonesia?"
```

---

## 🎥 Demo & Documentation

-   **Dive Deeper:** [**Explore the Full Zrb Documentation**](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)
-   **Watch the Video Demo:**

    [![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)

---

## 🤝 Join the Community & Support the Project

-   **Bugs & Feature Requests:** Found a bug or have a great idea? [Open an issue](https://github.com/state-alchemists/zrb/issues). Please include your Zrb version (`zrb version`) and steps to reproduce the issue.
-   **Contributions:** We love pull requests! See our [contribution guidelines](https://github.com/state-alchemists/zrb/pulls) to get started.
-   **Support Zrb:** If you find Zrb valuable, please consider showing your support.

    [![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com)

---

## 🎉 Fun Fact

**Did you know?** Zrb is named after `Zaruba`, a powerful, sentient Madou Ring that acts as a guide and support tool in the *Garo* universe.

> *Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor.* [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)