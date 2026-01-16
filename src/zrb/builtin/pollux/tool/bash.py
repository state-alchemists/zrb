import asyncio

from pydantic_ai import RunContext, Tool


async def run_shell_command(ctx: RunContext, command: str) -> str:
    """
    Executes a shell command and returns the output.
    Streams output to stdout during execution.
    """
    print(f"Executing: {command}")
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout_lines = []
    stderr_lines = []

    async def read_stream(stream, lines_list, prefix=""):
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode().strip()
            if decoded:
                print(f"{prefix}{decoded}")  # Stream to console
                lines_list.append(decoded)

    await asyncio.gather(
        read_stream(process.stdout, stdout_lines, ""),
        read_stream(process.stderr, stderr_lines, "[stderr] "),
    )

    await process.wait()

    output = "\n".join(stdout_lines)
    error = "\n".join(stderr_lines)

    return f"Exit Code: {process.returncode}\nStdout:\n{output}\nStderr:\n{error}"


shell_tool = Tool(
    run_shell_command, name="run_shell_command", description="Run a shell command"
)
