import asyncio

from pydantic_ai import Tool


async def run_shell_command(command: str, timeout: int = 30) -> str:
    """
    Executes a shell command and returns the output.
    Streams output to stdout during execution.

    Args:
        command (str): The shell command to execute.
        timeout (int): Maximum time in seconds to wait for the command. Defaults to 30.
    """
    try:
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

        # Wait for the process to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, stdout_lines, ""),
                    read_stream(process.stderr, stderr_lines, "[stderr] "),
                    process.wait(),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except ProcessLookupError:
                    pass
            return f"Error: Command timed out after {timeout} seconds."

        output = "\n".join(stdout_lines)
        error = "\n".join(stderr_lines)

        return f"Exit Code: {process.returncode}\nStdout:\n{output}\nStderr:\n{error}"

    except Exception as e:
        return f"Error executing command: {e}"


shell_tool = Tool(
    run_shell_command, name="run_shell_command", description="Run a shell command"
)
