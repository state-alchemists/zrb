![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)


[🫰 Installation](https://github.com/state-alchemists/zrb/blob/main/docs/installation.md) | [📖 Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md) | [🏁 Getting Started](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md) | [💃 Common Mistakes](https://github.com/state-alchemists/zrb/blob/main/docs/oops-i-did-it-again/README.md) | [❓ FAQ](https://github.com/state-alchemists/zrb/blob/main/docs/faq/README.md)


# 🤖 Zrb: A Framework to Enhance Your Workflow

Zrb is a [CLI-based](https://en.wikipedia.org/wiki/Command-line_interface) automation [tool](https://en.wikipedia.org/wiki/Programming_tool) and [low-code](https://en.wikipedia.org/wiki/Low-code_development_platform) platform. Zrb can help you to:

- __Automate__ day-to-day tasks.
- __Generate__ projects or applications.
- __Prepare__, __run__, and __deploy__ your applications with a single command.
- Etc.

You can also write custom task definitions in [Python](https://www.python.org/), enhancing Zrb's base capabilities. Defining your tasks in Zrb gives you several advantages because:

- Every task has a __retry mechanism__.
- Zrb handles your __task dependencies__ automatically.
- Zrb runs your task dependencies __concurrently__.

# 🫰 Installing Zrb

You can install Zrb as a pip package by invoking the following command:

```bash
pip install zrb
```

Alternatively, you can also use our installation script to install Zrb along with some prerequisites:

```bash
source <(curl -s https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)
```

Check our [installation guide](https://github.com/state-alchemists/zrb/blob/main/docs/installation.md) for more information about the installation methods, including installation as a docker container.

# ⚙️ Zrb as A Task-Automation Tool

At the very core, Zrb is a task automation tool. It helps you to automate some tedious jobs so that you can focus on what matters.

Let's say you want to be able to describe the statistics property of any public CSV dataset. To do this, you need to perform three tasks like the following:

- Install pandas.
- Download the CSV dataset (at the same time).
- Show statistics properties of the CSV dataset.

```
       🐼
Install Pandas ─────┐           📊
                    ├──► Show Statistics
Download Datasets ──┘
       ⬇️
```

You can create a file named `zrb_init.py` and define the tasks as follows:

```python
# File name: zrb_init.py
from zrb import runner, Parallel, CmdTask, python_task, StrInput

DEFAULT_URL = 'https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv'

# 🐼 Define a task named `install-pandas` to install pandas.
# If this task failed, we want Zrb to retry it again 4 times at most.
install_pandas = CmdTask(
    name='install-pandas',
    cmd='pip install pandas',
    retry=4
)

# ⬇️ Define a task named `download-dataset` to download dataset.
# This task has an input named `url`.
# The input will be accessible by using Jinja template: `{{input.url}}`
# If this task failed, we want Zrb to retry it again 4 times at most
download_dataset = CmdTask(
    name='download-dataset',
    inputs=[
        StrInput(name='url', default=DEFAULT_URL)
    ],
    cmd='wget -O dataset.csv {{input.url}}',
    retry=4
)

# 📊 Define a task named `show-stat` to show the statistics properties of the dataset.
# @python_task` decorator turns a function into a Zrb Task (i.e., `show_stat` is now a Zrb Task).
# If this task failed, we don't want to retry
@python_task(
    name='show-stats',
    retry=0
)
def show_stats(*args, **kwargs):
    import pandas as pd
    df = pd.read_csv('dataset.csv')
    return df.describe()

# Define dependencies: `show_stat` depends on both, `download_dataset` and `install_pandas`
Parallel(download_dataset, install_pandas) >> show_stats

# Register the tasks so that they are accessbie from the CLI
runner.register(install_pandas, download_dataset, show_stats)
```

> __📝 NOTE:__ It is possible (although less readable) to define `show_stat` as `CmdTask`:
> <details>
> <summary>Show code</summary>
>
> ```python
> show_stats = CmdTask(
>     name='show-stats',
>     cmd='python -c "import pandas as pd; df=pd.read_csv(\'dataset.csv\'); print(df.describe())"',
>     retry=0
> )
> ```
> </details>


Once you write the definitions, Zrb will automatically load your `zrb_init.py` so that you can invoke your registered task:

```bash
zrb show-stat
```

The command will give you the statistics property of the dataset:

```
       sepal_length  sepal_width  petal_length  petal_width
count    150.000000   150.000000    150.000000   150.000000
mean       5.843333     3.054000      3.758667     1.198667
std        0.828066     0.433594      1.764420     0.763161
min        4.300000     2.000000      1.000000     0.100000
25%        5.100000     2.800000      1.600000     0.300000
50%        5.800000     3.000000      4.350000     1.300000
75%        6.400000     3.300000      5.100000     1.800000
max        7.900000     4.400000      6.900000     2.500000
```

<details>
<summary>See the full output</summary>

```
Url [https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv]:
🤖 ○ ◷ ❁ 43598 → 1/3 🐮 zrb project install-pandas • Run script: pip install pandas
🤖 ○ ◷ ❁ 43598 → 1/3 🐮 zrb project install-pandas • Working directory: /home/gofrendi/playground/my-project
🤖 ○ ◷ ❁ 43598 → 1/3 🍓 zrb project download-dataset • Run script: wget -O dataset.csv https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 ○ ◷ ❁ 43598 → 1/3 🍓 zrb project download-dataset • Working directory: /home/gofrendi/playground/my-project
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • --2023-11-12 09:45:12--  https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • Resolving raw.githubusercontent.com (raw.githubusercontent.com)... 185.199.111.133, 185.199.109.133, 185.199.110.133, ...
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • Connecting to raw.githubusercontent.com (raw.githubusercontent.com)|185.199.111.133|:443... connected.
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • HTTP request sent, awaiting response... 200 OK
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • Length: 4606 (4.5K) [text/plain]
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • Saving to: ‘dataset.csv’
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset •      0K ....                                                  100% 1.39M=0.003s
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset • 2023-11-12 09:45:12 (1.39 MB/s) - ‘dataset.csv’ saved [4606/4606]
🤖 △ ◷ ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: pandas in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (2.1.3)
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: numpy<2,>=1.22.4 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (1.26.1)
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: python-dateutil>=2.8.2 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2.8.2)
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: pytz>=2020.1 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2023.3.post1)
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: tzdata>=2022.1 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2023.3)
🤖 ○ ◷ ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: six>=1.5 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from python-dateutil>=2.8.2->pandas) (1.16.0)
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-12 09:45:14.366 ❁ 43598 → 1/3 🍎 zrb project show-stats • Completed in 2.2365798950195312 seconds
       sepal_length  sepal_width  petal_length  petal_width
count    150.000000   150.000000    150.000000   150.000000
mean       5.843333     3.054000      3.758667     1.198667
std        0.828066     0.433594      1.764420     0.763161
min        4.300000     2.000000      1.000000     0.100000
25%        5.100000     2.800000      1.600000     0.300000
50%        5.800000     3.000000      4.350000     1.300000
75%        6.400000     3.300000      5.100000     1.800000
max        7.900000     4.400000      6.900000     2.500000
To run again: zrb project show-stats --url "https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv"
```
</details>

Since you have registered `install_pandas` and `download_dataset` (i.e., `runner.register(install_pandas, download_dataset)`), then you can also execute those tasks as well:

```bash
zrb install-pandas
zrb download-dataset
```

> __📝 NOTE:__  When executing a task, you can also provide the parameter directly, for example you want to provide the `url`
>
> ```bash
> zrb show-stat --url https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
> ```
>
> When you provide the parameter directly, Zrb will not prompt you to supply the URL.
> Another way to disable the prompt is by set `ZRB_SHOW_PROMPT` to `0` or `false`.

You can also run a Docker compose file, start a Web server, generate a CRUD application, or set up multiple servers simultaneously.

See [our getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md) and [tutorials](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/README.md) to learn more about the details.

# ✂️ Zrb as A Low-Code Framework

Zrb has some built-in tasks that allow you to create and run a [CRUD](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete) application.

Let's see the following example.

```bash
# Create a project
zrb project create --project-dir my-project --project-name "My Project"
cd my-project

# Create a Fastapp
zrb project add fastapp --project-dir . --app-name "fastapp" --http-port 3000

# Add library module to fastapp
zrb project add fastapp-module --project-dir . --app-name "fastapp" --module-name "library"

# Add entity named "books"
zrb project add fastapp-crud --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --plural-entity-name "books" --column-name "code"

# Add column to the entity
zrb project add fastapp-field --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --column-name "title" --column-type "str"

# Run Fastapp as monolith
zrb project start-fastapp --fastapp-run-mode "monolith"
```

Once you invoke the commands, you will be able to access the CRUD application by pointing your browser to [http://localhost:3000](http://localhost:3000)

![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/fastapp.png)

Furthermore, you can also split your application into `microservices`, run them as `docker containers`, and even deploy them to your `kubernetes cluster`.

```bash
# Run Fastapp as microservices
zrb project start-fastapp --fastapp-run-mode "microservices"

# Run Fastapp as container
zrb project start-fastapp-container --fastapp-run-mode "microservices"
zrb project stop-fastapp-container

# Deploy fastapp and all it's dependencies to kubernetes
docker login
zrb project deploy-fastapp --fastapp-deploy-mode "microservices"
```

Visit [our tutorials](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/README.md) to see more cool tricks.

# 📖 Documentation

- [🫰 Installation](https://github.com/state-alchemists/zrb/blob/main/docs/installation.md)
- [🏁 Getting Started](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md)
- [📖 Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md)
- [💃 Common Mistakes](https://github.com/state-alchemists/zrb/blob/main/docs/oops-i-did-it-again/README.md)
- [❓ FAQ](https://github.com/state-alchemists/zrb/blob/main/docs/faq/README.md)

# 🐞 Bug Report + Feature Request

You can submit bug report and feature request by creating a new [issue](https://github.com/state-alchemists/zrb/issues) on Zrb Github Repositories. When reporting a bug or requesting a feature, please be sure to:

- Include the version of Zrb you are using (i.e., `zrb version`)
- Tell us what you have try
- Tell us what you expect
- Tell us what you get

We will also welcome your [pull requests and contributions](https://github.com/state-alchemists/zrb/pulls).


# ☕ Donation

Help Red Skull to click the donation button:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com/donation)

# 🎉 Fun Fact

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)

# 🙇 Credits

We are thankful for the following libraries and services. They accelerate Zrb development processes and make things more fun.

- Libraries
    - [Beartype](https://pypi.org/project/beartype/): Catch invalid typing earlier during runtime.
    - [Click](https://pypi.org/project/click/): Creating a beautiful CLI interface.
    - [Termcolor](https://pypi.org/project/termcolor/): Make the terminal interface more colorful.
    - [Jinja](https://pypi.org/project/Jinja2): A robust templating engine.
    - [Ruamel.yaml](https://pypi.org/project/ruamel.yaml/): Parse YAML effortlessly.
    - [Jsons](https://pypi.org.project/jsons/): Parse JSON. This package should be part of the standard library.
    - [Libcst](https://pypi.org/project/libcst/): Turn Python code into a Concrete Syntax Tree.
    - [Croniter](https://pypi.org/project/croniter/): Parse cron pattern.
    - [Flit](https://pypi.org/project/flit), [Twine](https://pypi.org/project/twine/), and many more. See the complete list of Zrb's requirements.txt
- Services
    - [asciiflow.com](https://asciiflow.com/): Creates beautiful ASCII-based diagrams.
    - [emojipedia.org](https://emojipedia.org/): Find emoji.
    - [emoji.aranja.com](https://emoji.aranja.com/): Turns emoji into images
    - [favicon.io](https://favicon.io/): Turns pictures and texts (including emoji) into favicon.
