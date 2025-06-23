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
# pip install --pre zrb
```

Or run our installation script to set up Zrb along with all prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

You can also [run Zrb as container](https://github.com/state-alchemists/zrb?tab=readme-ov-file#-run-zrb-as-a-container)

# 🍲 Quick Start: Build Your First Automation Workflow

Zrb empowers you to create custom automation tasks using Python. This guide shows you how to define two simple tasks: one to generate a Mermaid script from your source code and another to convert that script into a PNG image.

## 1. Create Your Task Definition File

Place a file named `zrb_init.py` in a directory that's accessible from your projects. Zrb will automatically search for this file by starting in your current directory and then moving upward (i.e., checking parent directories) until it finds one. This means if you place your `zrb_init.py` in your home directory (e.g., `/home/<your-user-name>/zrb_init.py`), the tasks defined there will be available for any project.

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

    Uses an LLM to read all files in your current directory and generate a Mermaid script (e.g., `state diagram.mmd`).

- **Task 2 – make-image**:

    Executes a command that converts the Mermaid script into a PNG image (e.g., `state diagram.png`). This task will run only after the script has been generated.


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

    ```bash
    dir [./]:
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


# 🐋 Run Zrb as a Container

Zrb can be run in a containerized environment, offering two distinct versions to suit different needs:

- **Standard Version**: Ideal for general use cases where Docker CLI access is not required.
- **Dind (Docker in Docker) Version**: Includes built-in Docker commands, perfect for scenarios where you need to access the host's Docker CLI.

### Standard Version

The standard version of the Zrb container is suitable for most automation tasks. To run this version, execute the following command:

```bash
# Replace <host-path> and <container-path> with your desired paths
docker run -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:1.8.1 zrb
```

### Dind Version

The Dind version is tailored for advanced use cases where Docker commands need to be executed within the container. This version allows the container to interact with the host's Docker daemon. To run the Dind version, use the command below:

```bash
# Replace <host-path> and <container-path> with your desired paths
docker run \
    -v ${HOME}:/zrb-home \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -it --rm stalchmst/zrb:1.8.1-dind docker ps
```

> **Note:** The Dind (Docker in Docker) version of the container is larger in size compared to the standard version due to the inclusion of Docker CLI tools. Consider this when choosing the appropriate version for your needs.

# 🎥 Demo & Documentation

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

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com)

# 🎉 Fun Fact

Did you know?

Zrb is named after `Zaruba`, a powerful support tool from the Garo universe!

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
