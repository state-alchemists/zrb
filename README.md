![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse

Zrb allows you to write your automation tasks in Python. For example, you can define the following script in your home directory (`/home/<your-user-name>/zrb_init.py`).


```python
import os
from zrb import cli, LLMTask, CmdTask, StrInput
from zrb.builtin.llm.tool.file import read_source_code, write_text_file
from pydantic_ai.models.openai import OpenAIModel


CURRENT_DIR = os.getcwd()
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_NAME = os.getenv(
    "AGENT_MODEL_NAME", "anthropic/claude-3.7-sonnet"
)


# Defining a LLM Task to create a Plantuml script based on source code in current directory.
# User can choose the diagram type. By default it is "state diagram"
make_uml = cli.add_task(
    LLMTask(
        name="make-uml",
        description="Creating plantuml diagram based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        model=OpenAIModel(
            OPENROUTER_MODEL_NAME,
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        ),
        message=(
            f"Read source code in {CURRENT_DIR}, "
            "make a {ctx.input.diagram} in plantuml format. "
            f"Write the script into {CURRENT_DIR}/{{ctx.input.diagram}}.uml"
        ),
        tools=[
            read_source_code,
            write_text_file,
        ],
    )
)

# Defining a Cmd Task to transform Plantuml script into a png image.
make_png = cli.add_task(
    CmdTask(
        name="make-png",
        description="Creating png based on source code in current directory",
        input=StrInput(name="diagram", default="state diagram"),
        cmd="plantuml -tpng '{ctx.input.diagram}.uml'",
        cwd=CURRENT_DIR,
    )
)

# Making sure that make_png has make_uml as its dependency.
make_uml >> make_png
```

Once defined, your automation tasks are immediately accessible from the CLI. You can then invoke the tasks by invoking.

```bash
zrb make-png --diagram "state diagram"
```

Or you can invoke the tasks without parameter.

```bash
zrb make-png
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
