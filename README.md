# 🤖 Zrb (Read: Zaruba) : A Super Framework for Your Super App

![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/zrb/android-chrome-192x192.png)

[📖 Documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md) | [🏁 Getting Started](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md) | [💃 Oops, I did it Again](https://github.com/state-alchemists/zrb/blob/main/docs/oops-i-did-it-again/README.md) | [❓ FAQ](https://github.com/state-alchemists/zrb/blob/main/docs/faq/README.md)

Zrb is a [CLI-based](https://en.wikipedia.org/wiki/Command-line_interface) automation [tool](https://en.wikipedia.org/wiki/Programming_tool) and [low-code](https://en.wikipedia.org/wiki/Low-code_development_platform) platform. Once installed, Zrb will help you automate day-to-day tasks, generate projects and applications, and even deploy your applications to Kubernetes with a few commands.

To use Zrb, you need to be familiar with CLI.

Zrb task definitions are written in [Python](https://www.python.org/), and we have a [good reason](https://github.com/state-alchemists/zrb/blob/main/docs/faq/why-python.md) behind the decision.

## Zrb is A Task-Automation Tool

At the very core, Zrb is a task automation tool. It helps you to automate some tedious jobs so that you can focus on what matters.

Let's say you want to describe the statistics property of any public CSV. To do this, you need to perform three tasks like the following:

- Install pandas.
- Download the CSV dataset (at the same time).
- Show statistics properties of the CSV dataset using pandas (right after the two first tasks are completed).

```
 ┌──────────────────┐
 │                  │
 │  Install Pandas  ├─┐
 │                  │ │  ┌─────────────────┐
 └──────────────────┘ └─►│                 │
                         │ Show Statistics │
 ┌──────────────────┐ ┌─►│                 │
 │                  │ │  └─────────────────┘
 │ Download Dataset ├─┘
 │                  │
 └──────────────────┘
```

To do this, you can create a file named `zrb_init.py` and define the tasks as follows:

```python
# File name: zrb_init.py
from zrb import runner, CmdTask, python_task, StrInput

# Define a task to install pandas
install_pandas = CmdTask(
    name='install-pandas',
    cmd='pip install pandas'
)

# Define a task to download dataset
download_dataset = CmdTask(
    name='download-dataset',
    inputs=[
        # Allow user to put the CSV dataset URL.
        StrInput(
            name='url',
            default='https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv'
        )
    ],
    cmd='wget -O dataset.csv {{input.url}}'
)

# Define a task to show the statistics properties of the dataset
show_stat = CmdTask(
    name='show-stat',
    upstreams=[
        # Let the following tasks to be show_stat's upstream
        download_dataset,
        install_pandas
    ],
    cmd='python -c "import pandas as pd; df=pd.read_csv(\'dataset.csv\'); print(df.describe())"'  # noqa
)

# Register show_stat, so that the task is accessible from the CLI (i.e., zrb show-stat)
runner.register(show_stat)
```

Once you do so, you can invoke the task and get the output.

```bash
zrb show-stat
```

```
Url [https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv]:
🤖 ○ ❁ 27694 → 1/3 🍉 download-dataset • Run script: wget -O dataset.csv https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 ○ ❁ 27694 → 1/3 🍉 download-dataset • Working directory: /home/gofrendi/playground/myproject
🤖 ○ ❁ 27694 → 1/3 🦊   install-pandas • Run script: pip install pandas
🤖 ○ ❁ 27694 → 1/3 🦊   install-pandas • Working directory: /home/gofrendi/playground/myproject
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • --2023-11-11 15:29:01--  https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • Resolving raw.githubusercontent.com (raw.githubusercontent.com)... 185.199.108.133, 185.199.111.133, 185.199.109.133, ...
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • Connecting to raw.githubusercontent.com (raw.githubusercontent.com)|185.199.108.133|:443... connected.
🤖 ○ ❁ 27702 → 1/3 🦊   install-pandas • Requirement already satisfied: pandas in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (2.1.3)
🤖 ○ ❁ 27702 → 1/3 🦊   install-pandas • Requirement already satisfied: numpy<2,>=1.22.4 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (1.26.1)
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • HTTP request sent, awaiting response... 200 OK
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • Length: 4606 (4.5K) [text/plain]
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • Saving to: ‘dataset.csv’
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset •      0K ....                                                  100% 4.19M=0.001s
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset • 2023-11-11 15:29:01 (4.19 MB/s) - ‘dataset.csv’ saved [4606/4606]
🤖 △ ❁ 27700 → 1/3 🍉 download-dataset •
🤖 ○ ❁ 27694 → 1/3 🐯    zrb show-stat • Run script: python -c "import pandas as pd; df=pd.read_csv('dataset.csv'); print(df.describe())"
🤖 ○ ❁ 27694 → 1/3 🐯    zrb show-stat • Working directory: /home/gofrendi/playground/myproject
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat •        sepal_length  sepal_width  petal_length  petal_width
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • count    150.000000   150.000000    150.000000   150.000000
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • mean       5.843333     3.054000      3.758667     1.198667
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • std        0.828066     0.433594      1.764420     0.763161
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • min        4.300000     2.000000      1.000000     0.100000
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • 25%        5.100000     2.800000      1.600000     0.300000
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • 50%        5.800000     3.000000      4.350000     1.300000
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • 75%        6.400000     3.300000      5.100000     1.800000
🤖 ○ ❁ 27746 → 1/3 🐯    zrb show-stat • max        7.900000     4.400000      6.900000     2.500000
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ❁ 27746 → 1/3 🐯        zrb show-stat • Completed in 1.3806817531585693 seconds
       sepal_length  sepal_width  petal_length  petal_width
count    150.000000   150.000000    150.000000   150.000000
mean       5.843333     3.054000      3.758667     1.198667
std        0.828066     0.433594      1.764420     0.763161
min        4.300000     2.000000      1.000000     0.100000
25%        5.100000     2.800000      1.600000     0.300000
50%        5.800000     3.000000      4.350000     1.300000
75%        6.400000     3.300000      5.100000     1.800000
max        7.900000     4.400000      6.900000     2.500000
To run again: zrb show-stat --url "https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv"
```


To learn more about this, you can visit [our getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md).


## Zrb is A Low-Code Framework

Let's see how you can build and run a [CRUD](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete) application.

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

You will be able to access the application by pointing your browser to [http://localhost:3000](http://localhost:3000)

![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/fastapp.png)

Furthermore, you can run the same application as `microservices`, run the application as `docker containers`, and even do some deployments into your `kubernetes cluster`.


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

You can visit [our tutorials](https://github.com/state-alchemists/zrb/blob/main/docs/tutorials/README.md) to see more cool tricks.


# 🫰 Installation

## ⚙️ In Local Machine

Installing Zrb in your system is as easy as typing the following command in your terminal:

```bash
pip install zrb
```

Like any other Python package, you can install Zrb in your [virtual environment](https://docs.python.org/3/library/venv.html). This will allow you to have many versions of Zrb on the same computer.

> ⚠️ If the command doesn't work, you probably don't have Pip/Python on your computer. See `Main prerequisites` subsection to install them.

## 🐋 With Docker

If you prefer to work with Docker, you can create a file named `docker-compose.yml`

```yaml
version: '3'
networks:
  zrb:
    name: zrb
services:

  zrb:
    build:
      dockerfile: Dockerfile
      context: .
    image: docker.io/stalchmst/zrb:latest
    container_name: zrb
    hostname: zrb
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./project:/project
    networks:
      - zrb
    ports:
      - 3001:3001 # or/and any other ports you want to expose.
```

Once your docker-compose file is created, you can invoke the following command:

```bash
docker compose up -d
```

You will be able to access Zrb by using docker exec:

```bash
docker exec -it zrb zsh
```

# ✅ Main Prerequisites

Since Zrb is written in Python, you need to install a few things before installing Zrb:

- 🐍 `Python`
- 📦 `Pip`
- 🏝️ `Venv`

If you are using 🐧 Ubuntu, the following command should work:

```bash
sudo apt install python3 python3-pip python3-venv python-is-python3
```

If you are using 🍎 Mac, the following command will work:

```bash
# Make sure you have homebrew installed, see: https://brew.sh/
brew install python3
ln -s venv/bin/pip3 /usr/local/bin/pip
ln -s venv/bin/python3 /usr/local/bin/python
```

If you prefer Python distribution like [conda](https://docs.conda.io/en/latest/), that might work as well.

# ✔️ Other Prerequisites

If you want to generate applications using Zrb and run them on your computer, you will also need:

- 🐸 `Node.Js` and `Npm`.
    - You need Node.Js to modify/transpile frontend code into static files.
    - You can visit the [Node.Js website](https://nodejs.org/en) for installation instructions.
- 🐋 `Docker` and `Docker-compose` plugin.
    - You need `Docker` and `Docker-compose` plugin to
        - Run docker-compose-based tasks
        - Run some application prerequisites like RabbitMQ, Postgre, or Redpanda. 
    - The easiest way to install `Docker`, `Docker-compose` plugin, and local `Kubernetes` is by using [Docker Desktop](https://www.docker.com/products/docker-desktop/).
    - You can also install `Docker` and `Docker-compose` plugin by following the [Docker installation guide](https://docs.docker.com/engine/install/).
-  ☸️ `Kubernetes` cluster.
    - Zrb allows you to deploy your applications into `Kubernetes`.
    - To test it locally, you will need a [Minikube](https://minikube.sigs.k8s.io/docs/) or other alternatives. However, the easiest way is by enabling `Kubernetes` on your `Docker Desktop`.
- 🦆 `Pulumi`
    - You need Pulumi to deploy your applications

# 🏁 Getting Started

We have an excellent [getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md) to help you cover the basics. Make sure to check it out😉.

# 📖 Documentation

You can visit [Zrb documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md) for more detailed information.

# ☕ Donation

Help Red Skull to click the donation button:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/donator.png)](https://stalchmst.com/donation)

# 🎉 Fun Fact

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/_images/madou-ring-zaruba.jpg)
