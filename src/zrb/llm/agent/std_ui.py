import asyncio
import platform
import sys
from typing import Any, TextIO


class StdUI:
    """Standard UI implementation of UIProtocol for terminal environments."""

    async def ask_user(self, prompt: str) -> str:
        """Prompt user via CLI input."""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.output import create_output

        # Create output - handle Windows console compatibility
        # On Windows, prompt_toolkit needs proper console handles.
        # sys.__stderr__ works better than fd-based approaches.
        try:
            if platform.system() == "Windows":
                output = create_output(stdout=sys.__stderr__)
            else:
                output = create_output(stdout=sys.stderr)
        except Exception:
            output = create_output(stdout=sys.__stderr__)

        session = PromptSession(output=output)

        try:
            user_input = await session.prompt_async(prompt)
            return user_input.strip()
        except KeyboardInterrupt:
            # Let it propagate so the task runner can catch it or exit gracefully
            raise
        except EOFError:
            return ""

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        """Print output to stderr."""
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
