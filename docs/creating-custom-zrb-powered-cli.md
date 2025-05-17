🔖 [Documentation Home](../README.md) > Creating a Custom Zrb-Powered CLI

# Creating a Custom Zrb-Powered CLI (White-labeling Zrb)

Zrb is designed to be a flexible framework that can power your own custom command-line interfaces and automation suites. By packaging your Zrb tasks and configuration into a Python library, you can create a branded CLI that utilizes Zrb under the hood, effectively white-labeling the framework for your specific needs or organization.

This guide will walk you through the process of creating a custom Zrb-powered CLI using Poetry, using a fictional "Arasaka Automation" package as an example.

## Concept: Zrb as a Framework

Instead of just adding tasks to the default `zrb` command, you can create a completely new command (like `arasaka` in our example) that initializes and runs Zrb with your specific tasks, groups, and configuration overrides. This allows you to distribute your automation as a standalone tool with its own name and branding.

## Prerequisites

- Python 3.7+
- [Poetry](https://python-poetry.org/docs/#installation) installed.

## Step 1: Create a New Python Package with Poetry

Start by creating a new Python project using Poetry. This will be the container for your custom Zrb-powered CLI. Let's call our package `arasaka-automation`.

```bash
poetry new arasaka-automation
cd arasaka-automation
```

This creates a basic project structure:

```
arasaka-automation/
├── arasaka_automation/
│   └── __init__.py
├── pyproject.toml
└── README.md
```

Add `zrb` as a dependency to your new package:

```bash
poetry add zrb
```

## Step 2: Structure Your Package and Define Tasks

Organize your Zrb tasks and groups within the `arasaka_automation` package directory. You can create submodules for different functionalities (e.g., `security`, `logistics`).

Define your tasks and groups in Python files within your package (e.g., `arasaka_automation/security_tasks.py`).

Example (`arasaka_automation/security_tasks.py`):

```python
# arasaka_automation/security_tasks.py
from zrb import Task, CmdTask, make_task, Context, StrInput

# Define a task to check security logs
check_logs_task = CmdTask(
    name="check-logs",
    description="Checks Arasaka security logs",
    cmd="grep 'ALERT' /var/log/arasaka/security.log"
)

# Define a task to initiate lockdown
@make_task(
    name="initiate-lockdown",
    description="Initiates facility lockdown",
    input=StrInput(name="facility_id", description="ID of the facility to lock down")
)
def initiate_lockdown_task(ctx: Context):
    """Initiates lockdown for a specific facility."""
    ctx.print(f"Initiating lockdown for facility: {ctx.input.facility_id}...")
    # Simulate lockdown procedure
    ctx.print("Lockdown sequence initiated. Stay frosty.")
```

## Step 3: Define the Custom CLI Entry Point (`__main__.py`)

Create a file named `__main__.py` inside your `arasaka_automation` package directory (`arasaka_automation/__main__.py`). This file will be the main entry point when your package is executed as a command.

This `__main__.py` file will be responsible for:
1.  Setting up the Zrb environment.
2.  Overriding Zrb's default configuration to white-label the CLI.
3.  Loading your package's Zrb tasks and groups.
4.  Running the main Zrb CLI application.

Example (`arasaka_automation/__main__.py`):

```python
# arasaka_automation/__main__.py
import sys
import os
import importlib.metadata as metadata

# Import necessary Zrb components
from zrb.runner.cli import cli
from zrb.config import CFG
# from zrb.builtin import llm_ask # Import other Zrb components if needed

# Define package version (optional, but good practice)
try:
    VERSION = metadata.version("arasaka-automation")
except metadata.PackageNotFoundError:
    VERSION = "unknown"

# Define custom configuration values for white-labeling
# Pro tips: Use `figlet` to generate the banner, then escape the `\` characters
ARASAKA_BANNER = f"""
    _                        _
   / \\   _ __ __ _ ___  __ _| | ____ _
  / _ \\ | '__/ _` / __|/ _` | |/ / _` |
 / ___ \\| | | (_| \\__ \\ (_| |   < (_| |
/_/   \\_\\_|  \\__,_|___/\\__,_|_|\\_\\__,_| {VERSION}
Arasaka Corporation Automation Suite
"""
ARASAKA_JARGON = "Protecting the Corporate Net"

# Define your main entry point function
def run_arasaka_cli():
    # --- Configure Zrb Environment ---
    # Override default Zrb configurations using environment variables.
    # These environment variables are read by Zrb's core configuration (CFG).
    os.environ["ZRB_BANNER"] = ARASAKA_BANNER
    os.environ["ZRB_WEB_TITLE"] = "Arasaka NetWatch"
    os.environ["ZRB_WEB_JARGON"] = ARASAKA_JARGON
    os.environ["ZRB_ROOT_GROUP_NAME"] = "arasaka" # Set the root command name
    os.environ["ZRB_ROOT_GROUP_DESCRIPTION"] = ARASAKA_JARGON
    os.environ["_ZRB_CUSTOM_VERSION"] = VERSION
    os.environ["ZRB_INIT_FILE_NAME"] = "arasaka_init.py" # Specify your init file name

    # --- Run the Zrb CLI ---
    # Import and run the main Zrb CLI entry point.
    # This function handles parsing command-line arguments,
    # loading init files (including yours), and executing tasks.
    from zrb.__main__ import serve_cli as zrb_serve_cli
    zrb_serve_cli()

# This block makes the script executable when the package is run directly
if __name__ == "__main__":
    run_arasaka_cli()
```

## Step 4: Link the Custom Command in `pyproject.toml`

Edit your `pyproject.toml` file and add a `[tool.poetry.scripts]` section to define your custom command-line entry point.

```toml
# pyproject.toml
[tool.poetry]
name = "arasaka-automation"
version = "0.1.0" # Define your package version
description = "Arasaka Corporation Automation Suite powered by Zrb"
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.7"
zrb = "^1.0.0" # Ensure zrb is a dependency
# Add any other dependencies your tasks require
# httpx = "^0.27.0" # Example for LLM configuration
# pydantic-ai = "^0.1.6" # Example for LLM configuration

[tool.poetry.scripts]
# Define your custom command name and link it to the entry point function
arasaka = "arasaka_automation.__main__:run_arasaka_cli"
```
This tells Poetry to create an executable command named `arasaka` that calls the `run_arasaka_cli` function in your `arasaka_automation.__main__` module when the package is installed.

## Installation and Usage

Users of your package will need to install it. If you publish it to a package repository like PyPI, they can install it using pip:

```bash
pip install arasaka-automation
```

If they are installing directly from your project directory (e.g., for development), they can use Poetry:

```bash
poetry install
```

Once installed, they can run your custom automation suite using the command you defined in `pyproject.toml`:

```bash
arasaka # This will show the custom banner and help message
arasaka security check-logs
arasaka security initiate-lockdown --facility-id=NC-01
```

The `arasaka` command executes the `run_arasaka_cli` function, which configures Zrb with your branding and settings, loads your tasks, and then runs the standard Zrb CLI logic.

By following these steps, you can leverage Zrb's powerful automation capabilities while providing a completely custom and branded command-line experience.

🔖 [Documentation Home](../README.md)