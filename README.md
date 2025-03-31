![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse


**Unlock the full potential of automation in your projects!**

Zrb streamlines repetitive tasks, integrates with powerful LLMs, and lets you create custom automation workflows effortlessly. Whether you’re building CI/CD pipelines, code generators, or unique automation scripts, Zrb is designed to simplify and supercharge your workflow.


## 🚀 Why Zrb?

- **Easy Automation with Python:** Write your tasks in Python and let Zrb handle the rest.
- **Seamless Integration:** Utilize built-in support for LLM tasks, command execution, and more.
- **Custom Workflows:** Chain tasks, set dependencies, and build robust automation pipelines.
- **Developer-Friendly:** Quick to install and get started, with clear documentation and examples.
- **Web Interface:** Run Zrb as a server to make tasks accessible even to non-technical team members.


## 🔥 Key Features

- **LLM Integration:** Leverage state-of-the-art language models to generate code, diagrams, and documentation.
- **Task Chaining:** Easily define dependencies between tasks to create complex workflows.
- **CLI & Server Mode:** Run tasks directly from the command line or through a user-friendly web UI.
- **Flexible Input Handling:** Defaults, prompts, and command-line parameters to suit any workflow.
- **Extensible & Open Source:** Contribute, customize, or extend Zrb to fit your unique needs.


# 🛠️ Installation

Install Zrb via pip:

```bash
pip install zrb

```

Or run our installation script to set up Zrb along with all prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"

```

# 🍲 Quick Start: Build Your First Automation Workflow

Zrb empowers you to create custom automation tasks using Python. This guide shows you how to define two simple tasks: one to generate a PlantUML script from your source code and another to convert that script into a PNG image.

## 1. Create Your Task Definition File

Place a file named `zrb_init.py` in a directory that's accessible from your projects. Zrb will automatically search for this file by starting in your current directory and then moving upward (i.e., checking parent directories) until it finds one. This means if you place your `zrb_init.py` in your home directory (e.g., `/home/<your-user-name>/zrb_init.py`), the tasks defined there will be available for any project.

Add the following content to your zrb_init.py:

```python
import os
from zrb import cli, LLMTask, CmdTask, StrInput, Group
from zrb.builtin.llm.tool.file import (
    list_files, read_from_file, search_files, write_to_file
)


CURRENT_DIR = os.getcwd()

# Create a group for UML-related tasks
uml_group = cli.add_group(Group(name="uml", description="UML related tasks"))

# Task 1: Generate a PlantUML script from your source code
make_uml_script = uml_group.add_task(
    LLMTask(
        name="make-script",
        description="Creating plantuml diagram based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        message=(
            f"Read all necessary files in {CURRENT_DIR}, "
            "make a {ctx.input.diagram} in plantuml format. "
            f"Write the script into {CURRENT_DIR}/{{ctx.input.diagram}}.uml"
        ),
        tools=[
            list_files, read_from_file, search_files, write_to_file
        ],
    )
)

# Task 2: Convert the PlantUML script into a PNG image
make_uml_image = uml_group.add_task(
    CmdTask(
        name="make-image",
        description="Creating png based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        cmd="plantuml -tpng '{ctx.input.diagram}.uml'",
        cwd=CURRENT_DIR,
    )
)

# Set up the dependency: the image task runs after the script is created
make_uml_script >> make_uml_image
```

**What This Does**

- **Task 1 – make-script**:

    Uses an LLM to read all files in your current directory and generate a PlantUML script (e.g., `state diagram.uml`).

- **Task 2 – make-image**:

    Executes a command that converts the PlantUML script into a PNG image (e.g., `state diagram.png`). This task will run only after the script has been generated.


## 2. Run Your Tasks

After setting up your tasks, you can execute them from any project. For example:

- Clone/Create a Project:

    ```bash
    git clone git@github.com:jjinux/gotetris.git
    cd gotetris
    ```

- Create a state diagram:

    ```bash
    zrb uml make-image --diagram "state diagram"
    ```

- Or use the interactive mode:

    ```bash
    zrb uml make-image
    ```

    Zrb will prompt:

    ```bash
    diagram [state diagram]:
    ```

    Press **Enter** to use the default value

![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)


## 3. Try Out the Web UI

You can also serve your tasks through a user-friendly web interface:

```bash
zrb server start
```

Then open your browser and visit `http://localhost:21213`

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)


# 🎥 Demo & Documentation

- **Step by step guide:** [Getting started with Zrb](https://github.com/state-alchemists/zrb/blob/main/docs/recipes/getting-started/README.md).
- **Full documentation:** [Zrb Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)
- **Video demo:**

    [![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)


# 🤝 Join the Community

- **Bug Reports & Feature Requests:** Create an [issue](https://github.com/state-alchemists/zrb/issues) on Zrb's GitHub Repositories and include:
    - Your Zrb version (i.e., `zrb version`).
    - Steps you’ve taken and what you expected versus what happened
- **Contributions:** We welcome pull requests! Check out our [contribution guidelines](https://github.com/state-alchemists/zrb/pulls).


# ☕ Support The Project

If you find Zrb valuable, please consider donating:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com/donation)

# 🎉 Fun Fact

Did you know?

Zrb is named after `Zaruba`, a powerful support tool from the Garo universe!

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
