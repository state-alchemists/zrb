import asyncio
import re

from zrb.util.cli.style import stylize_faint


async def run_shell_command(command: str, timeout: int = 30) -> str:
    """
    Executes a shell command on the host system and returns its combined stdout and stderr.
    This is a powerful tool for running builds, tests, or system utilities.

    **CRITICAL SAFETY:**
    - DO NOT run destructive commands (e.g., `rm -rf /`) without absolute certainty.
    - Prefer specialized tools (like `read_file` or `write_file`) for file operations.

    **USAGE GUIDELINES:**
    - Use non-interactive commands.
    - If a command is expected to produce massive output, use `timeout` or pipe to a file.
    - The output is streamed to the console in real-time.

    Args:
        command (str): The full shell command to execute.
        timeout (int): Maximum wait time in seconds before terminating the process. Defaults to 30.
    """
    ANSI_ESCAPE = re.compile(
        r"(?:\x1B\[[0-?]*[ -/]*[@-~])|"  # CSI (Control Sequence Introducer)
        r"(?:\x1B\][^\a\x1b]*[\a\x1b])|"  # OSC (Operating System Command)
        r"(?:\x1B[0-9=>])"  # Simple 2-byte (DECSC, DECRC, etc.)
    )
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
                decoded = line.decode()
                if decoded:
                    shown = ANSI_ESCAPE.sub("", decoded)
                    shown = stylize_faint(shown)
                    print(f"{prefix}  {shown}", end="")  # Stream to console
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
