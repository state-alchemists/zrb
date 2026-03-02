🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > White-labeling

# White-labeling: Creating a Custom CLI

Zrb is designed to be a flexible framework. You can package your Zrb tasks and configurations into a Python library, effectively creating a completely custom, branded command-line interface powered by the Zrb engine under the hood.

This is perfect for distributing internal tooling to your company (e.g., creating an `acme-cli` instead of users typing `zrb`).

---

## 1. Project Setup

Create a new Python package (e.g., using Poetry).

```bash
poetry new acme-cli
cd acme-cli
poetry add zrb
```

## 2. Define your tasks
Create your specialized tasks inside your package (`acme_cli/tasks.py`).

```python
# acme_cli/tasks.py
from zrb import CmdTask

deploy_prod = CmdTask(
    name="deploy-prod",
    cmd="echo 'Deploying to Acme Corp Production!'"
)
```

## 3. Create the Custom Entry Point (`__main__.py`)

This is the magic file. You will override Zrb's default environment configurations to re-brand the CLI, load your tasks, and then invoke the Zrb runner.

```python
# acme_cli/__main__.py
import os
import sys
from zrb.runner.cli import cli

# 1. Import your tasks so they register with the 'cli' object
import acme_cli.tasks 

def run_acme_cli():
    # 2. White-label configuration overrides!
    
    # Change the env prefix. Instead of ZRB_LOG_LEVEL, users will use ACME_LOG_LEVEL
    os.environ["_ZRB_ENV_PREFIX"] = "ACME" 
    
    # Rebrand the root command name
    os.environ["ACME_ROOT_GROUP_NAME"] = "acme"
    os.environ["ACME_ROOT_GROUP_DESCRIPTION"] = "Acme Corp Internal Tools"
    
    # Custom ASCII Banner
    os.environ["ACME_BANNER"] = """
      ___                       
     / _ \                      
    / /_\ \ ___ _ __ ___   ___  
    |  _  |/ __| '_ ` _ \ / _ \ 
    | | | | (__| | | | | |  __/ 
    \_| |_/\___|_| |_| |_|\___| 
    Acme Corp Automation v1.0
    """

    # 3. Invoke the main Zrb engine!
    from zrb.__main__ import serve_cli
    serve_cli()

if __name__ == "__main__":
    run_acme_cli()
```

## 4. Link the command

If using Poetry, update your `pyproject.toml` to link the command name to your entry point.

```toml
[tool.poetry.scripts]
acme = "acme_cli.__main__:run_acme_cli"
```

## 5. Install and Run!

Install your package locally:
```bash
poetry install
```

Now, instead of `zrb`, you have a fully branded CLI!

```bash
acme deploy-prod
```
The terminal will display your custom "Acme" banner, the help menus will reference `acme` instead of `zrb`, and your custom tasks are ready to go.
