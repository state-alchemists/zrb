import asyncio
from typing import Any, TextIO


class StdUI:
    """Standard UI implementation of UIProtocol for terminal environments."""

    async def ask_user(self, prompt: str) -> str:
        """Prompt user via CLI input."""
        import sys

        if prompt:
            sys.stderr.write(prompt)
            sys.stderr.flush()

        # Use asyncio.to_thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        user_input = await loop.run_in_executor(None, input, "")
        return user_input.strip()

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        """Print output to stderr."""
        import sys

        # Always print to stderr as per requirements
        print(*values, sep=sep, end=end, file=sys.stderr, flush=flush)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run interactive commands using subprocess."""
        import subprocess

        def _run():
            return subprocess.run(cmd, shell=shell)

        return await asyncio.to_thread(_run)
