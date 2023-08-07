🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Preparing your machine

> This guide has been tested under `debian 12` and `ubuntu 22.0.4`

Zrb is a Python package. So, in order to get started, you will need to have:

- Python
- Pip
- Venv

```bash
sudo apt-get install python-is-python3 python3-dev python3-distutils python3-openssl python3-pip python3-venv
```

# Creating venv for setup

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

# Install zrb on venv

After having your virtual environment set up, you can install `zrb` on your virtual environment:

```bash
pip install zrb
```

# Install essential packages for ubuntu/debian

Next you can install essential packages for development

```bash
zrb ubuntu install packages
```

# Setup zsh

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


🔖 [Table of Contents](../README.md) / [Tutorials](README.md)