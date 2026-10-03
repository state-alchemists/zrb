"""
Command Task Example

Shows how to run shell commands with CmdTask.
"""

import os

from zrb import CmdTask, Env, StrInput, Tpl, cli

# =============================================================================
# Basic CmdTask
# =============================================================================

# Run a simple shell command
hello = cli.add_task(
    CmdTask(
        name="hello",
        cmd="echo 'Hello from Zrb!'",
    )
)

# =============================================================================
# CmdTask with Input
# =============================================================================

# Use input in the command by wrapping it in Tpl; a bare string is a literal
greet = cli.add_task(
    CmdTask(
        name="greet",
        description="Greet someone",
        input=[StrInput(name="name", default="World")],
        cmd=Tpl('echo "Hello, {ctx.input.name}!"'),
    )
)

# =============================================================================
# Figlet Example
# =============================================================================

# Create ASCII art with figlet (requires figlet installed)
figlet = cli.add_task(
    CmdTask(
        name="figlet",
        description="Create ASCII art text",
        input=[StrInput(name="message", description="Text to display", default="ZRB")],
        cmd=Tpl("figlet '{ctx.input.message}'"),
    )
)

# =============================================================================
# CmdTask with Cwd and Env
# =============================================================================

ls_task = cli.add_task(
    CmdTask(
        name="ls-home",
        description="List home directory",
        cmd="find . -maxdepth 1",
        cwd=os.path.expanduser("~"),  # cwd is not tilde-expanded, so expand it here
    )
)

# =============================================================================
# CmdTask with Environment Variables
# =============================================================================

env_task = cli.add_task(
    CmdTask(
        name="env-check",
        description="Check environment variables",
        cmd="echo $MY_VAR",
        env=[Env(name="MY_VAR", default="Hello from Zrb", link_to_os=False)],
    )
)

# =============================================================================
# CmdTask with Retry
# =============================================================================

flaky_task = cli.add_task(
    CmdTask(
        name="flaky",
        description="A command that might fail",
        cmd="exit 1",  # Always fails
        retries=3,  # Retry 3 times (4 attempts in total)
        retry_period=1,  # Wait 1 second between retries
    )
)
