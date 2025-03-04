![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)

# 🤖 Zrb: Your Automation Powerhouse

Zrb allows you to write your automation tasks in Python and declaratively:


```python
# Filename: zrb_init.py
from zrb import cli, Task, Group, IntInput

math = cli.add_group(Group("math", description="Math tools"))
math.add_task(Task(
    name="add",
    input=[
        IntInput("a", description="First number"),
        IntInput("b", description="Second number")
    ],
    action=lambda ctx: ctx.input.a + ctx.input.b
))
```

Once defined, you will be able to access your automation tasks from the CLI, Web Interface, or via HTTP API.

For more complex scenario, you can also defined Task dependencies (upstreams) and retry mechanisms. You can also make a scheduled tasks, just like in Apache Airflow.

Furthermore, Zrb has some builtin tasks to manage monorepo, generate FastAPI application, or play around with LLM.

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
