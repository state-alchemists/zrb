![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse

Zrb simplifies the creation and execution of automation tasks. It allows you to define tasks using Python classes or functions, organize them into groups, and run them via a command-line interface or a web UI. Zrb handles task dependencies, inputs, environment variables, and inter-task communication, allowing you to focus on the logic of your automation.

## 🚀 Why Zrb?

Zrb stands out by offering:
* **Python-Native Automation:** Write tasks in a familiar and powerful language.
* **LLM Integration:** Easily incorporate AI capabilities into your workflows.
* **Structured Workflows:** Define dependencies and organize tasks logically.
* **Flexible Execution:** Run tasks from the CLI or a web browser.
* **Extensibility:** Customize and build upon the Zrb framework.

## 🔥 Key Features

- **LLM Integration:** Leverage state-of-the-art language models to generate code, diagrams, and documentation.
- **Task Chaining:** Easily define dependencies between tasks to create complex workflows.
- **CLI & Server Mode:** Run tasks directly from the command line or through a user-friendly web UI.
- **Flexible Input Handling:** Defaults, prompts, and command-line parameters to suit any workflow.
* **Environment Variables:** Manage configuration using environment variables, loaded from the system, `.env` files, or task definitions.
* **Cross-Communication (XCom):** Safely exchange small amounts of data between tasks.
- **Extensible & Open Source:** Contribute, customize, or extend Zrb to fit your unique needs.


# 🛠️ Installation

The easiest way to install Zrb is using pip:

```bash
pip install zrb
# pip install --pre zrb
```

Alternatively, you can use Zrb installation script which handles prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

For more installation option like running Zrb on your **Android Device 📱** or **as a Container 🐋**, you can check the [installation and configuration guide](https://github.com/state-alchemists/zrb/blob/main/docs/installation-and-configuration/README.md).

# 🍲 Quick Start: Build Your First Automation Workflow

This guide shows you how to define two simple tasks:

- One to generate a Mermaid Diagram Script from your source code.
- And another one to convert that script into a PNG image.

> **Note:** This assume you have an `OPENAI_API_KEY` and a Mermaid CLI installed (i.e., `npm install -g @mermaid-js/mermaid-cli`)

## 1. Create Your Task Definition File

Place a file named `zrb_init.py` in a directory that's accessible from your projects.

Zrb will automatically search for this file by starting in your current directory and then moving upward (i.e., checking parent directories) until it finds one.

This means if you place your `zrb_init.py` in your home directory (e.g., `/home/<your-user-name>/zrb_init.py`), the tasks defined there will be available for any project inside your home directory.

Add the following content to your zrb_init.py:

```python
from zrb import cli, LLMTask, CmdTask, StrInput, Group
from zrb.builtin.llm.tool.code import analyze_repo
from zrb.builtin.llm.tool.file import write_to_file


# Create a group for Mermaid-related tasks
mermaid_group = cli.add_group(Group(name="mermaid", description="🧜 Mermaid diagram related tasks"))

# Task 1: Generate a Mermaid script from your source code
make_mermaid_script = mermaid_group.add_task(
    LLMTask(
        name="make-script",
        description="Creating mermaid diagram based on source code in current directory",
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
        description="Creating png based on source code in current directory",
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

**What This Does**

- **Task 1 – make-script**:

    Uses an LLM to read all files in your current directory and generate a [Mermaid Diagram Script](https://mermaid.js.org/) (e.g., `state diagram.mmd`).

- **Task 2 – make-image**:

    Executes a command that converts the Mermaid Diagram Script into a PNG image (e.g., `state diagram.png`). This task will run only after the script has been generated.


## 2. Run Your Tasks

After setting up your tasks, you can execute them from any project. For example:

- Clone/Create a Project:

    ```bash
    git clone git@github.com:jjinux/gotetris.git
    cd gotetris
    ```

- Create a state diagram:

    ```bash
    zrb mermaid make-image --diagram "state diagram" --dir ./
    ```

- Or use the interactive mode:

    ```bash
    zrb mermaid make-image
    ```

    Zrb will prompt:

    ```
    dir [./]:
    diagram [state diagram]:
    ```

    Press **Enter** to use the default value

- And you have your State Diagram ready :)

    ![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)


## 3. Try Out the Web UI

You can also serve your tasks through a user-friendly web interface:

```bash
zrb server start
```

Then open your browser and visit `http://localhost:21213`

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

# 🎥 Demo & Documentation

- **Go Further By Visiting Our Documentation:** [Zrb Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)
- **Video Demo:**

    [![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)


# 🤝 Join the Community

- **Bug Reports & Feature Requests:** Create an [issue](https://github.com/state-alchemists/zrb/issues) on Zrb's GitHub Repositories and include:
    - Your Zrb version (i.e., `zrb version`).
    - Steps you’ve taken and what you expected versus what happened
- **Contributions:** We welcome pull requests! Check out our [contribution guidelines](https://github.com/state-alchemists/zrb/pulls).


# ☕ Support The Project

If you find Zrb valuable, please consider donating:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com)

# 🎉 Fun Fact

Did you know?

Zrb is named after `Zaruba`, a powerful support tool from the Garo universe!

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
