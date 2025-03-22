![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse

**Unlock the full potential of automation in your computer!**  

Zrb streamlines repetitive tasks, integrates with powerful LLMs, and lets you create custom automation workflows effortlessly. Whether you’re building CI/CD pipelines, code generators, or custom development scripts, Zrb is designed to make automation simple and effective.

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

Once defined, your automation tasks are immediately accessible from the CLI. You can then invoke the tasks by invoking.

```bash
zrb uml make-image --diagram "state diagram"
```

Or you can invoke the tasks without parameter.

```bash
zrb uml make-image
```

At this point, Zrb will politely ask you to provide the diagram type.

```
diagram [state diagram]:
```

You can just press enter if you want to use the default value.

Finally, you can run Zrb as a server and make your tasks available for non technical users by invoking the following command.

```bash
zrb server start
```

You will have a nice web interface running on `http://localhost:12123`

![Zrb Web UI](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb-web-ui.png)

Now, let's see how Zrb generate the state diagram. Based on the source code in your current directory, Zrb will generate a `state diagram.uml` and transform it into `state diagram.png`.

![State Diagram](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/state-diagram.png)

See the [getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/recipes/getting-started/README.md) for more information. Or just watch the demo:

[![Video Title](https://img.youtube.com/vi/W7dgk96l__o/0.jpg)](https://www.youtube.com/watch?v=W7dgk96l__o)


# 🫰 Installing Zrb

You can install Zrb as a pip package by invoking the following command:

```bash
pip install --pre zrb
```

Alternatively, you can also use our installation script to install Zrb along with some prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

# 🐞 Bug Report + Feature Request

You can submit bug reports and feature requests by creating a new [issue](https://github.com/state-alchemists/zrb/issues) on Zrb's GitHub Repositories. When reporting a bug or requesting a feature, please be sure to:

- Include the version of Zrb you are using (i.e., `zrb version`)
- Tell us what you have tried
- Tell us what you expect
- Tell us what you get

We will also welcome your [pull requests and contributions](https://github.com/state-alchemists/zrb/pulls).


# ☕ Donation

Help Red Skull to click the donation button:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com/donation)

# 🎉 Fun Fact

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
