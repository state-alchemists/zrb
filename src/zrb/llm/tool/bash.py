import asyncio
import re
from zrb.util.cli.style import stylize_faint


async def run_shell_command(command: str, timeout: int = 30) -> str:
    """
    Executes a shell command and returns the output.
    Streams output to stdout during execution.

    Args:
        command (str): The shell command to execute.
        timeout (int): Maximum time in seconds to wait for the command. Defaults to 30.
    """
    ANSI_ESCAPE = re.compile(
        r'(?:\x1B\[[0-?]*[ -/]*[@-~])|' # CSI (Control Sequence Introducer)
        r'(?:\x1B\][^\a\x1b]*[\a\x1b])|'        # OSC (Operating System Command)
        r'(?:\x1B[0-9=>])'                      # Simple 2-byte (DECSC, DECRC, etc.)
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
                    shown = ANSI_ESCAPE.sub('', decoded)
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
