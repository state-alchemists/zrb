"""
Command Task Example

Shows how to run shell commands with CmdTask.
"""

from zrb import CmdTask, StrInput, cli

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

# Use input in the command with {ctx.input.name}
greet = cli.add_task(
    CmdTask(
        name="greet",
        description="Greet someone using figlet (if installed)",
        input=[StrInput(name="name", default="World")],
        cmd='echo "Hello, {ctx.input.name}!"',
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
        cmd="figlet '{ctx.input.message}'",
    )
)

# =============================================================================
# CmdTask with Cwd and Env
# =============================================================================

ls_task = cli.add_task(
    CmdTask(
        name="ls-home",
        description="List home directory",
        cmd="ls -la",
        cwd="~",  # Run in home directory
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
        env={"MY_VAR": "Hello from Zrb"},
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
        retry=3,  # Retry 3 times
        retry_interval=1,  # Wait 1 second between retries
    )
)

# =============================================================================
# CmdTask capturing Output
# =============================================================================

capture_task = cli.add_task(
    CmdTask(
        name="capture",
        description="Capture command output",
        cmd="echo 'captured output'",
        done_callback=lambda ctx: ctx.print(f"Got: {ctx.xcom['capture'].pop()}"),
    )
)
