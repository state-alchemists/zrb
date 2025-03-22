![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse


**Unlock the full potential of automation in your projects!**

Zrb streamlines repetitive tasks, integrates with powerful LLMs, and lets you create custom automation workflows effortlessly. Whether you’re building CI/CD pipelines, code generators, or unique automation scripts, Zrb is designed to simplify and supercharge your workflow.

---

## 🚀 Why Zrb?

- **Easy Automation with Python:** Write your tasks in Python and let Zrb handle the rest.
- **Seamless Integration:** Utilize built-in support for LLM tasks, command execution, and more.
- **Custom Workflows:** Chain tasks, set dependencies, and build robust automation pipelines.
- **Developer-Friendly:** Quick to install and get started, with clear documentation and examples.
- **Web Interface:** Run Zrb as a server to make tasks accessible even to non-technical team members.

---

## 🔥 Key Features

- **LLM Integration:** Leverage state-of-the-art language models to generate code, diagrams, and documentation.
- **Task Chaining:** Easily define dependencies between tasks to create complex workflows.
- **CLI & Server Mode:** Run tasks directly from the command line or through a user-friendly web UI.
- **Flexible Input Handling:** Defaults, prompts, and command-line parameters to suit any workflow.
- **Extensible & Open Source:** Contribute, customize, or extend Zrb to fit your unique needs.

---

## 🛠️ Getting Started

### Quick Installation

Install Zrb via pip:

```bash
pip install zrb

```

Or run our installation script to set up Zrb along with all prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"

```

### Your First Task

Create a file at `/home/<your-user-name>/zrb_init.py` with the following content:


```python
import os
from zrb import cli, llm_config, LLMTask, CmdTask, StrInput, Group
from zrb.builtin.llm.tool.file import read_all_files, write_text_file

CURRENT_DIR = os.getcwd()

# Make UML group
uml_group = cli.add_group(Group(name="uml", description="UML related tasks"))

# Generate UML script
make_uml_script = uml_group.add_task(
    LLMTask(
        name="make-script",
        description="Creating plantuml diagram based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        message=(
            f"Read source code in {CURRENT_DIR}, "
            "make a {ctx.input.diagram} in plantuml format. "
            f"Write the script into {CURRENT_DIR}/{{ctx.input.diagram}}.uml"
        ),
        tools=[
            read_all_files,
            write_text_file,
        ],
    )
)

# Defining a Cmd Task to transform Plantuml script into a png image.
make_uml_image = uml_group.add_task(
    CmdTask(
        name="make-image",
        description="Creating png based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        cmd="plantuml -tpng '{ctx.input.diagram}.uml'",
        cwd=CURRENT_DIR,
    )
)

# Making sure that make_png has make_uml as its dependency.
make_uml_script >> make_uml_image
```

You have just define two automation tasks.

The first one use LLM to read files in your current directory and create a `PlantUML script` on that directory.

The second task turn the PlantUML script into a `*.png` file. The second task depends on the first task and both of them are located under the same group.

You can run the tasks by invoking `zrb uml make-script` or `zrb uml make-image` respectively.

When you run zrb, it automatically searches for a file named `zrb_init.py` starting from your current directory and moving upward through its parent directories. This design lets you set up common automation tasks in a central location—like placing a `zrb_init.py` in your home directory (`/home/<your-user>/zrb_init.py`)—so that your tasks are available across all your projects.

Now, go to your project and create a state diagram:

```bash
git clone git@github.com:jjinux/gotetris.git
cd gotetris
zrb uml make-image --diagram "state diagram"
```

You can also invoke the task without specifying parameter.

```bash
zrb uml make-image
```

Once you do so, Zrb will ask you to provide the diagram type.

```
diagram [state diagram]:
```

You can just press enter if you want to use the default value (i.e., in this case `state diagram`).

Finally, you can also serve the tasks via a Web UI interface by invoking the following command:

```bash
zrb server start
```

You will have a nice web interface running on `http://localhost:12123`

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

Now, let's see how things work in detail. First, Zrb generates a `state diagram.uml` in your current directory, it then transform the UML script into a PNG image `state diagram.png`.

![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)


# 🎥 Demo & Documentation

- **Step by step guide:** [Getting started with Zrb](https://github.com/state-alchemists/zrb/blob/main/docs/recipes/getting-started/README.md).
- **Full documentation:** [Zrb Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)
- **Video demo:** [![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)


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
