# 🤖 Zrb: Your Faithful Companion

![](https://raw.githubusercontent.com/state-alchemists/zrb/main/images/zrb/android-chrome-192x192.png)

Zrb is a [CLI-based](https://en.wikipedia.org/wiki/Command-line_interface) automation [tool](https://en.wikipedia.org/wiki/Programming_tool) and [low-code](https://en.wikipedia.org/wiki/Low-code_development_platform) platform. Once installed, you can automate day-to-day tasks, generate projects and applications, and even deploy your applications to Kubernetes with a few commands.

To use Zrb, you need to be familiar with CLI.

Let's see how you can build a [CRUD](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete) application, add some fields to it, and deploy the application as monolith/microservices:

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

Zrb also allows you to define your automation commands in Python:

```python
# filename: zrb_init.py
from zrb import runner, CmdTask, StrInput

hello = CmdTask(
    name='hello',
    inputs=[StrInput(name='name', description='Name', default='world')],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)
```

Once defined, your command will be instantly available from the CLI:

```bash
zrb hello
```

```
Name [world]: Go Frendi
🤖 ➜  2023-06-10T21:20:19.850063 ⚙ 10008 ➤ 1 of 3 • 🐷            zrb hello • Run script: echo Hello Go Frendi
🤖 ➜  2023-06-10T21:20:19.850362 ⚙ 10008 ➤ 1 of 3 • 🐷            zrb hello • Current working directory: /home/gofrendi/zrb/playground
🤖 ➜  2023-06-10T21:20:19.857585 ⚙ 10009 ➤ 1 of 3 • 🐷            zrb hello • Hello Go Frendi
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ➜  2023-06-10T21:20:19.898304 ⚙ 10009 ➤ 1 of 3 • 🐷            zrb hello • zrb hello completed in 0.11999917030334473 seconds
To run again: zrb hello --name "Go Frendi"
Hello Go Frendi
```

To learn more about this, you can visit [our getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md).


# 🫰 Installation

## ⚙️ In local machine

Installing Zrb in your system is as easy as typing the following command in your terminal:

```bash
pip install zrb
```

Just like any other Python package, you can also install Zrb in your [virtual environment](https://docs.python.org/3/library/venv.html). This will allow you to have many versions of Zrb on the same computer.

> ⚠️ If the command doesn't work, you probably don't have Pip/Python on your computer. See `Main prerequisites` subsection to install them.

## 🐋 With docker

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
      - 3000:3000 # or/and any other ports you want to expose.
```

Once your docker-compose file is created, you can invoke the following command:

```bash
docker compose up -d
```

You will be able to access Zrb by using docker exec:

```bash
docker exec -it zrb zsh
```

# ✅ Main prerequisites

Since Zrb is written in Python, you need to install a few things before installing Zrb:

- 🐍 `Python`
- 📦 `Pip`
- 🏝️ `Venv`

If you are using 🐧 Ubuntu, the following command should work:

```bash
sudo apt-get install python3 python3-pip python3-venv python-is-python3
```

If you are using 🍎 Mac, the following command will work:

```bash
# Make sure you have homebrew installed, see: https://brew.sh/
brew install python3
ln -s venv/bin/pip3 /usr/local/bin/pip
ln -s venv/bin/python3 /usr/local/bin/python
```

If you prefer Python distribution like [conda](https://docs.conda.io/en/latest/), that might work as well.

# ✔️ Other prerequisites

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

# 🏁 Getting started

We have a nice [getting started guide](https://github.com/state-alchemists/zrb/blob/main/docs/getting-started.md) to help you cover the basics. Make sure to check it out😉.

# 📖 Documentation

You can visit [Zrb documentation](https://github.com/state-alchemists/zrb/blob/main/docs/README.md) for more detailed information.

# ☕ Donation

Help Red Skull to click the donation button:

[![](https://raw.githubusercontent.com/state-alchemists/zrb/main/images/donator.png)](https://stalchmst.com/donation)

# 🎉 Fun fact

> Madou Ring Zaruba (魔導輪ザルバ, Madōrin Zaruba) is a Madougu which supports bearers of the Garo Armor. [(Garo Wiki | Fandom)](https://garo.fandom.com/wiki/Zaruba)

![Madou Ring Zaruba on Kouga's Hand](https://raw.githubusercontent.com/state-alchemists/zrb/main/images/madou-ring-zaruba.jpg)
