🔖 [Table of Contents](README.md)

# Installation

- [Installation Methods](#installation-methods)
    - [Using Installation Script](#using-installation-script)
    - [As Python Package](#as-python-package)
        - [Checking for Prerequisites](#checking-for-prerequisites)
        - [Installing The Pip Package](#installing-the-pip-package)
    - [As Docker Container](#as-docker-container)
        - [Extending Zrb Docker Image](#extending-zrb-docker-image)
- [Post Installation](#post-installation)


# Installation Methods

## Using Installation Script

We provide an [installation script](https://github.com/state-alchemists/zrb/blob/main/install.sh) to help you install `pyenv` and `Zrb`. You can run the installation script as follows:

```bash
curl https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh | bash
```

We recommend this installation method if you work on a new computer/VM.

## As Python Package

You can also install Zrb as a Python package using pip.

### Checking for Prerequisites

Before installing Zrb as a Python package, make sure you have the following prerequisites:

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

### Installing The Pip Package

Installing Zrb in your system is as easy as typing the following command in your terminal:

```bash
pip install zrb
```

Like any Python package, you can install Zrb in your [virtual environment](https://docs.python.org/3/library/venv.html). Installing Zrb in a virtual environment allows you to have many versions of Zrb on the same computer.


## As Docker Container

If you prefer to work with Docker, you can create a `docker-compose.yml` file as follows:

```yaml
# Filename: docker-compose.yml
version: '3'

x-logging: &default-logging
  options:
    max-size: "100m"
    max-file: "5"
  driver: json-file

services:

  zrb:
    image: ${ZRB_IMAGE:-docker.io/stalchmst/zrb}
    logging: *default-logging
    container_name: zrb
    hostname: zrb
    command: sleep infinity
    volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ./project:/project
    ports:
    - 3001:3001 # or/and any other ports you want to expose.
```

Once you create a docker-compose file, you can invoke the following command to start the container:

```bash
docker compose up -d
```

You will be able to run any Zrb tasks by accessing the container's bash:

```bash
docker exec -it zrb bash
```

### Extending Zrb Docker Image

It is also possible to extend Zrb docker image to better match your need.

To do this, you need to create a `Dockerfile` as follow:

```Dockerfile
# Filename: Dockerfile
FROM docker.io/stalchmst/zrb:latest

# We want to install AWS CLI and numpy in our image
RUN zrb devtool install aws
RUN pip install numpy
```

Then you need to update your `docker-compose.yml`.

```yaml
# Filename: docker-compose.yml
version: '3'

x-logging: &default-logging
  options:
    max-size: "100m"
    max-file: "5"
  driver: json-file

services:

  zrb:
    # We want to use the new extended image instead of the original one.
    build:
      dockerfile: Dockerfile
      context: .
    logging: *default-logging
    container_name: zrb
    hostname: zrb
    command: sleep infinity
    volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ./project:/project
    ports:
    - 3001:3001 # or/and any other ports you want to expose.
```

Finally, you can recreate and run the container:

```bash
docker compose down
docker compose up -d
```


# Post Installation

Once Zrb has been installed, you can install third-party developer tools as needed. Some tools like `docker` and `nvm` are crucial if you want to create and test your application.

You can invoke `zrb devtool install <developer-tool>` to install the tools.

```bash
zrb devtool install
```

```
Usage: zrb devtool install [OPTIONS] COMMAND [ARGS]...

  Install developer tools

Options:
  --help  Show this message and exit.

Commands:
  aws        AWS CLI
  docker     Most popular containerization platform
  gcloud     Gcloud CLI
  gvm        GVM provides interface to manage go version
  helix      Post modern text editor
  helm       Package manager for kubernetes
  kubectl    Kubernetes CLI tool
  nvm        NVM allows you to quickly install and use different versions...
  pulumi     Universal infrastructure as code
  pyenv      Simple Python version management
  sdkman     SDKMAN! is a tool for managing parallel versions of multiple...
  selenium   Selenium + Chrome web driver
  terraform  Open source IAC by Hashicorp
  tmux       Terminal multiplexer
  zsh        Zsh terminal + oh-my-zsh + zdharma
```

# Next

Now, you have Zrb installed in your computer. Next, you can continue with our [getting-started guide](./getting-started.md).


🔖 [Table of Contents](README.md)