🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Preparing Your Machine

> This guide has been tested under `debian 12` and `ubuntu 22.0.4`

Zrb is a Python package. So, in order to get started, you will need to have:

- Python
- Pip
- Venv

```bash
sudo apt install python-is-python3 python3-dev python3-distutils python3-openssl python3-pip python3-venv
```

# Creating Venv for Setup

Once you have install Python, pip, and venv, you can make a directory named `zrb-setup` and create a virtual environment.

```bash
mkdir -p ~/zrb-setup
cd ~/zrb-setup
python -m venv .venv
source .venv/bin/activate
```

Please note that whenever you want to work with the virtual environment, you will have to execute `source .venv/bin/activate`.

Creating different virtual environment for each of your projects make your pip packages more manageable.
For example, you will be able to have two different version of the same python package in the different project.

# Install Zrb on Venv

After having your virtual environment set up, you can install `zrb` on your virtual environment:

```bash
pip install zrb
```

# Install Essential Packages for Ubuntu/Debian

Next you can install essential packages for development.

```bash
zrb ubuntu install essentials
```

# Setup Zsh

Zsh and oh-my-zsh is highly compatible, yet provide the same experience as `bash`.
Installing zsh is not mandatory, but highly recommended.

To setup and load Zsh, you need to run the following command:

```bash
zrb devtool install zsh
```

The command will help you to setup
- Zsh
- Oh-my-zsh
- Zinit
- Zdharma (will be installed once you reload the terminal)

To load the terminal, you need to `exit` from your current session and re-login.

```bash
exit
```

# Setup Tmux

Tmux is terminal multiplexer. It is useful and highly recommended if you need to spawn multiple terminals in a single panel.

To install tmux, you need to invoke the following command:

```bash
zrb devtool install tmux
```

# Setup Pyenv

With pyenv, you can manage multiple python environments.
Installing pyenv is highly recommended.

You can install pyenv by invoking the following command:

```bash
zrb devtool install pyenv
```

# Setup Nvm

Nvm allows you to manage multiple node.js environments. Node.js is mandatory if you want to run `fastapp` application.

You can install nvm by invoking the following command:

```bash
zrb devtool install nvm
```

# Setup Docker and Kubectl

If you are using WSL, the most recommended way is by installing docker desktop and enable wsl-integration

![Enable WSL integration](_images/enable-wsl-integration.png)

Otherwise, you can invoke the following command:

```bash
zrb devtool install docker
zrb devtool install kubectl
```

# Setup Pulumi

To setup pulumi, you can invoke the following command:

```bash
zrb devtool install pulumi
```

You need pulumi for app deployment.

# Setup Other Tools

There are some other tools you might need to install depending on your needs. For example:

- Helm
- Aws CLI
- GCloud CLI
- GVM
- SDKMAN
- Terraform

You can install those tools by invoking the following commands:

```
zrb devtool install helm
zrb devtool install aws
zrb devtool install gcloud
zrb devtool install gvm
zrb devtool install sdkman
zrb devtool install terraform
```

# Next

Now you are ready. Next, you can check our [low code tutorial](./development-to-deployment-low-code.md) or learn [zrb basic concepts](../concepts/README.md).


🔖 [Table of Contents](../README.md) / [Tutorials](README.md)